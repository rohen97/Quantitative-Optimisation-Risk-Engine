from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
import logging
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository
from src.features.feature_store import build_feature_store
from src.features.risk_features import build_price_risk_features
from src.models.forecasting import build_ml_forecast_features
from src.models.scorecard import build_scorecard
from src.optimisation.optimiser_inputs import build_optimiser_input_dataset
from src.optimisation.optimisers import cvar_constrained_portfolio
from src.utils.config import ROOT, load_yaml
from src.validation.transaction_cost_validation import estimate_transaction_cost


LOGGER = logging.getLogger(__name__)
ARTIFACT_VERSION = 2
FORECAST_HORIZONS = (3, 6, 9, 12)
MONETARY_COLUMNS = (
    'revenue',
    'operating_income',
    'net_income',
    'operating_cash_flow',
    'capital_expenditure',
    'free_cash_flow',
    'total_assets',
    'total_liabilities',
    'total_debt',
    'cash_and_equivalents',
    'shareholders_equity',
    'dividends_paid',
    'ebitda',
    'interest_expense',
)


@dataclass(frozen=True)
class WalkForwardConfig:
    output_directory: Path
    start_date: pd.Timestamp
    forecast_end_date: pd.Timestamp
    strategy_end_date: pd.Timestamp
    evidence_mode: str = 'reconstructed_pit_proxy'
    filing_lag_days: int = 120
    minimum_annual_periods: int = 2
    minimum_training_price_rows: int = 756
    price_lookback_rows: int = 756
    outcome_date_tolerance_days: int = 7
    portfolio_nav_usd: float = 100_000_000.0
    primary_strategy: str = 'wolf_cvar'
    approval_cap: str = 'CONDITIONALLY_APPROVED'
    maximum_rebalance_turnover: float = 0.10
    risk_ewma_decay: float = 0.94
    risk_lookback_rows: int = 252


@dataclass(frozen=True)
class WalkForwardResult:
    output_directory: Path
    forecast_rows: int
    outcome_rows: int
    portfolio_months: int
    risk_observations: int
    security_count: int
    evidence_mode: str


def load_walk_forward_config(
    output_directory: str | Path | None = None,
    **overrides: Any,
) -> WalkForwardConfig:
    raw = load_yaml('configs/validation.yaml').get('validation', {}).get('walk_forward', {})
    values = {**raw, **{key: value for key, value in overrides.items() if value is not None}}
    output = Path(output_directory or values.get('output_directory', 'reports/outputs/walk_forward'))
    if not output.is_absolute():
        output = ROOT / output
    risk_forecast = values.get('risk_forecast', {})
    risk_ewma_decay = float(risk_forecast.get('ewma_decay', 0.94))
    if not 0 < risk_ewma_decay < 1:
        raise ValueError('Walk-forward risk EWMA decay must be between zero and one.')
    maximum_rebalance_turnover = float(
        values.get('maximum_rebalance_turnover', 0.10)
    )
    if not 0 <= maximum_rebalance_turnover <= 1:
        raise ValueError('Walk-forward turnover limit must be between zero and one.')
    return WalkForwardConfig(
        output_directory=output,
        start_date=pd.Timestamp(values.get('start_date', '2024-06-30')).normalize(),
        forecast_end_date=pd.Timestamp(values.get('forecast_end_date', '2025-07-31')).normalize(),
        strategy_end_date=pd.Timestamp(values.get('strategy_end_date', '2026-06-30')).normalize(),
        evidence_mode=str(values.get('evidence_mode', 'reconstructed_pit_proxy')),
        filing_lag_days=int(values.get('filing_lag_days', 120)),
        minimum_annual_periods=int(values.get('minimum_annual_periods', 2)),
        minimum_training_price_rows=int(values.get('minimum_training_price_rows', 756)),
        price_lookback_rows=int(values.get('price_lookback_rows', 756)),
        outcome_date_tolerance_days=int(values.get('outcome_date_tolerance_days', 7)),
        portfolio_nav_usd=float(values.get('portfolio_nav_usd', 100_000_000)),
        primary_strategy=str(values.get('primary_strategy', 'wolf_cvar')),
        approval_cap=str(values.get('approval_cap', 'CONDITIONALLY_APPROVED')),
        maximum_rebalance_turnover=maximum_rebalance_turnover,
        risk_ewma_decay=risk_ewma_decay,
        risk_lookback_rows=int(risk_forecast.get('lookback_rows', 252)),
    )


def reconstruct_statement_availability(
    statements: pd.DataFrame,
    filing_lag_days: int,
) -> pd.DataFrame:
    result = statements.copy()
    period_end = pd.to_datetime(result['fiscal_period_end'], errors='coerce')
    filing_date = pd.to_datetime(result.get('filing_date'), errors='coerce')
    proxy_date = period_end + pd.to_timedelta(int(filing_lag_days), unit='D')
    source = result.get('source', pd.Series('', index=result.index)).astype(str)
    trusted_filing_source = ~source.str.contains(
        'yahoo_finance_timeseries',
        case=False,
        na=False,
    )
    valid_filing = (
        filing_date.notna()
        & period_end.notna()
        & filing_date.ge(period_end)
        & trusted_filing_source
    )
    result['reconstructed_available_from'] = filing_date.where(valid_filing, proxy_date)
    result['availability_basis'] = np.where(
        valid_filing,
        'reported_filing_date',
        f'fiscal_period_end_plus_{int(filing_lag_days)}d',
    )
    return result


def _normalise_fx_currency(values: pd.Series) -> pd.Series:
    aliases = {'GBX': 'GBP', 'GBP': 'GBP', 'GBp': 'GBP'}
    clean = values.fillna('USD').astype(str).str.strip()
    return clean.map(lambda value: aliases.get(value, value.upper()))


class _FxMatcher:
    def __init__(self, rates: pd.DataFrame) -> None:
        self._rates: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        clean = rates.copy()
        clean['rate_date'] = pd.to_datetime(clean['rate_date'])
        clean['quote_currency'] = _normalise_fx_currency(clean['quote_currency'])
        clean['rate'] = pd.to_numeric(clean['rate'], errors='coerce')
        clean = clean.loc[clean['rate'].gt(0)].sort_values(['quote_currency', 'rate_date'])
        for currency, group in clean.groupby('quote_currency', sort=False):
            self._rates[str(currency)] = (
                group['rate_date'].to_numpy(dtype='datetime64[ns]'),
                group['rate'].to_numpy(dtype=float),
            )

    def match(self, currencies: pd.Series, dates: pd.Series) -> pd.Series:
        original_index = currencies.index
        normalised = _normalise_fx_currency(currencies).reset_index(drop=True)
        query_dates = pd.to_datetime(dates).reset_index(drop=True).to_numpy(
            dtype='datetime64[ns]'
        )
        output = np.full(len(normalised), np.nan, dtype=float)
        for currency, positions in normalised.groupby(normalised, sort=False).groups.items():
            indexes = np.asarray(list(positions), dtype=int)
            if currency == 'USD':
                output[indexes] = 1.0
                continue
            values = self._rates.get(str(currency))
            if values is None:
                continue
            rate_dates, rates = values
            matched = np.searchsorted(rate_dates, query_dates[indexes], side='right') - 1
            valid = matched >= 0
            output[indexes[valid]] = rates[matched[valid]]
        return pd.Series(output, index=original_index, dtype=float)


