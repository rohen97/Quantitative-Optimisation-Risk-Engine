from __future__ import annotations

from math import e

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import kurtosis, norm, skew
from sklearn.covariance import LedoitWolf

from src.backtesting.models import ReplayResult


EULER_MASCHERONI = 0.5772156649015329


def drawdown_series(returns: pd.Series) -> pd.Series:
    wealth = (1.0 + pd.to_numeric(returns, errors='coerce')).cumprod()
    return wealth / wealth.cummax() - 1.0


def maximum_drawdown_duration(drawdown: pd.Series) -> int:
    longest = 0
    current = 0
    for value in drawdown.fillna(0.0):
        if value < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def lo_adjusted_sharpe(
    excess_returns: pd.Series,
    periods_per_year: int = 12,
    lags: int = 6,
) -> float:
    values = pd.to_numeric(excess_returns, errors='coerce').dropna()
    if len(values) < 3 or float(values.std(ddof=1)) <= 0:
        return np.nan
    monthly = float(values.mean() / values.std(ddof=1))
    maximum_lag = min(int(lags), len(values) - 2)
    adjustment = 1.0
    for lag in range(1, maximum_lag + 1):
        autocorrelation = float(values.autocorr(lag=lag))
        if np.isfinite(autocorrelation):
            weight = 1.0 - lag / (maximum_lag + 1.0)
            adjustment += 2.0 * weight * autocorrelation
    if adjustment <= 0:
        return np.nan
    return monthly * np.sqrt(periods_per_year / adjustment)


def performance_metrics(
    returns: pd.Series,
    initial_capital: float,
    cash_returns: pd.Series | None = None,
    periods_per_year: int = 12,
    lo_lags: int = 6,
) -> dict:
    values = pd.to_numeric(returns, errors='coerce').dropna()
    if values.empty:
        raise ValueError('Performance metrics require non-empty returns.')
    risk_free = (
        pd.to_numeric(cash_returns, errors='coerce').reindex(values.index).fillna(0.0)
        if cash_returns is not None
        else pd.Series(0.0, index=values.index)
    )
    excess = values - risk_free
    observations = len(values)
    years = observations / periods_per_year
    gross_multiple = float(np.prod(1.0 + values.to_numpy()))
    cagr = gross_multiple ** (1.0 / years) - 1.0 if years > 0 else np.nan
    volatility = float(values.std(ddof=1) * np.sqrt(periods_per_year))
    downside = values.clip(upper=0.0)
    downside_deviation = float(np.sqrt(np.mean(np.square(downside))) * np.sqrt(periods_per_year))
    sharpe = (
        float(excess.mean() / excess.std(ddof=1) * np.sqrt(periods_per_year))
        if float(excess.std(ddof=1)) > 0
        else np.nan
    )
    sortino = (
        float((values.mean() - risk_free.mean()) * periods_per_year / downside_deviation)
        if downside_deviation > 0
        else np.nan
    )
    drawdown = drawdown_series(values)
    maximum_drawdown = float(drawdown.min())
    var_5 = float(values.quantile(0.05))
    tail = values.loc[values.le(var_5)]
    expected_shortfall = float(-tail.mean()) if not tail.empty else float(-var_5)
    moment_dispersion = float(values.std(ddof=0))
    return {
        'start_date': values.index.min(),
        'end_date': values.index.max(),
        'observations': observations,
        'years': years,
        'cumulative_return': gross_multiple - 1.0,
        'cagr': cagr,
        'annualised_arithmetic_return': float(values.mean() * periods_per_year),
        'annualised_volatility': volatility,
        'sharpe': sharpe,
        'lo_adjusted_sharpe': lo_adjusted_sharpe(excess, periods_per_year, lo_lags),
        'sortino': sortino,
        'maximum_drawdown': maximum_drawdown,
        'maximum_drawdown_duration_months': maximum_drawdown_duration(drawdown),
        'calmar': cagr / abs(maximum_drawdown) if maximum_drawdown < 0 else np.nan,
        'monthly_var_5_loss': -var_5,
        'monthly_expected_shortfall_5': expected_shortfall,
        'skewness': (
            float(skew(values, bias=False))
            if len(values) > 2 and moment_dispersion > 1e-12
            else np.nan
        ),
        'pearson_kurtosis': (
            float(kurtosis(values, fisher=False, bias=False))
            if len(values) > 3 and moment_dispersion > 1e-12
            else np.nan
        ),
        'positive_month_ratio': float(values.gt(0).mean()),
        'worst_month': float(values.min()),
        'best_month': float(values.max()),
        'ending_value_usd': initial_capital * gross_multiple,
        'pnl_usd': initial_capital * (gross_multiple - 1.0),
    }


