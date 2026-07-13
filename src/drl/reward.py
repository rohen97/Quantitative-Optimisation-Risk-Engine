from __future__ import annotations


def reward(total_return: float, dividend_income: float, cvar_penalty: float, turnover_penalty: float) -> float:
    return total_return + dividend_income - cvar_penalty - turnover_penalty
