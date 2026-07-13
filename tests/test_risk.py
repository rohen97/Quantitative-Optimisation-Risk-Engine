import pandas as pd

from src.risk.var_cvar import var_cvar


def test_var_cvar():
    var5, cvar5 = var_cvar(pd.Series([-0.10, -0.05, 0.01, 0.02, 0.03]), 0.2)
    assert cvar5 <= var5
