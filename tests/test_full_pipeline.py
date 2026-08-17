from pathlib import Path

import pandas as pd

from src.pipeline import attach_drl_challenger_status, run_full_pipeline
from src.optimisation.portfolio_builder import build_final_portfolio_weights


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


def test_drl_selected_weights_zero_names_outside_challenger():
    recommendations = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB", "CCC"],
            "final_target_weight": [0.2, 0.3, 0.0],
        }
    )
    drl_outputs = {
        "drl_challenger_portfolio": pd.DataFrame(
            {
                "ticker": ["AAA", "CCC"],
                "accepted_target_weight": [0.6, 0.4],
            }
        ),
        "drl_acceptance_decision": pd.DataFrame(
            [{"accepted": False, "selected_weights_source": "baseline_optimiser"}]
        ),
    }

    result = attach_drl_challenger_status(recommendations, drl_outputs)

    assert result["final_selected_weight"].tolist() == [0.6, 0.0, 0.4]
    assert result["final_selected_weight"].sum() == 1.0


def test_drl_selected_weights_append_baseline_names_missing_from_recommendations():
    recommendations = pd.DataFrame(
        {"ticker": ["AAA"], "final_target_weight": [1.0]}
    )
    drl_outputs = {
        "drl_challenger_portfolio": pd.DataFrame(
            {
                "ticker": ["AAA", "BBB"],
                "accepted_target_weight": [0.6, 0.4],
            }
        ),
        "drl_acceptance_decision": pd.DataFrame(
            [{"accepted": False, "selected_weights_source": "baseline_optimiser"}]
        ),
    }

    result = attach_drl_challenger_status(recommendations, drl_outputs)

    assert set(result["ticker"]) == {"AAA", "BBB"}
    assert result["final_selected_weight"].sum() == 1.0


def test_final_portfolio_materialises_explicit_cash_residual():
    recommendations = pd.DataFrame(
        {"ticker": ["AAA", "BBB"], "final_selected_weight": [0.6, 0.3]}
    )
    optimiser = pd.DataFrame(
        {
            "security_id": ["A", "B"],
            "ticker": ["AAA", "BBB"],
            "company_name": ["A", "B"],
        }
    )
    result = build_final_portfolio_weights(recommendations, optimiser)
    assert result["target_weight"].sum() == 1.0
    cash_weight = result.loc[result["ticker"].eq("CASH"), "target_weight"].iloc[0]
    assert abs(cash_weight - 0.1) < 1e-12
