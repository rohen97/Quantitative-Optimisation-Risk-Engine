from __future__ import annotations

from itertools import combinations
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
    running_peak = wealth.cummax().clip(lower=1.0)
    return wealth / running_peak - 1.0


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
        current = values.iloc[lag:].to_numpy(dtype=float, copy=True)
        previous = values.iloc[:-lag].to_numpy(dtype=float, copy=True)
        current -= current.mean()
        previous -= previous.mean()
        denominator = float(
            np.sqrt(np.square(current).sum() * np.square(previous).sum())
        )
        autocorrelation = (
            float(np.dot(current, previous) / denominator)
            if denominator > 1e-15
            else np.nan
        )
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
        pre_bank_fee_returns = monthly.get(
            'pre_bank_fee_return',
            monthly['net_return'],
        )
        pre_bank_fee = performance_metrics(
            pre_bank_fee_returns,
            result.initial_capital_usd,
            monthly_cash,
            int(config['backtest']['annual_periods']),
            int(config['statistics']['lo_autocorrelation_lags']),
        )
        transaction_costs = pd.to_numeric(
            monthly.get(
                'transaction_cost_usd',
                pd.Series(0.0, index=monthly.index),
            ),
            errors='coerce',
        ).fillna(0.0)
        bank_fees = pd.to_numeric(
            monthly.get('bank_fee_usd', pd.Series(0.0, index=monthly.index)),
            errors='coerce',
        ).fillna(0.0)
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
                'pre_bank_fee_cagr': pre_bank_fee['cagr'],
                'annualised_transaction_cost_drag': (
                    gross['cagr'] - pre_bank_fee['cagr']
                ),
                'annualised_bank_fee_drag': (
                    pre_bank_fee['cagr'] - metrics['cagr']
                ),
                'annualised_cost_drag': gross['cagr'] - metrics['cagr'],
                'total_transaction_cost_usd': float(transaction_costs.sum()),
                'total_bank_fee_usd': float(bank_fees.sum()),
                'total_modeled_cost_usd': float(transaction_costs.sum() + bank_fees.sum()),
                'ending_value_before_bank_fee_usd': pre_bank_fee['ending_value_usd'],
                'ending_value_bank_fee_drag_usd': (
                    pre_bank_fee['ending_value_usd'] - metrics['ending_value_usd']
                ),
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


def _newey_west_regression(
    dependent: np.ndarray,
    explanatory: np.ndarray,
    lags: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    '''OLS coefficients with a Bartlett-kernel Newey-West covariance matrix.'''
    dependent_values = np.asarray(dependent, dtype=float)
    explanatory_values = np.asarray(explanatory, dtype=float)
    valid = np.isfinite(dependent_values) & np.isfinite(explanatory_values)
    dependent_values = dependent_values[valid]
    explanatory_values = explanatory_values[valid]
    if len(dependent_values) < 3:
        missing = np.full(2, np.nan)
        return missing, missing.copy(), missing.copy(), missing.copy()

    design = np.column_stack([np.ones(len(dependent_values)), explanatory_values])
    inverse_cross_product = np.linalg.pinv(design.T @ design)
    coefficients = inverse_cross_product @ design.T @ dependent_values
    residuals = dependent_values - design @ coefficients
    score = design * residuals[:, None]
    covariance_meat = score.T @ score
    maximum_lag = min(max(int(lags), 0), len(dependent_values) - 1)
    for lag in range(1, maximum_lag + 1):
        weight = 1.0 - lag / (maximum_lag + 1.0)
        lag_covariance = score[lag:].T @ score[:-lag]
        covariance_meat += weight * (lag_covariance + lag_covariance.T)
    degrees_of_freedom = max(len(dependent_values) - design.shape[1], 1)
    covariance = (
        inverse_cross_product
        @ covariance_meat
        @ inverse_cross_product
        * len(dependent_values)
        / degrees_of_freedom
    )
    standard_errors = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    t_statistics = np.divide(
        coefficients,
        standard_errors,
        out=np.full_like(coefficients, np.nan),
        where=standard_errors > 0,
    )
    p_values = 2.0 * norm.sf(np.abs(t_statistics))
    return coefficients, standard_errors, t_statistics, p_values


def _matched_return_matrices(
    strategies: list[ReplayResult],
    benchmarks: list[ReplayResult],
    window_start: pd.Timestamp | None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, ReplayResult]]:
    strategy_map = {result.strategy: result for result in strategies}
    benchmark_map = {result.strategy: result for result in benchmarks}
    eligible_keys = [
        key
        for key in strategy_map
        if f'{key}__regional_index' in benchmark_map
    ]
    if not eligible_keys:
        return pd.DataFrame(), pd.DataFrame(), strategy_map
    strategy_matrix = pd.concat(
        {
            key: strategy_map[key].monthly.set_index('date')['net_return']
            for key in eligible_keys
        },
        axis=1,
    )
    benchmark_matrix = pd.concat(
        {
            key: benchmark_map[f'{key}__regional_index'].monthly.set_index('date')[
                'net_return'
            ]
            for key in eligible_keys
        },
        axis=1,
    )
    if window_start is not None:
        start = pd.Timestamp(window_start)
        strategy_matrix = strategy_matrix.loc[strategy_matrix.index >= start]
        benchmark_matrix = benchmark_matrix.loc[benchmark_matrix.index >= start]
    common_index = strategy_matrix.dropna().index.intersection(
        benchmark_matrix.dropna().index
    )
    return (
        strategy_matrix.loc[common_index, eligible_keys],
        benchmark_matrix.loc[common_index, eligible_keys],
        strategy_map,
    )