def performance_summary(
    results: list[ReplayResult],
    cash_returns: pd.Series,
    config: dict,
    window_start: pd.Timestamp | None = None,
    window_label: str = 'requested_1997_window',
) -> pd.DataFrame:
    monthly_cash = (1.0 + cash_returns).resample('ME').prod() - 1.0
    rows = []
    for result in results:
        monthly = result.monthly.set_index('date').sort_index()
        if window_start is not None:
            monthly = monthly.loc[monthly.index >= pd.Timestamp(window_start)]
        if monthly.empty:
            continue
        metrics = performance_metrics(
            monthly['net_return'],
            result.initial_capital_usd,
            monthly_cash,
            int(config['backtest']['annual_periods']),
            int(config['statistics']['lo_autocorrelation_lags']),
        )
        gross = performance_metrics(
            monthly['gross_return'],
            result.initial_capital_usd,
            monthly_cash,
            int(config['backtest']['annual_periods']),
            int(config['statistics']['lo_autocorrelation_lags']),
        )
        rows.append(
            {
                'strategy': result.strategy,
                'strategy_label': result.label,
                'window': window_label,
                'initial_capital_usd': result.initial_capital_usd,
                'capital_source': result.capital_source,
                'evidence_type': result.evidence_type,
                'full_investment_start': result.full_investment_start,
                **metrics,
                'gross_cagr': gross['cagr'],
                'annualised_cost_drag': gross['cagr'] - metrics['cagr'],
                'total_transaction_cost_usd': float(monthly['transaction_cost_usd'].sum()),
                'annualised_turnover': float(monthly['turnover'].mean() * 12.0),
                'average_live_weight': float(monthly['live_weight'].mean()),
                'minimum_live_weight': float(monthly['live_weight'].min()),
                'liquidity_breach_count': int(monthly['liquidity_breaches'].sum()),
                'maximum_adv_participation': float(monthly['maximum_adv_participation'].max()),
            }
        )
    return pd.DataFrame(rows)


def probabilistic_sharpe_ratio(
    observed_sharpe: float,
    hurdle: float,
    observations: int,
    sample_skewness: float,
    pearson_kurtosis: float,
) -> float:
    denominator = 1.0 - sample_skewness * observed_sharpe
    denominator += (pearson_kurtosis - 1.0) * observed_sharpe**2 / 4.0
    if observations < 2 or denominator <= 0:
        return np.nan
    statistic = (observed_sharpe - hurdle) * np.sqrt(observations - 1.0)
    statistic /= np.sqrt(denominator)
    return float(norm.cdf(statistic))


def minimum_track_record_length(
    observed_sharpe: float,
    hurdle: float,
    sample_skewness: float,
    pearson_kurtosis: float,
    confidence: float = 0.95,
) -> float:
    gap = observed_sharpe - hurdle
    if gap <= 0:
        return np.inf
    adjustment = 1.0 - sample_skewness * observed_sharpe
    adjustment += (pearson_kurtosis - 1.0) * observed_sharpe**2 / 4.0
    return float(1.0 + adjustment * (norm.ppf(confidence) / gap) ** 2)


def expected_maximum_sharpe(sharpe_variance: float, trials: int) -> float:
    if trials <= 1 or sharpe_variance <= 0:
        return 0.0
    scale = np.sqrt(sharpe_variance)
    first = (1.0 - EULER_MASCHERONI) * norm.ppf(1.0 - 1.0 / trials)
    second = EULER_MASCHERONI * norm.ppf(1.0 - 1.0 / (trials * e))
    return float(scale * (first + second))


