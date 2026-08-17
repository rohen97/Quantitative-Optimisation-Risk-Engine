from __future__ import annotations

from collections.abc import Sequence
import logging

import numpy as np
import pandas as pd

from src.data.config import load_data_config
from src.data.model_input_summaries import price_summary_status
from src.data.repository.duckdb_repository import DuckDBRepository


LOGGER = logging.getLogger(__name__)


def load_duckdb_universe(
    max_securities: int = 0,
    min_price_rows: int = 120,
    regions: Sequence[str] = (),
    repository: DuckDBRepository | None = None,
) -> pd.DataFrame:
    """Load the stable, priced equity universe without materialising price history."""
    data_config = load_data_config()
    repo = repository or DuckDBRepository(
        data_config.duckdb_path,
        read_only=data_config.duckdb_read_only_for_models,
    )
    region_filter = "AND s.region IN (SELECT UNNEST(?))" if regions else ""
    parameters: list[object] = [int(min_price_rows)]
    if regions:
        parameters.append(list(regions))
    limit_clause = ""
    if max_securities > 0:
        limit_clause = "LIMIT ?"
        parameters.append(int(max_securities))
    summary_status = price_summary_status(repo)
    if summary_status.fresh:
        price_ctes = """
        priced AS (
            SELECT
                security_id,
                price_rows,
                latest_trade_date,
                avg_daily_traded_value_local,
                observed_volume_rows
            FROM security_price_summaries
            WHERE price_rows >= ?
        )
        """
    else:
        LOGGER.warning(
            "Price summary is stale or absent; using the exact full-table fallback. "
            "Run scripts/refresh_model_input_summaries.py to restore low-latency reads."
        )
        price_ctes = """
        source_ranked AS (
            SELECT
                security_id,
                trade_date,
                COALESCE(adjusted_close, close_price) AS close_price,
                volume,
                ROW_NUMBER() OVER (
                    PARTITION BY security_id, trade_date
                    ORDER BY retrieved_at DESC, source DESC
                ) AS source_row
            FROM prices_daily
            WHERE COALESCE(adjusted_close, close_price) IS NOT NULL
        ),
        latest_prices AS (
            SELECT
                security_id,
                trade_date,
                MAX(close_price) FILTER (WHERE source_row = 1) AS close_price,
                MAX(volume) FILTER (WHERE volume IS NOT NULL AND volume > 0) AS volume
            FROM source_ranked
            GROUP BY security_id, trade_date
        ),
        ranked_prices AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY security_id
                    ORDER BY trade_date DESC
                ) AS recency_row
            FROM latest_prices
        ),
        priced AS (
            SELECT
                security_id,
                COUNT(*) AS price_rows,
                MAX(trade_date) AS latest_trade_date,
                AVG(volume * close_price) FILTER (
                    WHERE recency_row <= 60 AND volume IS NOT NULL AND volume > 0
                ) AS avg_daily_traded_value_local,
                COUNT(*) FILTER (
                    WHERE recency_row <= 60 AND volume IS NOT NULL AND volume > 0
                ) AS observed_volume_rows
            FROM ranked_prices
            GROUP BY security_id
            HAVING COUNT(*) >= ?
        )
        """
    universe = repo.query(
        f"""
        WITH {price_ctes},
        identifiers AS (
            SELECT
                security_id,
                MAX(identifier_value) FILTER (
                    WHERE identifier_type = 'isin'
                ) AS isin
            FROM security_identifiers
            GROUP BY security_id
        ),
        latest_fx AS (
            SELECT
                quote_currency,
                ARG_MAX(rate, rate_date) AS units_per_usd
            FROM fx_rates
            WHERE base_currency = 'USD'
              AND rate > 0
            GROUP BY quote_currency
        ),
        latest_reference AS (
            SELECT * EXCLUDE (reference_row)
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY security_id
                        ORDER BY as_of_date DESC, retrieved_at DESC
                    ) AS reference_row
                FROM security_reference_snapshots
            )
            WHERE reference_row = 1
        ),
        security_base AS (
            SELECT
                s.*,
                COALESCE(
                    NULLIF(s.trading_currency, ''),
                    NULLIF(s.domicile_currency, ''),
                    'USD'
                ) AS model_currency
            FROM securities s
        )
        SELECT
            s.security_id,
            s.security_id AS ticker,
            CASE
                WHEN REGEXP_REPLACE(LOWER(s.company_name), '[^a-z0-9]+', '', 'g') IN ('', 'unknown', 'none', 'nan')
                    THEN COALESCE(i.isin, s.security_id)
                ELSE 'NAME:' || REGEXP_REPLACE(LOWER(s.company_name), '[^a-z0-9]+', '', 'g')
            END AS issuer_id,
            i.isin,
            s.company_name,
            s.instrument_type,
            s.listing_status,
            s.exchange_code,
            s.country,
            s.region,
            COALESCE(NULLIF(r.sector, ''), NULLIF(s.sector, ''), 'Unknown') AS sector,
            COALESCE(NULLIF(r.industry, ''), NULLIF(s.industry, ''), 'Unknown') AS industry,
            s.model_currency AS currency,
            COALESCE(
                CASE
                    WHEN s.model_currency = 'USD' THEN p.avg_daily_traded_value_local
                    WHEN fx.units_per_usd > 0 THEN p.avg_daily_traded_value_local / fx.units_per_usd
                    ELSE NULL
                END,
                r.average_daily_value_usd
            ) AS avg_daily_traded_value_usd,
            r.market_cap_usd,
            CASE
                WHEN p.observed_volume_rows = 0 AND r.average_daily_value_usd > 0
                    THEN r.source || '_3m_average_volume'
                WHEN p.observed_volume_rows = 0 THEN 'missing'
                WHEN s.model_currency = 'USD' THEN 'observed_price_volume'
                WHEN fx.units_per_usd > 0 THEN 'observed_price_volume_fx'
                ELSE 'missing'
            END AS liquidity_data_source,
            CASE
                WHEN r.market_cap_usd > 0 THEN r.source
                ELSE 'missing'
            END AS market_cap_data_source,
            CASE
                WHEN NULLIF(r.sector, '') IS NOT NULL THEN r.source
                WHEN NULLIF(s.sector, '') IS NULL OR LOWER(s.sector) = 'unknown' THEN 'missing'
                ELSE 'security_master'
            END AS sector_data_source,
            FALSE AS is_synthetic_data,
            p.price_rows,
            p.latest_trade_date,
            CASE
                WHEN p.observed_volume_rows > 0 THEN p.observed_volume_rows
                WHEN r.average_daily_value_usd > 0 THEN 60
                ELSE 0
            END AS liquidity_observation_count
        FROM security_base s
        JOIN priced p USING (security_id)
        LEFT JOIN identifiers i USING (security_id)
        LEFT JOIN latest_fx fx ON fx.quote_currency = s.model_currency
        LEFT JOIN latest_reference r USING (security_id)
        WHERE s.listing_status = 'Active'
          AND s.instrument_type = 'Equity'
          {region_filter}
        ORDER BY p.price_rows DESC, s.region, s.security_id
        {limit_clause}
        """,
        parameters,
    )
    if universe.empty:
        raise RuntimeError("DuckDB model input query returned no securities with usable price history.")
    universe["_pipeline_index"] = np.arange(len(universe), dtype=np.int64)
    universe.attrs["price_summary_mode"] = "materialised" if summary_status.fresh else "fallback"
    return universe


