from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Mapping, Sequence
import warnings

import joblib
import numpy as np
import pandas as pd
from scipy.stats import binomtest, spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    ExtraTreesRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import ElasticNet, LinearRegression, Ridge, SGDRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


LOGGER = logging.getLogger(__name__)
ARTIFACT_VERSION = 5

DEFAULT_NUMERIC_FEATURES = (
    'revenue_growth',
    'ebitda_margin',
    'net_income_margin',
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
    'dividend_yield',
    'dividend_growth_3y',
    'dividend_growth_5y',
    'payout_ratio',
    'positive_fcf_years_5',
    'cash_flow_quality_score',
    'balance_sheet_strength_score',
    'earnings_stability_score',
    'fcf_dividend_cover',
    'dividend_stability_score',
    'dividend_safety_score',
    'valuation_score',
    'valuation_percentile',
    'volatility_1y',
    'downside_volatility',
    'beta_local_market',
    'beta_global_market',
    'max_drawdown_1y',
    'var_5',
    'cvar_5',
    'momentum_6m',
    'sharpe_proxy',
    'sortino_proxy',
    'risk_score',
    'liquidity_score',
    'liquidity_stress_score',
    'average_daily_value_usd',
    'market_cap_usd',
    'fundamentals_period_count',
    'fundamentals_coverage_ratio',
)

DEFAULT_CATEGORICAL_FEATURES = ('region', 'sector', 'country', 'currency')
RANK_FEATURES = (
    'revenue_growth',
    'free_cash_flow_yield',
    'net_debt_to_ebitda',
    'interest_coverage',
    'roe',
    'roic',
    'pe_ratio',
    'pb_ratio',
    'ev_ebitda',
    'dividend_yield',
    'cash_flow_quality_score',
    'balance_sheet_strength_score',
    'dividend_safety_score',
    'valuation_score',
    'volatility_1y',
    'beta_local_market',
    'max_drawdown_1y',
    'momentum_6m',
    'liquidity_score',
    'average_daily_value_usd',
    'market_cap_usd',
)


@dataclass(frozen=True)
class SupervisedAlphaSettings:
    output_directory: Path = Path('reports/outputs/supervised_alpha')
    model_directory: Path = Path('data/processed/supervised_alpha')
    checkpoint_directory: Path = Path('data/interim/supervised_alpha_checkpoints')
    resume_checkpoints: bool = True
    horizons_months: tuple[int, ...] = (3, 6, 9, 12)
    validation_start: pd.Timestamp = pd.Timestamp('2024-03-31')
    validation_end: pd.Timestamp = pd.Timestamp('2025-04-30')
    frozen_test_start: pd.Timestamp = pd.Timestamp('2025-06-30')
    frozen_test_end: pd.Timestamp = pd.Timestamp('2026-05-31')
    prospective_holdout_start: pd.Timestamp = pd.Timestamp('2026-08-31')
    cv_test_periods: int = 3
    minimum_train_periods: int = 24
    minimum_test_securities: int = 30
    primary_horizon_months: int = 3
    top_fraction: float = 0.20
    regional_benchmark_weight: float = 0.70
    sector_benchmark_weight: float = 0.30
    minimum_peer_count: int = 5
    random_seed: int = 42
    n_jobs: int = 4
    categorical_min_frequency: int = 10
    ols_minimum_features: int = 5
    ols_maximum_features: int = 20
    ols_minimum_abs_t_stat: float = 1.0
    ols_minimum_sign_consistency: float = 0.55
    base_cost_bps: float = 17.5
    currency_conversion_bps: float = 2.0
    impact_coefficient_bps: float = 10.0
    maximum_participation_rate: float = 0.05
    assumed_position_weight: float = 0.03
    portfolio_nav_usd: float = 186_060_522.0
    no_trade_band_return: float = 0.002
    retention_rank_bonus: float = 0.10
    entry_cost_rank_penalty: float = 0.03
    annual_bank_fee_rate: float = 0.0025
    annual_turnover_budget: float = 1.50
    minimum_outcome_cross_section_coverage: float = 0.90
    quantile_calibration_periods: int = 12
    quantile_minimum_calibration_periods: int = 6
    quantile_calibration_target_coverage: float = 0.95
    bootstrap_samples: int = 1000
    minimum_oos_periods: int = 12
    minimum_oos_rank_ic: float = 0.02
    maximum_oos_sign_test_p_value: float = 0.05
    maximum_annual_turnover: float = 1.50
    require_positive_active_return_ci: bool = True
    maximum_deployment_blend: float = 0.25
    enabled_families: tuple[str, ...] = (
        'ols_screened',
        'ridge',
        'elastic_net',
        'huber',
        'random_forest',
        'extra_trees',
        'hist_gradient_boosting',
        'xgboost',
        'xgb_ranker',
    )
    model_grids: Mapping[str, tuple[Mapping[str, Any], ...]] = field(
        default_factory=dict
    )

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, Any] | None,
        *,
        root: Path | None = None,
    ) -> 'SupervisedAlphaSettings':
        raw = dict(values or {})
        validation = dict(raw.get('validation', {}))
        costs = dict(raw.get('costs', {}))
        acceptance = dict(raw.get('acceptance', {}))
        models = dict(raw.get('models', {}))

        def path_value(key: str, default: str) -> Path:
            path = Path(raw.get(key, default))
            return (root / path).resolve() if root is not None and not path.is_absolute() else path

        grids: dict[str, tuple[Mapping[str, Any], ...]] = {}
        for family, candidates in dict(models.get('parameter_grids', {})).items():
            grids[str(family)] = tuple(dict(candidate) for candidate in candidates)
        return cls(
            output_directory=path_value(
                'output_directory', 'reports/outputs/supervised_alpha'
            ),
            model_directory=path_value(
                'model_directory', 'data/processed/supervised_alpha'
            ),
            checkpoint_directory=path_value(
                'checkpoint_directory', 'data/interim/supervised_alpha_checkpoints'
            ),
            resume_checkpoints=bool(raw.get('resume_checkpoints', True)),
            horizons_months=tuple(int(value) for value in raw.get('horizons_months', [3, 6, 9, 12])),
            validation_start=pd.Timestamp(validation.get('validation_start', '2024-03-31')).normalize(),
            validation_end=pd.Timestamp(validation.get('validation_end', '2025-04-30')).normalize(),
            frozen_test_start=pd.Timestamp(validation.get('frozen_test_start', '2025-06-30')).normalize(),
            frozen_test_end=pd.Timestamp(validation.get('frozen_test_end', '2026-05-31')).normalize(),
            prospective_holdout_start=pd.Timestamp(validation.get('prospective_holdout_start', '2026-08-31')).normalize(),
            cv_test_periods=max(int(validation.get('cv_test_periods', 3)), 1),
            minimum_train_periods=max(int(validation.get('minimum_train_periods', 24)), 3),
            minimum_test_securities=max(int(validation.get('minimum_test_securities', 30)), 5),
            primary_horizon_months=int(raw.get('primary_horizon_months', 3)),
            top_fraction=float(raw.get('top_fraction', 0.20)),
            regional_benchmark_weight=float(raw.get('regional_benchmark_weight', 0.70)),
            sector_benchmark_weight=float(raw.get('sector_benchmark_weight', 0.30)),
            minimum_peer_count=max(int(raw.get('minimum_peer_count', 5)), 2),
            random_seed=int(raw.get('random_seed', 42)),
            n_jobs=max(int(raw.get('n_jobs', 4)), 1),
            categorical_min_frequency=max(int(raw.get('categorical_min_frequency', 10)), 1),
            ols_minimum_features=max(int(raw.get('ols_minimum_features', 5)), 1),
            ols_maximum_features=max(int(raw.get('ols_maximum_features', 20)), 1),
            ols_minimum_abs_t_stat=float(raw.get('ols_minimum_abs_t_stat', 1.0)),
            ols_minimum_sign_consistency=float(raw.get('ols_minimum_sign_consistency', 0.55)),
            base_cost_bps=float(costs.get('base_cost_bps', 17.5)),
            currency_conversion_bps=float(costs.get('currency_conversion_bps', 2.0)),
            impact_coefficient_bps=float(costs.get('impact_coefficient_bps', 10.0)),
            maximum_participation_rate=max(float(costs.get('maximum_participation_rate', 0.05)), 1e-6),
            assumed_position_weight=float(costs.get('assumed_position_weight', 0.03)),
            portfolio_nav_usd=float(costs.get('portfolio_nav_usd', 186_060_522.0)),
            no_trade_band_return=float(costs.get('no_trade_band_return', 0.002)),
            retention_rank_bonus=float(costs.get('retention_rank_bonus', 0.10)),
            entry_cost_rank_penalty=float(costs.get('entry_cost_rank_penalty', 0.03)),
            annual_bank_fee_rate=max(float(costs.get('annual_bank_fee_rate', 0.0025)), 0.0),
            annual_turnover_budget=max(float(costs.get('annual_turnover_budget', 1.50)), 0.0),
            minimum_outcome_cross_section_coverage=min(
                max(float(validation.get('minimum_outcome_cross_section_coverage', 0.90)), 0.0),
                1.0,
            ),
            quantile_calibration_periods=max(
                int(validation.get('quantile_calibration_periods', 12)),
                1,
            ),
            quantile_minimum_calibration_periods=max(
                int(validation.get('quantile_minimum_calibration_periods', 6)),
                2,
            ),
            quantile_calibration_target_coverage=min(
                max(
                    float(validation.get('quantile_calibration_target_coverage', 0.95)),
                    0.90,
                ),
                0.999,
            ),
            bootstrap_samples=max(int(validation.get('bootstrap_samples', 1000)), 100),
            minimum_oos_periods=max(int(acceptance.get('minimum_oos_periods', 12)), 1),
            minimum_oos_rank_ic=float(acceptance.get('minimum_oos_rank_ic', 0.02)),
            maximum_oos_sign_test_p_value=min(
                max(float(acceptance.get('maximum_oos_sign_test_p_value', 0.05)), 0.0),
                1.0,
            ),
            maximum_annual_turnover=float(acceptance.get('maximum_annual_turnover', 1.50)),
            require_positive_active_return_ci=bool(acceptance.get('require_positive_active_return_ci', True)),
            maximum_deployment_blend=float(acceptance.get('maximum_deployment_blend', 0.25)),
            enabled_families=tuple(str(value) for value in models.get('enabled_families', cls.enabled_families)),
            model_grids=grids,
        )


@dataclass(frozen=True)
class CandidateSpec:
    key: str
    family: str
    category: str
    parameters: Mapping[str, Any]


@dataclass
class FittedCandidate:
    spec: CandidateSpec
    estimator: Any
    feature_mask: np.ndarray | None = None


@dataclass
class SupervisedAlphaResult:
    dataset_profile: pd.DataFrame
    validation_summary: pd.DataFrame
    family_winners: pd.DataFrame
    ensemble_weights: pd.DataFrame
    validation_monthly: pd.DataFrame
    oos_summary: pd.DataFrame
    oos_monthly: pd.DataFrame
    oos_predictions: pd.DataFrame
    ols_screening: pd.DataFrame
    quantile_metrics: pd.DataFrame
    generalisation_audit: pd.DataFrame
    latest_predictions: pd.DataFrame
    acceptance_decision: pd.DataFrame
    model_manifest: pd.DataFrame
    failures: pd.DataFrame


