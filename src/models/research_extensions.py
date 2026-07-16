from __future__ import annotations

import pandas as pd


SUPPORTED_RESEARCH_ASSET_CLASSES = ["listed_equity", "equity_index", "rates", "fx", "commodities", "credit"]
FUTURE_ARCHITECTURES = ["cnn_1d", "lstm", "transformer_encoder", "xlstm"]


def list_research_extension_points() -> pd.DataFrame:
    """Document inactive extension points inspired by distributional forecasting research."""
    return pd.DataFrame(
        [
            {
                "extension_area": "asset_classes",
                "status": "placeholder",
                "supported_values": ", ".join(SUPPORTED_RESEARCH_ASSET_CLASSES),
                "notes": "Only listed equities are active in the current Wolf model.",
            },
            {
                "extension_area": "deep_architectures",
                "status": "placeholder",
                "supported_values": ", ".join(FUTURE_ARCHITECTURES),
                "notes": "TensorFlow/PyTorch are not hard dependencies; architectures are disabled by default.",
            },
            {
                "extension_area": "quantile_forecasting",
                "status": "placeholder",
                "supported_values": "quantile_regression, conformal_prediction, quantile_neural_networks",
                "notes": "Current quantiles are derived from distribution parameters.",
            },
            {
                "extension_area": "trading_strategy_research",
                "status": "placeholder",
                "supported_values": "distribution_score, tail_adjusted_expected_return, risk_budget_signal",
                "notes": "Research-only signal scaffolding; no automated trading or DRL is implemented.",
            },
        ]
    )


def run_distribution_sensitivity_analysis(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Measure sensitivity of distributional risk to tail thickness and skewness assumptions."""
    data = forecasts.copy()
    if "ticker" not in data:
        return pd.DataFrame()
    nu = data.get("distribution_nu_12m", pd.Series(8, index=data.index)).fillna(8)
    xi = data.get("distribution_xi_12m", pd.Series(1, index=data.index)).fillna(1)
    sigma = data.get("distribution_sigma_12m", data.get("expected_volatility_12m", pd.Series(0.2, index=data.index))).fillna(0.2)
    return pd.DataFrame(
        {
            "ticker": data["ticker"],
            "nu_minus_25pct_tail_risk_delta": ((6 - nu * 0.75).clip(lower=0) - (6 - nu).clip(lower=0)).clip(lower=0),
            "nu_plus_25pct_tail_risk_delta": ((6 - nu * 1.25).clip(lower=0) - (6 - nu).clip(lower=0)),
            "xi_downside_skew_delta": ((1 - xi * 0.75).clip(lower=0) - (1 - xi).clip(lower=0)).clip(lower=0),
            "sigma_plus_25pct_var_delta": sigma * 0.25 * 1.65,
            "sensitivity_commentary": "Mock sensitivity checks tail thickness, skewness and volatility shocks.",
        }
    )


def build_distribution_trading_research_signals(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Create research-only signals from forecasted distributions; not an execution engine."""
    data = forecasts.copy()
    if "ticker" not in data:
        return pd.DataFrame()
    expected = data.get("expected_total_return_12m", pd.Series(0, index=data.index)).fillna(0)
    cvar = data.get("cvar_5_12m", pd.Series(-0.12, index=data.index)).fillna(-0.12)
    confidence = data.get("distribution_model_confidence", pd.Series(70, index=data.index)).fillna(70)
    tail = data.get("tail_risk_score", pd.Series(50, index=data.index)).fillna(50)
    score = (50 + 160 * expected + 80 * cvar + 0.20 * confidence - 0.20 * tail).clip(0, 100)
    return pd.DataFrame(
        {
            "ticker": data["ticker"],
            "distribution_research_signal_score": score,
            "research_signal": pd.cut(score, bins=[-1, 35, 55, 70, 101], labels=["avoid_research", "neutral_research", "constructive_research", "high_conviction_research"]),
            "research_only_flag": True,
            "signal_commentary": "Distribution-derived research signal only; not an automated trading instruction.",
        }
    )
