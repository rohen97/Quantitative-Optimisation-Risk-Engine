import pandas as pd

from src.reporting.chart_factory import _bar, build_charts


def test_chart_factory_writes_charts(tmp_path):
    charts = build_charts({"final_portfolio": pd.DataFrame({"ticker": ["AAA"], "final_weight": [0.1]})}, tmp_path)
    assert charts["final_weights"].exists()


def test_bar_chart_sanitises_mixed_and_missing_category_labels(tmp_path):
    output = _bar(
        pd.DataFrame({"sector": ["Technology", float("nan"), 7.0], "target_weight": [0.4, 0.3, 0.3]}),
        tmp_path / "mixed-labels.png",
        "sector",
        "target_weight",
        "Mixed labels",
    )

    assert output.exists()