def benchmark_alpha_significance(
    strategies: list[ReplayResult],
    benchmarks: list[ReplayResult],
    cash_returns: pd.Series,
    config: dict,
    window_start: pd.Timestamp | None = None,
    window_label: str = 'common_investable_window',
    trailing_months: int | None = None,
) -> pd.DataFrame:
    '''Test matched-benchmark alpha with autocorrelation-robust errors.'''
    strategy_matrix, benchmark_matrix, strategy_map = _matched_return_matrices(
        strategies,
        benchmarks,
        window_start,
    )
    if strategy_matrix.empty:
        return pd.DataFrame()
    if trailing_months is not None:
        strategy_matrix = strategy_matrix.tail(int(trailing_months))
        benchmark_matrix = benchmark_matrix.reindex(strategy_matrix.index)
    monthly_cash = (
        (1.0 + pd.to_numeric(cash_returns, errors='coerce')).resample('ME').prod()
        - 1.0
    ).reindex(strategy_matrix.index).fillna(0.0)
    lags = int(config['statistics']['lo_autocorrelation_lags'])
    rows = []
    for strategy in strategy_matrix:
        strategy_excess = strategy_matrix[strategy] - monthly_cash
        benchmark_excess = benchmark_matrix[strategy] - monthly_cash
        coefficients, standard_errors, t_statistics, p_values = (
            _newey_west_regression(strategy_excess, benchmark_excess, lags)
        )
        evidence_type = strategy_map[strategy].evidence_type
        significant = bool(
            np.isfinite(p_values[0])
            and p_values[0] < float(config['statistics']['familywise_alpha'])
            and coefficients[0] > 0
        )
        point_in_time_types = {'native_live_oos', 'point_in_time_index_challenger'}
        alpha_claim_status = (
            'SUPPORTED'
            if evidence_type in point_in_time_types and significant
            else 'NOT_ESTABLISHED'
            if evidence_type in point_in_time_types
            else 'RETROSPECTIVE_ONLY'
            if 'replay' in evidence_type
            else 'NOT_ESTABLISHED'
        )
        rows.append(
            {
                'window': window_label,
                'strategy': strategy,
                'strategy_label': strategy_map[strategy].label,
                'benchmark': f'{strategy}__regional_index',
                'observations': len(strategy_matrix),
                'annualised_alpha': float(coefficients[0] * 12.0),
                'beta': float(coefficients[1]),
                'annualised_alpha_standard_error': float(
                    standard_errors[0] * 12.0
                ),
                'newey_west_t_statistic': float(t_statistics[0]),
                'two_sided_p_value': float(p_values[0]),
                'newey_west_lags': min(lags, max(len(strategy_matrix) - 1, 0)),
                'positive_alpha_significant_5pct': significant,
                'evidence_type': evidence_type,
                'alpha_claim_status': alpha_claim_status,
            }
        )
    return pd.DataFrame(rows)


def _deduplicate_return_columns(
    matrix: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, str]]:
    unique: list[str] = []
    duplicates: dict[str, str] = {}
    for column in matrix:
        duplicate_of = next(
            (
                candidate
                for candidate in unique
                if np.allclose(
                    matrix[column].to_numpy(dtype=float),
                    matrix[candidate].to_numpy(dtype=float),
                    rtol=1.0e-10,
                    atol=1.0e-13,
                )
            ),
            None,
        )
        if duplicate_of is None:
            unique.append(column)
        else:
            duplicates[column] = duplicate_of
    return matrix[unique], duplicates


