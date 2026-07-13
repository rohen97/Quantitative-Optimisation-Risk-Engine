from __future__ import annotations


def estimate_transaction_cost(turnover: float, bps: float = 15) -> float:
    return turnover * bps / 10_000
