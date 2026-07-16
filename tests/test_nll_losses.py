import numpy as np

from src.models.nll_losses import normal_nll, skewed_student_t_nll_placeholder, student_t_nll


def test_nll_losses_are_finite():
    realized = np.array([0.01, -0.02, 0.03])
    normal = normal_nll(realized, 0, 0.1)
    student = student_t_nll(realized, 0, 0.1, 6)
    skewed = skewed_student_t_nll_placeholder(realized, 0, 0.1, 6, 0.8)
    assert np.isfinite(normal["mean_nll"])
    assert np.isfinite(student["mean_nll"])
    assert np.isfinite(skewed["mean_nll"])
    assert len(normal["observation_level_nll"]) == 3