def _block_bootstrap_max_t(
    values: np.ndarray,
    samples: int,
    block_months: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    observations, trial_count = values.shape
    standard_deviation = values.std(axis=0, ddof=1)
    observed_t = np.divide(
        np.sqrt(observations) * values.mean(axis=0),
        standard_deviation,
        out=np.full(trial_count, np.nan),
        where=standard_deviation > 0,
    )
    centered = values - values.mean(axis=0)
    indices = moving_block_indices(observations, samples, block_months, seed)
    bootstrap_max_t = np.empty(samples)
    for start in range(0, samples, 256):
        sampled = centered[indices[start : start + 256]]
        sampled_std = sampled.std(axis=1, ddof=1)
        sampled_t = np.divide(
            np.sqrt(observations) * sampled.mean(axis=1),
            sampled_std,
            out=np.full_like(sampled_std, np.nan),
            where=sampled_std > 0,
        )
        bootstrap_max_t[start : start + len(sampled)] = np.nanmax(
            sampled_t,
            axis=1,
        )
    adjusted_p_values = np.array(
        [
            (1.0 + np.sum(bootstrap_max_t >= statistic)) / (samples + 1.0)
            for statistic in observed_t
        ]
    )
    global_p_value = float(
        (1.0 + np.sum(bootstrap_max_t >= np.nanmax(observed_t)))
        / (samples + 1.0)
    )
    return observed_t, adjusted_p_values, global_p_value


def _cscv_diagnostics(
    values: np.ndarray,
    requested_slices: int,
) -> tuple[dict[str, float | int], np.ndarray]:
    observations, trial_count = values.shape
    slice_count = min(int(requested_slices), observations // 2)
    slice_count -= slice_count % 2
    slice_count = max(slice_count, 4)
    slices = np.array_split(np.arange(observations), slice_count)
    overfit_count = 0
    oos_percentiles: list[float] = []
    rank_correlations: list[float] = []
    selected_is_information_ratios: list[float] = []
    selected_oos_information_ratios: list[float] = []
    selection_counts = np.zeros(trial_count, dtype=int)
    split_count = 0
    for selected_slices in combinations(range(slice_count), slice_count // 2):
        selected_set = set(selected_slices)
        in_sample_index = np.concatenate([slices[index] for index in selected_slices])
        out_of_sample_index = np.concatenate(
            [slices[index] for index in range(slice_count) if index not in selected_set]
        )
        in_sample = values[in_sample_index]
        out_of_sample = values[out_of_sample_index]
        in_sample_std = in_sample.std(axis=0, ddof=1)
        out_of_sample_std = out_of_sample.std(axis=0, ddof=1)
        in_sample_score = np.divide(
            in_sample.mean(axis=0),
            in_sample_std,
            out=np.full(trial_count, -np.inf),
            where=in_sample_std > 0,
        )
        out_of_sample_score = np.divide(
            out_of_sample.mean(axis=0),
            out_of_sample_std,
            out=np.full(trial_count, -np.inf),
            where=out_of_sample_std > 0,
        )
        winner = int(np.argmax(in_sample_score))
        rank = int(np.where(np.argsort(out_of_sample_score) == winner)[0][0]) + 1
        percentile = (rank - 0.5) / trial_count
        overfit_count += int(percentile <= 0.5)
        split_count += 1
        oos_percentiles.append(percentile)
        rank_correlations.append(
            float(
                pd.Series(in_sample_score).corr(
                    pd.Series(out_of_sample_score),
                    method='spearman',
                )
            )
        )
        selected_is_information_ratios.append(
            float(in_sample_score[winner] * np.sqrt(12.0))
        )
        selected_oos_information_ratios.append(
            float(out_of_sample_score[winner] * np.sqrt(12.0))
        )
        selection_counts[winner] += 1

    median_is = float(np.median(selected_is_information_ratios))
    median_oos = float(np.median(selected_oos_information_ratios))
    return (
        {
            'cscv_slices': slice_count,
            'cscv_splits': split_count,
            'probability_of_backtest_overfitting': float(
                overfit_count / max(split_count, 1)
            ),
            'median_oos_percentile_of_is_winner': float(
                np.median(oos_percentiles)
            ),
            'median_is_oos_rank_correlation': float(
                np.nanmedian(rank_correlations)
            ),
            'median_selected_is_information_ratio': median_is,
            'median_selected_oos_information_ratio': median_oos,
            'selected_information_ratio_haircut': (
                1.0 - median_oos / median_is if median_is > 0 else np.nan
            ),
        },
        selection_counts,
    )


def strategy_overfitting_diagnostics(
    strategies: list[ReplayResult],
    benchmarks: list[ReplayResult],
    config: dict,
    window_start: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    '''Run a block-bootstrap max-t test and CSCV probability of overfitting.'''
    strategy_matrix, benchmark_matrix, strategy_map = _matched_return_matrices(
        strategies,
        benchmarks,
        window_start,
    )
    if strategy_matrix.empty:
        return pd.DataFrame(), pd.DataFrame()
    active = strategy_matrix - benchmark_matrix
    unique_active, duplicates = _deduplicate_return_columns(active)
    values = unique_active.to_numpy(dtype=float)
    observations, trial_count = values.shape
    if observations < 8 or trial_count < 2:
        return pd.DataFrame(), pd.DataFrame()
    settings = config.get('overfitting', {})
    samples = int(settings.get('bootstrap_samples', config['resampling']['samples']))
    block_months = int(
        settings.get('block_months', config['resampling']['block_months'])
    )
    seed = int(settings.get('random_seed', config['backtest']['random_seed']))
    alpha = float(config['statistics']['familywise_alpha'])
    observed_t, adjusted_p_values, global_p_value = _block_bootstrap_max_t(
        values,
        samples,
        block_months,
        seed,
    )
    cscv, selection_counts = _cscv_diagnostics(
        values,
        int(settings.get('cscv_slices', 12)),
    )
    standard_deviation = values.std(axis=0, ddof=1)
    unique_rows = []
    for position, strategy in enumerate(unique_active):
        tracking_error = float(standard_deviation[position] * np.sqrt(12.0))
        annualised_active_return = float(values[:, position].mean() * 12.0)
        unique_rows.append(
            {
                'strategy': strategy,
                'strategy_label': strategy_map[strategy].label,
                'observations': observations,
                'annualised_active_return': annualised_active_return,
                'information_ratio': (
                    annualised_active_return / tracking_error
                    if tracking_error > 0
                    else np.nan
                ),
                'active_return_t_statistic': float(observed_t[position]),
                'max_t_adjusted_p_value': float(adjusted_p_values[position]),
                'familywise_significant': bool(adjusted_p_values[position] < alpha),
                'cscv_selection_count': int(selection_counts[position]),
                'cscv_selection_frequency': float(
                    selection_counts[position] / max(int(cscv['cscv_splits']), 1)
                ),
                'duplicate_of': '',
                'evidence_type': strategy_map[strategy].evidence_type,
            }
        )
    reality_check = pd.DataFrame(unique_rows)
    for strategy, duplicate_of in duplicates.items():
        source = reality_check.loc[reality_check['strategy'].eq(duplicate_of)].iloc[0]
        duplicate = source.to_dict()
        duplicate.update(
            {
                'strategy': strategy,
                'strategy_label': strategy_map[strategy].label,
                'duplicate_of': duplicate_of,
                'cscv_selection_count': 0,
                'cscv_selection_frequency': 0.0,
                'evidence_type': strategy_map[strategy].evidence_type,
            }
        )
        reality_check = pd.concat(
            [reality_check, pd.DataFrame([duplicate])],
            ignore_index=True,
        )
    reality_check = reality_check.sort_values(
        'information_ratio',
        ascending=False,
        kind='stable',
    ).reset_index(drop=True)

    pbo = float(cscv['probability_of_backtest_overfitting'])
    evidence_types = {result.evidence_type for result in strategy_map.values()}
    retrospective = any('replay' in value for value in evidence_types)
    summary = pd.DataFrame(
        [
            {
                'start_date': strategy_matrix.index.min(),
                'end_date': strategy_matrix.index.max(),
                'observations': observations,
                'raw_trial_count': active.shape[1],
                'unique_trial_count': trial_count,
                'duplicate_paths_removed': '; '.join(
                    f'{key}={value}' for key, value in sorted(duplicates.items())
                ),
                'bootstrap_samples': samples,
                'block_months': block_months,
                'global_reality_check_p_value': global_p_value,
                'global_reality_check_significant': global_p_value < alpha,
                **cscv,
                'selection_overfit_risk': (
                    'LOW' if pbo < 0.25 else 'MODERATE' if pbo < 0.50 else 'HIGH'
                ),
                'alpha_evidence_status': (
                    'RETROSPECTIVE_ONLY' if retrospective else 'STATISTICAL_EVIDENCE'
                ),
                'deployable_alpha_status': (
                    'NOT_ESTABLISHED' if retrospective else 'REVIEW_REQUIRED'
                ),
            }
        ]
    )
    return reality_check, summary


def point_in_time_alpha_significance(
    monthly_returns: pd.DataFrame,
    performance_summary: pd.DataFrame,
    config: dict,
    primary_strategy: str = 'wolf_cvar',
) -> pd.DataFrame:
    '''Compare a dated strategy with its point-in-time eligible-universe controls.'''
    required = {'date', 'strategy', 'net_return'}
    if monthly_returns.empty or not required.issubset(monthly_returns):
        return pd.DataFrame()
    monthly = monthly_returns.copy()
    monthly['date'] = pd.to_datetime(monthly['date'])
    panel = monthly.pivot_table(
        index='date',
        columns='strategy',
        values='net_return',
        aggfunc='last',
    )
    if primary_strategy not in panel:
        return pd.DataFrame()
    benchmark_keys = [column for column in panel if column != primary_strategy]
    if not benchmark_keys:
        return pd.DataFrame()
    alpha = float(config['statistics']['familywise_alpha'])
    sidak_alpha = 1.0 - (1.0 - alpha) ** (1.0 / len(benchmark_keys))
    settings = config.get('overfitting', {})
    minimum_months = int(settings.get('minimum_point_in_time_months', 60))
    lags = min(int(config['statistics']['lo_autocorrelation_lags']), 3)
    summary_lookup = (
        performance_summary.set_index('strategy')
        if not performance_summary.empty and 'strategy' in performance_summary
        else pd.DataFrame()
    )
    rows = []
    for benchmark in benchmark_keys:
        paired = panel[[primary_strategy, benchmark]].dropna()
        if len(paired) < 3:
            continue
        coefficients, standard_errors, t_statistics, p_values = (
            _newey_west_regression(
                paired[primary_strategy].to_numpy(dtype=float),
                paired[benchmark].to_numpy(dtype=float),
                lags,
            )
        )
        active = paired[primary_strategy] - paired[benchmark]
        tracking_error = float(active.std(ddof=1) * np.sqrt(12.0))
        significant = bool(
            coefficients[0] > 0
            and np.isfinite(p_values[0])
            and p_values[0] < sidak_alpha
        )
        primary_cost_drag = (
            float(summary_lookup.loc[primary_strategy, 'annualised_cost_drag'])
            if not summary_lookup.empty
            and primary_strategy in summary_lookup.index
            and 'annualised_cost_drag' in summary_lookup
            else np.nan
        )
        benchmark_cost_drag = (
            float(summary_lookup.loc[benchmark, 'annualised_cost_drag'])
            if not summary_lookup.empty
            and benchmark in summary_lookup.index
            and 'annualised_cost_drag' in summary_lookup
            else np.nan
        )
        evidence_mode = str(
            monthly.get(
                'evidence_mode',
                pd.Series('unknown', index=monthly.index),
            ).iloc[0]
        )
        if coefficients[0] <= 0:
            verdict = 'NO_ALPHA'
        elif len(paired) < minimum_months:
            verdict = 'INSUFFICIENT_HISTORY'
        elif not significant:
            verdict = 'NOT_SIGNIFICANT'
        else:
            verdict = 'SUPPORTED'
        rows.append(
            {
                'strategy': primary_strategy,
                'benchmark': benchmark,
                'observations': len(paired),
                'start_date': paired.index.min(),
                'end_date': paired.index.max(),
                'annualised_active_return': float(active.mean() * 12.0),
                'tracking_error': tracking_error,
                'information_ratio': (
                    float(active.mean() * 12.0 / tracking_error)
                    if tracking_error > 0
                    else np.nan
                ),
                'annualised_regression_alpha': float(coefficients[0] * 12.0),
                'beta': float(coefficients[1]),
                'annualised_alpha_standard_error': float(
                    standard_errors[0] * 12.0
                ),
                'newey_west_t_statistic': float(t_statistics[0]),
                'two_sided_p_value': float(p_values[0]),
                'sidak_per_comparison_alpha': sidak_alpha,
                'positive_alpha_familywise_significant': significant,
                'minimum_required_months': minimum_months,
                'primary_annualised_cost_drag': primary_cost_drag,
                'benchmark_annualised_cost_drag': benchmark_cost_drag,
                'incremental_annualised_cost_drag': (
                    primary_cost_drag - benchmark_cost_drag
                    if np.isfinite(primary_cost_drag)
                    and np.isfinite(benchmark_cost_drag)
                    else np.nan
                ),
                'alpha_evidence_verdict': verdict,
                'evidence_mode': evidence_mode,
                'deployable_alpha_status': (
                    'NOT_ESTABLISHED'
                    if evidence_mode != 'native_live_oos'
                    else verdict
                ),
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
