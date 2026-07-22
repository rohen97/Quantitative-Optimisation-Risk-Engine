import pandas as pd

from src.drl.training import (
    apply_scaler,
    build_walk_forward_windows,
    chronological_train_validation_test_split,
    fit_training_scaler,
)


def test_drl_training_split_is_chronological():
    split = chronological_train_validation_test_split(pd.date_range("2020-01-31", periods=10, freq="ME"), 0.6, 0.2)
    assert split["train"] == (0, 6)
    assert split["validation"] == (6, 8)
    assert split["test"] == (8, 10)


def test_walk_forward_windows_use_default_5_1_1_with_embargo():
    windows = build_walk_forward_windows(pd.date_range("2015-01-31", periods=120, freq="ME"))
    assert windows
    first = windows[0]
    assert first.train_start == pd.Timestamp("2015-01-31")
    assert first.train_end == pd.Timestamp("2019-12-31")
    assert first.validation_start == pd.Timestamp("2020-02-29")
    assert first.validation_end == pd.Timestamp("2021-01-31")
    assert first.test_start == pd.Timestamp("2021-03-31")
    assert first.test_end == pd.Timestamp("2022-02-28")


def test_walk_forward_windows_use_limited_history_fallback():
    windows = build_walk_forward_windows(pd.date_range("2020-01-31", periods=60, freq="ME"))
    assert len(windows) == 1
    assert windows[0].train_end == pd.Timestamp("2022-12-31")
    assert windows[0].validation_start == pd.Timestamp("2023-02-28")
    assert windows[0].test_start == pd.Timestamp("2023-09-30")


def test_training_only_scaler_does_not_fit_future_rows():
    data = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-31", "2020-02-29", "2021-01-31"]),
            "feature": [1.0, 3.0, 100.0],
        }
    )
    scaler = fit_training_scaler(data, ["feature"], "date", pd.Timestamp("2020-02-29"))
    scaled = apply_scaler(data, scaler)
    assert scaler.mean[0] == 2.0
    assert scaled.loc[2, "feature"] == 98.0