def _effective_trial_clusters(returns: pd.DataFrame, threshold: float) -> int:
    if returns.shape[1] <= 1:
        return 1
    correlation = returns.corr().fillna(0.0).clip(-1.0, 1.0)
    correlation_values = correlation.to_numpy(copy=True)
    np.fill_diagonal(correlation_values, 1.0)
    distance = np.sqrt(np.maximum((1.0 - correlation_values) / 2.0, 0.0))
    tree = linkage(squareform(distance, checks=False), method='average')
    distance_threshold = np.sqrt(max((1.0 - threshold) / 2.0, 0.0))
    clusters = fcluster(tree, t=distance_threshold, criterion='distance')
    return int(len(np.unique(clusters)))


def statistical_significance(
    results: list[ReplayResult],
    cash_returns: pd.Series,
    config: dict,
) -> pd.DataFrame:
    matrix = pd.concat(
        {
            result.strategy: result.monthly.set_index('date')['net_return']
            for result in results
        },
        axis=1,
    ).dropna()
    monthly_cash = ((1.0 + cash_returns).resample('ME').prod() - 1.0).reindex(matrix.index).fillna(0.0)
    excess = matrix.sub(monthly_cash, axis=0)
    monthly_sharpes = excess.mean() / excess.std(ddof=1)
    trial_count = len(monthly_sharpes)
    effective_trials = _effective_trial_clusters(
        matrix,
        float(config['statistics']['correlation_cluster_threshold']),
    )
    sharpe_variance = float(monthly_sharpes.var(ddof=1)) if trial_count > 1 else 0.0
    actual_hurdle = expected_maximum_sharpe(sharpe_variance, trial_count)
    clustered_hurdle = expected_maximum_sharpe(sharpe_variance, effective_trials)
    alpha = float(config['statistics']['familywise_alpha'])
    sidak_alpha = 1.0 - (1.0 - alpha) ** (1.0 / max(trial_count, 1))
    configured_hurdle = float(config['statistics']['sharpe_hurdle']) / np.sqrt(12.0)
    rows = []
    for strategy in matrix:
        values = excess[strategy].dropna()
        observed = float(values.mean() / values.std(ddof=1))
        sample_skewness = float(skew(values, bias=False))
        sample_kurtosis = float(kurtosis(values, fisher=False, bias=False))
        psr = probabilistic_sharpe_ratio(
            observed,
            configured_hurdle,
            len(values),
            sample_skewness,
            sample_kurtosis,
        )
        dsr_actual = probabilistic_sharpe_ratio(
            observed,
            actual_hurdle,
            len(values),
            sample_skewness,
            sample_kurtosis,
        )
        dsr_clustered = probabilistic_sharpe_ratio(
            observed,
            clustered_hurdle,
            len(values),
            sample_skewness,
            sample_kurtosis,
        )
        track_record = minimum_track_record_length(
            observed,
            configured_hurdle,
            sample_skewness,
            sample_kurtosis,
            1.0 - alpha,
        )
        p_value = 1.0 - psr if np.isfinite(psr) else np.nan
        rows.append(
            {
                'strategy': strategy,
                'observations': len(values),
                'annualised_sharpe': observed * np.sqrt(12.0),
                'probabilistic_sharpe_ratio': psr,
                'minimum_track_record_months': track_record,
                'track_record_sufficient': bool(len(values) >= track_record),
                'one_sided_p_value': p_value,
                'familywise_method': 'Sidak',
                'familywise_alpha': alpha,
                'sidak_per_trial_alpha': sidak_alpha,
                'sidak_significant': bool(np.isfinite(p_value) and p_value < sidak_alpha),
                'trial_count': trial_count,
                'effective_clustered_trials': effective_trials,
                'expected_maximum_monthly_sharpe': actual_hurdle,
                'clustered_expected_maximum_monthly_sharpe': clustered_hurdle,
                'deflated_sharpe_ratio': dsr_actual,
                'cluster_adjusted_deflated_sharpe_ratio': dsr_clustered,
            }
        )
    return pd.DataFrame(rows)


