from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.config import load_yaml


@dataclass(frozen=True)
class DRLConfig:
    """Runtime settings for the bounded DRL allocation overlay."""

    enabled: bool = True
    mode: str = "mock"
    lookback_days: int = 60
    horizons_months: tuple[int, ...] = (3, 6, 9, 12)
    random_seeds: tuple[int, ...] = (7, 17, 29)
    max_adjustment: float = 0.015
    cash_weight: float = 0.02
    transaction_cost_bps: float = 12.0
    slippage_bps: float = 5.0
    market_impact_bps: float = 3.0
    liquidity_penalty_lambda: float = 0.10
    risk_aversion: float = 2.0
    drawdown_penalty_lambda: float = 0.50
    turnover_limit: float = 0.20
    train_fraction: float = 0.60
    validation_fraction: float = 0.20
    benchmark_method: str = "selected_classical_optimiser"


def _coalesce(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value is not None:
            return value
    return default


def normalize_drl_config(raw_config: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize structured DRL YAML into the flat runtime keys used by modules.

    The config file is intentionally grouped by model concern. Runtime modules
    still consume a small set of stable top-level aliases, so this function
    preserves the nested sections and adds those aliases in one place.
    """
    raw = dict(raw_config or {})
    defaults = DRLConfig()
    merged = defaults.__dict__.copy()
    merged.update(raw)

    role = raw.get("role", {}) or {}
    environment = raw.get("environment", {}) or {}
    action = raw.get("action", {}) or {}
    constraints = raw.get("constraints", {}) or {}
    costs = raw.get("transaction_costs", {}) or {}
    reward = raw.get("reward", {}) or {}
    risk_throttle = raw.get("risk_throttle", {}) or {}
    algorithms = raw.get("algorithms", {}) or {}
    ppo = raw.get("ppo", {}) or {}
    seeds = raw.get("seeds", {}) or {}
    training = raw.get("training", {}) or {}
    acceptance = raw.get("acceptance", {}) or {}

    decision_frequency = str(_coalesce(environment.get("decision_frequency"), raw.get("rebalance_frequency"), default="monthly"))
    monthly_delta = float(_coalesce(action.get("max_monthly_delta_weight"), raw.get("monthly_max_delta_weight"), default=0.01))
    quarterly_delta = float(_coalesce(action.get("max_quarterly_delta_weight"), raw.get("quarterly_max_delta_weight"), default=0.02))
    selected_delta = quarterly_delta if decision_frequency.lower() == "quarterly" else monthly_delta
    include_cash = bool(_coalesce(environment.get("include_cash"), default=True))
    cash_weight = float(
        _coalesce(
            raw.get("cash_weight"),
            constraints.get("minimum_cash_weight_normal"),
            default=0.02 if include_cash else 0.0,
        )
    )

    merged.update(
        {
            "enabled": bool(_coalesce(raw.get("enabled"), default=defaults.enabled)),
            "mode": str(_coalesce(raw.get("mode"), default=defaults.mode)),
            "allocation_mode": _coalesce(role.get("allocation_mode"), default="residual_overlay"),
            "deployment_mode": str(_coalesce(raw.get("deployment_mode"), default="blend")),
            "allow_full_drl_replacement": bool(_coalesce(role.get("allow_full_replacement"), raw.get("allow_full_drl_replacement"), default=False)),
            "maximum_drl_blend": float(_coalesce(role.get("maximum_drl_blend_weight"), raw.get("maximum_drl_blend"), default=0.25)),
            "blend_weight_drl": float(_coalesce(role.get("maximum_drl_blend_weight"), raw.get("blend_weight_drl"), default=0.25)),
            "baseline_blend_weight": float(_coalesce(role.get("baseline_blend_weight"), default=0.75)),
            "rebalance_frequency": decision_frequency,
            "monitoring_frequency": str(_coalesce(environment.get("monitoring_frequency"), default="daily")),
            "lookback_days": int(_coalesce(environment.get("temporal_lookback_days"), raw.get("lookback_days"), default=defaults.lookback_days)),
            "include_cash": include_cash,
            "cash_weight": cash_weight,
            "long_only": bool(_coalesce(environment.get("long_only"), default=True)),
            "leverage_allowed": bool(_coalesce(environment.get("leverage_allowed"), default=False)),
            "shorting_allowed": bool(_coalesce(environment.get("shorting_allowed"), default=False)),
            "risk_free_rate_annual": float(_coalesce(environment.get("risk_free_rate_annual"), raw.get("risk_free_rate_annual"), default=0.0)),
            "action_type": _coalesce(action.get("type"), default="residual_weight_adjustment"),
            "monthly_max_delta_weight": monthly_delta,
            "quarterly_max_delta_weight": quarterly_delta,
            "max_adjustment": float(_coalesce(raw.get("max_adjustment"), raw.get("max_delta_weight"), default=selected_delta)),
            "max_delta_weight": float(_coalesce(raw.get("max_delta_weight"), raw.get("max_adjustment"), default=selected_delta)),
            "use_softmax": bool(_coalesce(action.get("use_softmax"), default=False)),
            "use_constraint_projection": bool(_coalesce(action.get("use_constraint_projection"), default=True)),
            "maximum_assets": int(_coalesce(action.get("maximum_assets"), raw.get("maximum_assets"), default=100)),
            "turnover_limit": float(_coalesce(constraints.get("maximum_turnover_monthly"), raw.get("turnover_limit"), default=0.10)),
            "maximum_turnover": float(_coalesce(constraints.get("maximum_turnover_monthly"), raw.get("maximum_turnover"), default=0.10)),
            "annual_turnover_limit": float(_coalesce(constraints.get("maximum_turnover_annual"), default=0.35)),
            "minimum_model_confidence": float(_coalesce(raw.get("minimum_model_confidence"), default=0.50)),
            "model_confidence": float(_coalesce(raw.get("model_confidence"), default=0.75)),
            "weight_sum_tolerance": float(_coalesce(raw.get("weight_sum_tolerance"), default=1e-4)),
            "maximum_seed_instability_ratio": float(_coalesce(acceptance.get("maximum_seed_sharpe_std"), raw.get("maximum_seed_instability_ratio"), default=0.50)),
            "minimum_seed_stability_scale": float(_coalesce(raw.get("minimum_seed_stability_scale"), default=1e-8)),
            "validation_underperformance_tolerance": float(_coalesce(raw.get("validation_underperformance_tolerance"), default=0.0)),
            "test_leakage_detected": bool(_coalesce(raw.get("test_leakage_detected"), default=False)),
            "primary_algorithm": str(_coalesce(algorithms.get("primary"), raw.get("primary_algorithm"), default="ppo")).upper(),
            "fallback_policy": _coalesce(algorithms.get("fallback_policy"), default="deterministic_mock"),
            "random_seeds": tuple(_coalesce(seeds.get("values"), raw.get("random_seeds"), default=defaults.random_seeds)),
            "train_years": int(_coalesce(training.get("train_years"), raw.get("train_years"), default=5)),
            "validation_years": int(_coalesce(training.get("validation_years"), raw.get("validation_years"), default=1)),
            "test_years": int(_coalesce(training.get("test_years"), raw.get("test_years"), default=1)),
            "step_years": int(_coalesce(training.get("step_years"), raw.get("step_years"), default=1)),
            "embargo_periods": int(_coalesce(training.get("embargo_rebalance_periods"), raw.get("embargo_periods"), default=1)),
            "use_random_split": bool(_coalesce(training.get("use_random_split"), default=False)),
        }
    )

    merged["constraints"] = {
        **constraints,
        "max_single_name_weight": float(_coalesce(constraints.get("max_single_name_weight"), default=0.05)),
        "max_new_position_weight": float(_coalesce(constraints.get("max_new_position_weight"), default=0.03)),
        "max_sector_weight": float(_coalesce(constraints.get("max_sector_weight"), default=0.25)),
        "max_country_weight": float(_coalesce(constraints.get("max_country_weight"), default=0.30)),
        "max_region_weight": float(_coalesce(constraints.get("max_region_weight"), default=0.40)),
        "max_currency_weight": float(_coalesce(constraints.get("max_currency_weight"), default=0.40)),
        "minimum_liquidity_score": float(_coalesce(constraints.get("minimum_liquidity_score"), default=40)),
        "minimum_average_daily_value_usd": float(_coalesce(constraints.get("minimum_average_daily_value_usd"), default=5_000_000)),
        "maximum_portfolio_cvar_5": float(_coalesce(constraints.get("maximum_cvar_5"), constraints.get("maximum_portfolio_cvar_5"), default=-0.25)),
        "maximum_portfolio_expected_shortfall_5": float(
            _coalesce(constraints.get("maximum_expected_shortfall_5"), constraints.get("maximum_portfolio_expected_shortfall_5"), default=-0.25)
        ),
        "maximum_large_drawdown_probability": float(_coalesce(constraints.get("maximum_drawdown_probability"), default=0.35)),
        "maximum_turnover": merged["maximum_turnover"],
    }
    for key, value in merged["constraints"].items():
        if key not in merged:
            merged[key] = value

    merged["market_friction"] = {
        "enabled": bool(_coalesce(costs.get("enabled"), default=True)),
        "commission_bps": float(_coalesce(costs.get("commission_bps"), raw.get("transaction_cost_bps"), default=2.0)),
        "half_spread_bps": float(_coalesce(costs.get("half_spread_bps_default"), costs.get("half_spread_bps"), raw.get("slippage_bps"), default=5.0)),
        "impact_coefficient": float(
            _coalesce(costs.get("market_impact_coefficient_bps"), costs.get("impact_coefficient"), raw.get("market_impact_bps"), default=10.0)
        ),
        "currency_conversion_bps": float(_coalesce(costs.get("currency_conversion_bps"), default=2.0)),
        "missing_adv_usd": float(_coalesce(costs.get("missing_adv_usd"), constraints.get("minimum_average_daily_value_usd"), default=5_000_000)),
        "minimum_adv_usd": float(_coalesce(costs.get("minimum_adv_usd"), constraints.get("minimum_average_daily_value_usd"), default=5_000_000)),
        "max_participation_rate": float(_coalesce(costs.get("maximum_participation_rate"), costs.get("max_participation_rate"), default=0.05)),
        "enable_country_transaction_tax": bool(_coalesce(costs.get("enable_country_transaction_tax"), default=False)),
        "country_transaction_tax_bps": costs.get("country_transaction_tax_bps", {}),
    }
    merged["transaction_cost_bps"] = merged["market_friction"]["commission_bps"]
    merged["slippage_bps"] = merged["market_friction"]["half_spread_bps"]
    merged["market_impact_bps"] = merged["market_friction"]["impact_coefficient"]

    reward_weights = {
        "differential_sharpe": float(_coalesce(reward.get("differential_sharpe_weight"), default=0.30)),
        "net_total_return": float(_coalesce(reward.get("net_return_weight"), default=0.20)),
        "dividend_income": float(_coalesce(reward.get("dividend_income_weight"), default=0.10)),
        "regime_suitability_change": float(_coalesce(reward.get("regime_suitability_weight"), default=0.08)),
        "diversification_improvement": float(_coalesce(reward.get("diversification_weight"), default=0.07)),
        "quality_improvement": float(_coalesce(reward.get("quality_weight"), default=0.05)),
        "cvar_penalty": float(_coalesce(reward.get("cvar_penalty_weight"), default=0.10)),
        "drawdown_penalty": float(_coalesce(reward.get("drawdown_penalty_weight"), default=0.10)),
        "transaction_cost_penalty": float(_coalesce(reward.get("transaction_cost_penalty_weight"), default=0.07)),
        "turnover_penalty": float(_coalesce(reward.get("turnover_penalty_weight"), default=0.05)),
        "dividend_cut_risk_penalty": float(_coalesce(reward.get("dividend_cut_penalty_weight"), default=0.04)),
        "liquidity_penalty": float(_coalesce(reward.get("liquidity_penalty_weight"), default=0.04)),
        "narrative_credit_penalty": float(_coalesce(reward.get("narrative_credit_penalty_weight"), default=0.03)),
        "stress_loss_penalty": float(_coalesce(reward.get("stress_loss_penalty_weight"), default=0.02)),
    }
    if "weights" in reward:
        reward_weights.update({key: float(value) for key, value in reward["weights"].items()})
    merged["reward"] = {**reward, "weights": reward_weights}

    merged["ppo"] = {
        **ppo,
        "policy": str(_coalesce(ppo.get("policy"), default="MlpPolicy")),
        "use_stable_baselines": bool(_coalesce(ppo.get("use_stable_baselines"), algorithms.get("use_stable_baselines3_if_available"), default=False)),
        "total_timesteps": int(_coalesce(ppo.get("total_timesteps"), ppo.get("total_timesteps_mock"), default=2048)),
        "minimum_random_seeds": int(_coalesce(ppo.get("minimum_random_seeds"), default=5)),
        "deterministic_evaluation": bool(_coalesce(ppo.get("deterministic_evaluation"), default=True)),
    }

    merged["risk_throttle"] = {
        **risk_throttle,
        "normal_minimum_cash_weight": float(_coalesce(risk_throttle.get("normal_minimum_cash_weight"), constraints.get("minimum_cash_weight_normal"), default=0.0)),
        "elevated_minimum_cash_weight": float(
            _coalesce(risk_throttle.get("elevated_minimum_cash_weight"), constraints.get("minimum_cash_weight_stress"), default=0.05)
        ),
        "severe_minimum_cash_weight": float(
            _coalesce(risk_throttle.get("severe_minimum_cash_weight"), constraints.get("minimum_cash_weight_stress"), default=0.05)
        ),
        "extreme_minimum_cash_weight": float(_coalesce(risk_throttle.get("extreme_minimum_cash_weight"), default=0.20)),
    }
    return merged


def load_drl_config(path: str | Path = "configs/drl.yaml") -> dict[str, Any]:
    """Load DRL config and return a plain dictionary with defaults applied."""
    loaded = load_yaml(path)
    raw = loaded.get("drl", loaded)
    return normalize_drl_config(raw)
