import pandas as pd

from src.optimisation.optimiser_inputs import build_optimiser_input_dataset, load_optimiser_input_dataset


def test_optimiser_input_dataset_is_created_with_fallbacks():
    scorecard = pd.DataFrame(
        {
            "ticker": ["AAA"],
            "final_recommendation_score": [70],
            "recommendation": ["Buy / Accumulate"],
            "dividend_yield": [0.04],
        }
    )
    dataset = build_optimiser_input_dataset(scorecard)
    assert dataset.shape[0] == 1
    assert "expected_total_return_12m" in dataset.columns
    assert dataset["expected_total_return_12m"].iloc[0] == 0.05


def test_missing_input_files_return_empty_dataset(tmp_path):
    dataset = load_optimiser_input_dataset(tmp_path)
    assert dataset.empty
