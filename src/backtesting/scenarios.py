from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtesting.models import MarketDataBundle, ReplayResult
from src.backtesting.statistics import performance_metrics


def event_definitions(config: dict) -> pd.DataFrame:
    events = pd.DataFrame(config.get('macro_events', []))
    if events.empty:
        return events
    events = events.copy()
    events['start_date'] = pd.to_datetime(events['start_date'])
    events['end_date'] = pd.to_datetime(events['end_date'])
    if events['event_id'].duplicated().any():
        raise ValueError('macro_events event_id values must be unique.')
    if events['end_date'].lt(events['start_date']).any():
        raise ValueError('macro_events end dates must not precede start dates.')
    events['window_days'] = (events['end_date'] - events['start_date']).dt.days + 1
    return events.sort_values('start_date').reset_index(drop=True)


def _monthly_last(values: pd.Series, calendar: pd.DatetimeIndex) -> pd.Series:
    numeric = pd.to_numeric(values, errors='coerce').sort_index()
    return numeric.resample('ME').last().reindex(calendar)


def build_monthly_regimes(
    bundle: MarketDataBundle,
    config: dict,
) -> pd.DataFrame:
    settings = config['macro_regimes']
    benchmark_symbol = settings['market_benchmark_symbol']
    benchmark = pd.to_numeric(
        bundle.benchmark_prices_usd[benchmark_symbol],
        errors='coerce',
    ).sort_index()
    benchmark_monthly = benchmark.resample('ME').last()
    calendar = benchmark_monthly.index

    rate_series = settings['rate_series']
    recession_series = settings['recession_series']
    if rate_series not in bundle.macro_series:
        raise ValueError(f'Missing macro regime series: {rate_series}.')
    if recession_series not in bundle.macro_series:
        raise ValueError(f'Missing macro regime series: {recession_series}.')

    observed_rate = _monthly_last(bundle.macro_series[rate_series], calendar)
    observed_recession = _monthly_last(
        bundle.macro_series[recession_series],
        calendar,
    )
    rate = observed_rate.shift(1)
    recession = observed_recession.shift(1)
    direction_lookback = int(settings['rate_direction_lookback_months'])
    rate_change = observed_rate.shift(1) - observed_rate.shift(direction_lookback + 1)
    direction_threshold = float(settings['rate_direction_threshold_pp'])

    rate_level = pd.cut(
        rate,
        bins=[
            -np.inf,
            float(settings['low_rate_upper_pct']),
            float(settings['high_rate_lower_pct']),
            np.inf,
        ],
        labels=['Low (<2%)', 'Moderate (2-4%)', 'High (>=4%)'],
        right=False,
    ).astype('object')
    rate_direction = pd.Series(
        np.select(
            [
                rate_change.gt(direction_threshold),
                rate_change.lt(-direction_threshold),
            ],
            ['Rising', 'Falling'],
            default='Stable',
        ),
        index=calendar,
        dtype='object',
    )
    rate_level.loc[rate.isna()] = 'Unavailable'
    rate_direction.loc[rate_change.isna()] = 'Unavailable'

    market_returns = benchmark_monthly.pct_change(fill_method=None)
    momentum = benchmark_monthly.pct_change(
        int(settings['market_momentum_lookback_months']),
        fill_method=None,
    ).shift(1)
    volatility = (
        market_returns.rolling(
            int(settings['market_volatility_lookback_months']),
            min_periods=int(settings['market_volatility_lookback_months']),
        ).std()
        * np.sqrt(12.0)
    ).shift(1)
    market_regime = pd.Series(
        np.where(momentum.ge(0.0), 'Bull', 'Bear')
        + np.where(
            volatility.ge(float(settings['market_high_volatility'])),
            ' / Volatile',
            ' / Calm',
        ),
        index=calendar,
        dtype='object',
    )
    market_regime.loc[momentum.isna() | volatility.isna()] = 'Unavailable'
    economic_cycle = pd.Series(
        np.where(recession.ge(0.5), 'Recession', 'Expansion'),
        index=calendar,
        dtype='object',
    )
    economic_cycle.loc[recession.isna()] = 'Unavailable'

    return pd.DataFrame(
        {
            'date': calendar,
            'rate_pct': rate.to_numpy(),
            'rate_level': rate_level.to_numpy(),
            'rate_change_12m_pp': rate_change.to_numpy(),
            'rate_direction': rate_direction.to_numpy(),
            'market_trailing_return_12m': momentum.to_numpy(),
            'market_volatility_6m': volatility.to_numpy(),
            'market_regime': market_regime.to_numpy(),
            'economic_cycle': economic_cycle.to_numpy(),
        }
    )


