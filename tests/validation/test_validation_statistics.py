import numpy as np
from scipy.stats import ttest_rel

from src.validation.statistics.bootstrap import block_bootstrap_interval
from src.validation.statistics.hypothesis_tests import paired_mean_test


def test_paired_mean_test_uses_small_sample_student_t_distribution():
    left = np.array([0.04, 0.03, -0.01, 0.02, 0.00])
    right = np.array([0.01, 0.02, 0.00, 0.01, -0.01])

    result = paired_mean_test(left, right)
    expected = ttest_rel(left, right)

    assert result['t_statistic'] == expected.statistic
    assert result['p_value'] == expected.pvalue


def test_monthly_block_bootstrap_is_seeded_and_can_span_zero():
    values = np.array(
        [
            -0.01,
            0.02,
            -0.03,
            0.01,
            0.00,
            0.02,
            -0.01,
            0.01,
            -0.02,
            0.01,
            0.00,
            0.01,
        ]
    )
    first = block_bootstrap_interval(values, samples=500, block_size=3, seed=7)
    second = block_bootstrap_interval(values, samples=500, block_size=3, seed=7)

    assert first == second
    assert first[0] < 0 < first[1]