def benchmark_relative_summary(
    strategies: list[ReplayResult],
    benchmarks: list[ReplayResult],
    window_start: pd.Timestamp | None = None,
    window_label: str = 'requested_1997_window',
) -> pd.DataFrame:
    benchmark_map = {result.strategy: result for result in benchmarks}
    rows = []
    for strategy in strategies:
        benchmark_key = f'{strategy.strategy}__regional_index'
        if benchmark_key not in benchmark_map:
            continue
        benchmark = benchmark_map[benchmark_key]
        strategy_returns = strategy.monthly.set_index('date')['net_return']
        benchmark_returns = benchmark.monthly.set_index('date')['net_return']
        aligned = pd.concat(
            [strategy_returns.rename('strategy'), benchmark_returns.rename('benchmark')],
            axis=1,
        ).dropna()
        if window_start is not None:
            aligned = aligned.loc[aligned.index >= pd.Timestamp(window_start)]
        if aligned.empty:
            continue
        active = aligned['strategy'] - aligned['benchmark']
        variance = float(aligned['benchmark'].var(ddof=1))
        beta = (
            float(aligned['strategy'].cov(aligned['benchmark']) / variance)
            if variance > 0
            else np.nan
        )
        alpha = float((aligned['strategy'].mean() - beta * aligned['benchmark'].mean()) * 12.0)
        tracking_error = float(active.std(ddof=1) * np.sqrt(12.0))
        information_ratio = (
            float(active.mean() * 12.0 / tracking_error)
            if tracking_error > 0
            else np.nan
        )
        upside = aligned.loc[aligned['benchmark'].gt(0)]
        downside = aligned.loc[aligned['benchmark'].lt(0)]
        strategy_multiple = float((1.0 + aligned['strategy']).prod())
        benchmark_multiple = float((1.0 + aligned['benchmark']).prod())
        rows.append(
            {
                'window': window_label,
                'strategy': strategy.strategy,
                'strategy_label': strategy.label,
                'benchmark': benchmark.strategy,
                'benchmark_label': benchmark.label,
                'observations': len(aligned),
                'annualised_alpha': alpha,
                'beta': beta,
                'tracking_error': tracking_error,
                'information_ratio': information_ratio,
                'active_return_cumulative': strategy_multiple / benchmark_multiple - 1.0,
                'outperformance_month_ratio': float(active.gt(0).mean()),
                'upside_capture': (
                    float(upside['strategy'].mean() / upside['benchmark'].mean())
                    if not upside.empty and upside['benchmark'].mean() != 0
                    else np.nan
                ),
                'downside_capture': (
                    float(downside['strategy'].mean() / downside['benchmark'].mean())
                    if not downside.empty and downside['benchmark'].mean() != 0
                    else np.nan
                ),
                'strategy_ending_value_usd': strategy.initial_capital_usd * strategy_multiple,
                'benchmark_ending_value_usd': strategy.initial_capital_usd * benchmark_multiple,
                'relative_pnl_usd': strategy.initial_capital_usd * (strategy_multiple - benchmark_multiple),
            }
        )
    return pd.DataFrame(rows)


def embargo_comparison(
    results: list[ReplayResult],
    cash_returns: pd.Series,
    config: dict,
) -> pd.DataFrame:
    months = int(config['backtest']['embargo_months'])
    monthly_cash = (1.0 + cash_returns).resample('ME').prod() - 1.0
    rows = []
    for result in results:
        values = result.monthly.set_index('date')['net_return'].sort_index()
        if len(values) <= months:
            continue
        split = values.index[-months]
        for period, sample in (
            ('development', values.loc[values.index < split]),
            ('untouched_embargo', values.loc[values.index >= split]),
        ):
            metrics = performance_metrics(
                sample,
                result.initial_capital_usd,
                monthly_cash,
                int(config['backtest']['annual_periods']),
                int(config['statistics']['lo_autocorrelation_lags']),
            )
            rows.append(
                {
                    'strategy': result.strategy,
                    'period': period,
                    'embargo_start': split,
                    **metrics,
                }
            )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    pivot = frame.pivot(index='strategy', columns='period', values='sharpe')
    deterioration = (
        pivot.get('untouched_embargo', pd.Series(dtype=float))
        - pivot.get('development', pd.Series(dtype=float))
    ).rename('embargo_sharpe_change')
    return frame.merge(deterioration, on='strategy', how='left')