def _default_model_grids() -> dict[str, tuple[Mapping[str, Any], ...]]:
    return {
        'ols_screened': ({},),
        'ridge': ({'alpha': 1.0}, {'alpha': 10.0}, {'alpha': 100.0}),
        'elastic_net': (
            {'alpha': 0.001, 'l1_ratio': 0.50},
            {'alpha': 0.01, 'l1_ratio': 0.10},
            {'alpha': 0.01, 'l1_ratio': 0.50},
        ),
        'huber': ({'alpha': 0.0001, 'epsilon': 0.05},),
        'random_forest': (
            {'n_estimators': 120, 'max_depth': 6, 'min_samples_leaf': 80, 'max_features': 0.7},
            {'n_estimators': 120, 'max_depth': 10, 'min_samples_leaf': 80, 'max_features': 0.7},
        ),
        'extra_trees': (
            {'n_estimators': 160, 'max_depth': 8, 'min_samples_leaf': 60, 'max_features': 0.7},
        ),
        'hist_gradient_boosting': (
            {'learning_rate': 0.04, 'max_iter': 160, 'max_leaf_nodes': 7, 'l2_regularization': 5.0},
            {'learning_rate': 0.04, 'max_iter': 160, 'max_leaf_nodes': 15, 'l2_regularization': 10.0},
        ),
        'xgboost': (
            {'learning_rate': 0.035, 'n_estimators': 400, 'max_depth': 2, 'min_child_weight': 50.0, 'reg_lambda': 15.0},
            {'learning_rate': 0.035, 'n_estimators': 400, 'max_depth': 3, 'min_child_weight': 75.0, 'reg_lambda': 25.0},
        ),
        'xgb_ranker': (
            {'learning_rate': 0.04, 'n_estimators': 240, 'max_depth': 3, 'min_child_weight': 50.0, 'reg_lambda': 20.0},
        ),
    }


def _slug(value: Any) -> str:
    return str(value).replace('.', 'p').replace('-', 'm')


def build_candidate_specs(settings: SupervisedAlphaSettings) -> list[CandidateSpec]:
    defaults = _default_model_grids()
    categories = {
        'ols_screened': 'linear',
        'ridge': 'linear',
        'elastic_net': 'linear',
        'huber': 'linear',
        'random_forest': 'tree',
        'extra_trees': 'tree',
        'hist_gradient_boosting': 'tree',
        'xgboost': 'tree',
        'xgb_ranker': 'ranker',
    }
    specs: list[CandidateSpec] = []
    for family in settings.enabled_families:
        candidates = settings.model_grids.get(family, defaults.get(family, ({},)))
        for index, parameters in enumerate(candidates, start=1):
            suffix = '_'.join(f'{key}-{_slug(value)}' for key, value in sorted(parameters.items()))
            key = family if len(candidates) == 1 else f'{family}__{suffix or index}'
            specs.append(CandidateSpec(key, family, categories.get(family, 'other'), dict(parameters)))
    return specs


def _coalesce_numeric(data: pd.DataFrame, primary: str, alternatives: Sequence[str]) -> None:
    if primary not in data:
        data[primary] = np.nan
    values = pd.to_numeric(data[primary], errors='coerce')
    for alternative in alternatives:
        if alternative in data:
            values = values.fillna(pd.to_numeric(data[alternative], errors='coerce'))
    data[primary] = values


