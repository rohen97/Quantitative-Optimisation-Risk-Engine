import pandas as pd

from src.models.walk_forward import purged_walk_forward_split, time_ordered_train_validation_split, walk_forward_split


def test_walk_forward_split_preserves_time_order():
    dates = pd.Series(pd.date_range("2025-01-01", periods=20, freq="D"))
    splits = walk_forward_split(dates, min_train_periods=5, test_periods=2)
    assert splits
    for train_idx, test_idx in splits:
        assert dates.loc[train_idx].max() < dates.loc[test_idx].min()


def test_purged_walk_forward_applies_embargo():
    dates = pd.Series(pd.date_range("2025-01-01", periods=30, freq="D"))
    splits = purged_walk_forward_split(dates, min_train_periods=10, test_periods=2, embargo_days=3)
    assert splits
    for train_idx, test_idx in splits:
        assert dates.loc[train_idx].max() <= dates.loc[test_idx].min() - pd.Timedelta(days=3)


def test_time_ordered_train_validation_split():
    dates = pd.Series(pd.date_range("2025-01-01", periods=12, freq="D"))
    train_idx, validation_idx = time_ordered_train_validation_split(dates, validation_periods=3)
    assert dates.loc[train_idx].max() < dates.loc[validation_idx].min()
