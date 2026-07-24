from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def _unavailable(output_path: Path, title: str) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(8, 4))
    axis.text(0.5, 0.5, "Data unavailable", ha="center", va="center")
    axis.set_title(title)
    axis.set_axis_off()
    figure.tight_layout()
    figure.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(figure)
    return output_path


def save_current_vs_target_chart(data: pd.DataFrame, output_path: Path, top_n: int = 15) -> Path:
    required = {"ticker", "current_weight", "target_weight"}
    if data.empty or not required.issubset(data.columns):
        return _unavailable(output_path, "Current versus target portfolio weights")
    plot_data = data.copy()
    plot_data["maximum_weight"] = plot_data[["current_weight", "target_weight"]].max(axis=1)
    plot_data = plot_data.nlargest(top_n, "maximum_weight").sort_values("target_weight", ascending=True)
    figure, axis = plt.subplots(figsize=(11, 7))
    positions = range(len(plot_data))
    axis.barh(positions, plot_data["current_weight"], height=0.35, label="Current")
    axis.barh([position + 0.35 for position in positions], plot_data["target_weight"], height=0.35, label="Target")
    axis.set_yticks([position + 0.175 for position in positions])
    axis.set_yticklabels(plot_data["ticker"].astype(str), fontsize=8)
    axis.set_xlabel("Portfolio weight")
    axis.set_title("Current versus target portfolio weights")
    axis.legend()
    axis.grid(axis="x", alpha=0.25)
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(figure)
    return output_path


def _bar(data: pd.DataFrame, output_path: Path, x: str, y: str, title: str, ylabel: str = "Value", horizontal: bool = False) -> Path:
    if data.empty or x not in data or y not in data:
        return _unavailable(output_path, title)
    plot_data = data.copy()
    plot_data[y] = pd.to_numeric(plot_data[y], errors="coerce").fillna(0.0)
    plot_data = plot_data.sort_values(y).tail(15)
    figure, axis = plt.subplots(figsize=(10, 5))
    if horizontal:
        axis.barh(plot_data[x].astype(str), plot_data[y])
        axis.set_xlabel(ylabel)
    else:
        axis.bar(plot_data[x].astype(str), plot_data[y])
        axis.set_ylabel(ylabel)
        axis.tick_params(axis="x", rotation=35, labelsize=8)
    axis.set_title(title)
    axis.grid(axis="y" if not horizontal else "x", alpha=0.25)
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(figure)
    return output_path


def _scatter(data: pd.DataFrame, output_path: Path, x: str, y: str, title: str) -> Path:
    if data.empty or x not in data or y not in data:
        return _unavailable(output_path, title)
    figure, axis = plt.subplots(figsize=(8, 5))
    axis.scatter(pd.to_numeric(data[x], errors="coerce"), pd.to_numeric(data[y], errors="coerce"), alpha=0.75)
    axis.set_xlabel(x)
    axis.set_ylabel(y)
    axis.set_title(title)
    axis.grid(alpha=0.25)
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(figure)
    return output_path


def _matrix(data: pd.DataFrame, output_path: Path, title: str) -> Path:
    if data.empty:
        return _unavailable(output_path, title)
    categorical = data.select_dtypes(exclude="number").head(20)
    if categorical.empty:
        return _unavailable(output_path, title)
    counts = categorical.apply(lambda col: col.astype(str)).melt()["value"].value_counts().head(12)
    return _bar(counts.rename_axis("category").reset_index(name="count"), output_path, "category", "count", title, "Count", horizontal=True)


