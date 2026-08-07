import pandas as pd

from src.validation.validation_pipeline import _weight_column


def test_validation_uses_accepted_drl_weights_before_raw_challenger_weights():
    frame = pd.DataFrame(
        {
            "target_weight": [0.45, 0.50],
            "accepted_target_weight": [0.50, 0.50],
        }
    )
    assert _weight_column(frame) == "accepted_target_weight"
