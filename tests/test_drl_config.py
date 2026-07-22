from src.drl.config import load_drl_config, normalize_drl_config


def test_structured_drl_config_loads_with_runtime_aliases():
    config = load_drl_config()

    assert config["role"]["allocation_mode"] == "residual_overlay"
    assert config["environment"]["decision_frequency"] == "monthly"
    assert config["action"]["max_monthly_delta_weight"] == 0.01
    assert config["lookback_days"] == 60
    assert config["rebalance_frequency"] == "monthly"
    assert config["max_adjustment"] == 0.01
    assert config["max_delta_weight"] == 0.01
    assert config["random_seeds"] == (11, 23, 37, 53, 71)
    assert config["maximum_drl_blend"] == 0.25
    assert config["blend_weight_drl"] == 0.25
    assert not config["allow_full_drl_replacement"]


def test_structured_drl_config_maps_cost_reward_and_acceptance_aliases():
    config = load_drl_config()

    assert config["market_friction"]["commission_bps"] == 2.0
    assert config["market_friction"]["half_spread_bps"] == 5.0
    assert config["market_friction"]["impact_coefficient"] == 10.0
    assert config["market_friction"]["max_participation_rate"] == 0.05
    assert config["reward"]["weights"]["differential_sharpe"] == 0.30
    assert config["reward"]["weights"]["net_total_return"] == 0.20
    assert config["reward"]["weights"]["dividend_cut_risk_penalty"] == 0.04
    assert config["maximum_seed_instability_ratio"] == 0.50
    assert config["constraints"]["maximum_portfolio_cvar_5"] == -0.25
    assert config["constraints"]["maximum_portfolio_expected_shortfall_5"] == -0.25


def test_normalize_drl_config_preserves_inline_flat_overrides():
    config = normalize_drl_config(
        {
            "random_seeds": (1, 2),
            "max_adjustment": 0.03,
            "lookback_days": 10,
            "cash_weight": 0.01,
            "deployment_mode": "reject",
        }
    )

    assert config["random_seeds"] == (1, 2)
    assert config["max_adjustment"] == 0.03
    assert config["lookback_days"] == 10
    assert config["cash_weight"] == 0.01
    assert config["deployment_mode"] == "reject"
