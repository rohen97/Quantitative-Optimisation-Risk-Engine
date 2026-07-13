from src.pipeline import run_full_pipeline
from src.models.scorecard import build_scorecard


def test_scorecard_ranking_and_hard_filters(tmp_path):
    scorecard = run_full_pipeline(tmp_path)["scorecard"]
    assert scorecard["final_recommendation_score"].is_monotonic_decreasing
    assert "passes_hard_filters" in scorecard.columns
    assert set(scorecard["recommendation"]).issubset({"Strong Buy / Core Income Holding", "Buy / Accumulate", "Watchlist", "Avoid", "Exclude"})


def test_hard_filters_exclude_unsafe_securities(tmp_path):
    features = run_full_pipeline(tmp_path)["features"].copy()
    features.loc[features.index[0], "instrument_type"] = "ETF"
    features.loc[features.index[1], "market_cap_usd"] = 1
    features.loc[features.index[2], "free_cash_flow"] = -1
    scorecard = build_scorecard(features)
    excluded = scorecard.set_index("ticker")
    assert not excluded.loc[features.loc[features.index[0], "ticker"], "passes_hard_filters"]
    assert not excluded.loc[features.loc[features.index[1], "ticker"], "passes_hard_filters"]
    assert not excluded.loc[features.loc[features.index[2], "ticker"], "passes_hard_filters"]