def conditional_performance(
    results: list[ReplayResult],
    regimes: pd.DataFrame,
    cash_returns: pd.Series,
    config: dict,
    dimension: str,
) -> pd.DataFrame:
    if dimension not in regimes:
        raise ValueError(f'Unknown regime dimension: {dimension}.')
    monthly_cash = (1.0 + cash_returns).resample('ME').prod() - 1.0
    regime_values = regimes.set_index('date')[dimension]
    rows = []
    for result in results:
        monthly = result.monthly.set_index('date').sort_index()
        labels = regime_values.reindex(monthly.index)
        available = labels.notna() & labels.ne('Unavailable')
        total = int(available.sum())
        for environment, sample in monthly.loc[available].groupby(labels.loc[available]):
            returns = sample['net_return']
            metrics = performance_metrics(
                returns,
                result.initial_capital_usd,
                monthly_cash,
                int(config['backtest']['annual_periods']),
                int(config['statistics']['lo_autocorrelation_lags']),
            )
            rows.append(
                {
                    'dimension': dimension,
                    'environment': environment,
                    'strategy': result.strategy,
                    'strategy_label': result.label,
                    'evidence_type': result.evidence_type,
                    'observations': len(sample),
                    'environment_share': len(sample) / total if total else np.nan,
                    'cumulative_conditional_return': metrics['cumulative_return'],
                    'annualised_arithmetic_return': metrics['annualised_arithmetic_return'],
                    'annualised_geometric_return': metrics['cagr'],
                    'annualised_volatility': metrics['annualised_volatility'],
                    'sharpe': metrics['sharpe'],
                    'lo_adjusted_sharpe': metrics['lo_adjusted_sharpe'],
                    'sortino': metrics['sortino'],
                    'maximum_drawdown': metrics['maximum_drawdown'],
                    'positive_month_ratio': metrics['positive_month_ratio'],
                    'worst_month': metrics['worst_month'],
                }
            )
    return pd.DataFrame(rows)


def macro_event_performance(
    results: list[ReplayResult],
    events: pd.DataFrame,
    cash_returns: pd.Series,
    config: dict,
) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    monthly_cash = (1.0 + cash_returns).resample('ME').prod() - 1.0
    rows = []
    for event in events.itertuples(index=False):
        for result in results:
            monthly = result.monthly.copy()
            monthly['date'] = pd.to_datetime(monthly['date'])
            monthly['period_start'] = pd.to_datetime(monthly['period_start'])
            sample = monthly.loc[
                monthly['period_start'].le(event.end_date)
                & monthly['date'].ge(event.start_date)
            ].set_index('date')
            if sample.empty:
                continue
            returns = sample['net_return']
            metrics = performance_metrics(
                returns,
                result.initial_capital_usd,
                monthly_cash,
                int(config['backtest']['annual_periods']),
                int(config['statistics']['lo_autocorrelation_lags']),
            )
            first_return = float(returns.iloc[0])
            first_end_value = float(sample['net_value_usd'].iloc[0])
            event_start_aum = (
                first_end_value / (1.0 + first_return)
                if first_return > -1.0
                else np.nan
            )
            rows.append(
                {
                    'event_id': event.event_id,
                    'event_label': event.label,
                    'event_category': event.category,
                    'event_start': event.start_date,
                    'event_end': event.end_date,
                    'source_url': event.source_url,
                    'strategy': result.strategy,
                    'strategy_label': result.label,
                    'evidence_type': result.evidence_type,
                    'observations': len(sample),
                    'first_observation': sample.index.min(),
                    'last_observation': sample.index.max(),
                    'cumulative_return': metrics['cumulative_return'],
                    'annualised_volatility': metrics['annualised_volatility'],
                    'sharpe': metrics['sharpe'],
                    'maximum_drawdown': metrics['maximum_drawdown'],
                    'worst_month': metrics['worst_month'],
                    'event_start_aum_usd': event_start_aum,
                    'event_pnl_usd': event_start_aum * metrics['cumulative_return'],
                    'pnl_on_assigned_capital_usd': (
                        result.initial_capital_usd * metrics['cumulative_return']
                    ),
                }
            )
    return pd.DataFrame(rows)
