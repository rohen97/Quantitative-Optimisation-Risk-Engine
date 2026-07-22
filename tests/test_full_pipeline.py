from pathlib import Path

from src.pipeline import run_full_pipeline


def test_full_pipeline_with_mock_data(tmp_path):
    outputs = run_full_pipeline(tmp_path)
    assert outputs["scorecard"].shape[0] > 0
    assert "sentiment_alt_data_score" in outputs["scorecard"].columns
    assert "alt_data_review_required_flag" in outputs["scorecard"].columns
    assert (Path(tmp_path) / "features_monthly.csv").exists()
    assert (Path(tmp_path) / "alt_features_monthly.csv").exists()
    assert (Path(tmp_path) / "alt_event_signals.csv").exists()
    assert (Path(tmp_path) / "stock_scorecard.csv").exists()
    assert (Path(tmp_path) / "recommendations_12m.csv").exists()
    assert (Path(tmp_path) / "model_validation_report.md").exists()
    assert (Path(tmp_path) / "drl_baseline_portfolio.csv").exists()
    assert (Path(tmp_path) / "drl_challenger_portfolio.csv").exists()
    assert (Path(tmp_path) / "drl_final_selected_weights_source.csv").exists()
    assert "drl_challenger_status" in outputs["final_recommendations"].columns
    assert "final_selected_weights_source" in outputs["final_recommendations"].columns
    assert "final_selected_weight" in outputs["final_recommendations"].columns
    assert "final_target_weight" in outputs["final_recommendations"].columns