def _safe_number(value: object) -> float:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(number) if pd.notna(number) and np.isfinite(number) else np.nan


def _safe_ratio(numerator: float, denominator: float) -> float:
    if not np.isfinite(numerator) or not np.isfinite(denominator) or denominator == 0:
        return np.nan
    return float(numerator / denominator)


def _annualised_growth(values: pd.Series, dates: pd.Series) -> float:
    valid = pd.DataFrame({"value": values, "date": dates}).dropna().sort_values("date")
    valid = valid.loc[valid["value"] > 0]
    if len(valid) < 2:
        return np.nan
    first = valid.iloc[0]
    last = valid.iloc[-1]
    years = max((pd.Timestamp(last["date"]) - pd.Timestamp(first["date"])).days / 365.25, 1.0)
    return float((last["value"] / first["value"]) ** (1.0 / years) - 1.0)


def load_observed_fundamentals(
    universe: pd.DataFrame,
    minimum_annual_periods: int = 2,
    repository: DuckDBRepository | None = None,
) -> pd.DataFrame:
    """Build model-ready financial features from reported annual statements."""
    if universe.empty:
        return pd.DataFrame()
    data_config = load_data_config()
    repo = repository or DuckDBRepository(
        data_config.duckdb_path,
        read_only=data_config.duckdb_read_only_for_models,
    )
    security_ids = universe["security_id"].astype(str).tolist()
    statements = repo.query(
        """
        WITH ranked AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY security_id, fiscal_period_end, fiscal_period_type
                    ORDER BY
                        CASE
                            WHEN source = 'sec_companyfacts' THEN 1
                            WHEN source IN (
                                'finnhub_reported',
                                'eastmoney_china_financials',
                                'eastmoney_hk_financials'
                            ) THEN 2
                            WHEN source LIKE 'akshare%' THEN 3
                            WHEN source = 'yahoo_finance_timeseries' THEN 4
                            ELSE 5
                        END,
                        available_from DESC,
                        retrieved_at DESC
                ) AS source_row
            FROM fundamentals_reported
            WHERE security_id IN (SELECT UNNEST(?))
              AND fiscal_period_type = 'annual'
              AND LOWER(source) NOT LIKE '%mock%'
              AND LOWER(source) NOT LIKE '%synthetic%'
        )
        SELECT * EXCLUDE (source_row)
        FROM ranked
        WHERE source_row = 1
        ORDER BY security_id, fiscal_period_end
        """,
        [security_ids],
    )
    if statements.empty:
        return pd.DataFrame()
    reference = repo.query(
        """
        WITH ranked AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY security_id
                    ORDER BY as_of_date DESC, retrieved_at DESC
                ) AS reference_row
            FROM security_reference_snapshots
            WHERE security_id IN (SELECT UNNEST(?))
        )
        SELECT * EXCLUDE (reference_row)
        FROM ranked
        WHERE reference_row = 1
        """,
        [security_ids],
    )
    fx = repo.query(
        """
        SELECT quote_currency, ARG_MAX(rate, rate_date) AS units_per_usd
        FROM fx_rates
        WHERE base_currency = 'USD' AND rate > 0
        GROUP BY quote_currency
        """
    )
    rates = dict(zip(fx["quote_currency"].astype(str), fx["units_per_usd"].astype(float)))
    rates["USD"] = 1.0
    statements["currency"] = statements["currency"].astype(str).str.upper()
    statements["_units_per_usd"] = statements["currency"].map(rates)
    monetary_columns = [
        "revenue",
        "operating_income",
        "net_income",
        "operating_cash_flow",
        "capital_expenditure",
        "free_cash_flow",
        "total_assets",
        "total_liabilities",
        "total_debt",
        "cash_and_equivalents",
        "shareholders_equity",
        "dividends_paid",
        "ebitda",
        "interest_expense",
    ]
    for column in monetary_columns:
        statements[f"{column}_usd"] = (
            pd.to_numeric(statements[column], errors="coerce")
            / statements["_units_per_usd"]
        )
    statements["diluted_shares"] = pd.to_numeric(statements["diluted_shares"], errors="coerce")
    statements["fiscal_period_end"] = pd.to_datetime(statements["fiscal_period_end"])
    universe_by_id = universe.set_index("security_id", drop=False)
    reference_by_id = reference.set_index("security_id", drop=False) if not reference.empty else pd.DataFrame()
    rows: list[dict[str, object]] = []
    for security_id, group in statements.groupby("security_id", sort=False):
        group = group.sort_values("fiscal_period_end").drop_duplicates("fiscal_period_end", keep="last")
        if len(group) < minimum_annual_periods or security_id not in universe_by_id.index:
            continue
        latest = group.iloc[-1]
        previous = group.iloc[-2] if len(group) > 1 else None
        universe_row = universe_by_id.loc[security_id]
        reference_row = (
            reference_by_id.loc[security_id]
            if not reference.empty and security_id in reference_by_id.index
            else pd.Series(dtype=object)
        )

        def metric(name: str) -> float:
            return _safe_number(latest.get(f"{name}_usd"))

        def reference_metric(name: str) -> float:
            return _safe_number(reference_row.get(name))

        financial_currency = str(reference_row.get("financial_currency") or latest.get("currency") or "USD").upper()
        financial_rate = _safe_number(rates.get(financial_currency))

        def reference_financial_usd(name: str) -> float:
            value = reference_metric(name)
            return value / financial_rate if np.isfinite(value) and np.isfinite(financial_rate) and financial_rate > 0 else np.nan

        revenue = metric("revenue")
        operating_income = metric("operating_income")
        net_income = metric("net_income")
        operating_cash_flow = metric("operating_cash_flow")
        capital_expenditure = abs(metric("capital_expenditure"))
        free_cash_flow = metric("free_cash_flow")
        if not np.isfinite(free_cash_flow) and np.isfinite(operating_cash_flow) and np.isfinite(capital_expenditure):
            free_cash_flow = operating_cash_flow - capital_expenditure
        total_debt = metric("total_debt")
        cash = metric("cash_and_equivalents")
        shareholders_equity = metric("shareholders_equity")
        ebitda = metric("ebitda")
        if not np.isfinite(ebitda):
            ebitda = reference_financial_usd("ebitda")
        interest_expense = abs(metric("interest_expense"))
        market_cap_usd = _safe_number(universe_row.get("market_cap_usd"))
        enterprise_value = reference_metric("enterprise_value_usd")
        dividends_paid = abs(metric("dividends_paid"))
        payout_ratio = reference_metric("payout_ratio")
        if not np.isfinite(payout_ratio):
            payout_ratio = _safe_ratio(dividends_paid, net_income) if net_income > 0 else np.nan

        fcf_history = pd.to_numeric(group["free_cash_flow_usd"], errors="coerce").dropna()
        positive_fcf_years = int((fcf_history > 0).sum())
        if len(fcf_history) >= 2 and fcf_history.abs().mean() > 0:
            variability = float(fcf_history.std(ddof=0) / fcf_history.abs().mean())
            fcf_stability = float(100 * (1 - min(variability / 1.5, 1.0)))
        else:
            fcf_stability = np.nan

        dividend_history = group[["fiscal_period_end", "dividends_paid_usd", "diluted_shares"]].copy()
        dividend_history["dps"] = (
            dividend_history["dividends_paid_usd"].abs()
            / dividend_history["diluted_shares"].replace(0, np.nan)
        )
        dividend_history = dividend_history.dropna(subset=["dps"])
        dividend_changes = dividend_history["dps"].pct_change()
        dividend_cut = float((dividend_changes < -0.20).tail(3).any()) if len(dividend_history) >= 2 else np.nan
        revenue_growth = (
            _safe_ratio(
                revenue,
                _safe_number(previous.get("revenue_usd")),
            )
            - 1.0
            if previous is not None
            else np.nan
        )
        required_values = [
            revenue,
            operating_income,
            net_income,
            operating_cash_flow,
            free_cash_flow,
            total_debt,
            cash,
            shareholders_equity,
            ebitda,
            market_cap_usd,
            reference_metric("dividend_yield"),
            payout_ratio,
        ]
        rows.append(
            {
                "security_id": security_id,
                "ticker": str(universe_row["ticker"]),
                "sector": universe_row.get("sector", "Unknown"),
                "revenue": revenue,
                "revenue_growth": revenue_growth,
                "ebitda": ebitda,
                "ebitda_margin": _safe_ratio(ebitda, revenue),
                "net_income": net_income,
                "net_income_margin": _safe_ratio(net_income, revenue),
                "operating_cash_flow": operating_cash_flow,
                "capex": capital_expenditure,
                "free_cash_flow": free_cash_flow,
                "total_debt": total_debt,
                "cash": cash,
                "shareholders_equity": shareholders_equity,
                "enterprise_value": enterprise_value,
                "dividend_yield": reference_metric("dividend_yield"),
                "trailing_12m_dps": _safe_number(dividend_history["dps"].iloc[-1]) if not dividend_history.empty else np.nan,
                "dividend_growth_3y": _annualised_growth(
                    dividend_history["dps"].tail(4),
                    dividend_history["fiscal_period_end"].tail(4),
                ),
                "dividend_growth_5y": _annualised_growth(
                    dividend_history["dps"].tail(6),
                    dividend_history["fiscal_period_end"].tail(6),
                ),
                "payout_ratio": payout_ratio,
                "positive_fcf_years_5": positive_fcf_years,
                "free_cash_flow_yield": _safe_ratio(free_cash_flow, market_cap_usd),
                "fcf_margin": _safe_ratio(free_cash_flow, revenue),
                "fcf_stability": fcf_stability,
                "cfo_to_net_income": _safe_ratio(operating_cash_flow, net_income),
                "net_debt_to_ebitda": _safe_ratio(total_debt - cash, ebitda),
                "interest_coverage": _safe_ratio(operating_income, interest_expense),
                "roe": _safe_ratio(net_income, shareholders_equity),
                "roic": _safe_ratio(
                    operating_income * 0.79,
                    total_debt + shareholders_equity - cash,
                ),
                "pe_ratio": reference_metric("trailing_pe"),
                "pb_ratio": reference_metric("price_to_book"),
                "ev_ebitda": reference_metric("enterprise_to_ebitda"),
                "dividend_cut_flag_3y": dividend_cut,
                "cet1_ratio": np.nan,
                "solvency_ratio": np.nan,
                "npl_ratio": np.nan,
                "book_value_growth": np.nan,
                "fundamentals_data_source": ",".join(sorted(group["source"].astype(str).unique())),
                "fundamentals_as_of_date": latest["fiscal_period_end"],
                "fundamentals_available_from": latest["available_from"],
                "fundamentals_period_count": len(group),
                "fundamentals_observation_count": sum(np.isfinite(value) for value in required_values),
                "fundamentals_coverage_ratio": sum(np.isfinite(value) for value in required_values) / len(required_values),
                "is_synthetic_fundamentals": False,
            }
        )
    return pd.DataFrame(rows)