def build_charts(context: dict[str, object], output_dir: Path, chart_format: str = "png") -> dict[str, Path]:
    charts_dir = output_dir / "charts"
    holdings = context.get("current_vs_target_holdings", pd.DataFrame())
    sector = context.get("sector_exposures", pd.DataFrame())
    country = context.get("country_exposures", pd.DataFrame())
    region = context.get("region_exposures", pd.DataFrame())
    currency = context.get("currency_exposures", pd.DataFrame())
    concentration = context.get("concentration_summary", pd.DataFrame())
    forecasts = context.get("forecast_horizon_summary", pd.DataFrame())
    security_forecasts = context.get("security_forecast_summary", pd.DataFrame())
    regime = context.get("regime_summary_table", pd.DataFrame())
    risk = context.get("top_risk_contributors_table", pd.DataFrame())
    stress = context.get("stress_scenario_summary", pd.DataFrame())
    branch = context.get("model_branch_comparison", pd.DataFrame())
    drl = context.get("drl_constraint_trace", pd.DataFrame())
    reward = context.get("drl_reward_decomposition", pd.DataFrame())
    trades = context.get("final_trade_recommendations", pd.DataFrame())
    charts = {
        "current_vs_target_top_holdings": save_current_vs_target_chart(holdings, charts_dir / f"current_vs_target_top_holdings.{chart_format}"),
        "portfolio_concentration": _bar(concentration, charts_dir / f"portfolio_concentration.{chart_format}", "maximum_single_name_weight", "hhi", "Portfolio concentration", "HHI"),
        "sector_exposure_current_vs_target": _bar(sector, charts_dir / f"sector_exposure_current_vs_target.{chart_format}", "sector", "target_weight", "Sector target exposure", "Weight"),
        "country_exposure_current_vs_target": _bar(country, charts_dir / f"country_exposure_current_vs_target.{chart_format}", "country", "target_weight", "Country target exposure", "Weight"),
        "region_exposure_current_vs_target": _bar(region, charts_dir / f"region_exposure_current_vs_target.{chart_format}", "region", "target_weight", "Region target exposure", "Weight"),
        "currency_exposure_current_vs_target": _bar(currency, charts_dir / f"currency_exposure_current_vs_target.{chart_format}", "currency", "target_weight", "Currency target exposure", "Weight"),
        "forecast_horizon_summary": _bar(forecasts, charts_dir / f"forecast_horizon_summary.{chart_format}", "horizon", "weighted_expected_total_return", "Forecast horizon summary", "Return"),
        "expected_return_vs_cvar": _scatter(security_forecasts, charts_dir / f"expected_return_vs_cvar.{chart_format}", "expected_total_return", "cvar_5", "Expected return versus CVaR"),
        "dividend_yield_vs_dividend_risk": _scatter(security_forecasts, charts_dir / f"dividend_yield_vs_dividend_risk.{chart_format}", "expected_dividend_return", "dividend_cut_probability", "Dividend yield versus dividend risk"),
        "regime_probabilities": _matrix(regime, charts_dir / f"regime_probabilities.{chart_format}", "Regime probabilities"),
        "wolf_chaos_history": _bar(regime, charts_dir / f"wolf_chaos_history.{chart_format}", "dominant_regime", "wolf_chaos_index", "Wolf Chaos history", "Index"),
        "top_risk_contributors": _bar(risk, charts_dir / f"top_risk_contributors.{chart_format}", "ticker", risk.select_dtypes(include="number").columns[0] if not risk.empty and not risk.select_dtypes(include="number").empty else "missing", "Top risk contributors", "Contribution", horizontal=True),
        "stress_test_losses": _bar(stress, charts_dir / f"stress_test_losses.{chart_format}", "scenario_name", "portfolio_loss_percentage", "Stress test losses", "Loss"),
        "branch_weight_comparison": _bar(branch, charts_dir / f"branch_weight_comparison.{chart_format}", "ticker", "final_weight", "Branch weight comparison", "Weight"),
        "recommendation_matrix": _matrix(branch, charts_dir / f"recommendation_matrix.{chart_format}", "Recommendation matrix"),
        "drl_baseline_vs_projected": _bar(drl, charts_dir / f"drl_baseline_vs_projected.{chart_format}", "ticker", "projected_drl_weight", "DRL baseline versus projected", "Weight"),
        "drl_reward_decomposition": _matrix(reward, charts_dir / f"drl_reward_decomposition.{chart_format}", "DRL reward decomposition"),
        "trade_notional_by_action": _bar(trades.groupby("trade_action", dropna=False)["trade_notional_usd"].sum().abs().reset_index() if not trades.empty and "trade_action" in trades else pd.DataFrame(), charts_dir / f"trade_notional_by_action.{chart_format}", "trade_action", "trade_notional_usd", "Trade notional by action", "USD"),
    }
    charts["final_weights"] = charts["current_vs_target_top_holdings"]
    charts["stress_losses"] = charts["stress_test_losses"]
    return charts
