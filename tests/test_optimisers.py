import pandas as pd

from src.optimisation.constraint_report import build_constraint_report
from src.optimisation.optimisers import cvar_constrained_portfolio, dividend_income_portfolio, risk_parity_portfolio, score_weighted_portfolio


def _data():
    rows = []
    for i in range(20):
        rows.append(
            {
                "ticker": f"T{i:02d}",
                "company_name": f"Company {i}",
                "country": f"C{i % 5}",
                "region": f"R{i % 4}",
                "sector": f"S{i % 5}",
                "currency": f"CUR{i % 4}",
                "current_weight": 0.0,
                "instrument_type": "Equity",
                "listing_status": "Active",
                "final_recommendation": "Buy",
                "final_recommendation_score": 90 - i,
                "portfolio_fit_score": 70,
                "regime_suitability_score": 70,
                "dividend_safety_score": 70,
                "cashflow_quality_score": 70,
                "balance_sheet_strength_score": 70,
                "expected_total_return_12m": 0.08,
                "expected_dividend_return_12m": 0.03,
                "expected_volatility_12m": 0.10 + i * 0.01,
                "var_5_12m": -0.10 - i * 0.005,
                "cvar_5_12m": -0.12 - i * 0.01,
                "expected_shortfall_5_12m": -0.12 - i * 0.01,
                "dividend_yield": 0.04 if i < 10 else 0.02,
                "dividend_cut_probability": 0.05 if i < 10 else 0.30,
                "large_drawdown_probability_12m": 0.10,
                "tail_risk_score": 20,
                "skewness_risk_score": 20,
                "forecast_uncertainty_score": 30,
                "liquidity_score": 80,
                "average_daily_value_usd": 10_000_000,
                "regime_exclusion_flag": False,
                "reframing_exclusion_flag": False,
                "alt_data_exclusion_flag": False,
                "regime_review_required_flag": False,
                "reframing_review_required_flag": False,
                "alt_data_review_required_flag": False,
            }
        )
    return pd.DataFrame(rows)


def test_score_weighted_weights_sum_and_respect_cap():
    portfolio = score_weighted_portfolio(_data(), {"max_single_name_weight": 0.05})
    assert round(portfolio["target_weight"].sum(), 6) == 1.0
    assert portfolio["target_weight"].max() <= 0.05 + 1e-9
    assert portfolio.loc[portfolio["ticker"].eq("T00"), "target_weight"].iloc[0] >= portfolio.loc[portfolio["ticker"].eq("T19"), "target_weight"].iloc[0]


def test_risk_parity_gives_lower_weight_to_high_volatility_stock():
    portfolio = risk_parity_portfolio(_data(), {"max_single_name_weight": 0.10})
    assert portfolio.loc[portfolio["ticker"].eq("T00"), "target_weight"].iloc[0] > portfolio.loc[portfolio["ticker"].eq("T19"), "target_weight"].iloc[0]


def test_cvar_and_dividend_optimisers_penalise_risky_names():
    data = _data()
    cvar = cvar_constrained_portfolio(data, {"max_single_name_weight": 0.10})
    income = dividend_income_portfolio(data, {"max_single_name_weight": 0.10})
    assert cvar.loc[cvar["ticker"].eq("T00"), "target_weight"].iloc[0] > cvar.loc[cvar["ticker"].eq("T19"), "target_weight"].iloc[0]
    assert income.loc[income["ticker"].eq("T00"), "target_weight"].iloc[0] > income.loc[income["ticker"].eq("T19"), "target_weight"].iloc[0]


def test_cross_listed_issuer_is_allocated_once():
    data = _data()
    data["issuer_id"] = [f"ISSUER-{i}" for i in range(len(data))]
    data.loc[[0, 1], "issuer_id"] = "DUPLICATE-ISSUER"
    portfolio = score_weighted_portfolio(data, {"max_single_name_weight": 0.10})
    invested = portfolio.loc[portfolio["target_weight"].gt(0)]
    assert invested["issuer_id"].is_unique


def test_turnover_limit_projects_from_feasible_current_weights():
    data = _data()
    data['current_weight'] = 0.0
    data.loc[data.index[10:], 'current_weight'] = 0.10

    portfolio = cvar_constrained_portfolio(
        data,
        {
            'max_single_name_weight': 0.10,
            'maximum_turnover': 0.10,
        },
    )

    turnover = 0.5 * (
        portfolio['target_weight'] - portfolio['current_weight']
    ).abs().sum()
    assert abs(portfolio['target_weight'].sum() - 1.0) < 1.0e-10
    assert turnover <= 0.10 + 1.0e-10
    assert portfolio['turnover_constraint_applied'].all()
    assert portfolio['optimisation_feasible'].all()


def test_retention_buffer_prevents_forced_exit_on_marginal_liquidity_move():
    data = _data()
    data.loc[data.index[10:], 'current_weight'] = 0.10
    data.loc[10, 'average_daily_value_usd'] = 4_500_000
    portfolio = cvar_constrained_portfolio(
        data,
        {
            'max_single_name_weight': 0.10,
            'minimum_average_daily_value_usd': 5_000_000,
            'maximum_turnover': 0.10,
            'retention_minimum_factor': 0.80,
        },
    )
    held = portfolio.loc[portfolio['ticker'].eq('T10')].iloc[0]
    assert bool(held['retention_eligible'])
    assert not bool(held['turnover_constraint_skipped_for_hard_exit'])
    assert portfolio['turnover_constraint_applied'].all()


def test_no_trade_band_keeps_feasible_current_portfolio():
    data = _data()
    data['current_weight'] = 0.05
    portfolio = cvar_constrained_portfolio(
        data,
        {
            'max_single_name_weight': 0.05,
            'maximum_turnover': 1.0,
            'minimum_rebalance_turnover': 1.0,
        },
    )
    assert portfolio['no_trade_band_applied'].all()
    assert portfolio['target_weight'].equals(portfolio['current_weight'])


def test_optimizer_holds_cash_when_country_caps_limit_equity_capacity():
    data = _data()
    data["country"] = ["US"] * 10 + ["UK"] * 4 + ["HK"] * 3 + ["CH"] * 2 + ["FR"]
    limits = {
        "max_single_name_weight": 0.05,
        "max_country_weight": 0.30,
        "maximum_cash_weight": 0.25,
    }
    portfolio = score_weighted_portfolio(data, limits)
    cash = portfolio.loc[portfolio["ticker"].eq("CASH"), "target_weight"].iloc[0]
    equities = portfolio.loc[~portfolio["ticker"].eq("CASH")]
    report = build_constraint_report(portfolio, limits)

    assert abs(float(portfolio["target_weight"].sum()) - 1.0) < 1e-9
    assert abs(float(cash) - 0.20) < 1e-9
    assert equities["target_weight"].max() <= 0.05 + 1e-9
    assert not report.loc[report["constraint_type"].eq("hard"), "breach_flag"].any()