class _PriceMatcher:
    def __init__(self, prices: pd.DataFrame) -> None:
        self.prices = prices.sort_values(['security_id', 'trade_date']).reset_index(drop=True)
        self._groups: dict[str, pd.DataFrame] = {
            str(security_id): group.reset_index(drop=True)
            for security_id, group in self.prices.groupby('security_id', sort=False)
        }

    def trailing(
        self,
        security_ids: pd.Series | list[str],
        as_of_date: pd.Timestamp,
        rows: int,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        history: list[pd.DataFrame] = []
        latest: list[dict[str, Any]] = []
        target = np.datetime64(pd.Timestamp(as_of_date), 'ns')
        for security_id in map(str, security_ids):
            group = self._groups.get(security_id)
            if group is None:
                continue
            dates = group['trade_date'].to_numpy(dtype='datetime64[ns]')
            end = int(np.searchsorted(dates, target, side='right'))
            if end <= 0:
                continue
            start = max(0, end - int(rows))
            history.append(group.iloc[start:end])
            row = group.iloc[end - 1].to_dict()
            row['history_row_count'] = end
            latest.append(row)
        recent = pd.concat(history, ignore_index=True) if history else pd.DataFrame()
        return recent, pd.DataFrame(latest)

    def match_requests(
        self,
        requests: pd.DataFrame,
        date_column: str,
        direction: str,
        tolerance_days: int | None = None,
    ) -> pd.DataFrame:
        if requests.empty:
            return requests.copy()
        requests = requests.reset_index(drop=True)
        rows: list[dict[str, Any]] = []
        for security_id, group_requests in requests.groupby('security_id', sort=False):
            prices = self._groups.get(str(security_id))
            if prices is None:
                continue
            price_dates = prices['trade_date'].to_numpy(dtype='datetime64[ns]')
            query_dates = pd.to_datetime(group_requests[date_column]).to_numpy(
                dtype='datetime64[ns]'
            )
            positions = np.searchsorted(
                price_dates,
                query_dates,
                side='right' if direction == 'backward' else 'left',
            )
            if direction == 'backward':
                positions -= 1
            valid = (positions >= 0) & (positions < len(prices))
            for request_position, price_position, is_valid in zip(
                group_requests.index,
                positions,
                valid,
            ):
                if not is_valid:
                    continue
                request = requests.loc[request_position].to_dict()
                price = prices.iloc[int(price_position)]
                matched_date = pd.Timestamp(price['trade_date'])
                requested_date = pd.Timestamp(request[date_column])
                gap = abs((matched_date - requested_date).days)
                if tolerance_days is not None and gap > tolerance_days:
                    continue
                request.update(
                    {
                        'matched_trade_date': matched_date,
                        'matched_adjusted_close': float(price['adjusted_close']),
                        'matched_close_price': float(price['close_price']),
                    }
                )
                rows.append(request)
        return pd.DataFrame(rows)

    def between(
        self,
        security_ids: list[str],
        start_exclusive: pd.Timestamp,
        end_inclusive: pd.Timestamp,
    ) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        start = np.datetime64(pd.Timestamp(start_exclusive), 'ns')
        end = np.datetime64(pd.Timestamp(end_inclusive), 'ns')
        for security_id in map(str, security_ids):
            group = self._groups.get(security_id)
            if group is None:
                continue
            dates = group['trade_date'].to_numpy(dtype='datetime64[ns]')
            left = int(np.searchsorted(dates, start, side='right'))
            right = int(np.searchsorted(dates, end, side='right'))
            if right > left:
                frames.append(group.iloc[left:right])
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _load_source_data(
    repository: DuckDBRepository,
    config: WalkForwardConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    minimum_periods = int(config.minimum_annual_periods)
    universe = repository.query(
        f'''
        WITH coverage AS (
            SELECT security_id, COUNT(DISTINCT fiscal_period_end) AS annual_periods
            FROM fundamentals_reported
            WHERE fiscal_period_type = 'annual'
              AND LOWER(source) NOT LIKE '%mock%'
              AND LOWER(source) NOT LIKE '%synthetic%'
            GROUP BY security_id
            HAVING COUNT(DISTINCT fiscal_period_end) >= {minimum_periods}
        ),
        reference AS (
            SELECT * EXCLUDE (reference_row)
            FROM (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY security_id ORDER BY as_of_date DESC, retrieved_at DESC
                ) AS reference_row
                FROM security_reference_snapshots
            )
            WHERE reference_row = 1
        )
        SELECT
            s.security_id, s.security_id AS ticker,
            'NAME:' || REGEXP_REPLACE(LOWER(s.company_name), '[^a-z0-9]+', '', 'g') AS issuer_id,
            s.company_name, s.instrument_type, s.listing_status, s.exchange_code,
            s.country, s.region,
            COALESCE(NULLIF(r.sector, ''), NULLIF(s.sector, ''), 'Unknown') AS sector,
            COALESCE(NULLIF(r.industry, ''), NULLIF(s.industry, ''), 'Unknown') AS industry,
            COALESCE(NULLIF(r.quote_currency, ''), NULLIF(s.trading_currency, ''), 'USD') AS currency,
            COALESCE(NULLIF(r.financial_currency, ''), NULLIF(s.domicile_currency, ''), 'USD') AS financial_currency,
            COALESCE(r.price_scale, 1.0) AS price_scale,
            r.shares_outstanding AS reference_shares_outstanding,
            r.average_daily_value_usd AS reference_average_daily_value_usd,
            c.annual_periods
        FROM securities s
        JOIN coverage c USING (security_id)
        LEFT JOIN reference r USING (security_id)
        WHERE s.listing_status = 'Active'
          AND s.instrument_type = 'Equity'
          AND s.region IN ('US', 'UK', 'DACH', 'Mainland China', 'Hong Kong', 'EU ex-DACH')
        ORDER BY s.region, s.security_id
        '''
    )
    security_ids = universe['security_id'].astype(str).tolist()
    placeholder = chr(63)
    statements = repository.query(
        f'''
        SELECT * EXCLUDE (source_row)
        FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY security_id, fiscal_period_end, fiscal_period_type
                ORDER BY
                    CASE
                        WHEN source = 'sec_companyfacts' THEN 1
                        WHEN source LIKE 'akshare%' THEN 2
                        WHEN source = 'yahoo_finance_timeseries' THEN 3
                        ELSE 4
                    END,
                    retrieved_at DESC
            ) AS source_row
            FROM fundamentals_reported
            WHERE security_id IN (SELECT UNNEST({placeholder}))
              AND fiscal_period_type = 'annual'
              AND LOWER(source) NOT LIKE '%mock%'
              AND LOWER(source) NOT LIKE '%synthetic%'
        )
        WHERE source_row = 1
        ORDER BY security_id, fiscal_period_end
        ''',
        [security_ids],
    )
    price_end = max(
        config.strategy_end_date + pd.DateOffset(months=2),
        config.forecast_end_date + pd.DateOffset(months=13),
    ).date()
    prices = repository.query(
        f'''
        SELECT
            security_id, trade_date, close_price,
            COALESCE(adjusted_close, close_price) AS adjusted_close,
            volume, trading_currency, source
        FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY security_id, trade_date
                ORDER BY
                    CASE WHEN adjusted_close IS NOT NULL THEN 0 ELSE 1 END,
                    CASE
                        WHEN source = 'yfinance' THEN 1
                        WHEN source = 'eodhd' THEN 2
                        WHEN source = 'alpaca' THEN 3
                        WHEN source = 'tickdb' THEN 4
                        ELSE 5
                    END,
                    retrieved_at DESC
            ) AS source_row
            FROM prices_daily
            WHERE security_id IN (SELECT UNNEST({placeholder}))
              AND trade_date <= {placeholder}
              AND COALESCE(adjusted_close, close_price) > 0
        )
        WHERE source_row = 1
        ORDER BY security_id, trade_date
        ''',
        [security_ids, price_end],
    )
    fx = repository.query(
        '''
        SELECT rate_date, quote_currency, rate
        FROM fx_rates
        WHERE base_currency = 'USD' AND rate > 0
        ORDER BY quote_currency, rate_date
        '''
    )
    return universe, statements, prices, fx


def _prepare_prices(prices: pd.DataFrame) -> pd.DataFrame:
    result = prices.copy()
    result['trade_date'] = pd.to_datetime(result['trade_date'])
    for column in ('close_price', 'adjusted_close', 'volume'):
        result[column] = pd.to_numeric(result[column], errors='coerce')
    result = result.dropna(
        subset=['security_id', 'trade_date', 'close_price', 'adjusted_close']
    )
    grouped = result.groupby('security_id', sort=False)
    result['raw_return'] = grouped['adjusted_close'].pct_change(fill_method=None)
    result['return_outlier_flag'] = result['raw_return'].abs().gt(1.0)
    result['return'] = result['raw_return'].clip(-1.0, 1.0).fillna(0.0)
    result['ticker'] = result['security_id'].astype(str)
    return result


def _prepare_statements(
    statements: pd.DataFrame,
    universe: pd.DataFrame,
    fx_matcher: _FxMatcher,
    filing_lag_days: int,
) -> pd.DataFrame:
    result = reconstruct_statement_availability(statements, filing_lag_days)
    result['fiscal_period_end'] = pd.to_datetime(result['fiscal_period_end'])
    result = result.merge(
        universe[['security_id', 'financial_currency']],
        on='security_id',
        how='left',
    )
    statement_currency = result['currency'].where(
        result['currency'].fillna('').astype(str).str.strip().ne(''),
        result['financial_currency'],
    )
    result['_units_per_usd'] = fx_matcher.match(
        statement_currency,
        result['fiscal_period_end'],
    )
    for column in MONETARY_COLUMNS:
        result[f'{column}_usd'] = (
            pd.to_numeric(result[column], errors='coerce') / result['_units_per_usd']
        )
    result['diluted_shares'] = pd.to_numeric(result['diluted_shares'], errors='coerce')
    result['dps'] = (
        result['dividends_paid_usd'].abs()
        / result['diluted_shares'].replace(0, np.nan)
    )
    return result.sort_values(['security_id', 'fiscal_period_end']).reset_index(drop=True)


def _annualised_dps_growth(history: pd.DataFrame, periods: int) -> pd.Series:
    valid = (
        history.loc[history['dps'].gt(0)]
        .groupby('security_id', group_keys=False)
        .tail(periods)
    )
    if valid.empty:
        return pd.Series(dtype=float)
    summary = valid.groupby('security_id').agg(
        first_value=('dps', 'first'),
        last_value=('dps', 'last'),
        first_date=('fiscal_period_end', 'first'),
        last_date=('fiscal_period_end', 'last'),
        observations=('dps', 'size'),
    )
    years = (
        pd.to_datetime(summary['last_date']) - pd.to_datetime(summary['first_date'])
    ).dt.days.div(365.25).clip(lower=1.0)
    growth = np.power(summary['last_value'] / summary['first_value'], 1.0 / years) - 1.0
    return growth.where(summary['observations'].ge(2))


def _fundamental_snapshot(
    statements: pd.DataFrame,
    as_of_date: pd.Timestamp,
    minimum_periods: int,
) -> pd.DataFrame:
    available = statements.loc[
        pd.to_datetime(statements['reconstructed_available_from']).le(as_of_date)
    ].copy()
    if available.empty:
        return pd.DataFrame()
    available = available.sort_values(['security_id', 'fiscal_period_end'])
    available['_period_count'] = available.groupby('security_id')[
        'security_id'
    ].transform('size')
    available = available.loc[available['_period_count'].ge(minimum_periods)]
    if available.empty:
        return pd.DataFrame()
    grouped = available.groupby('security_id', sort=False)
    available['_previous_revenue_usd'] = grouped['revenue_usd'].shift(1)
    available['_dps_change'] = grouped['dps'].pct_change(fill_method=None)
    latest = grouped.tail(1).set_index('security_id')
    trailing_five = grouped.tail(5)
    stability = trailing_five.groupby('security_id').agg(
        positive_fcf_years_5=(
            'free_cash_flow_usd',
            lambda values: int(values.gt(0).sum()),
        ),
        fcf_mean_abs=(
            'free_cash_flow_usd',
            lambda values: float(values.abs().mean()),
        ),
        fcf_std=(
            'free_cash_flow_usd',
            lambda values: float(values.std(ddof=0)),
        ),
        fundamentals_period_count=('fiscal_period_end', 'size'),
    )
    stability['fcf_stability'] = (
        100.0
        * (
            1.0
            - (stability['fcf_std'] / stability['fcf_mean_abs'])
            .div(1.5)
            .clip(0, 1)
        )
    ).where(stability['fcf_mean_abs'].gt(0))
    dividend_cut = (
        grouped.tail(4)
        .groupby('security_id')['_dps_change']
        .apply(lambda values: float(values.lt(-0.20).any()))
        .rename('dividend_cut_flag_3y')
    )
    result = latest.join(stability).join(dividend_cut)
    result['dividend_growth_3y'] = _annualised_dps_growth(available, 4)
    result['dividend_growth_5y'] = _annualised_dps_growth(available, 6)
    return result.reset_index()


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    values = pd.to_numeric(numerator, errors='coerce') / pd.to_numeric(
        denominator,
        errors='coerce',
    ).replace(0, np.nan)
    return values.replace([np.inf, -np.inf], np.nan)


def _build_anchor_inputs(
    universe: pd.DataFrame,
    statements: pd.DataFrame,
    price_matcher: _PriceMatcher,
    fx_matcher: _FxMatcher,
    as_of_date: pd.Timestamp,
    config: WalkForwardConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    financials = _fundamental_snapshot(
        statements,
        as_of_date,
        config.minimum_annual_periods,
    )
    if financials.empty:
        return pd.DataFrame(), pd.DataFrame()
    financials = financials.drop(
        columns=['currency', 'financial_currency', 'ticker'],
        errors='ignore',
    )
    candidates = universe.merge(financials, on='security_id', how='inner')
    recent, latest_prices = price_matcher.trailing(
        candidates['security_id'],
        as_of_date,
        config.price_lookback_rows,
    )
    if recent.empty or latest_prices.empty:
        return pd.DataFrame(), pd.DataFrame()
    latest = latest_prices[
        [
            'security_id',
            'trade_date',
            'close_price',
            'adjusted_close',
            'history_row_count',
        ]
    ].rename(
        columns={
            'trade_date': 'latest_trade_date',
            'close_price': 'anchor_close_price',
            'adjusted_close': 'anchor_adjusted_close',
        }
    )
    candidates = candidates.merge(latest, on='security_id', how='inner')
    candidates = candidates.loc[
        candidates['history_row_count'].ge(config.minimum_training_price_rows)
    ].copy()
    freshness = as_of_date - pd.to_datetime(candidates['latest_trade_date'])
    candidates = candidates.loc[
        freshness.dt.days.le(config.outcome_date_tolerance_days)
    ].copy()
    if candidates.empty:
        return pd.DataFrame(), pd.DataFrame()

    candidates['_quote_fx'] = fx_matcher.match(
        candidates['currency'],
        pd.Series(as_of_date, index=candidates.index),
    )
    candidates['price_scale'] = pd.to_numeric(
        candidates['price_scale'],
        errors='coerce',
    ).fillna(1.0)
    candidates['market_cap_usd'] = (
        candidates['anchor_close_price']
        * candidates['price_scale']
        * pd.to_numeric(candidates['diluted_shares'], errors='coerce')
        / candidates['_quote_fx']
    )
    candidates['revenue'] = pd.to_numeric(candidates['revenue_usd'], errors='coerce')
    candidates['operating_income'] = pd.to_numeric(
        candidates['operating_income_usd'],
        errors='coerce',
    )
    candidates['net_income'] = pd.to_numeric(
        candidates['net_income_usd'],
        errors='coerce',
    )
    candidates['operating_cash_flow'] = pd.to_numeric(
        candidates['operating_cash_flow_usd'],
        errors='coerce',
    )
    candidates['capex'] = pd.to_numeric(
        candidates['capital_expenditure_usd'],
        errors='coerce',
    ).abs()
    candidates['free_cash_flow'] = pd.to_numeric(
        candidates['free_cash_flow_usd'],
        errors='coerce',
    ).fillna(candidates['operating_cash_flow'] - candidates['capex'])
    candidates['total_debt'] = pd.to_numeric(
        candidates['total_debt_usd'],
        errors='coerce',
    )
    candidates['cash'] = pd.to_numeric(
        candidates['cash_and_equivalents_usd'],
        errors='coerce',
    )
    candidates['shareholders_equity'] = pd.to_numeric(
        candidates['shareholders_equity_usd'],
        errors='coerce',
    )
    candidates['ebitda'] = pd.to_numeric(
        candidates['ebitda_usd'],
        errors='coerce',
    ).fillna(candidates['operating_income'])
    candidates['interest_expense'] = pd.to_numeric(
        candidates['interest_expense_usd'],
        errors='coerce',
    ).abs()
    candidates['enterprise_value'] = (
        candidates['market_cap_usd'] + candidates['total_debt'] - candidates['cash']
    )
    candidates['dividends_paid'] = pd.to_numeric(
        candidates['dividends_paid_usd'],
        errors='coerce',
    ).abs()
    candidates['dividend_yield'] = _safe_ratio(
        candidates['dividends_paid'],
        candidates['market_cap_usd'],
    ).clip(0, 0.25)
    candidates['payout_ratio'] = _safe_ratio(
        candidates['dividends_paid'],
        candidates['net_income'],
    ).where(candidates['net_income'].gt(0))
    candidates['revenue_growth'] = _safe_ratio(
        candidates['revenue'],
        candidates['_previous_revenue_usd'],
    ) - 1.0
    candidates['ebitda_margin'] = _safe_ratio(
        candidates['ebitda'],
        candidates['revenue'],
    )
    candidates['net_income_margin'] = _safe_ratio(
        candidates['net_income'],
        candidates['revenue'],
    )
    candidates['free_cash_flow_yield'] = _safe_ratio(
        candidates['free_cash_flow'],
        candidates['market_cap_usd'],
    )
    candidates['fcf_margin'] = _safe_ratio(
        candidates['free_cash_flow'],
        candidates['revenue'],
    )
    candidates['cfo_to_net_income'] = _safe_ratio(
        candidates['operating_cash_flow'],
        candidates['net_income'],
    )

    candidates['_quote_fx'] = fx_matcher.match(
        candidates['currency'],
        pd.Series(as_of_date, index=candidates.index),
    )
    candidates['price_scale'] = pd.to_numeric(
        candidates['price_scale'],
        errors='coerce',
    ).fillna(1.0)
    candidates['market_cap_usd'] = (
        candidates['anchor_close_price']
        * candidates['price_scale']
        * pd.to_numeric(candidates['diluted_shares'], errors='coerce')
        / candidates['_quote_fx']
    )
    recent = recent.loc[
        recent['security_id'].astype(str).isin(candidates['security_id'].astype(str))
    ].copy()
    scales = candidates.set_index('security_id')['price_scale']
    recent['_price_scale'] = recent['security_id'].map(scales).fillna(1.0)
    recent['_traded_value_local'] = (
        recent['close_price'] * recent['volume'] * recent['_price_scale']
    )
    liquidity = (
        recent.groupby('security_id', group_keys=False)
        .tail(60)
        .groupby('security_id')
        .agg(
            avg_daily_traded_value_local=('_traded_value_local', 'mean'),
            liquidity_observation_count=(
                '_traded_value_local',
                lambda values: int(values.gt(0).sum()),
            ),
        )
    )
    candidates = candidates.join(liquidity, on='security_id')
    candidates['avg_daily_traded_value_usd'] = (
        candidates['avg_daily_traded_value_local'] / candidates['_quote_fx']
    )
    candidates['avg_daily_traded_value_usd'] = candidates[
        'avg_daily_traded_value_usd'
    ].where(
        candidates['avg_daily_traded_value_usd'].gt(0),
        pd.to_numeric(
            candidates['reference_average_daily_value_usd'],
            errors='coerce',
        ),
    )
    candidates['liquidity_observation_count'] = candidates[
        'liquidity_observation_count'
    ].where(
        candidates['liquidity_observation_count'].gt(0),
        np.where(candidates['avg_daily_traded_value_usd'].gt(0), 60, 0),
    )
    candidates = candidates.loc[
        candidates['market_cap_usd'].gt(0)
        & candidates['avg_daily_traded_value_usd'].gt(0)
        & pd.to_numeric(candidates['diluted_shares'], errors='coerce').gt(0)
    ].copy()
    if candidates.empty:
        return pd.DataFrame(), pd.DataFrame()

    candidates['net_debt_to_ebitda'] = _safe_ratio(
        candidates['total_debt'] - candidates['cash'],
        candidates['ebitda'],
    )
    candidates['interest_coverage'] = _safe_ratio(
        candidates['operating_income'],
        candidates['interest_expense'],
    )
    candidates['roe'] = _safe_ratio(
        candidates['net_income'],
        candidates['shareholders_equity'],
    )
    candidates['roic'] = _safe_ratio(
        candidates['operating_income'] * 0.79,
        candidates['total_debt'] + candidates['shareholders_equity'] - candidates['cash'],
    )
    candidates['pe_ratio'] = _safe_ratio(
        candidates['market_cap_usd'],
        candidates['net_income'],
    ).where(candidates['net_income'].gt(0))
    candidates['pb_ratio'] = _safe_ratio(
        candidates['market_cap_usd'],
        candidates['shareholders_equity'],
    ).where(candidates['shareholders_equity'].gt(0))
    candidates['ev_ebitda'] = _safe_ratio(
        candidates['enterprise_value'],
        candidates['ebitda'],
    ).where(candidates['ebitda'].gt(0))
    candidates['trailing_12m_dps'] = pd.to_numeric(
        candidates['dps'],
        errors='coerce',
    )
    candidates['fundamentals_as_of_date'] = pd.to_datetime(
        candidates['fiscal_period_end']
    )
    candidates['fundamentals_available_from'] = pd.to_datetime(
        candidates['reconstructed_available_from']
    )
    candidates['fundamentals_data_source'] = (
        candidates['source'].astype(str) + ':reconstructed_availability'
    )
    coverage_columns = [
        'revenue',
        'operating_income',
        'net_income',
        'operating_cash_flow',
        'free_cash_flow',
        'total_debt',
        'cash',
        'shareholders_equity',
        'ebitda',
        'market_cap_usd',
        'dividend_yield',
        'payout_ratio',
    ]
    candidates['fundamentals_observation_count'] = candidates[
        coverage_columns
    ].notna().sum(axis=1)
    candidates['fundamentals_coverage_ratio'] = (
        candidates['fundamentals_observation_count'] / len(coverage_columns)
    )
    candidates['is_synthetic_fundamentals'] = False
    for column in ('cet1_ratio', 'solvency_ratio', 'npl_ratio', 'book_value_growth'):
        candidates[column] = np.nan

    universe_columns = [
        'security_id',
        'ticker',
        'issuer_id',
        'company_name',
        'instrument_type',
        'listing_status',
        'exchange_code',
        'country',
        'region',
        'sector',
        'industry',
        'currency',
        'avg_daily_traded_value_usd',
        'market_cap_usd',
        'liquidity_observation_count',
        'latest_trade_date',
    ]
    universe_snapshot = candidates[universe_columns].copy()
    universe_snapshot['liquidity_data_source'] = np.where(
        candidates['avg_daily_traded_value_local'].gt(0),
        'historical_price_volume_fx',
        'current_reference_adv_proxy',
    )
    universe_snapshot['market_cap_data_source'] = 'historical_price_reported_shares'
    universe_snapshot['sector_data_source'] = 'current_security_reference_proxy'
    universe_snapshot['is_synthetic_data'] = False

    fundamental_columns = [
        'security_id',
        'ticker',
        'sector',
        'revenue',
        'revenue_growth',
        'ebitda',
        'ebitda_margin',
        'net_income',
        'net_income_margin',
        'operating_cash_flow',
        'capex',
        'free_cash_flow',
        'total_debt',
        'cash',
        'shareholders_equity',
        'enterprise_value',
        'dividend_yield',
        'trailing_12m_dps',
        'dividend_growth_3y',
        'dividend_growth_5y',
        'payout_ratio',
        'positive_fcf_years_5',
        'free_cash_flow_yield',
        'fcf_margin',
        'fcf_stability',
        'cfo_to_net_income',
        'net_debt_to_ebitda',
        'interest_coverage',
        'roe',
        'roic',
        'pe_ratio',
        'pb_ratio',
        'ev_ebitda',
        'dividend_cut_flag_3y',
        'cet1_ratio',
        'solvency_ratio',
        'npl_ratio',
        'book_value_growth',
        'fundamentals_data_source',
        'fundamentals_as_of_date',
        'fundamentals_available_from',
        'fundamentals_period_count',
        'fundamentals_observation_count',
        'fundamentals_coverage_ratio',
        'is_synthetic_fundamentals',
    ]
    fundamentals = candidates[fundamental_columns].copy()

    active_ids = set(candidates['security_id'].astype(str))
    recent = recent.loc[recent['security_id'].astype(str).isin(active_ids)].copy()
    recent['date'] = pd.to_datetime(recent['trade_date'])
    recent['close'] = recent['adjusted_close']
    recent['full_history_daily_return'] = recent.groupby('ticker')['return'].transform(
        'mean'
    )
    risk_features = build_price_risk_features(recent)

    neutral = candidates[['security_id', 'ticker']].copy()
    neutral['sentiment_alt_data_score'] = 50.0
    neutral['news_sentiment_30d'] = 0.0
    neutral['negative_news_intensity'] = 0.0
    neutral['controversy_score'] = 0.0
    neutral['credit_stress_score'] = 0.0
    neutral['regulatory_risk_score'] = 0.0
    neutral['alt_data_review_required_flag'] = False
    neutral['alt_data_exclusion_flag'] = False
    regime = candidates[['ticker']].copy()
    regime['regime_suitability_score'] = 50.0
    regime['regime_risk_score'] = 50.0
    regime['regime_deterioration_probability'] = 0.0
    regime['regime_weight_adjustment'] = 0.0
    regime['regime_review_required_flag'] = False
    regime['regime_exclusion_flag'] = False
    regime['dominant_regime'] = 'historical_neutral'
    portfolio = pd.DataFrame(
        columns=[
            'ticker',
            'sector',
            'country',
            'region',
            'currency',
            'weight',
            'market_value_usd',
        ]
    )
    features = build_feature_store(
        universe_snapshot,
        recent,
        fundamentals,
        neutral,
        portfolio,
        regime,
        price_risk_features=risk_features,
    )
    features['as_of_date'] = pd.Timestamp(as_of_date)
    features['feature_month'] = pd.Timestamp(as_of_date).replace(day=1)
    features['available_from'] = pd.to_datetime(
        features['fundamentals_available_from']
    )
    features['price_feature_end_date'] = pd.to_datetime(features['latest_trade_date'])
    features['evidence_mode'] = config.evidence_mode
    features['historical_non_market_features_mode'] = 'neutral_no_historical_vintage'
    features['dividend_risk_score'] = 0.0
    features['dividend_risk_similarity_score'] = 50.0
    features['risk_reframing_score'] = 50.0
    features['distress_similarity_score'] = 50.0
    features['credit_stress_similarity_score'] = 50.0
    features['regulatory_risk_similarity_score'] = 50.0
    features['narrative_reframing_score'] = 50.0
    features['reframing_review_required_flag'] = False
    features['reframing_exclusion_flag'] = False
    features['markov_negative_to_distress_prob'] = 0.0
    features['governance_red_flag_count'] = 0
    return features.reset_index(drop=True), recent.reset_index(drop=True)


def _forecast_anchor(
    features: pd.DataFrame,
    as_of_date: pd.Timestamp,
    evidence_mode: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    outputs = build_ml_forecast_features(features)
    metadata_columns = [
        'ticker',
        'issuer_id',
        'country',
        'region',
        'sector',
        'currency',
        'fundamentals_as_of_date',
        'fundamentals_available_from',
        'price_feature_end_date',
        'fundamentals_period_count',
    ]
    metadata = features[
        [column for column in metadata_columns if column in features]
    ].drop_duplicates('ticker')
    rows: list[pd.DataFrame] = []
    for months in FORECAST_HORIZONS:
        frame = outputs[f'ml_forecasts_{months}m'].copy()
        frame = frame.drop(
            columns=[
                column
                for column in metadata.columns
                if column in frame.columns and column != 'ticker'
            ],
            errors='ignore',
        ).merge(metadata, on='ticker', how='left')
        frame['as_of_date'] = pd.Timestamp(as_of_date)
        frame['forecast_date'] = pd.Timestamp(as_of_date)
        frame['horizon'] = f'{months}M'
        frame['horizon_months'] = months
        frame['evidence_mode'] = evidence_mode
        frame['model_version'] = 'wolf_deterministic_forecast_v1'
        rows.append(frame)
    return pd.concat(rows, ignore_index=True), outputs['ml_features']


def build_realised_outcomes(
    forecasts: pd.DataFrame,
    price_matcher: _PriceMatcher,
    tolerance_days: int,
) -> pd.DataFrame:
    if forecasts.empty:
        return pd.DataFrame()
    requests = forecasts[
        ['security_id', 'ticker', 'as_of_date', 'horizon', 'horizon_months']
    ].copy()
    requests['target_date'] = [
        pd.Timestamp(date) + pd.DateOffset(months=int(months))
        for date, months in zip(requests['as_of_date'], requests['horizon_months'])
    ]
    starts = price_matcher.match_requests(
        requests,
        'as_of_date',
        'backward',
        tolerance_days,
    ).rename(
        columns={
            'matched_trade_date': 'start_trade_date',
            'matched_adjusted_close': 'start_adjusted_close',
            'matched_close_price': 'start_close_price',
        }
    )
    if starts.empty:
        return pd.DataFrame()
    ends = price_matcher.match_requests(
        starts,
        'target_date',
        'forward',
        tolerance_days,
    ).rename(
        columns={
            'matched_trade_date': 'end_trade_date',
            'matched_adjusted_close': 'end_adjusted_close',
            'matched_close_price': 'end_close_price',
        }
    )
    if ends.empty:
        return pd.DataFrame()
    ends['realised_return'] = (
        ends['end_adjusted_close'] / ends['start_adjusted_close'] - 1.0
    )
    ends['outcome_date'] = pd.to_datetime(ends['end_trade_date'])
    return ends[
        [
            'security_id',
            'ticker',
            'as_of_date',
            'horizon',
            'horizon_months',
            'target_date',
            'start_trade_date',
            'end_trade_date',
            'outcome_date',
            'start_adjusted_close',
            'end_adjusted_close',
            'realised_return',
        ]
    ].reset_index(drop=True)


def _greedy_constrained_portfolio(
    scorecard: pd.DataFrame,
    constraints: dict[str, Any],
) -> pd.DataFrame:
    eligible = scorecard.loc[scorecard['passes_hard_filters'].fillna(False)].copy()
    eligible = eligible.sort_values(
        ['final_recommendation_score', 'ticker'],
        ascending=[False, True],
        kind='stable',
    ).drop_duplicates('issuer_id')
    selected: list[int] = []
    counts: dict[tuple[str, str], int] = {}
    group_limits = {
        'sector': int(float(constraints.get('max_sector_weight', 0.25)) / 0.05),
        'country': int(float(constraints.get('max_country_weight', 0.30)) / 0.05),
        'region': int(float(constraints.get('max_region_weight', 0.40)) / 0.05),
        'currency': int(float(constraints.get('max_currency_weight', 0.40)) / 0.05),
    }
    for index, row in eligible.iterrows():
        allowed = True
        for column, limit in group_limits.items():
            key = (column, str(row[column]))
            if counts.get(key, 0) >= limit:
                allowed = False
                break
        if not allowed:
            continue
        selected.append(index)
        for column in group_limits:
            key = (column, str(row[column]))
            counts[key] = counts.get(key, 0) + 1
        if len(selected) == 20:
            break
    if len(selected) < 20:
        raise RuntimeError(
            f'Only {len(selected)} names satisfied the historical portfolio constraints.'
        )
    portfolio = scorecard.loc[selected].copy()
    portfolio['target_weight'] = 0.05
    portfolio['optimisation_feasible'] = True
    portfolio['optimisation_status'] = 'greedy_constraint_fallback'
    return portfolio


def _build_anchor_portfolios(
    features: pd.DataFrame,
    forecast_wide: pd.DataFrame,
    previous_wolf_weights: pd.Series | None = None,
    maximum_rebalance_turnover: float = 0.10,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    merge_columns = [
        column
        for column in forecast_wide.columns
        if column == 'ticker' or column not in features.columns
    ]
    model_features = features.merge(
        forecast_wide[merge_columns],
        on='ticker',
        how='left',
    )
    risk_limits = load_yaml('configs/risk_limits.yaml')
    scorecard = build_scorecard(model_features, risk_limits)
    optimisation = load_yaml('configs/optimisation.yaml').get('optimisation', {})
    constraints = dict(optimisation.get('constraints', {}))
    constraints['maximum_candidates'] = int(optimisation.get('maximum_candidates', 2000))
    constraints['maximum_turnover'] = float(maximum_rebalance_turnover)
    optimiser_input = build_optimiser_input_dataset(scorecard)
    if previous_wolf_weights is not None:
        optimiser_input['current_weight'] = (
            optimiser_input['security_id']
            .astype(str)
            .map(previous_wolf_weights)
            .fillna(0.0)
        )
    wolf = cvar_constrained_portfolio(optimiser_input, constraints)
    wolf = wolf.loc[pd.to_numeric(wolf['target_weight'], errors='coerce').gt(1.0e-10)]
    feasible = (
        not wolf.empty
        and bool(wolf.get('optimisation_feasible', pd.Series(False)).fillna(False).all())
        and abs(float(wolf['target_weight'].sum()) - 1.0) <= 1.0e-6
    )
    if not feasible:
        wolf = _greedy_constrained_portfolio(scorecard, constraints)
    wolf = wolf.copy()
    wolf['strategy'] = 'wolf_cvar'
    wolf['weight'] = pd.to_numeric(wolf['target_weight'], errors='coerce')

    benchmark_base = scorecard.loc[
        scorecard['passes_hard_filters'].fillna(False)
    ].sort_values(
        ['final_recommendation_score', 'ticker'],
        ascending=[False, True],
        kind='stable',
    ).drop_duplicates('issuer_id')
    if benchmark_base.empty:
        raise RuntimeError('No eligible historical benchmark securities were available.')
    equal = benchmark_base.copy()
    equal['weight'] = 1.0 / len(equal)
    equal['strategy'] = 'equal_weight_eligible'
    cap_weight = pd.to_numeric(
        benchmark_base['market_cap_usd'],
        errors='coerce',
    ).clip(lower=0)
    cap = benchmark_base.copy()
    cap['weight'] = cap_weight / cap_weight.sum()
    cap['strategy'] = 'cap_weight_eligible'
    return {
        'wolf_cvar': wolf,
        'equal_weight_eligible': equal,
        'cap_weight_eligible': cap,
    }, scorecard


def _series_weights(portfolio: pd.DataFrame) -> pd.Series:
    return pd.Series(
        pd.to_numeric(portfolio['weight'], errors='coerce').to_numpy(),
        index=portfolio['security_id'].astype(str),
        dtype=float,
    )


def _portfolio_outcome(
    portfolio: pd.DataFrame,
    as_of_date: pd.Timestamp,
    price_matcher: _PriceMatcher,
    tolerance_days: int,
) -> tuple[float, float]:
    requests = portfolio[['security_id', 'ticker']].copy()
    requests['as_of_date'] = as_of_date
    requests['horizon'] = '1M'
    requests['horizon_months'] = 1
    outcomes = build_realised_outcomes(requests, price_matcher, tolerance_days)
    if outcomes.empty:
        return float('nan'), 0.0
    weights = _series_weights(portfolio)
    outcomes['weight'] = outcomes['security_id'].astype(str).map(weights)
    valid_weight = float(outcomes['weight'].sum())
    if valid_weight < 0.95:
        return float('nan'), valid_weight
    realised = float(
        (
            outcomes['realised_return']
            * outcomes['weight']
            / valid_weight
        ).sum()
    )
    return realised, valid_weight


def _portfolio_cost(
    current: pd.DataFrame,
    previous_weights: pd.Series | None,
    feature_lookup: pd.DataFrame,
    nav_usd: float,
) -> tuple[float, float]:
    target = _series_weights(current)
    if previous_weights is None:
        delta = target
        turnover = 1.0
    else:
        union = target.index.union(previous_weights.index)
        delta = target.reindex(union, fill_value=0.0) - previous_weights.reindex(
            union,
            fill_value=0.0,
        )
        turnover = float(0.5 * delta.abs().sum())
    costs = load_yaml('configs/validation.yaml').get('validation', {}).get('costs', {})
    lookup = feature_lookup.set_index('security_id', drop=False)
    total_cost = 0.0
    for security_id, weight_change in delta.items():
        if abs(float(weight_change)) <= 1.0e-12:
            continue
        row = lookup.loc[security_id] if security_id in lookup.index else pd.Series()
        estimate = estimate_transaction_cost(
            traded_notional=abs(float(weight_change)) * nav_usd,
            commission_bps=float(costs.get('base_commission_bps', 5.0)),
            half_spread_bps=float(costs.get('half_spread_bps', 7.5)),
            slippage_bps=float(costs.get('slippage_bps', 5.0)),
            volatility=float(row.get('volatility_1y', 0.25)),
            average_daily_value=float(row.get('average_daily_value_usd', np.nan)),
            impact_coefficient=float(costs.get('impact_coefficient', 0.10)),
        )
        total_cost += float(estimate['total_cost'])
    return turnover, total_cost / nav_usd


def _weighted_daily_returns(
    prices: pd.DataFrame,
    weights: pd.Series,
    minimum_coverage: float = 0.80,
) -> pd.Series:
    if prices.empty:
        return pd.Series(dtype=float)
    matrix = prices.pivot_table(
        index='trade_date',
        columns='security_id',
        values='return',
        aggfunc='last',
    )
    aligned_weights = weights.reindex(matrix.columns.astype(str), fill_value=0.0)
    aligned_weights.index = matrix.columns
    coverage = matrix.notna().mul(aligned_weights, axis=1).sum(axis=1)
    weighted = matrix.fillna(0.0).mul(aligned_weights, axis=1).sum(axis=1)
    return (weighted / coverage.replace(0, np.nan)).loc[coverage.ge(minimum_coverage)].dropna()


def _risk_rows(
    portfolio: pd.DataFrame,
    as_of_date: pd.Timestamp,
    price_matcher: _PriceMatcher,
    config: WalkForwardConfig,
) -> pd.DataFrame:
    weights = _series_weights(portfolio)
    security_ids = weights.index.astype(str).tolist()
    trailing, _ = price_matcher.trailing(
        security_ids,
        as_of_date,
        config.risk_lookback_rows + 1,
    )
    historical = _weighted_daily_returns(trailing, weights).tail(
        config.risk_lookback_rows
    )
    target_date = as_of_date + pd.DateOffset(months=1)
    realised_prices = price_matcher.between(security_ids, as_of_date, target_date)
    realised = _weighted_daily_returns(realised_prices, weights).sort_index()
    if len(historical) < 120 or realised.empty:
        return pd.DataFrame()
    normal = NormalDist()
    history = historical.astype(float).copy()
    rows: list[dict[str, Any]] = []
    for date, realised_return in realised.items():
        sample = history.tail(config.risk_lookback_rows).to_numpy(dtype=float)
        powers = np.arange(len(sample) - 1, -1, -1, dtype=float)
        weights_ewma = np.power(config.risk_ewma_decay, powers)
        volatility = float(
            np.sqrt(np.average(np.square(sample), weights=weights_ewma))
        )
        forecasts: dict[str, float] = {}
        for confidence in (0.95, 0.99):
            alpha = 1.0 - confidence
            quantile = normal.inv_cdf(alpha)
            density = normal.pdf(quantile)
            forecasts[f'var_{int(confidence * 100)}'] = quantile * volatility
            forecasts[f'expected_shortfall_{int(confidence * 100)}'] = (
                -volatility * density / alpha
            )
        rows.append(
            {
                'date': pd.Timestamp(date),
                'as_of_date': as_of_date,
                'strategy': 'wolf_cvar',
                'realised_return': float(realised_return),
                **forecasts,
                'forecast_volatility': volatility,
                'risk_model': 'daily_ewma_normal',
                'ewma_decay': config.risk_ewma_decay,
                'training_observations': len(sample),
                'training_end_date': pd.Timestamp(history.index.max()),
                'evidence_mode': config.evidence_mode,
            }
        )
        history.loc[pd.Timestamp(date)] = float(realised_return)
    return pd.DataFrame(rows)


def _constraint_rows(
    portfolio: pd.DataFrame,
    as_of_date: pd.Timestamp,
) -> pd.DataFrame:
    optimisation = load_yaml('configs/optimisation.yaml').get('optimisation', {})
    limits = optimisation.get('constraints', {})
    weights = _series_weights(portfolio)
    rows = [
        {
            'as_of_date': as_of_date,
            'strategy': 'wolf_cvar',
            'constraint_name': 'weights_sum_to_one',
            'constraint_type': 'hard',
            'actual_value': float(weights.sum()),
            'limit_value': 1.0,
            'breach_flag': abs(float(weights.sum()) - 1.0) > 1.0e-6,
        },
        {
            'as_of_date': as_of_date,
            'strategy': 'wolf_cvar',
            'constraint_name': 'maximum_single_name_weight',
            'constraint_type': 'hard',
            'actual_value': float(weights.max()),
            'limit_value': float(limits.get('max_single_name_weight', 0.05)),
            'breach_flag': float(weights.max())
            > float(limits.get('max_single_name_weight', 0.05)) + 1.0e-6,
        },
    ]
    group_limits = {
        'sector': 'max_sector_weight',
        'country': 'max_country_weight',
        'region': 'max_region_weight',
        'currency': 'max_currency_weight',
    }
    for column, key in group_limits.items():
        exposure = (
            portfolio.assign(_weight=portfolio['weight'])
            .groupby(column, dropna=False)['_weight']
            .sum()
        )
        actual = float(exposure.max()) if not exposure.empty else 0.0
        limit = float(limits.get(key, 1.0))
        rows.append(
            {
                'as_of_date': as_of_date,
                'strategy': 'wolf_cvar',
                'constraint_name': f'maximum_{column}_weight',
                'constraint_type': 'hard',
                'actual_value': actual,
                'limit_value': limit,
                'breach_flag': actual > limit + 1.0e-6,
            }
        )
    return pd.DataFrame(rows)


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    frame.to_parquet(temporary, index=False, compression='zstd')
    temporary.replace(path)


def _atomic_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding='utf-8',
    )
    temporary.replace(path)


def _frame_hash(frame: pd.DataFrame, columns: list[str]) -> str:
    digest = hashlib.sha256()
    if frame.empty:
        return digest.hexdigest()
    values = frame[columns].astype(str).sort_values(columns).agg('|'.join, axis=1)
    for value in values:
        digest.update(value.encode('utf-8'))
    return digest.hexdigest()


def run_walk_forward(config: WalkForwardConfig | None = None) -> WalkForwardResult:
    config = config or load_walk_forward_config()
    if config.start_date > config.forecast_end_date:
        raise ValueError('Walk-forward start date must not exceed forecast end date.')
    if config.forecast_end_date > config.strategy_end_date:
        raise ValueError('Forecast end date must not exceed strategy end date.')
    data_config = load_data_config()
    repository = DuckDBRepository(data_config.duckdb_path, read_only=True)
    LOGGER.info('Loading observed walk-forward source data from %s.', data_config.duckdb_path)
    universe, statements_raw, prices_raw, fx = _load_source_data(repository, config)
    if universe.empty or statements_raw.empty or prices_raw.empty:
        raise RuntimeError('Observed walk-forward source data is incomplete.')
    fx_matcher = _FxMatcher(fx)
    prices = _prepare_prices(prices_raw)
    statements = _prepare_statements(
        statements_raw,
        universe,
        fx_matcher,
        config.filing_lag_days,
    )
    price_matcher = _PriceMatcher(prices)
    anchors = pd.date_range(
        config.start_date,
        config.strategy_end_date,
        freq='ME',
    )

    forecast_frames: list[pd.DataFrame] = []
    outcome_frames: list[pd.DataFrame] = []
    weight_frames: list[pd.DataFrame] = []
    portfolio_rows: list[dict[str, Any]] = []
    risk_frames: list[pd.DataFrame] = []
    constraint_frames: list[pd.DataFrame] = []
    anchor_rows: list[dict[str, Any]] = []
    previous_weights: dict[str, pd.Series] = {}

    for position, anchor in enumerate(anchors, start=1):
        features, recent = _build_anchor_inputs(
            universe,
            statements,
            price_matcher,
            fx_matcher,
            pd.Timestamp(anchor),
            config,
        )
        if features.empty:
            raise RuntimeError(f'No point-in-time features were available at {anchor.date()}.')
        forecasts, forecast_wide = _forecast_anchor(
            features,
            pd.Timestamp(anchor),
            config.evidence_mode,
        )
        if anchor <= config.forecast_end_date:
            realised = build_realised_outcomes(
                forecasts,
                price_matcher,
                config.outcome_date_tolerance_days,
            )
            forecast_frames.append(forecasts)
            outcome_frames.append(realised)

        portfolios, scorecard = _build_anchor_portfolios(
            features,
            forecast_wide,
            previous_weights.get(config.primary_strategy),
            config.maximum_rebalance_turnover,
        )
        regime = (
            'high_volatility'
            if float(features['volatility_1y'].median()) > 0.30
            else 'negative_momentum'
            if float(features['momentum_6m'].median()) < 0
            else 'steady'
        )
        for strategy, portfolio in portfolios.items():
            portfolio = portfolio.copy()
            gross_return, valid_weight = _portfolio_outcome(
                portfolio,
                pd.Timestamp(anchor),
                price_matcher,
                config.outcome_date_tolerance_days,
            )
            turnover, transaction_cost = _portfolio_cost(
                portfolio,
                previous_weights.get(strategy),
                scorecard,
                config.portfolio_nav_usd,
            )
            previous_weights[strategy] = _series_weights(portfolio)
            portfolio['as_of_date'] = pd.Timestamp(anchor)
            portfolio['evidence_mode'] = config.evidence_mode
            portfolio['strategy'] = strategy
            weight_frames.append(portfolio)
            portfolio_rows.append(
                {
                    'date': pd.Timestamp(anchor) + pd.DateOffset(months=1),
                    'as_of_date': pd.Timestamp(anchor),
                    'strategy': strategy,
                    'gross_return': gross_return,
                    'transaction_cost': transaction_cost,
                    'net_return': gross_return - transaction_cost,
                    'turnover': turnover,
                    'valid_outcome_weight': valid_weight,
                    'holding_count': int(portfolio['weight'].gt(1.0e-10).sum()),
                    'regime': regime,
                    'evidence_mode': config.evidence_mode,
                }
            )

        wolf = portfolios['wolf_cvar']
        risk = _risk_rows(
            wolf,
            pd.Timestamp(anchor),
            price_matcher,
            config,
        )
        if not risk.empty:
            risk_frames.append(risk)
        constraint_frames.append(_constraint_rows(wolf, pd.Timestamp(anchor)))
        anchor_rows.append(
            {
                'as_of_date': pd.Timestamp(anchor),
                'feature_security_count': len(features),
                'forecast_security_count': forecasts['security_id'].nunique(),
                'wolf_holding_count': int(wolf['weight'].gt(1.0e-10).sum()),
                'latest_price_feature_date': pd.to_datetime(
                    features['price_feature_end_date']
                ).max(),
                'latest_fundamental_available_from': pd.to_datetime(
                    features['fundamentals_available_from']
                ).max(),
            }
        )
        LOGGER.info(
            'Walk-forward anchor %s/%s %s: features=%s holdings=%s.',
            position,
            len(anchors),
            anchor.date(),
            len(features),
            int(wolf['weight'].gt(1.0e-10).sum()),
        )

    historical_forecasts = pd.concat(forecast_frames, ignore_index=True)
    outcomes = pd.concat(outcome_frames, ignore_index=True)
    portfolio_weights = pd.concat(weight_frames, ignore_index=True, sort=False)
    portfolio_returns = pd.DataFrame(portfolio_rows)
    risk_forecasts = pd.concat(risk_frames, ignore_index=True)
    constraints = pd.concat(constraint_frames, ignore_index=True)
    anchor_summary = pd.DataFrame(anchor_rows)

    chronology_checks = {
        'future_fundamental_rows': int(
            (
                pd.to_datetime(historical_forecasts['fundamentals_available_from'])
                > pd.to_datetime(historical_forecasts['as_of_date'])
            ).sum()
        ),
        'future_price_feature_rows': int(
            (
                pd.to_datetime(historical_forecasts['price_feature_end_date'])
                > pd.to_datetime(historical_forecasts['as_of_date'])
            ).sum()
        ),
        'outcomes_before_target_rows': int(
            (
                pd.to_datetime(outcomes['end_trade_date'])
                < pd.to_datetime(outcomes['target_date'])
            ).sum()
        ),
        'hard_constraint_breaches': int(constraints['breach_flag'].fillna(False).sum()),
    }
    if any(chronology_checks.values()):
        raise RuntimeError(f'Walk-forward chronology checks failed: {chronology_checks}')

    output = config.output_directory
    _atomic_parquet(historical_forecasts, output / 'historical_forecasts.parquet')
    _atomic_parquet(outcomes, output / 'historical_realised_outcomes.parquet')
    _atomic_parquet(portfolio_weights, output / 'historical_portfolio_weights.parquet')
    _atomic_parquet(portfolio_returns, output / 'historical_portfolio_returns.parquet')
    _atomic_parquet(risk_forecasts, output / 'historical_risk_forecasts.parquet')
    _atomic_parquet(constraints, output / 'historical_constraint_report.parquet')
    _atomic_parquet(anchor_summary, output / 'walk_forward_anchor_summary.parquet')

    primary_returns = portfolio_returns.loc[
        portfolio_returns['strategy'].eq(config.primary_strategy)
    ]
    manifest = {
        'artifact_version': ARTIFACT_VERSION,
        'generated_at': datetime.now(UTC).isoformat(),
        'evidence_mode': config.evidence_mode,
        'release_approval_cap': config.approval_cap,
        'primary_strategy': config.primary_strategy,
        'configuration': asdict(config),
        'source_database': str(data_config.duckdb_path),
        'source_universe_hash': _frame_hash(universe, ['security_id', 'region']),
        'source_profile': {
            'security_count': int(universe['security_id'].nunique()),
            'statement_rows': len(statements),
            'price_rows': len(prices),
            'price_min_date': pd.to_datetime(prices['trade_date']).min(),
            'price_max_date': pd.to_datetime(prices['trade_date']).max(),
            'fundamental_min_period': pd.to_datetime(
                statements['fiscal_period_end']
            ).min(),
            'fundamental_max_period': pd.to_datetime(
                statements['fiscal_period_end']
            ).max(),
        },
        'artifact_profile': {
            'anchors': len(anchors),
            'forecast_rows': len(historical_forecasts),
            'outcome_rows': len(outcomes),
            'aligned_outcome_fraction': len(outcomes) / max(len(historical_forecasts), 1),
            'portfolio_months': int(primary_returns['date'].nunique()),
            'portfolio_weight_rows': len(portfolio_weights),
            'risk_observations': len(risk_forecasts),
            'constraint_rows': len(constraints),
        },
        'chronology_checks': chronology_checks,
        'limitations': [
            'Historical filing availability is reconstructed from fiscal period end plus a conservative reporting lag when an observed filing date is unavailable.',
            'The current active universe and current sector metadata introduce survivorship and reference-data bias.',
            'Historical sentiment, narrative, and regime vintages are unavailable and are held neutral in this reconstruction.',
            'Stored candidate price bars have zero volume, so observed current 3-month ADV is used as a static liquidity proxy.',
            'Adjusted-close outcomes may include provider-side retrospective corporate-action adjustments.',
            'This evidence can support conditional model use but cannot support full production approval.',
        ],
    }
    _atomic_json(manifest, output / 'walk_forward_manifest.json')
    result = WalkForwardResult(
        output_directory=output,
        forecast_rows=len(historical_forecasts),
        outcome_rows=len(outcomes),
        portfolio_months=int(primary_returns['date'].nunique()),
        risk_observations=len(risk_forecasts),
        security_count=int(universe['security_id'].nunique()),
        evidence_mode=config.evidence_mode,
    )
    LOGGER.info(
        'Walk-forward artifacts completed: forecasts=%s outcomes=%s months=%s risk=%s.',
        result.forecast_rows,
        result.outcome_rows,
        result.portfolio_months,
        result.risk_observations,
    )
    return result
