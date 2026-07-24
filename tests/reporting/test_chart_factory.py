import pandas as pd

from src.reporting.chart_factory import build_charts


def test_chart_factory_writes_charts(tmp_path):
    charts = build_charts({"final_portfolio": pd.DataFrame({"ticker": ["AAA"], "final_weight": [0.1]})}, tmp_path)
    assert charts["final_weights"].exists()
