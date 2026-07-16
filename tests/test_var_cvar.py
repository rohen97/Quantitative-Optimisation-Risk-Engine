import pandas as pd

from src.risk.var_cvar import var_cvar


def test_var_cvar_are_calculated_and_cvar_is_more_severe():
    var5, cvar5 = var_cvar(pd.Series([-0.20, -0.10, -0.05, 0.02, 0.05]), 0.05)
    assert cvar5 <= var5
