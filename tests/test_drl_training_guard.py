from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.drl.training import run_seed_training


def test_historical_drl_fails_closed_without_training_evidence() -> None:
    assets = pd.DataFrame(
        {
            "ticker": ["AAA"],
            "region": ["US"],
            "eligible_for_optimisation": [True],
        }
    )
    with pytest.raises(RuntimeError, match="mock fallback is disabled"):
        run_seed_training(
            assets,
            np.array([1.0]),
            np.array([True]),
            pd.DataFrame(),
            {"max_single_name_weight": 1.0},
            {
                "mode": "historical_walk_forward",
                "allow_mock_fallback": False,
                "random_seeds": (1, 2, 3, 4, 5),
            },
            historical_panel=pd.DataFrame(),
        )
