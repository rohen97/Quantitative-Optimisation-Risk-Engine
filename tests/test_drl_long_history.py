from __future__ import annotations

import numpy as np
import pandas as pd

from src.drl.long_history import (
    build_long_history_regional_panel,
    convert_regional_benchmarks_to_usd,
    point_in_time_macro_features,
    splice_benchmark_prehistory,
)
from src.drl.regional_ppo import (
    REGIONAL_FEATURES,
    REGIONAL_SLEEVES,
    block_bootstrap_regional_panel,
    load_and_combine_regional_history,
)


def _regional_bars(periods: int = 72) -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    dates = pd.date_range("1993-01-31", periods=periods, freq="ME")
    rows = []
    definitions = {}
    for region_index, region in enumerate(REGIONAL_SLEEVES):
        symbol = f"IDX{region_index}"
        definitions[region] = {"symbol": symbol, "currency": "USD"}
        for position, date in enumerate(dates):
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "adjusted_close": 100.0 * (1.0 + 0.004 + region_index * 0.0005) ** position,
                    "volume": 1_000_000 + region_index * 100_000,
                }
            )
    return pd.DataFrame(rows), definitions


def test_long_history_panel_builds_complete_usd_regional_months():
    bars, definitions = _regional_bars()
    usd = convert_regional_benchmarks_to_usd(
        bars,
        pd.DataFrame(),
        definitions,
        {},
    )
    panel = build_long_history_regional_panel(
        usd,
        pd.DataFrame(),
        start_date="1997-01-31",
    )
    assert not panel.empty
    assert set(panel["sleeve"]) == set(REGIONAL_SLEEVES)
    assert panel.groupby("date")["sleeve"].nunique().eq(len(REGIONAL_SLEEVES)).all()
    assert np.allclose(panel.groupby("date")["baseline_weight"].sum(), 1.0)
    assert panel["panel_source"].eq("public_regional_benchmark_proxy").all()
    assert panel["forward_return"].notna().all()


def test_macro_features_use_only_vintages_available_at_decision_time():
    vintages = pd.DataFrame(
        {
            "series_id": ["DFF", "DFF"],
            "observation_date": ["2000-01-31", "2000-01-31"],
            "available_from": ["2000-02-01", "2000-04-01"],
            "value": [1.0, 2.0],
        }
    )
    features = point_in_time_macro_features(
        vintages,
        pd.DatetimeIndex(["2000-03-31", "2000-04-30"]),
    )
    assert features.loc[0, "macro_policy_rate"] == 1.0
    assert features.loc[1, "macro_policy_rate"] == 2.0


def test_prehistory_splice_preserves_fallback_returns_and_primary_rows():
    bars = pd.DataFrame(
        {
            "date": pd.to_datetime(["1997-01-31", "1997-02-28", "1997-03-31", "1997-04-30"]),
            "symbol": ["FALLBACK", "FALLBACK", "PRIMARY", "PRIMARY"],
            "adjusted_close": [100.0, 110.0, 220.0, 242.0],
            "volume": [1.0, 1.0, 2.0, 2.0],
        }
    )
    spliced, manifest = splice_benchmark_prehistory(
        bars,
        primary_symbol="PRIMARY",
        fallback_symbol="FALLBACK",
    )
    history = spliced.loc[spliced["symbol"].eq("PRIMARY")].sort_values("date")
    assert np.isclose(history.iloc[1]["adjusted_close"] / history.iloc[0]["adjusted_close"] - 1.0, 0.10)
    assert history.iloc[2]["adjusted_close"] == 220.0
    assert manifest["applied"] is True


def _panel(start: str, periods: int, source: str) -> pd.DataFrame:
    rows = []
    for date in pd.date_range(start, periods=periods, freq="ME"):
        for sleeve in REGIONAL_SLEEVES:
            row = {
                "date": date,
                "sleeve": sleeve,
                "baseline_weight": 1.0 / len(REGIONAL_SLEEVES),
                "forward_return": 0.01,
                "panel_source": source,
            }
            row.update({feature: 0.0 for feature in REGIONAL_FEATURES})
            rows.append(row)
    return pd.DataFrame(rows)


def test_long_history_enriches_but_never_replaces_overlapping_walk_forward_rows(tmp_path):
    long_panel = _panel("2018-01-31", 36, "public_regional_benchmark_proxy")
    long_panel["macro_policy_rate"] = 3.25
    path = tmp_path / "regional.parquet"
    long_panel.to_parquet(path, index=False)
    walk = _panel("2019-01-31", 24, "walk_forward_stock_portfolio")
    walk["forward_return"] = 0.02
    combined = load_and_combine_regional_history(
        walk,
        {"long_history": {"enabled": True, "panel_path": str(path)}},
    )
    overlap = combined.loc[combined["date"].eq(pd.Timestamp("2019-01-31"))]
    assert overlap["panel_source"].eq("walk_forward_stock_portfolio").all()
    assert overlap["forward_return"].eq(0.02).all()
    assert overlap["macro_policy_rate"].eq(3.25).all()
    assert len(overlap) == len(REGIONAL_SLEEVES)


def test_block_bootstrap_samples_training_dates_only():
    train = _panel("2000-01-31", 60, "training")
    bootstrapped = block_bootstrap_regional_panel(
        train,
        block_length=12,
        periods=48,
        seed=17,
    )
    assert bootstrapped["date"].nunique() == 48
    assert set(bootstrapped["bootstrap_source_date"]).issubset(set(train["date"]))
    assert bootstrapped.groupby("date")["sleeve"].nunique().eq(len(REGIONAL_SLEEVES)).all()
