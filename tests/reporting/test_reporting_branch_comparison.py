import pandas as pd

from src.reporting.branch_comparison import build_branch_comparison
from src.reporting.models import ICDataBundle


def test_branch_comparison_keeps_expected_columns():
    frame = pd.DataFrame({"ticker": ["AAA"], "branch_classification": ["Agree"], "extra": [1]})
    result = build_branch_comparison(ICDataBundle({"branch_comparison": frame}))
    assert result.columns.tolist() == ["ticker", "branch_classification"]
