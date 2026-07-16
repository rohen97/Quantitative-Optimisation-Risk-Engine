from __future__ import annotations

import json


def build_model_validation_report(metrics_by_horizon: dict[int, dict[str, float]], feature_groups: dict[str, list[str]]) -> str:
    """Build the markdown model validation report for the mock ML forecasting engine."""
    lines = [
        "# Model Validation Report",
        "",
        "## Model Summary",
        "Deterministic mock ML Forecasting & Return Distribution Engine for conservative equity selection.",
        "The distribution layer is inspired by probabilistic return forecasting research that predicts distribution parameters rather than only point returns.",
        "",
        "## Data Mode",
        "mock / dry-run. No real APIs, paid data, OpenAI or Claude calls are used.",
        "",
        "## Feature Groups Used",
    ]
    for group, columns in feature_groups.items():
        lines.append(f"- {group}: {', '.join(columns) if columns else 'not available in current run'}")
    lines.extend(
        [
            "",
            "## Targets Used",
            "Forward total return, price return, dividend return, volatility, max drawdown, dividend-cut event and large-drawdown event for 3M, 6M, 9M and 12M horizons.",
            "",
            "## Validation Method",
            "Walk-forward-ready chronological validation interfaces. No random train-test split is used. The report includes proxy placeholders for probabilistic metrics such as Log Predictive Score, CRPS, PIT calibration and VaR exceedance rates.",
            "",
            "## Metrics By Horizon",
        ]
    )
    for horizon, metrics in metrics_by_horizon.items():
        lines.append(f"- {horizon}M: `{json.dumps(metrics, sort_keys=True)}`")
    lines.extend(
        [
            "",
            "## Leakage Controls",
            "- Forecast feature matrix drops all `forward_*` target columns.",
            "- Target generation uses future windows only for labels, not features.",
            "- Walk-forward split preserves time ordering and supports embargo periods.",
            "- Filing-date awareness is reserved for future real fundamental history.",
            "",
            "## Known Limitations",
            "- Current engine uses deterministic mock/fallback models, not trained production models.",
            "- The current skewed Student-t distribution parameters are rule-based proxies, not neural-network outputs optimized by negative log likelihood.",
            "- No real vendor history, corporate action feed or full point-in-time fundamentals are connected.",
            "- Quantile bands use volatility and uncertainty fallbacks rather than conformal prediction.",
            "",
            "## Next Improvements",
            "Add real historical data, CNN/LSTM distributional models, negative-log-likelihood training for Normal/Student-t/skewed-Student-t parameters, purged cross-validation, conformal prediction, XGBoost/LightGBM, Bayesian models, richer dividend-risk classifiers and MLflow registry integration.",
            "",
        ]
    )
    return "\n".join(lines)