def load_recent_duckdb_prices(
    tickers: Sequence[str],
    lookback_rows: int = 253,
    max_abs_daily_return: float = 1.0,
    repository: DuckDBRepository | None = None,
) -> pd.DataFrame:
    """Load only the recent rows needed for features plus exact full-history mean return."""
    if not tickers:
        return pd.DataFrame(columns=["ticker", "date", "close", "return", "full_history_daily_return"])
    data_config = load_data_config()
    repo = repository or DuckDBRepository(
        data_config.duckdb_path,
        read_only=data_config.duckdb_read_only_for_models,
    )
    prices = repo.query(
        """
        WITH source_ranked AS (
            SELECT
                security_id AS ticker,
                trade_date AS date,
                COALESCE(adjusted_close, close_price) AS close,
                ROW_NUMBER() OVER (
                    PARTITION BY security_id, trade_date
                    ORDER BY retrieved_at DESC, source DESC
                ) AS source_row
            FROM prices_daily
            WHERE security_id IN (SELECT UNNEST(?))
              AND COALESCE(adjusted_close, close_price) IS NOT NULL
        ),
        raw_daily AS (
            SELECT
                ticker,
                date,
                close,
                close / LAG(close) OVER (PARTITION BY ticker ORDER BY date) - 1.0 AS raw_return
            FROM source_ranked
            WHERE source_row = 1
        ),
        quality_adjusted AS (
            SELECT
                ticker,
                date,
                close,
                raw_return,
                COALESCE(
                    GREATEST(-?, LEAST(?, raw_return)),
                    0.0
                ) AS return,
                COALESCE(ABS(raw_return) > ?, FALSE) AS return_outlier_flag,
                AVG(
                    CASE WHEN ABS(raw_return) <= ? THEN raw_return END
                ) OVER (PARTITION BY ticker) AS full_history_daily_return,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) AS history_row
            FROM raw_daily
        )
        SELECT
            ticker,
            date,
            close,
            return,
            raw_return,
            return_outlier_flag,
            COALESCE(full_history_daily_return, 0.0) AS full_history_daily_return
        FROM quality_adjusted
        WHERE history_row <= ?
        ORDER BY ticker, date
        """,
        [
            list(tickers),
            float(max_abs_daily_return),
            float(max_abs_daily_return),
            float(max_abs_daily_return),
            float(max_abs_daily_return),
            int(lookback_rows),
        ],
    )
    prices["date"] = pd.to_datetime(prices["date"])
    for column in ["close", "return", "raw_return", "full_history_daily_return"]:
        prices[column] = pd.to_numeric(prices[column], errors="coerce")
    prices["return_outlier_flag"] = prices["return_outlier_flag"].fillna(False).astype(bool)
    return prices.dropna(subset=["ticker", "date", "close", "return"])
