import pandas as pd

from src.validation.benchmark_comparison import compare_benchmarks, pairwise_return_differences


def test_benchmark_comparison_is_aligned():
    returns = pd.DataFrame({"baseline": [0.01] * 24, "challenger": [0.02] * 24})
    assert set(compare_benchmarks(returns, samples=20, block_size=3)["strategy"]) == {"baseline", "challenger"}
    assert pairwise_return_differences(returns, "baseline").loc[0, "mean_return_difference"] > 0