def annual_return_table(results: list[ReplayResult]) -> pd.DataFrame:
    rows = []
    for result in results:
        monthly = result.monthly.set_index('date')['net_return'].sort_index()
        annual = (1.0 + monthly).groupby(monthly.index.year).prod() - 1.0
        rows.extend(
            {'strategy': result.strategy, 'year': int(year), 'return': value}
            for year, value in annual.items()
        )
    return pd.DataFrame(rows)


def moving_block_indices(
    observations: int,
    samples: int,
    block_size: int,
    seed: int,
) -> np.ndarray:
    if observations < 1:
        raise ValueError('Block resampling requires observations.')
    block = max(1, min(int(block_size), observations))
    blocks = int(np.ceil(observations / block))
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, observations, size=(samples, blocks))
    offsets = np.arange(block)
    indices = (starts[:, :, None] + offsets[None, None, :]) % observations
    return indices.reshape(samples, -1)[:, :observations]


def _sample_path_metrics(sampled: np.ndarray) -> dict[str, np.ndarray]:
    clipped = np.clip(sampled, -0.999999, None)
    observations = clipped.shape[1]
    log_multiple = np.log1p(clipped).sum(axis=1)
    ending_multiple = np.exp(log_multiple)
    cagr = np.exp(log_multiple * 12.0 / observations) - 1.0
    volatility = clipped.std(axis=1, ddof=1) * np.sqrt(12.0)
    sharpe = np.divide(
        clipped.mean(axis=1) * 12.0,
        volatility,
        out=np.full(clipped.shape[0], np.nan),
        where=volatility > 0,
    )
    wealth = np.cumprod(1.0 + clipped, axis=1)
    peaks = np.maximum.accumulate(wealth, axis=1)
    maximum_drawdown = np.min(wealth / peaks - 1.0, axis=1)
    return {
        'ending_multiple': ending_multiple,
        'cagr': cagr,
        'sharpe': sharpe,
        'maximum_drawdown': maximum_drawdown,
    }