def prepare_supervised_features(
    frame: pd.DataFrame,
    *,
    numeric_features: Sequence[str] = DEFAULT_NUMERIC_FEATURES,
    categorical_features: Sequence[str] = DEFAULT_CATEGORICAL_FEATURES,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Create stable contemporaneous features without fitting global transforms."""

    data = frame.copy()
    if 'as_of_date' not in data:
        data['as_of_date'] = pd.Timestamp.now().normalize()
    data['as_of_date'] = pd.to_datetime(data['as_of_date'], errors='coerce')
    _coalesce_numeric(data, 'average_daily_value_usd', ('avg_daily_traded_value_usd',))
    _coalesce_numeric(data, 'ev_ebitda', ('ev_to_ebitda',))
    for column in numeric_features:
        if column not in data:
            data[column] = np.nan
        data[column] = pd.to_numeric(data[column], errors='coerce').replace([np.inf, -np.inf], np.nan)
    for column in categorical_features:
        if column not in data:
            data[column] = 'Unknown'
        data[column] = data[column].fillna('Unknown').astype(str)

    data['log_market_cap_usd'] = np.log1p(data['market_cap_usd'].clip(lower=0.0))
    data['log_average_daily_value_usd'] = np.log1p(
        data['average_daily_value_usd'].clip(lower=0.0)
    )
    resolved_numeric = list(numeric_features) + [
        'log_market_cap_usd',
        'log_average_daily_value_usd',
    ]
    group_keys = [data['as_of_date'], data['region']]
    for column in RANK_FEATURES:
        if column not in data:
            continue
        rank_column = f'{column}__regional_rank'
        data[rank_column] = data[column].groupby(group_keys, dropna=False).rank(
            pct=True,
            method='average',
        )
        resolved_numeric.append(rank_column)
    return data, resolved_numeric, list(categorical_features)


def _estimated_one_way_cost_bps(
    data: pd.DataFrame,
    settings: SupervisedAlphaSettings,
) -> pd.Series:
    adv = pd.to_numeric(data.get('average_daily_value_usd'), errors='coerce').fillna(0.0).clip(lower=1.0)
    participation = (
        settings.assumed_position_weight * settings.portfolio_nav_usd / (21.0 * adv)
    ).clip(lower=0.0, upper=settings.maximum_participation_rate)
    impact = settings.impact_coefficient_bps * np.sqrt(
        participation / settings.maximum_participation_rate
    )
    currency = data.get('currency', pd.Series('USD', index=data.index)).fillna('USD').astype(str)
    return (
        settings.base_cost_bps
        + impact
        + currency.ne('USD').astype(float) * settings.currency_conversion_bps
    )


def build_supervised_alpha_dataset(
    feature_panel: pd.DataFrame,
    outcomes: pd.DataFrame,
    settings: SupervisedAlphaSettings,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Align PIT features and realised outcomes into benchmark-relative labels."""

    features, numeric, categorical = prepare_supervised_features(feature_panel)
    feature_universe_counts = (
        features.drop_duplicates(['security_id', 'as_of_date'])
        .groupby('as_of_date')['security_id']
        .nunique()
    )
    chronology_errors = pd.Series(False, index=features.index)
    if 'fundamentals_available_from' in features:
        chronology_errors |= pd.to_datetime(
            features['fundamentals_available_from'], errors='coerce'
        ).gt(features['as_of_date'])
    if 'price_feature_end_date' in features:
        chronology_errors |= pd.to_datetime(
            features['price_feature_end_date'], errors='coerce'
        ).gt(features['as_of_date'])
    if bool(chronology_errors.any()):
        raise ValueError('Future information was detected in the feature panel.')

    result = outcomes.copy()
    for column in ('as_of_date', 'target_date', 'outcome_date'):
        result[column] = pd.to_datetime(result[column], errors='coerce')
    result = result.loc[result['horizon_months'].isin(settings.horizons_months)].copy()
    feature_columns = list(
        dict.fromkeys(
            [
                'security_id',
                'ticker',
                'company_name',
                'as_of_date',
                'region',
                'sector',
                'country',
                'currency',
                'fundamentals_available_from',
                'price_feature_end_date',
                'evidence_mode',
            ]
            + numeric
            + categorical
        )
    )
    feature_columns = [column for column in feature_columns if column in features]
    result = result.merge(
        features[feature_columns].drop_duplicates(['security_id', 'as_of_date']),
        on=['security_id', 'as_of_date'],
        how='inner',
        validate='many_to_one',
    )
    result['realised_return'] = pd.to_numeric(result['realised_return'], errors='coerce')
    result = result.loc[result['realised_return'].notna()].copy()
    outcome_counts = result.groupby(
        ['as_of_date', 'horizon_months']
    )['security_id'].transform('nunique')
    result['feature_universe_count'] = (
        result['as_of_date'].map(feature_universe_counts).fillna(0).astype(int)
    )
    result['outcome_cross_section_count'] = outcome_counts.astype(int)
    result['outcome_cross_section_coverage'] = (
        outcome_counts
        / result['feature_universe_count'].replace(0, np.nan)
    )
    result = result.loc[
        result['outcome_cross_section_coverage'].ge(
            settings.minimum_outcome_cross_section_coverage
        )
    ].copy()
    base_group = ['as_of_date', 'horizon_months', 'region']
    peer_group = base_group + ['sector']
    regional_benchmark = result.groupby(base_group, dropna=False)['realised_return'].transform('median')
    peer_count = result.groupby(peer_group, dropna=False)['realised_return'].transform('count')
    sector_benchmark = result.groupby(peer_group, dropna=False)['realised_return'].transform('median')
    sector_benchmark = sector_benchmark.where(
        peer_count.ge(settings.minimum_peer_count),
        regional_benchmark,
    )
    total_weight = settings.regional_benchmark_weight + settings.sector_benchmark_weight
    if total_weight <= 0:
        benchmark = regional_benchmark
    else:
        benchmark = (
            settings.regional_benchmark_weight * regional_benchmark
            + settings.sector_benchmark_weight * sector_benchmark
        ) / total_weight
    result['regional_realised_benchmark_return'] = regional_benchmark
    result['peer_realised_benchmark_return'] = benchmark
    result['target_excess_return'] = result['realised_return'] - benchmark
    result['estimated_one_way_cost_bps'] = _estimated_one_way_cost_bps(result, settings)
    counts = result.groupby(['as_of_date', 'horizon_months'])['security_id'].transform('count').clip(lower=1)
    result['sample_weight'] = 1.0 / counts
    result['row_id'] = (
        result['security_id'].astype(str)
        + '|'
        + result['as_of_date'].dt.strftime('%Y-%m-%d')
        + '|'
        + result['horizon_months'].astype(str)
    )
    result = result.sort_values(['horizon_months', 'as_of_date', 'security_id']).reset_index(drop=True)
    return result, numeric, categorical


def expanding_purged_folds(
    data: pd.DataFrame,
    settings: SupervisedAlphaSettings,
) -> list[tuple[str, pd.Index, pd.Index]]:
    """Create expanding folds whose training labels finish before validation."""

    validation_dates = sorted(
        pd.to_datetime(
            data.loc[
                data['as_of_date'].between(settings.validation_start, settings.validation_end)
                & data['target_date'].lt(settings.frozen_test_start),
                'as_of_date',
            ].unique()
        )
    )
    folds: list[tuple[str, pd.Index, pd.Index]] = []
    for start in range(0, len(validation_dates), settings.cv_test_periods):
        dates = validation_dates[start : start + settings.cv_test_periods]
        if not dates:
            continue
        test_start = pd.Timestamp(dates[0])
        train_mask = data['target_date'].lt(test_start) & data['as_of_date'].lt(test_start)
        test_mask = data['as_of_date'].isin(dates)
        if data.loc[train_mask, 'as_of_date'].nunique() < settings.minimum_train_periods:
            continue
        if len(data.loc[test_mask]) < settings.minimum_test_securities:
            continue
        fold_id = f'{pd.Timestamp(dates[0]).date()}_{pd.Timestamp(dates[-1]).date()}'
        folds.append((fold_id, data.index[train_mask], data.index[test_mask]))
    return folds


def _newey_west_t_stat(values: pd.Series, lag: int) -> tuple[float, float]:
    clean = pd.to_numeric(values, errors='coerce').dropna().to_numpy(dtype=float)
    count = len(clean)
    if count < 3:
        return float(np.nanmean(clean)) if count else np.nan, np.nan
    mean = float(clean.mean())
    if count < 2 * (max(int(lag), 0) + 1):
        return mean, np.nan
    centred = clean - mean
    long_run = float(np.dot(centred, centred) / count)
    for offset in range(1, min(max(lag, 0), count - 1) + 1):
        weight = 1.0 - offset / (lag + 1.0)
        covariance = float(np.dot(centred[offset:], centred[:-offset]) / count)
        long_run += 2.0 * weight * covariance
    standard_error = np.sqrt(max(long_run, 0.0) / count)
    return mean, mean / standard_error if standard_error > 0 else np.nan


def fama_macbeth_ols_screen(
    train: pd.DataFrame,
    numeric_features: Sequence[str],
    settings: SupervisedAlphaSettings,
    horizon_months: int,
) -> tuple[list[str], pd.DataFrame]:
    """Screen train-only features using monthly univariate OLS slope stability."""

    target_rank = train.groupby('as_of_date')['target_excess_return'].rank(pct=True, method='average')
    rows: list[dict[str, Any]] = []
    for feature in numeric_features:
        values = pd.to_numeric(train[feature], errors='coerce')
        feature_rank = values.groupby(train['as_of_date']).rank(pct=True, method='average')
        slopes: list[float] = []
        for date in train['as_of_date'].drop_duplicates().sort_values():
            mask = train['as_of_date'].eq(date) & feature_rank.notna() & target_rank.notna()
            x = feature_rank.loc[mask].to_numpy(dtype=float, copy=True)
            y = target_rank.loc[mask].to_numpy(dtype=float, copy=True)
            if len(x) < settings.minimum_test_securities:
                continue
            x -= x.mean()
            y -= y.mean()
            denominator = float(np.dot(x, x))
            if denominator > 0:
                slopes.append(float(np.dot(x, y) / denominator))
        slope_series = pd.Series(slopes, dtype=float)
        mean_slope, t_stat = _newey_west_t_stat(
            slope_series,
            lag=max(int(horizon_months) - 1, 0),
        )
        sign = np.sign(mean_slope) if np.isfinite(mean_slope) else 0.0
        consistency = float((np.sign(slope_series) == sign).mean()) if len(slope_series) else np.nan
        rows.append(
            {
                'feature': feature,
                'monthly_slopes': len(slope_series),
                'mean_slope': mean_slope,
                'newey_west_t_stat': t_stat,
                'sign_consistency': consistency,
                'selected': False,
            }
        )
    report = pd.DataFrame(rows)
    if report.empty:
        return list(numeric_features[: settings.ols_minimum_features]), report
    eligible = report.loc[
        report['newey_west_t_stat'].abs().ge(settings.ols_minimum_abs_t_stat)
        & report['sign_consistency'].ge(settings.ols_minimum_sign_consistency)
    ].copy()
    ranked = report.assign(_score=report['newey_west_t_stat'].abs()).sort_values(
        ['_score', 'sign_consistency'], ascending=False
    )
    if len(eligible) < settings.ols_minimum_features:
        selected = ranked.head(settings.ols_minimum_features)['feature'].tolist()
    else:
        selected = eligible.assign(_score=eligible['newey_west_t_stat'].abs()).sort_values(
            '_score', ascending=False
        ).head(settings.ols_maximum_features)['feature'].tolist()
    report['selected'] = report['feature'].isin(selected)
    return selected, report


def _build_preprocessor(
    numeric_features: Sequence[str],
    categorical_features: Sequence[str],
    settings: SupervisedAlphaSettings,
) -> ColumnTransformer:
    numeric_pipeline = Pipeline(
        [
            (
                'imputer',
                SimpleImputer(
                    strategy='median',
                    add_indicator=True,
                    keep_empty_features=True,
                ),
            ),
            ('scaler', StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        [
            ('imputer', SimpleImputer(strategy='most_frequent')),
            (
                'encoder',
                OneHotEncoder(
                    handle_unknown='ignore',
                    min_frequency=settings.categorical_min_frequency,
                    sparse_output=False,
                    dtype=np.float32,
                ),
            ),
        ]
    )
    return ColumnTransformer(
        [
            ('numeric', numeric_pipeline, list(numeric_features)),
            ('categorical', categorical_pipeline, list(categorical_features)),
        ],
        sparse_threshold=0.0,
        verbose_feature_names_out=True,
    )


def _training_target(data: pd.DataFrame) -> np.ndarray:
    values = pd.to_numeric(data['target_excess_return'], errors='coerce')
    clipped = values.groupby(data['as_of_date']).transform(
        lambda series: series.clip(series.quantile(0.01), series.quantile(0.99))
    )
    return clipped.fillna(0.0).to_numpy(dtype=np.float32)


def _relevance_target(data: pd.DataFrame) -> np.ndarray:
    ranks = data.groupby('as_of_date')['target_excess_return'].rank(pct=True, method='average')
    return np.floor(ranks.fillna(0.5).clip(0.0, 0.999999) * 5.0).astype(int).to_numpy()


def _xgboost_classes() -> tuple[Any, Any]:
    try:
        from xgboost import XGBRanker, XGBRegressor
    except ImportError as error:  # pragma: no cover - exercised when optional extra is absent
        raise RuntimeError('xgboost is not installed; install the project ml extra.') from error
    return XGBRegressor, XGBRanker


def _make_estimator(
    spec: CandidateSpec,
    settings: SupervisedAlphaSettings,
    *,
    early_stopping: bool = False,
) -> Any:
    parameters = dict(spec.parameters)
    if spec.family == 'ols_screened':
        return LinearRegression()
    if spec.family == 'ridge':
        return Ridge(**parameters)
    if spec.family == 'elastic_net':
        return ElasticNet(max_iter=5000, tol=1e-4, random_state=settings.random_seed, **parameters)
    if spec.family == 'huber':
        return SGDRegressor(
            loss='huber',
            penalty='l2',
            learning_rate='adaptive',
            eta0=0.01,
            max_iter=2000,
            tol=1e-4,
            average=True,
            random_state=settings.random_seed,
            **parameters,
        )
    if spec.family == 'random_forest':
        return RandomForestRegressor(
            random_state=settings.random_seed,
            n_jobs=settings.n_jobs,
            bootstrap=True,
            **parameters,
        )
    if spec.family == 'extra_trees':
        return ExtraTreesRegressor(
            random_state=settings.random_seed,
            n_jobs=settings.n_jobs,
            bootstrap=False,
            **parameters,
        )
    if spec.family == 'hist_gradient_boosting':
        return HistGradientBoostingRegressor(
            loss='squared_error',
            early_stopping=False,
            random_state=settings.random_seed,
            min_samples_leaf=50,
            **parameters,
        )
    if spec.family == 'xgboost':
        XGBRegressor, _ = _xgboost_classes()
        return XGBRegressor(
            objective='reg:squarederror',
            tree_method='hist',
            subsample=0.80,
            colsample_bytree=0.80,
            reg_alpha=0.10,
            n_jobs=settings.n_jobs,
            random_state=settings.random_seed,
            early_stopping_rounds=25 if early_stopping else None,
            **parameters,
        )
    if spec.family == 'xgb_ranker':
        _, XGBRanker = _xgboost_classes()
        return XGBRanker(
            objective='rank:ndcg',
            tree_method='hist',
            subsample=0.80,
            colsample_bytree=0.80,
            reg_alpha=0.10,
            n_jobs=settings.n_jobs,
            random_state=settings.random_seed,
            **parameters,
        )
    raise ValueError(f'Unsupported supervised-alpha model family: {spec.family}')


def _ols_feature_mask(
    feature_names: np.ndarray,
    selected_numeric: Sequence[str],
) -> np.ndarray:
    selected = set(selected_numeric)
    keep = []
    for name in feature_names.astype(str):
        if name.startswith('categorical__'):
            keep.append(True)
            continue
        clean = name.removeprefix('numeric__')
        if clean.startswith('missingindicator_'):
            clean = clean.removeprefix('missingindicator_')
        keep.append(clean in selected)
    mask = np.asarray(keep, dtype=bool)
    return mask if bool(mask.any()) else np.ones(len(feature_names), dtype=bool)


def _fit_candidate(
    spec: CandidateSpec,
    X: np.ndarray,
    train: pd.DataFrame,
    settings: SupervisedAlphaSettings,
    *,
    feature_mask: np.ndarray | None = None,
) -> FittedCandidate:
    fit_X = X[:, feature_mask] if feature_mask is not None else X
    target = _relevance_target(train) if spec.family == 'xgb_ranker' else _training_target(train)
    weights = pd.to_numeric(train['sample_weight'], errors='coerce').fillna(0.0).to_numpy(dtype=float)
    positive_weight_mean = float(weights[weights > 0].mean()) if bool((weights > 0).any()) else 1.0
    weights = weights / max(positive_weight_mean, 1e-12)
    if spec.family == 'xgb_ranker':
        estimator = _make_estimator(spec, settings)
        qid = pd.factorize(train['as_of_date'], sort=True)[0]
        estimator.fit(fit_X, target, qid=qid, verbose=False)
        return FittedCandidate(spec, estimator, feature_mask)

    unique_dates = pd.Series(pd.to_datetime(train['as_of_date']).sort_values().unique())
    use_early_stopping = spec.family == 'xgboost' and len(unique_dates) >= 8
    estimator = _make_estimator(spec, settings, early_stopping=use_early_stopping)
    if use_early_stopping:
        evaluation_dates = set(unique_dates.iloc[-3:])
        evaluation_mask = train['as_of_date'].isin(evaluation_dates).to_numpy()
        core_mask = ~evaluation_mask
        estimator.fit(
            fit_X[core_mask],
            target[core_mask],
            sample_weight=weights[core_mask],
            eval_set=[(fit_X[evaluation_mask], target[evaluation_mask])],
            sample_weight_eval_set=[weights[evaluation_mask]],
            verbose=False,
        )
        return FittedCandidate(spec, estimator, feature_mask)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', ConvergenceWarning)
        try:
            estimator.fit(fit_X, target, sample_weight=weights)
        except TypeError:
            estimator.fit(fit_X, target)
    convergence = [warning for warning in caught if issubclass(warning.category, ConvergenceWarning)]
    if convergence:
        raise RuntimeError(
            f'{spec.key} did not converge: {convergence[-1].message}'
        )
    return FittedCandidate(spec, estimator, feature_mask)


def _predict_candidate(model: FittedCandidate, X: np.ndarray) -> np.ndarray:
    predict_X = X[:, model.feature_mask] if model.feature_mask is not None else X
    return np.asarray(model.estimator.predict(predict_X), dtype=float)


def _neutralise_predictions(data: pd.DataFrame, values: np.ndarray) -> np.ndarray:
    predictions = pd.Series(values, index=data.index, dtype=float)
    centred = predictions - predictions.groupby(
        [data['as_of_date'], data['region']], dropna=False
    ).transform('mean')
    return centred.fillna(0.0).to_numpy(dtype=float)


def _block_bootstrap_mean_ci(
    values: pd.Series,
    *,
    block_length: int,
    samples: int,
    seed: int,
) -> tuple[float, float]:
    clean = pd.to_numeric(values, errors='coerce').dropna().to_numpy(dtype=float)
    count = len(clean)
    if count < 2:
        value = float(clean[0]) if count else np.nan
        return value, value
    rng = np.random.default_rng(seed)
    block = min(max(int(block_length), 1), count)
    if count < 2 * block:
        return np.nan, np.nan
    means = np.empty(samples, dtype=float)
    for sample in range(samples):
        selected: list[float] = []
        while len(selected) < count:
            start = int(rng.integers(0, count))
            selected.extend(clean[(start + offset) % count] for offset in range(block))
        means[sample] = float(np.mean(selected[:count]))
    lower, upper = np.quantile(means, [0.025, 0.975])
    return float(lower), float(upper)


def _non_overlapping_cohort_mask(monthly: pd.DataFrame) -> pd.Series:
    """Select a deterministic set of forward-return cohorts that do not overlap."""

    selected = pd.Series(False, index=monthly.index)
    next_available = pd.Timestamp.min
    for index, row in monthly.sort_values('as_of_date').iterrows():
        decision_date = pd.Timestamp(row['as_of_date'])
        target_date = pd.Timestamp(row['cohort_target_date'])
        if pd.isna(target_date):
            target_date = decision_date + pd.DateOffset(
                months=int(row['horizon_months'])
            )
        if decision_date >= next_available:
            selected.loc[index] = True
            next_available = target_date
    return selected


def _regional_selection_weights(
    data: pd.DataFrame,
    prediction_column: str,
    settings: SupervisedAlphaSettings,
    previous_weights: Mapping[str, float] | None = None,
) -> pd.Series:
    previous = set((previous_weights or {}).keys())
    signal_rank = data.groupby('region', dropna=False)[prediction_column].rank(
        pct=True, method='first'
    )
    cost_rank = data.groupby('region', dropna=False)['estimated_one_way_cost_bps'].rank(
        pct=True, method='average'
    )
    held = data['security_id'].astype(str).isin(previous).astype(float)
    selection_utility = (
        signal_rank
        - settings.entry_cost_rank_penalty * cost_rank
        + settings.retention_rank_bonus * held
    )
    selected = pd.Series(False, index=data.index)
    for _, region_rows in data.groupby('region', dropna=False):
        target_count = max(int(np.ceil(len(region_rows) * settings.top_fraction)), 1)
        chosen = selection_utility.loc[region_rows.index].nlargest(target_count).index
        selected.loc[chosen] = True
    selected_count = selected.groupby(data['region'], dropna=False).transform('sum')
    represented_regions = int(data.loc[selected, 'region'].nunique())
    if represented_regions <= 0:
        return pd.Series(0.0, index=data.index)
    weights = selected.astype(float) / selected_count.replace(0, np.nan)
    return (weights / represented_regions).fillna(0.0)


def _turnover_capped_weights(
    desired_weights: Mapping[str, float],
    previous_weights: Mapping[str, float],
    *,
    previous_cash_weight: float,
    available_security_ids: set[str],
    maximum_turnover: float,
) -> tuple[dict[str, float], float, float]:
    """Move toward desired weights without exceeding the ex-ante turnover budget."""

    desired = {
        str(name): float(weight)
        for name, weight in desired_weights.items()
        if float(weight) > 1e-12
    }
    previous = {
        str(name): float(weight)
        for name, weight in previous_weights.items()
        if float(weight) > 1e-12
    }
    if not previous and previous_cash_weight <= 1e-12:
        return desired, 0.0, 0.0

    missing = set(previous) - available_security_ids
    mandatory_exit_weight = float(sum(previous[name] for name in missing))
    base = {name: weight for name, weight in previous.items() if name not in missing}
    base_cash = float(previous_cash_weight + mandatory_exit_weight)
    budget = max(float(maximum_turnover), 0.0)
    if mandatory_exit_weight >= budget - 1e-12:
        return base, base_cash, mandatory_exit_weight

    names = set(base) | set(desired)
    transition_turnover = 0.5 * (
        sum(abs(desired.get(name, 0.0) - base.get(name, 0.0)) for name in names)
        + abs(base_cash)
    )
    if transition_turnover <= 1e-12:
        return desired, 0.0, mandatory_exit_weight
    blend = min(
        max((budget - mandatory_exit_weight) / transition_turnover, 0.0),
        1.0,
    )
    projected = {
        name: (1.0 - blend) * base.get(name, 0.0) + blend * desired.get(name, 0.0)
        for name in names
    }
    projected = {name: weight for name, weight in projected.items() if weight > 1e-12}
    projected_cash = (1.0 - blend) * base_cash
    return projected, float(projected_cash), mandatory_exit_weight


def evaluate_predictions(
    predictions: pd.DataFrame,
    settings: SupervisedAlphaSettings,
    *,
    horizon_months: int,
    prediction_column: str = 'prediction',
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Evaluate monthly ranking and cost-aware regional cohort selection."""

    monthly_rows: list[dict[str, Any]] = []
    previous_weights: dict[str, float] = {}
    previous_costs: dict[str, float] = {}
    previous_cash_weight = 0.0
    for date, month in predictions.sort_values(['as_of_date', 'security_id']).groupby(
        'as_of_date', sort=True
    ):
        clean = month.loc[
            pd.to_numeric(month[prediction_column], errors='coerce').notna()
            & pd.to_numeric(month['target_excess_return'], errors='coerce').notna()
        ].copy()
        if len(clean) < settings.minimum_test_securities:
            continue
        if (
            clean[prediction_column].nunique(dropna=True) < 2
            or clean['target_excess_return'].nunique(dropna=True) < 2
        ):
            rank_ic = np.nan
        else:
            rank_ic = spearmanr(
                clean[prediction_column].to_numpy(dtype=float),
                clean['target_excess_return'].to_numpy(dtype=float),
                nan_policy='omit',
            ).statistic
        clean['target_weight'] = _regional_selection_weights(
            clean,
            prediction_column,
            settings,
            previous_weights,
        )
        desired_weights = dict(
            zip(
                clean['security_id'].astype(str),
                clean['target_weight'].astype(float),
            )
        )
        current_weights, current_cash_weight, mandatory_exit_turnover = (
            _turnover_capped_weights(
                desired_weights,
                previous_weights,
                previous_cash_weight=previous_cash_weight,
                available_security_ids=set(clean['security_id'].astype(str)),
                maximum_turnover=settings.annual_turnover_budget / 12.0,
            )
        )
        clean['target_weight'] = clean['security_id'].astype(str).map(
            current_weights
        ).fillna(0.0)
        selected = clean.loc[clean['target_weight'].gt(0)].copy()
        current_costs = dict(
            zip(
                selected['security_id'].astype(str),
                pd.to_numeric(selected['estimated_one_way_cost_bps'], errors='coerce').fillna(settings.base_cost_bps),
            )
        )
        names = set(previous_weights) | set(current_weights)
        absolute_trades = {
            name: abs(current_weights.get(name, 0.0) - previous_weights.get(name, 0.0))
            for name in names
        }
        transaction_cost = sum(
            trade
            * current_costs.get(name, previous_costs.get(name, settings.base_cost_bps))
            / 10_000.0
            for name, trade in absolute_trades.items()
        )
        turnover = 0.5 * (
            sum(absolute_trades.values())
            + abs(float(current_cash_weight) - float(previous_cash_weight))
        )
        is_initial_funding = not bool(previous_weights) and previous_cash_weight <= 1e-12
        bank_fee = settings.annual_bank_fee_rate * horizon_months / 12.0
        gross = float(
            (
                selected['target_weight']
                * pd.to_numeric(selected['target_excess_return'], errors='coerce').fillna(0.0)
            ).sum()
        )
        monthly_rows.append(
            {
                'as_of_date': pd.Timestamp(date),
                'cohort_target_date': pd.to_datetime(
                    clean['target_date'], errors='coerce'
                ).max(),
                'horizon_months': int(horizon_months),
                'security_count': len(clean),
                'selected_count': len(selected),
                'rank_ic': float(rank_ic) if np.isfinite(rank_ic) else np.nan,
                'gross_active_return': gross,
                'transaction_cost': float(transaction_cost),
                'bank_fee': float(bank_fee),
                'total_cost': float(transaction_cost) + float(bank_fee),
                'net_active_return': gross - float(transaction_cost) - float(bank_fee),
                'turnover': float(turnover),
                'turnover_budget': float(settings.annual_turnover_budget / 12.0),
                'mandatory_exit_turnover': float(mandatory_exit_turnover),
                'cash_weight': float(current_cash_weight),
                'is_initial_funding': is_initial_funding,
            }
        )
        previous_weights = current_weights
        previous_costs = current_costs
        previous_cash_weight = current_cash_weight
    monthly = pd.DataFrame(monthly_rows)
    if monthly.empty:
        return {
            'observations': 0,
            'independent_observations': 0,
            'mean_rank_ic': np.nan,
            'rank_ic_information_ratio': np.nan,
            'rank_ic_newey_west_t_stat': np.nan,
            'independent_rank_ic_hit_rate': np.nan,
            'independent_rank_ic_sign_test_p_value': np.nan,
            'mean_horizon_net_active_return': np.nan,
            'annualised_net_active_return': np.nan,
            'indicative_annualised_cohort_return': np.nan,
            'active_sharpe': np.nan,
            'active_return_newey_west_t_stat': np.nan,
            'annualised_turnover': np.nan,
            'initial_funding_turnover': np.nan,
            'initial_funding_cost': np.nan,
            'annualised_transaction_cost_drag': np.nan,
            'annualised_bank_fee_drag': settings.annual_bank_fee_rate,
            'annualised_cost_drag': np.nan,
            'active_return_ci_lower_95': np.nan,
            'active_return_ci_upper_95': np.nan,
            'selection_score': -np.inf,
        }, monthly
    ic = pd.to_numeric(monthly['rank_ic'], errors='coerce')
    net = pd.to_numeric(monthly['net_active_return'], errors='coerce')
    independent = monthly.loc[_non_overlapping_cohort_mask(monthly)].copy()
    independent_ic = pd.to_numeric(independent['rank_ic'], errors='coerce')
    independent_net = pd.to_numeric(independent['net_active_return'], errors='coerce')
    independent_ic_clean = independent_ic.dropna()
    inference_ready = len(independent) >= settings.minimum_oos_periods
    mean_net = float(net.mean())
    annualisation = 12.0 / max(float(horizon_months), 1.0)
    indicative_annualised_net = (
        float((1.0 + mean_net) ** annualisation - 1.0)
        if mean_net > -1.0
        else np.nan
    )
    diagnostic_active_sharpe = (
        float(independent_net.mean() / independent_net.std(ddof=1) * np.sqrt(annualisation))
        if len(independent_net) >= 3 and independent_net.std(ddof=1) > 0
        else np.nan
    )
    active_sharpe = diagnostic_active_sharpe if inference_ready else np.nan
    mean_ic = float(ic.mean())
    diagnostic_ic_ir = (
        float(independent_ic.mean() / independent_ic.std(ddof=1))
        if len(independent_ic.dropna()) >= 3 and independent_ic.std(ddof=1) > 0
        else np.nan
    )
    ic_ir = diagnostic_ic_ir if inference_ready else np.nan
    if inference_ready:
        _, ic_nw_t = _newey_west_t_stat(ic, lag=max(horizon_months - 1, 0))
        _, net_nw_t = _newey_west_t_stat(net, lag=max(horizon_months - 1, 0))
    else:
        ic_nw_t = np.nan
        net_nw_t = np.nan
    independent_hit_rate = (
        float(independent_ic_clean.gt(0).mean())
        if not independent_ic_clean.empty
        else np.nan
    )
    independent_sign_p_value = (
        float(
            binomtest(
                int(independent_ic_clean.gt(0).sum()),
                len(independent_ic_clean),
                p=0.5,
                alternative='greater',
            ).pvalue
        )
        if not independent_ic_clean.empty
        else np.nan
    )
    ci_lower, ci_upper = _block_bootstrap_mean_ci(
        net,
        block_length=horizon_months,
        samples=settings.bootstrap_samples,
        seed=settings.random_seed + horizon_months,
    )
    if not inference_ready:
        ci_lower, ci_upper = np.nan, np.nan
    ongoing = monthly.loc[~monthly['is_initial_funding'].fillna(False)].copy()
    annual_turnover = (
        float(ongoing['turnover'].mean() * 12.0)
        if not ongoing.empty
        else np.nan
    )
    annual_transaction_cost = (
        float(ongoing['transaction_cost'].mean() * 12.0)
        if not ongoing.empty
        else np.nan
    )
    initial = monthly.loc[monthly['is_initial_funding'].fillna(False)]
    initial_turnover = float(initial['turnover'].iloc[0]) if not initial.empty else np.nan
    initial_cost = float(initial['transaction_cost'].iloc[0]) if not initial.empty else np.nan
    score_turnover = annual_turnover if np.isfinite(annual_turnover) else 0.0
    score = (
        mean_ic
        + 0.10 * np.tanh(
            diagnostic_active_sharpe
            if np.isfinite(diagnostic_active_sharpe)
            else 0.0
        )
        + 0.25 * mean_net
        - 0.01 * score_turnover
    )
    summary = {
        'observations': len(monthly),
        'independent_observations': len(independent),
        'mean_rank_ic': mean_ic,
        'rank_ic_information_ratio': ic_ir,
        'rank_ic_newey_west_t_stat': ic_nw_t,
        'rank_ic_hit_rate': float(ic.gt(0).mean()),
        'independent_rank_ic_hit_rate': independent_hit_rate,
        'independent_rank_ic_sign_test_p_value': independent_sign_p_value,
        'mean_horizon_gross_active_return': float(monthly['gross_active_return'].mean()),
        'mean_horizon_net_active_return': mean_net,
        'annualised_net_active_return': (
            indicative_annualised_net if inference_ready else np.nan
        ),
        'indicative_annualised_cohort_return': indicative_annualised_net,
        'active_sharpe': active_sharpe,
        'active_return_newey_west_t_stat': net_nw_t,
        'annualised_turnover': annual_turnover,
        'initial_funding_turnover': initial_turnover,
        'initial_funding_cost': initial_cost,
        'annualised_transaction_cost_drag': annual_transaction_cost,
        'annualised_bank_fee_drag': settings.annual_bank_fee_rate,
        'annualised_cost_drag': (
            annual_transaction_cost + settings.annual_bank_fee_rate
            if np.isfinite(annual_transaction_cost)
            else np.nan
        ),
        'active_return_ci_lower_95': ci_lower,
        'active_return_ci_upper_95': ci_upper,
        'selection_score': float(score),
    }
    return summary, monthly


def _prediction_frame(
    data: pd.DataFrame,
    values: np.ndarray,
    spec: CandidateSpec,
    split: str,
) -> pd.DataFrame:
    columns = [
        'row_id',
        'security_id',
        'ticker',
        'company_name',
        'as_of_date',
        'target_date',
        'horizon_months',
        'region',
        'sector',
        'country',
        'currency',
        'target_excess_return',
        'realised_return',
        'peer_realised_benchmark_return',
        'estimated_one_way_cost_bps',
    ]
    frame = data[[column for column in columns if column in data]].copy()
    frame['prediction'] = _neutralise_predictions(data, values)
    frame['candidate'] = spec.key
    frame['family'] = spec.family
    frame['category'] = spec.category
    frame['split'] = split
    return frame


def _fit_preprocessor(
    train: pd.DataFrame,
    test: pd.DataFrame,
    numeric_features: Sequence[str],
    categorical_features: Sequence[str],
    settings: SupervisedAlphaSettings,
) -> tuple[ColumnTransformer, np.ndarray, np.ndarray]:
    preprocessor = _build_preprocessor(numeric_features, categorical_features, settings)
    X_train = np.asarray(
        preprocessor.fit_transform(train[list(numeric_features) + list(categorical_features)]),
        dtype=np.float32,
    )
    X_test = np.asarray(
        preprocessor.transform(test[list(numeric_features) + list(categorical_features)]),
        dtype=np.float32,
    )
    return preprocessor, X_train, X_test


def _run_validation_horizon(
    data: pd.DataFrame,
    numeric_features: Sequence[str],
    categorical_features: Sequence[str],
    specs: Sequence[CandidateSpec],
    settings: SupervisedAlphaSettings,
    horizon_months: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    folds = expanding_purged_folds(data, settings)
    prediction_frames: list[pd.DataFrame] = []
    screening_frames: list[pd.DataFrame] = []
    failures: list[dict[str, Any]] = []
    expected_folds = len(folds)
    for fold_id, train_index, test_index in folds:
        train = data.loc[train_index].sort_values(['as_of_date', 'security_id']).copy()
        test = data.loc[test_index].sort_values(['as_of_date', 'security_id']).copy()
        selected_numeric, screening = fama_macbeth_ols_screen(
            train,
            numeric_features,
            settings,
            horizon_months,
        )
        screening['horizon_months'] = horizon_months
        screening['fold'] = fold_id
        screening_frames.append(screening)
        preprocessor, X_train, X_test = _fit_preprocessor(
            train,
            test,
            numeric_features,
            categorical_features,
            settings,
        )
        feature_names = preprocessor.get_feature_names_out()
        ols_mask = _ols_feature_mask(feature_names, selected_numeric)
        for spec in specs:
            try:
                model = _fit_candidate(
                    spec,
                    X_train,
                    train,
                    settings,
                    feature_mask=ols_mask if spec.family == 'ols_screened' else None,
                )
                values = _predict_candidate(model, X_test)
                frame = _prediction_frame(test, values, spec, 'validation')
                frame['fold'] = fold_id
                prediction_frames.append(frame)
            except Exception as error:  # keep independent challengers isolated
                LOGGER.exception('Supervised-alpha candidate %s failed in fold %s.', spec.key, fold_id)
                failures.append(
                    {
                        'horizon_months': horizon_months,
                        'split': 'validation',
                        'fold': fold_id,
                        'candidate': spec.key,
                        'family': spec.family,
                        'error': f'{type(error).__name__}: {error}',
                    }
                )
    predictions = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()
    summary_rows: list[dict[str, Any]] = []
    monthly_frames: list[pd.DataFrame] = []
    if not predictions.empty:
        for candidate, candidate_predictions in predictions.groupby('candidate', sort=True):
            metrics, monthly = evaluate_predictions(
                candidate_predictions,
                settings,
                horizon_months=horizon_months,
            )
            first = candidate_predictions.iloc[0]
            fold_count = int(candidate_predictions['fold'].nunique())
            summary_rows.append(
                {
                    'horizon_months': horizon_months,
                    'candidate': candidate,
                    'family': first['family'],
                    'category': first['category'],
                    'folds': fold_count,
                    'expected_folds': expected_folds,
                    'complete_validation': fold_count == expected_folds,
                    **metrics,
                }
            )
            monthly['candidate'] = candidate
            monthly['family'] = first['family']
            monthly['split'] = 'validation'
            monthly_frames.append(monthly)
    return (
        pd.DataFrame(summary_rows),
        pd.concat(monthly_frames, ignore_index=True) if monthly_frames else pd.DataFrame(),
        pd.concat(screening_frames, ignore_index=True) if screening_frames else pd.DataFrame(),
        pd.DataFrame(
            failures,
            columns=['horizon_months', 'split', 'fold', 'candidate', 'family', 'error'],
        ),
        predictions,
    )


def _validation_checkpoint_signature(
    data: pd.DataFrame,
    settings: SupervisedAlphaSettings,
    specs: Sequence[CandidateSpec],
    horizon_months: int,
) -> str:
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    row_hashes = pd.util.hash_pandas_object(
        data[['row_id', 'target_excess_return', 'target_date']],
        index=False,
    ).to_numpy(dtype=np.uint64)
    evidence_hash = hashlib.sha256(row_hashes.tobytes()).hexdigest()
    payload = {
        'artifact_version': ARTIFACT_VERSION,
        'source_hash': source_hash,
        'evidence_hash': evidence_hash,
        'horizon_months': horizon_months,
        'validation_start': str(settings.validation_start),
        'validation_end': str(settings.validation_end),
        'cv_test_periods': settings.cv_test_periods,
        'minimum_train_periods': settings.minimum_train_periods,
        'random_seed': settings.random_seed,
        'specs': [
            {'key': spec.key, 'family': spec.family, 'parameters': dict(spec.parameters)}
            for spec in specs
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode('utf-8')
    ).hexdigest()


def _checkpoint_paths(directory: Path, horizon_months: int) -> dict[str, Path]:
    prefix = directory / f'{horizon_months}m'
    return {
        'metadata': prefix.with_suffix('.json'),
        'summary': prefix.with_name(prefix.name + '_summary.parquet'),
        'monthly': prefix.with_name(prefix.name + '_monthly.parquet'),
        'screening': prefix.with_name(prefix.name + '_screening.parquet'),
        'failures': prefix.with_name(prefix.name + '_failures.parquet'),
        'predictions': prefix.with_name(prefix.name + '_predictions.parquet'),
    }


def _atomic_checkpoint_frame(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + '.tmp')
    frame.to_parquet(temporary, index=False, compression='zstd')
    temporary.replace(path)


def _load_validation_checkpoint(
    directory: Path,
    horizon_months: int,
    signature: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame] | None:
    paths = _checkpoint_paths(directory, horizon_months)
    if not all(path.exists() for path in paths.values()):
        return None
    try:
        metadata = json.loads(paths['metadata'].read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    if metadata.get('signature') != signature:
        return None
    return (
        pd.read_parquet(paths['summary']),
        pd.read_parquet(paths['monthly']),
        pd.read_parquet(paths['screening']),
        pd.read_parquet(paths['failures']),
        pd.read_parquet(paths['predictions']),
    )


def _write_validation_checkpoint(
    directory: Path,
    horizon_months: int,
    signature: str,
    frames: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    paths = _checkpoint_paths(directory, horizon_months)
    names = ('summary', 'monthly', 'screening', 'failures', 'predictions')
    for name, frame in zip(names, frames):
        _atomic_checkpoint_frame(frame, paths[name])
    temporary = paths['metadata'].with_suffix('.json.tmp')
    temporary.write_text(
        json.dumps(
            {
                'artifact_version': ARTIFACT_VERSION,
                'horizon_months': horizon_months,
                'signature': signature,
            },
            indent=2,
            sort_keys=True,
        )
        + '\n',
        encoding='utf-8',
    )
    temporary.replace(paths['metadata'])


def _family_winners(validation: pd.DataFrame) -> pd.DataFrame:
    if validation.empty:
        return validation.copy()
    eligible = validation.loc[validation['complete_validation'].fillna(False)].copy()
    if eligible.empty:
        eligible = validation.copy()
    winners = (
        eligible.sort_values(
            ['horizon_months', 'family', 'selection_score', 'mean_rank_ic'],
            ascending=[True, True, False, False],
        )
        .groupby(['horizon_months', 'family'], as_index=False)
        .head(1)
        .reset_index(drop=True)
    )
    winners['selected_family_winner'] = True
    return winners


def _ensemble_components(winners: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for horizon, group in winners.groupby('horizon_months', sort=True):
        positive = group.loc[
            group['mean_rank_ic'].gt(0)
            & group['mean_horizon_net_active_return'].gt(0)
        ].copy()
        if positive.empty:
            ridge = group.loc[group['family'].eq('ridge')]
            positive = ridge if not ridge.empty else group.nlargest(1, 'selection_score')
        selected: list[pd.Series] = []
        for category in ('linear', 'tree', 'ranker'):
            category_rows = positive.loc[positive['category'].eq(category)]
            if not category_rows.empty:
                selected.append(category_rows.nlargest(1, 'selection_score').iloc[0])
        if not selected:
            selected.append(positive.nlargest(1, 'selection_score').iloc[0])
        frame = pd.DataFrame(selected).drop_duplicates('candidate').head(3).copy()
        frame['ensemble_weight'] = 1.0 / len(frame)
        frame['horizon_months'] = int(horizon)
        rows.append(frame[['horizon_months', 'candidate', 'family', 'category', 'ensemble_weight']])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _fit_selected_models(
    train: pd.DataFrame,
    test: pd.DataFrame,
    numeric_features: Sequence[str],
    categorical_features: Sequence[str],
    specs_by_key: Mapping[str, CandidateSpec],
    selected_keys: Sequence[str],
    settings: SupervisedAlphaSettings,
    horizon_months: int,
    split: str,
) -> tuple[pd.DataFrame, ColumnTransformer, dict[str, FittedCandidate], pd.DataFrame]:
    selected_numeric, screening = fama_macbeth_ols_screen(
        train,
        numeric_features,
        settings,
        horizon_months,
    )
    preprocessor, X_train, X_test = _fit_preprocessor(
        train,
        test,
        numeric_features,
        categorical_features,
        settings,
    )
    ols_mask = _ols_feature_mask(preprocessor.get_feature_names_out(), selected_numeric)
    predictions: list[pd.DataFrame] = []
    fitted: dict[str, FittedCandidate] = {}
    for key in selected_keys:
        spec = specs_by_key[key]
        model = _fit_candidate(
            spec,
            X_train,
            train,
            settings,
            feature_mask=ols_mask if spec.family == 'ols_screened' else None,
        )
        fitted[key] = model
        predictions.append(
            _prediction_frame(test, _predict_candidate(model, X_test), spec, split)
        )
    screening['horizon_months'] = horizon_months
    screening['fold'] = f'{split}_fit'
    return (
        pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame(),
        preprocessor,
        fitted,
        screening,
    )


def _combine_ensemble_predictions(
    predictions: pd.DataFrame,
    weights: pd.DataFrame,
    *,
    split: str,
) -> pd.DataFrame:
    if predictions.empty or weights.empty:
        return pd.DataFrame()
    relevant = predictions.merge(
        weights[['candidate', 'ensemble_weight']],
        on='candidate',
        how='inner',
        validate='many_to_one',
    )
    relevant['_comparable_rank_signal'] = (
        relevant.groupby(
            ['candidate', 'as_of_date', 'region'],
            dropna=False,
        )['prediction']
        .rank(pct=True, method='average')
        .sub(0.5)
    )
    metadata_columns = [
        column
        for column in predictions.columns
        if column not in {'prediction', 'candidate', 'family', 'category', 'split', 'fold'}
    ]
    metadata = relevant[metadata_columns].drop_duplicates('row_id')
    values = (
        relevant.assign(
            weighted_prediction=(
                relevant['_comparable_rank_signal'] * relevant['ensemble_weight']
            )
        )
        .groupby('row_id', as_index=False)['weighted_prediction']
        .sum()
        .rename(columns={'weighted_prediction': 'prediction'})
    )
    result = metadata.merge(values, on='row_id', how='inner', validate='one_to_one')
    result['candidate'] = 'supervised_alpha_ensemble'
    result['family'] = 'ensemble'
    result['category'] = 'ensemble'
    result['split'] = split
    return result


def _quantile_models(
    train: pd.DataFrame,
    test: pd.DataFrame,
    numeric_features: Sequence[str],
    categorical_features: Sequence[str],
    settings: SupervisedAlphaSettings,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    unique_dates = pd.Series(
        pd.to_datetime(train['as_of_date']).sort_values().unique()
    )
    calibration_count = min(settings.quantile_calibration_periods, len(unique_dates))
    calibration_dates = set(unique_dates.iloc[-calibration_count:])
    calibration_start = pd.Timestamp(unique_dates.iloc[-calibration_count])
    model_train = train.loc[
        train['as_of_date'].lt(calibration_start)
        & train['target_date'].lt(calibration_start)
    ].copy()
    calibration = train.loc[train['as_of_date'].isin(calibration_dates)].copy()
    calibrate = (
        calibration['as_of_date'].nunique()
        >= settings.quantile_minimum_calibration_periods
        and model_train['as_of_date'].nunique() >= settings.minimum_train_periods
    )
    if not calibrate:
        model_train = train.copy()
        calibration = pd.DataFrame()

    preprocessor = _build_preprocessor(
        numeric_features,
        categorical_features,
        settings,
    )
    feature_columns = list(numeric_features) + list(categorical_features)
    X_train = np.asarray(
        preprocessor.fit_transform(model_train[feature_columns]),
        dtype=np.float32,
    )
    X_test = np.asarray(
        preprocessor.transform(test[feature_columns]),
        dtype=np.float32,
    )
    X_calibration = (
        np.asarray(preprocessor.transform(calibration[feature_columns]), dtype=np.float32)
        if calibrate
        else np.empty((0, X_train.shape[1]), dtype=np.float32)
    )
    target = _training_target(model_train)
    output = test[['row_id', 'security_id', 'as_of_date', 'horizon_months', 'target_excess_return']].copy()
    calibration_predictions = calibration[
        ['as_of_date', 'target_excess_return']
    ].copy() if calibrate else pd.DataFrame()
    models: dict[str, Any] = {'preprocessor': preprocessor}
    for quantile in (0.05, 0.50, 0.95):
        model = HistGradientBoostingRegressor(
            loss='quantile',
            quantile=quantile,
            learning_rate=0.04,
            max_iter=160,
            max_leaf_nodes=15,
            min_samples_leaf=50,
            l2_regularization=10.0,
            early_stopping=False,
            random_state=settings.random_seed,
        )
        model.fit(X_train, target)
        column = f'q{int(quantile * 100):02d}_excess_return'
        output[column] = model.predict(X_test)
        output[f'raw_{column}'] = output[column]
        if calibrate:
            calibration_predictions[column] = model.predict(X_calibration)
        models[column] = model
    quantile_columns = ['q05_excess_return', 'q50_excess_return', 'q95_excess_return']
    output[quantile_columns] = np.sort(output[quantile_columns].to_numpy(dtype=float), axis=1)
    conformal_adjustment = 0.0
    median_bias = 0.0
    if calibrate:
        calibration_predictions[quantile_columns] = np.sort(
            calibration_predictions[quantile_columns].to_numpy(dtype=float),
            axis=1,
        )
        realised = pd.to_numeric(
            calibration_predictions['target_excess_return'], errors='coerce'
        )
        conformity = np.maximum(
            calibration_predictions['q05_excess_return'] - realised,
            realised - calibration_predictions['q95_excess_return'],
        )
        calibration_target = settings.quantile_calibration_target_coverage
        date_scores = conformity.groupby(
            calibration_predictions['as_of_date']
        ).quantile(calibration_target)
        date_count = len(date_scores)
        quantile_level = min(
            np.ceil((date_count + 1) * calibration_target) / max(date_count, 1),
            1.0,
        )
        conformal_adjustment = max(
            float(np.quantile(date_scores, quantile_level, method='higher')),
            0.0,
        )
        date_bias = (
            realised - calibration_predictions['q50_excess_return']
        ).groupby(calibration_predictions['as_of_date']).median()
        median_bias = float(date_bias.median())
        output['q05_excess_return'] -= conformal_adjustment
        output['q50_excess_return'] += median_bias
        output['q95_excess_return'] += conformal_adjustment
        output[quantile_columns] = np.sort(
            output[quantile_columns].to_numpy(dtype=float),
            axis=1,
        )
    output['quantile_calibration_method'] = (
        'purged_date_block_conformal' if calibrate else 'uncalibrated_insufficient_history'
    )
    output['quantile_calibration_dates'] = (
        int(calibration['as_of_date'].nunique()) if calibrate else 0
    )
    output['quantile_calibration_target_coverage'] = (
        settings.quantile_calibration_target_coverage if calibrate else np.nan
    )
    output['conformal_interval_adjustment'] = conformal_adjustment
    output['quantile_median_bias_adjustment'] = median_bias
    models['calibration'] = {
        'method': output['quantile_calibration_method'].iloc[0],
        'calibration_dates': int(output['quantile_calibration_dates'].iloc[0]),
        'target_coverage': float(
            output['quantile_calibration_target_coverage'].iloc[0]
        ),
        'calibration_start': str(calibration_start) if calibrate else None,
        'conformal_interval_adjustment': conformal_adjustment,
        'median_bias_adjustment': median_bias,
    }
    return output, models


def _quantile_summary(predictions: pd.DataFrame, split: str) -> dict[str, Any]:
    target = pd.to_numeric(predictions['target_excess_return'], errors='coerce')
    q05 = pd.to_numeric(predictions['q05_excess_return'], errors='coerce')
    q50 = pd.to_numeric(predictions['q50_excess_return'], errors='coerce')
    q95 = pd.to_numeric(predictions['q95_excess_return'], errors='coerce')

    def pinball(prediction: pd.Series, quantile: float) -> float:
        error = target - prediction
        return float(np.maximum(quantile * error, (quantile - 1.0) * error).mean())

    return {
        'split': split,
        'observations': len(predictions),
        'calibration_method': str(
            predictions.get(
                'quantile_calibration_method',
                pd.Series('unknown', index=predictions.index),
            ).iloc[0]
        ),
        'calibration_dates': int(
            pd.to_numeric(
                predictions.get(
                    'quantile_calibration_dates',
                    pd.Series(0, index=predictions.index),
                ),
                errors='coerce',
            ).fillna(0).iloc[0]
        ),
        'calibration_target_coverage': float(
            pd.to_numeric(
                predictions.get(
                    'quantile_calibration_target_coverage',
                    pd.Series(np.nan, index=predictions.index),
                ),
                errors='coerce',
            ).iloc[0]
        ),
        'lower_coverage': float(target.le(q05).mean()),
        'central_90_coverage': float(target.between(q05, q95).mean()),
        'upper_coverage': float(target.le(q95).mean()),
        'mean_interval_width': float((q95 - q05).mean()),
        'pinball_loss_q05': pinball(q05, 0.05),
        'pinball_loss_q50': pinball(q50, 0.50),
        'pinball_loss_q95': pinball(q95, 0.95),
    }


def _acceptance_decisions(
    oos_summary: pd.DataFrame,
    settings: SupervisedAlphaSettings,
    *,
    evidence_reasons: Sequence[str] = (),
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon in settings.horizons_months:
        selected = oos_summary.loc[
            oos_summary['horizon_months'].eq(horizon)
            & oos_summary['candidate'].eq('supervised_alpha_ensemble')
        ]
        reasons: list[str] = []
        if selected.empty:
            reasons.append('missing_oos_evidence')
            observations = 0
        else:
            result = selected.iloc[0]
            monthly_observations = int(result['observations'])
            observations = int(result.get('independent_observations', monthly_observations))
            if observations < settings.minimum_oos_periods:
                reasons.append('insufficient_independent_oos_periods')
            if float(result['mean_rank_ic']) < settings.minimum_oos_rank_ic:
                reasons.append('oos_rank_ic_below_threshold')
            sign_p_value = float(
                result.get('independent_rank_ic_sign_test_p_value', np.nan)
            )
            if not np.isfinite(sign_p_value):
                reasons.append('oos_independent_sign_test_unavailable')
            elif sign_p_value > settings.maximum_oos_sign_test_p_value:
                reasons.append('oos_independent_sign_test_not_significant')
            if float(result['mean_horizon_net_active_return']) <= 0:
                reasons.append('oos_net_active_return_not_positive')
            if settings.require_positive_active_return_ci:
                ci_lower = float(result['active_return_ci_lower_95'])
                if not np.isfinite(ci_lower):
                    reasons.append('oos_uncertainty_interval_unavailable')
                elif ci_lower <= 0:
                    reasons.append('oos_active_return_ci_not_positive')
            annual_turnover = float(result['annualised_turnover'])
            if not np.isfinite(annual_turnover):
                reasons.append('ongoing_turnover_estimate_unavailable')
            elif annual_turnover > settings.maximum_annual_turnover:
                reasons.append('annual_turnover_exceeds_limit')
        reasons.extend(reason for reason in evidence_reasons if reason not in reasons)
        accepted = not reasons
        rows.append(
            {
                'scope': f'{horizon}m',
                'horizon_months': horizon,
                'accepted': accepted,
                'status': 'ACCEPTED' if accepted else ('INSUFFICIENT_EVIDENCE' if observations < settings.minimum_oos_periods else 'REJECTED'),
                'oos_observations': observations,
                'oos_monthly_observations': monthly_observations if not selected.empty else 0,
                'deployment_blend_weight': settings.maximum_deployment_blend if accepted else 0.0,
                'reasons': ';'.join(reasons),
            }
        )
    primary = next(
        row for row in rows if row['horizon_months'] == settings.primary_horizon_months
    )
    rows.append(
        {
            'scope': 'overall',
            'horizon_months': settings.primary_horizon_months,
            'accepted': primary['accepted'],
            'status': primary['status'],
            'oos_observations': primary['oos_observations'],
            'oos_monthly_observations': primary['oos_monthly_observations'],
            'deployment_blend_weight': primary['deployment_blend_weight'],
            'reasons': primary['reasons'],
        }
    )
    return pd.DataFrame(rows)


def _generalisation_audit(
    validation_summary: pd.DataFrame,
    oos_summary: pd.DataFrame,
) -> pd.DataFrame:
    validation = validation_summary.loc[
        validation_summary['candidate'].eq('supervised_alpha_ensemble')
    ].copy()
    legacy_oos = oos_summary.loc[
        oos_summary['candidate'].eq('supervised_alpha_ensemble')
    ].copy()
    if validation.empty or legacy_oos.empty:
        return pd.DataFrame()
    validation = validation[
        [
            'horizon_months',
            'folds',
            'independent_observations',
            'mean_rank_ic',
            'mean_horizon_net_active_return',
        ]
    ].rename(
        columns={
            'folds': 'validation_folds',
            'independent_observations': 'validation_independent_observations',
            'mean_rank_ic': 'validation_mean_rank_ic',
            'mean_horizon_net_active_return': 'validation_mean_net_active_return',
        }
    )
    legacy_oos = legacy_oos[
        [
            'horizon_months',
            'independent_observations',
            'mean_rank_ic',
            'mean_horizon_net_active_return',
        ]
    ].rename(
        columns={
            'independent_observations': 'legacy_oos_independent_observations',
            'mean_rank_ic': 'legacy_oos_mean_rank_ic',
            'mean_horizon_net_active_return': 'legacy_oos_mean_net_active_return',
        }
    )
    audit = validation.merge(legacy_oos, on='horizon_months', validate='one_to_one')
    audit['rank_ic_change'] = (
        audit['legacy_oos_mean_rank_ic'] - audit['validation_mean_rank_ic']
    )
    audit['net_active_return_change'] = (
        audit['legacy_oos_mean_net_active_return']
        - audit['validation_mean_net_active_return']
    )
    audit['rank_ic_retention_ratio'] = (
        audit['legacy_oos_mean_rank_ic']
        / audit['validation_mean_rank_ic'].replace(0.0, np.nan)
    )
    degraded = (
        audit['rank_ic_retention_ratio'].lt(0.5)
        | audit['legacy_oos_mean_rank_ic'].le(0.0)
        | audit['legacy_oos_mean_net_active_return'].le(0.0)
    )
    audit['overfitting_signal'] = np.where(
        degraded,
        'DEGRADATION_OBSERVED',
        'NO_DEGRADATION_IN_LEGACY_SAMPLE',
    )
    audit['deployment_interpretation'] = 'NOT_PROSPECTIVE_OR_NATIVE_PIT_EVIDENCE'
    return audit.sort_values('horizon_months').reset_index(drop=True)


def _latest_prediction_output(
    latest: pd.DataFrame,
    ensemble_predictions: pd.Series,
    quantiles: pd.DataFrame,
    horizon_months: int,
    settings: SupervisedAlphaSettings,
    deployment_weight: float,
) -> pd.DataFrame:
    columns = [
        'security_id',
        'ticker',
        'company_name',
        'as_of_date',
        'region',
        'sector',
        'country',
        'currency',
        'current_weight',
        'row_id',
        f'expected_total_return_{horizon_months}m',
    ]
    output = latest[[column for column in columns if column in latest]].copy()
    output['horizon_months'] = horizon_months
    output['ensemble_rank_signal'] = output['row_id'].map(ensemble_predictions).fillna(0.0)
    output = output.merge(
        quantiles.drop(columns=['target_excess_return'], errors='ignore'),
        on=['row_id', 'security_id', 'as_of_date', 'horizon_months'],
        how='left',
        validate='one_to_one',
    )
    output['predicted_benchmark_relative_return'] = pd.to_numeric(
        output['q50_excess_return'], errors='coerce'
    ).fillna(0.0)
    output['estimated_one_way_cost_bps'] = _estimated_one_way_cost_bps(latest, settings).to_numpy()
    output['cost_adjusted_predicted_excess_return'] = (
        output['predicted_benchmark_relative_return']
        - output['estimated_one_way_cost_bps'] / 10_000.0
    )
    baseline_column = f'expected_total_return_{horizon_months}m'
    if baseline_column in latest:
        baseline = pd.to_numeric(latest[baseline_column], errors='coerce').fillna(0.0)
        benchmark = baseline.groupby(latest['region'], dropna=False).transform('median')
    else:
        benchmark = pd.Series(0.0, index=latest.index)
    output['predicted_total_return'] = benchmark.to_numpy() + output['predicted_benchmark_relative_return']
    ensemble_rank = output.groupby('region', dropna=False)['ensemble_rank_signal'].rank(
        pct=True, method='average'
    )
    return_rank = output.groupby('region', dropna=False)['cost_adjusted_predicted_excess_return'].rank(
        pct=True, method='average'
    )
    selection_signal = 0.70 * ensemble_rank + 0.30 * return_rank
    region_rank = selection_signal.groupby(output['region'], dropna=False).rank(
        pct=True, method='average'
    )
    peer_keys = [output['region'], output['sector']]
    peer_count = output.groupby(['region', 'sector'], dropna=False)['security_id'].transform('count')
    sector_rank = selection_signal.groupby(peer_keys, dropna=False).rank(
        pct=True, method='average'
    )
    sector_rank = sector_rank.where(peer_count.ge(settings.minimum_peer_count), region_rank)
    output['supervised_alpha_score'] = 100.0 * (
        settings.regional_benchmark_weight * region_rank
        + settings.sector_benchmark_weight * sector_rank
    ) / max(settings.regional_benchmark_weight + settings.sector_benchmark_weight, 1e-8)
    current = (
        pd.to_numeric(output['current_weight'], errors='coerce').fillna(0.0)
        if 'current_weight' in output
        else pd.Series(0.0, index=output.index)
    )
    output['no_trade_recommended'] = (
        output['cost_adjusted_predicted_excess_return'].abs().le(settings.no_trade_band_return)
        | (current.gt(0) & output['cost_adjusted_predicted_excess_return'].gt(-settings.no_trade_band_return))
    )
    output['deployment_blend_weight'] = deployment_weight
    output['eligible_for_live_overlay'] = deployment_weight > 0
    return output.sort_values(
        ['cost_adjusted_predicted_excess_return', 'security_id'],
        ascending=[False, True],
    ).reset_index(drop=True)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def apply_governed_supervised_alpha_overlay(
    optimiser_input: pd.DataFrame,
    latest_predictions: pd.DataFrame,
    acceptance_decision: pd.DataFrame,
    settings: SupervisedAlphaSettings,
) -> pd.DataFrame:
    """Blend accepted alpha into expected returns; rejected evidence is a no-op."""

    data = optimiser_input.copy()
    primary = latest_predictions.loc[
        latest_predictions['horizon_months'].eq(settings.primary_horizon_months)
    ].copy()
    if primary.empty:
        data['supervised_alpha_deployment_blend_weight'] = 0.0
        data['supervised_alpha_overlay_status'] = 'MISSING_PREDICTIONS'
        return data
    decision = acceptance_decision.loc[acceptance_decision['scope'].eq('overall')]
    blend = float(decision.iloc[0]['deployment_blend_weight']) if not decision.empty else 0.0
    status = str(decision.iloc[0]['status']) if not decision.empty else 'NOT_EVALUATED'
    prediction_columns = [
        'security_id',
        'predicted_benchmark_relative_return',
        'cost_adjusted_predicted_excess_return',
        'supervised_alpha_score',
        'no_trade_recommended',
    ]
    data = data.merge(
        primary[prediction_columns].drop_duplicates('security_id'),
        on='security_id',
        how='left',
        validate='one_to_one',
    )
    horizon = max(settings.primary_horizon_months, 1)
    predicted = pd.to_numeric(
        data['cost_adjusted_predicted_excess_return'], errors='coerce'
    ).fillna(0.0).clip(lower=-0.95)
    data['supervised_alpha_annualised_excess_return'] = (
        (1.0 + predicted) ** (12.0 / horizon) - 1.0
    )
    baseline = (
        pd.to_numeric(data['expected_total_return_12m'], errors='coerce').fillna(0.0)
        if 'expected_total_return_12m' in data
        else pd.Series(0.0, index=data.index)
    )
    region = data.get('region', pd.Series('Unknown', index=data.index)).fillna('Unknown')
    market_cap = (
        pd.to_numeric(data['market_cap_usd'], errors='coerce').fillna(0.0).clip(lower=0.0)
        if 'market_cap_usd' in data
        else pd.Series(0.0, index=data.index)
    )
    weighted_numerator = (baseline * market_cap).groupby(region, dropna=False).transform('sum')
    weighted_denominator = market_cap.groupby(region, dropna=False).transform('sum')
    regional_benchmark = (
        weighted_numerator / weighted_denominator.replace(0.0, np.nan)
    ).fillna(baseline.groupby(region, dropna=False).transform('median'))
    baseline_excess = baseline - regional_benchmark
    data['expected_total_return_12m_pre_supervised_alpha'] = baseline
    data['supervised_alpha_deployment_blend_weight'] = blend
    data['supervised_alpha_overlay_status'] = status
    blended_excess = (
        (1.0 - blend) * baseline_excess
        + blend * data['supervised_alpha_annualised_excess_return']
    )
    data['expected_total_return_12m'] = regional_benchmark + blended_excess
    return data


def run_supervised_alpha_research(
    feature_panel: pd.DataFrame,
    outcomes: pd.DataFrame,
    latest_features: pd.DataFrame,
    settings: SupervisedAlphaSettings,
) -> SupervisedAlphaResult:
    """Train, validate, freeze-test, and snapshot supervised alpha challengers."""

    dataset, numeric, categorical = build_supervised_alpha_dataset(
        feature_panel,
        outcomes,
        settings,
    )
    latest, _, _ = prepare_supervised_features(
        latest_features,
        numeric_features=DEFAULT_NUMERIC_FEATURES,
        categorical_features=DEFAULT_CATEGORICAL_FEATURES,
    )
    for column in numeric + categorical:
        if column not in latest:
            latest[column] = np.nan if column in numeric else 'Unknown'
    specs = build_candidate_specs(settings)
    specs_by_key = {spec.key: spec for spec in specs}

    validation_frames: list[pd.DataFrame] = []
    validation_monthly_frames: list[pd.DataFrame] = []
    screening_frames: list[pd.DataFrame] = []
    failure_frames: list[pd.DataFrame] = []
    validation_prediction_frames: list[pd.DataFrame] = []
    for horizon in settings.horizons_months:
        horizon_data = dataset.loc[dataset['horizon_months'].eq(horizon)].copy()
        LOGGER.info(
            'Validating supervised-alpha horizon=%sm rows=%s dates=%s candidates=%s.',
            horizon,
            len(horizon_data),
            horizon_data['as_of_date'].nunique(),
            len(specs),
        )
        checkpoint_signature = _validation_checkpoint_signature(
            horizon_data,
            settings,
            specs,
            horizon,
        )
        cached = (
            _load_validation_checkpoint(
                settings.checkpoint_directory,
                horizon,
                checkpoint_signature,
            )
            if settings.resume_checkpoints
            else None
        )
        if cached is not None:
            LOGGER.info('Loaded supervised-alpha %sm validation checkpoint.', horizon)
            summary, monthly, screening, failures, predictions = cached
        else:
            summary, monthly, screening, failures, predictions = _run_validation_horizon(
                horizon_data,
                numeric,
                categorical,
                specs,
                settings,
                horizon,
            )
            _write_validation_checkpoint(
                settings.checkpoint_directory,
                horizon,
                checkpoint_signature,
                (summary, monthly, screening, failures, predictions),
            )
        validation_frames.append(summary)
        validation_monthly_frames.append(monthly)
        screening_frames.append(screening)
        failure_frames.append(failures)
        validation_prediction_frames.append(predictions)
    validation_summary = pd.concat(validation_frames, ignore_index=True)
    family_winners = _family_winners(validation_summary)
    ensemble_weights = _ensemble_components(family_winners)
    validation_monthly = pd.concat(validation_monthly_frames, ignore_index=True)
    validation_predictions = (
        pd.concat(validation_prediction_frames, ignore_index=True)
        if validation_prediction_frames
        else pd.DataFrame()
    )
    ensemble_validation_rows: list[dict[str, Any]] = []
    ensemble_validation_monthly: list[pd.DataFrame] = []
    for horizon in settings.horizons_months:
        weights = ensemble_weights.loc[
            ensemble_weights['horizon_months'].eq(horizon)
        ]
        selected_keys = set(weights['candidate'])
        source = validation_predictions.loc[
            validation_predictions['horizon_months'].eq(horizon)
            & validation_predictions['candidate'].isin(selected_keys)
        ]
        ensemble = _combine_ensemble_predictions(
            source,
            weights,
            split='validation',
        )
        if ensemble.empty:
            continue
        metrics, monthly = evaluate_predictions(
            ensemble,
            settings,
            horizon_months=horizon,
        )
        ensemble_validation_rows.append(
            {
                'horizon_months': horizon,
                'candidate': 'supervised_alpha_ensemble',
                'family': 'ensemble',
                'category': 'ensemble',
                'folds': int(source.get('fold', pd.Series(dtype=str)).nunique()),
                'expected_folds': int(source.get('fold', pd.Series(dtype=str)).nunique()),
                'complete_validation': True,
                **metrics,
            }
        )
        monthly['candidate'] = 'supervised_alpha_ensemble'
        monthly['family'] = 'ensemble'
        monthly['split'] = 'validation'
        ensemble_validation_monthly.append(monthly)
    if ensemble_validation_rows:
        validation_summary = pd.concat(
            [validation_summary, pd.DataFrame(ensemble_validation_rows)],
            ignore_index=True,
        )
    if ensemble_validation_monthly:
        validation_monthly = pd.concat(
            [validation_monthly, *ensemble_validation_monthly],
            ignore_index=True,
        )
    ols_screening = pd.concat(screening_frames, ignore_index=True)
    failures = pd.concat(failure_frames, ignore_index=True) if any(not frame.empty for frame in failure_frames) else pd.DataFrame(
        columns=['horizon_months', 'split', 'fold', 'candidate', 'family', 'error']
    )

    oos_predictions_frames: list[pd.DataFrame] = []
    oos_summary_rows: list[dict[str, Any]] = []
    oos_monthly_frames: list[pd.DataFrame] = []
    quantile_rows: list[dict[str, Any]] = []
    final_model_state: dict[int, dict[str, Any]] = {}
    final_screening_frames: list[pd.DataFrame] = []

    for horizon in settings.horizons_months:
        horizon_data = dataset.loc[dataset['horizon_months'].eq(horizon)].copy()
        development = horizon_data.loc[
            horizon_data['target_date'].lt(settings.frozen_test_start)
            & horizon_data['as_of_date'].lt(settings.frozen_test_start)
        ].sort_values(['as_of_date', 'security_id'])
        oos = horizon_data.loc[
            horizon_data['as_of_date'].between(
                settings.frozen_test_start,
                settings.frozen_test_end,
            )
        ].sort_values(['as_of_date', 'security_id'])
        horizon_weights = ensemble_weights.loc[
            ensemble_weights['horizon_months'].eq(horizon)
        ].copy()
        selected_keys = horizon_weights['candidate'].tolist()
        if development.empty or oos.empty or not selected_keys:
            continue
        try:
            family_predictions, preprocessor, _, screening = _fit_selected_models(
                development,
                oos,
                numeric,
                categorical,
                specs_by_key,
                selected_keys,
                settings,
                horizon,
                'legacy_locked_oos',
            )
            ensemble = _combine_ensemble_predictions(
                family_predictions,
                horizon_weights,
                split='legacy_locked_oos',
            )
            combined = pd.concat([family_predictions, ensemble], ignore_index=True)
            oos_predictions_frames.append(combined)
            for candidate, candidate_predictions in combined.groupby('candidate', sort=True):
                metrics, monthly = evaluate_predictions(
                    candidate_predictions,
                    settings,
                    horizon_months=horizon,
                )
                first = candidate_predictions.iloc[0]
                oos_summary_rows.append(
                    {
                        'horizon_months': horizon,
                        'candidate': candidate,
                        'family': first['family'],
                        'category': first['category'],
                        **metrics,
                    }
                )
                monthly['candidate'] = candidate
                monthly['family'] = first['family']
                monthly['split'] = 'legacy_locked_oos'
                oos_monthly_frames.append(monthly)
            quantile_predictions, _ = _quantile_models(
                development,
                oos,
                numeric,
                categorical,
                settings,
            )
            quantile_rows.append(
                {
                    'horizon_months': horizon,
                    **_quantile_summary(quantile_predictions, 'legacy_locked_oos'),
                }
            )
            final_screening_frames.append(screening)
        except Exception as error:
            LOGGER.exception('Frozen OOS evaluation failed for horizon=%sm.', horizon)
            failures = pd.concat(
                [
                    failures,
                    pd.DataFrame(
                        [
                            {
                                'horizon_months': horizon,
                                'split': 'legacy_locked_oos',
                                'fold': 'frozen',
                                'candidate': 'selected_ensemble',
                                'family': 'ensemble',
                                'error': f'{type(error).__name__}: {error}',
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )

    oos_summary = pd.DataFrame(oos_summary_rows)
    oos_monthly = pd.concat(oos_monthly_frames, ignore_index=True) if oos_monthly_frames else pd.DataFrame()
    oos_predictions = pd.concat(oos_predictions_frames, ignore_index=True) if oos_predictions_frames else pd.DataFrame()
    quantile_metrics = pd.DataFrame(quantile_rows)
    generalisation_audit = _generalisation_audit(
        validation_summary,
        oos_summary,
    )
    evidence_modes = {
        str(value)
        for value in dataset.get('evidence_mode', pd.Series(dtype=str)).dropna().unique()
    }
    evidence_reasons = ['legacy_oos_exposed_to_research_iteration']
    if evidence_modes != {'native_live_oos'}:
        evidence_reasons.append('point_in_time_evidence_not_native_live')
    acceptance = _acceptance_decisions(
        oos_summary,
        settings,
        evidence_reasons=evidence_reasons,
    )

    latest_frames: list[pd.DataFrame] = []
    model_manifest_rows: list[dict[str, Any]] = []
    settings.model_directory.mkdir(parents=True, exist_ok=True)
    data_cutoff = pd.to_datetime(outcomes['outcome_date'], errors='coerce').max()
    for horizon in settings.horizons_months:
        horizon_data = dataset.loc[
            dataset['horizon_months'].eq(horizon)
            & dataset['target_date'].le(data_cutoff)
        ].sort_values(['as_of_date', 'security_id'])
        horizon_weights = ensemble_weights.loc[
            ensemble_weights['horizon_months'].eq(horizon)
        ].copy()
        selected_keys = horizon_weights['candidate'].tolist()
        if horizon_data.empty or not selected_keys:
            continue
        latest_horizon = latest.copy()
        latest_horizon['horizon_months'] = horizon
        latest_horizon['target_excess_return'] = 0.0
        latest_horizon['target_date'] = pd.NaT
        latest_horizon['realised_return'] = np.nan
        latest_horizon['peer_realised_benchmark_return'] = np.nan
        latest_horizon['estimated_one_way_cost_bps'] = _estimated_one_way_cost_bps(latest_horizon, settings)
        latest_horizon['row_id'] = (
            latest_horizon['security_id'].astype(str)
            + '|latest|'
            + str(horizon)
        )
        counts = max(len(latest_horizon), 1)
        latest_horizon['sample_weight'] = 1.0 / counts
        family_predictions, preprocessor, fitted, screening = _fit_selected_models(
            horizon_data,
            latest_horizon,
            numeric,
            categorical,
            specs_by_key,
            selected_keys,
            settings,
            horizon,
            'latest_refit',
        )
        ensemble = _combine_ensemble_predictions(
            family_predictions,
            horizon_weights,
            split='latest_refit',
        )
        quantiles, quantile_models = _quantile_models(
            horizon_data,
            latest_horizon,
            numeric,
            categorical,
            settings,
        )
        decision = acceptance.loc[acceptance['scope'].eq(f'{horizon}m')].iloc[0]
        latest_frames.append(
            _latest_prediction_output(
                latest_horizon,
                ensemble.set_index('row_id')['prediction'],
                quantiles,
                horizon,
                settings,
                float(decision['deployment_blend_weight']),
            )
        )
        screening['horizon_months'] = horizon
        screening['fold'] = 'latest_refit'
        final_screening_frames.append(screening)
        bundle_path = settings.model_directory / f'supervised_alpha_{horizon}m.joblib'
        joblib.dump(
            {
                'artifact_version': ARTIFACT_VERSION,
                'horizon_months': horizon,
                'trained_through_outcome_date': str(data_cutoff),
                'numeric_features': list(numeric),
                'categorical_features': list(categorical),
                'preprocessor': preprocessor,
                'fitted_candidates': fitted,
                'ensemble_weights': horizon_weights.to_dict(orient='records'),
                'quantile_models': quantile_models,
                'acceptance': decision.to_dict(),
            },
            bundle_path,
            compress=3,
        )
        final_model_state[horizon] = {'path': bundle_path, 'models': len(fitted)}
        model_manifest_rows.append(
            {
                'horizon_months': horizon,
                'model_path': str(bundle_path),
                'sha256': _file_sha256(bundle_path),
                'component_models': len(fitted),
                'trained_through_outcome_date': data_cutoff,
                'deployment_status': decision['status'],
                'deployment_blend_weight': decision['deployment_blend_weight'],
            }
        )

    if final_screening_frames:
        ols_screening = pd.concat(
            [ols_screening, *final_screening_frames],
            ignore_index=True,
        )
    profile_rows = []
    for horizon in settings.horizons_months:
        horizon_data = dataset.loc[dataset['horizon_months'].eq(horizon)]
        profile_rows.append(
            {
                'horizon_months': horizon,
                'rows': len(horizon_data),
                'securities': int(horizon_data['security_id'].nunique()),
                'decision_dates': int(horizon_data['as_of_date'].nunique()),
                'start_date': horizon_data['as_of_date'].min(),
                'end_date': horizon_data['as_of_date'].max(),
                'latest_target_date': horizon_data['target_date'].max(),
                'minimum_outcome_cross_section_coverage': float(
                    horizon_data['outcome_cross_section_coverage'].min()
                ),
                'median_outcome_cross_section_coverage': float(
                    horizon_data['outcome_cross_section_coverage'].median()
                ),
                'evidence_modes': ';'.join(
                    sorted(
                        str(value)
                        for value in horizon_data.get(
                            'evidence_mode', pd.Series(dtype=str)
                        ).dropna().unique()
                    )
                ),
                'numeric_features': len(numeric),
                'categorical_features': len(categorical),
            }
        )
    return SupervisedAlphaResult(
        dataset_profile=pd.DataFrame(profile_rows),
        validation_summary=validation_summary,
        family_winners=family_winners,
        ensemble_weights=ensemble_weights,
        validation_monthly=validation_monthly,
        oos_summary=oos_summary,
        oos_monthly=oos_monthly,
        oos_predictions=oos_predictions,
        ols_screening=ols_screening,
        quantile_metrics=quantile_metrics,
        generalisation_audit=generalisation_audit,
        latest_predictions=pd.concat(latest_frames, ignore_index=True) if latest_frames else pd.DataFrame(),
        acceptance_decision=acceptance,
        model_manifest=pd.DataFrame(model_manifest_rows),
        failures=failures,
    )
