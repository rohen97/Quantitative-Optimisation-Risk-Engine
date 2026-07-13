from src.pipeline import run_full_pipeline


def test_scorecard_ranking_and_hard_filters(tmp_path):
    scorecard = run_full_pipeline(tmp_path)["scorecard"]
    assert scorecard["final_recommendation_score"].is_monotonic_decreasing
    assert "passes_hard_filters" in scorecard.columns
    assert set(scorecard["recommendation"]).issubset({"Strong Buy / Core Income Holding", "Buy / Accumulate", "Watchlist", "Avoid", "Exclude"})