def block_resampling(
    results: list[ReplayResult],
    benchmarks: list[ReplayResult],
    config: dict,
    selected_strategies: set[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected = selected_strategies or {
        'final_portfolio',
        'clean_sheet',
        'llm_benchmark',
        'trend_risk_controlled_indices',
    }
    matrix = pd.concat(
        {
            result.strategy: result.monthly.set_index('date')['net_return']
            for result in results
        },
        axis=1,
    ).dropna()
    benchmark_matrix = pd.concat(
        {
            result.strategy: result.monthly.set_index('date')['net_return']
            for result in benchmarks
        },
        axis=1,
    ).reindex(matrix.index)
    settings = config['resampling']
    indices = moving_block_indices(
        len(matrix),
        int(settings['samples']),
        int(settings['block_months']),
        int(config['backtest']['random_seed']),
    )
    result_lookup = {result.strategy: result for result in results}
    rows = []
    distributions = []
    for strategy in matrix:
        sampled = matrix[strategy].to_numpy()[indices]
        metrics = _sample_path_metrics(sampled)
        benchmark_key = (
            'equal_weight_regional_indices'
            if strategy == 'trend_risk_controlled_indices'
            else f'{strategy}__regional_index'
        )
        probability_outperform = np.nan
        if benchmark_key in benchmark_matrix:
            benchmark_sampled = benchmark_matrix[benchmark_key].to_numpy()[indices]
            benchmark_multiple = np.prod(1.0 + benchmark_sampled, axis=1)
            probability_outperform = float(
                np.mean(metrics['ending_multiple'] > benchmark_multiple)
            )
        capital = result_lookup[strategy].initial_capital_usd
        rows.append(
            {
                'strategy': strategy,
                'method': 'circular_moving_block_bootstrap',
                'samples': len(indices),
                'block_months': int(settings['block_months']),
                'cagr_p05': float(np.quantile(metrics['cagr'], 0.05)),
                'cagr_median': float(np.quantile(metrics['cagr'], 0.50)),
                'cagr_p95': float(np.quantile(metrics['cagr'], 0.95)),
                'sharpe_p05': float(np.nanquantile(metrics['sharpe'], 0.05)),
                'sharpe_median': float(np.nanquantile(metrics['sharpe'], 0.50)),
                'sharpe_p95': float(np.nanquantile(metrics['sharpe'], 0.95)),
                'maximum_drawdown_p05': float(np.quantile(metrics['maximum_drawdown'], 0.05)),
                'maximum_drawdown_median': float(np.quantile(metrics['maximum_drawdown'], 0.50)),
                'ending_value_p05_usd': float(capital * np.quantile(metrics['ending_multiple'], 0.05)),
                'ending_value_median_usd': float(capital * np.quantile(metrics['ending_multiple'], 0.50)),
                'ending_value_p95_usd': float(capital * np.quantile(metrics['ending_multiple'], 0.95)),
                'probability_of_loss': float(np.mean(metrics['ending_multiple'] < 1.0)),
                'probability_outperform_regional_benchmark': probability_outperform,
            }
        )
        if strategy in selected:
            distributions.append(
                pd.DataFrame(
                    {
                        'strategy': strategy,
                        'sample': np.arange(len(indices)),
                        'cagr': metrics['cagr'],
                        'sharpe': metrics['sharpe'],
                        'maximum_drawdown': metrics['maximum_drawdown'],
                        'ending_value_usd': capital * metrics['ending_multiple'],
                    }
                )
            )
    distribution = pd.concat(distributions, ignore_index=True) if distributions else pd.DataFrame()
    return pd.DataFrame(rows), distribution


def monte_carlo_simulation(
    results: list[ReplayResult],
    config: dict,
    selected_strategies: set[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    selected = selected_strategies or {
        'final_portfolio',
        'clean_sheet',
        'llm_benchmark',
        'trend_risk_controlled_indices',
    }
    matrix = pd.concat(
        {
            result.strategy: result.monthly.set_index('date')['net_return']
            for result in results
        },
        axis=1,
    ).dropna()
    values = matrix.to_numpy(dtype=float)
    mean = values.mean(axis=0)
    lagged = values[:-1] - mean
    current = values[1:] - mean
    denominator = np.square(lagged).sum(axis=0)
    phi = np.divide(
        (lagged * current).sum(axis=0),
        denominator,
        out=np.zeros_like(mean),
        where=denominator > 0,
    ).clip(-0.30, 0.30)
    residuals = current - lagged * phi
    residual_scale = residuals.std(axis=0, ddof=1)
    residual_scale = np.where(residual_scale > 1e-8, residual_scale, 1e-8)
    standardised = residuals / residual_scale
    covariance = LedoitWolf().fit(standardised).covariance_
    diagonal = np.sqrt(np.diag(covariance))
    correlation = covariance / np.outer(diagonal, diagonal)
    correlation = np.nan_to_num(correlation, nan=0.0)
    np.fill_diagonal(correlation, 1.0)
    eigenvalues, eigenvectors = np.linalg.eigh(correlation)
    correlation = eigenvectors @ np.diag(np.clip(eigenvalues, 1e-8, None)) @ eigenvectors.T
    diagonal = np.sqrt(np.diag(correlation))
    correlation /= np.outer(diagonal, diagonal)
    cholesky = np.linalg.cholesky(correlation + np.eye(len(mean)) * 1e-10)

    excess_kurtosis = np.nanmedian(kurtosis(standardised, fisher=True, bias=False, axis=0))
    settings = config['monte_carlo']
    if np.isfinite(excess_kurtosis) and excess_kurtosis > 0:
        degrees_of_freedom = 6.0 / excess_kurtosis + 4.0
    else:
        degrees_of_freedom = float(settings['maximum_degrees_of_freedom'])
    degrees_of_freedom = float(
        np.clip(
            degrees_of_freedom,
            float(settings['minimum_degrees_of_freedom']),
            float(settings['maximum_degrees_of_freedom']),
        )
    )

    paths = int(settings['paths'])
    horizon = int(settings['horizon_months']) or len(matrix)
    persistence = float(settings['ewma_lambda'])
    rng = np.random.default_rng(int(config['backtest']['random_seed']) + 1)
    state = np.tile(values[-1], (paths, 1))
    conditional_variance = np.tile(np.square(residual_scale), (paths, 1))
    baseline_variance = np.square(residual_scale)
    wealth = np.ones((paths, len(mean)))
    peak = np.ones_like(wealth)
    maximum_drawdown = np.zeros_like(wealth)
    return_sum = np.zeros_like(wealth)
    return_square_sum = np.zeros_like(wealth)
    for _ in range(horizon):
        gaussian = rng.standard_normal((paths, len(mean))) @ cholesky.T
        chi_square = rng.chisquare(degrees_of_freedom, size=paths)
        student_scale = np.sqrt(
            (degrees_of_freedom - 2.0) / np.maximum(chi_square, 1e-12)
        )
        shock = gaussian * np.sqrt(conditional_variance) * student_scale[:, None]
        simulated = mean + phi * (state - mean) + shock
        simulated = np.clip(simulated, -0.95, 2.0)
        wealth *= 1.0 + simulated
        peak = np.maximum(peak, wealth)
        maximum_drawdown = np.minimum(maximum_drawdown, wealth / peak - 1.0)
        return_sum += simulated
        return_square_sum += np.square(simulated)
        state = simulated
        conditional_variance = persistence * conditional_variance
        conditional_variance += (1.0 - persistence) * np.square(shock)
        conditional_variance = np.clip(
            conditional_variance,
            baseline_variance * 0.05,
            baseline_variance * 25.0,
        )

    average = return_sum / horizon
    variance = np.maximum(return_square_sum / horizon - np.square(average), 0.0)
    annualised_volatility = np.sqrt(variance * 12.0)
    sharpe = np.divide(
        average * 12.0,
        annualised_volatility,
        out=np.full_like(average, np.nan),
        where=annualised_volatility > 0,
    )
    cagr = np.power(wealth, 12.0 / horizon) - 1.0
    lookup = {result.strategy: result for result in results}
    rows = []
    distributions = []
    for column, strategy in enumerate(matrix.columns):
        capital = lookup[strategy].initial_capital_usd
        rows.append(
            {
                'strategy': strategy,
                'method': 'correlated_student_t_ar1_ewma',
                'paths': paths,
                'horizon_months': horizon,
                'degrees_of_freedom': degrees_of_freedom,
                'cagr_p05': float(np.quantile(cagr[:, column], 0.05)),
                'cagr_median': float(np.quantile(cagr[:, column], 0.50)),
                'cagr_p95': float(np.quantile(cagr[:, column], 0.95)),
                'sharpe_p05': float(np.nanquantile(sharpe[:, column], 0.05)),
                'sharpe_median': float(np.nanquantile(sharpe[:, column], 0.50)),
                'sharpe_p95': float(np.nanquantile(sharpe[:, column], 0.95)),
                'maximum_drawdown_p05': float(np.quantile(maximum_drawdown[:, column], 0.05)),
                'maximum_drawdown_median': float(np.quantile(maximum_drawdown[:, column], 0.50)),
                'ending_value_p05_usd': float(capital * np.quantile(wealth[:, column], 0.05)),
                'ending_value_median_usd': float(capital * np.quantile(wealth[:, column], 0.50)),
                'ending_value_p95_usd': float(capital * np.quantile(wealth[:, column], 0.95)),
                'probability_of_loss': float(np.mean(wealth[:, column] < 1.0)),
            }
        )
        if strategy in selected:
            distributions.append(
                pd.DataFrame(
                    {
                        'strategy': strategy,
                        'path': np.arange(paths),
                        'cagr': cagr[:, column],
                        'sharpe': sharpe[:, column],
                        'maximum_drawdown': maximum_drawdown[:, column],
                        'ending_value_usd': capital * wealth[:, column],
                    }
                )
            )
    diagnostics = pd.DataFrame(
        {
            'strategy': matrix.columns,
            'monthly_mean': mean,
            'ar1_coefficient': phi,
            'residual_volatility': residual_scale,
            'residual_skewness': skew(standardised, bias=False, axis=0),
            'residual_pearson_kurtosis': kurtosis(
                standardised,
                fisher=False,
                bias=False,
                axis=0,
            ),
            'student_t_degrees_of_freedom': degrees_of_freedom,
        }
    )
    distribution = pd.concat(distributions, ignore_index=True) if distributions else pd.DataFrame()
    return pd.DataFrame(rows), distribution, diagnostics
