from __future__ import annotations


__all__ = [
    'MarketDataBundle',
    'PortfolioSpec',
    'ReplayResult',
    'run_backtest_suite',
]


def __getattr__(name: str):
    if name in {'MarketDataBundle', 'PortfolioSpec', 'ReplayResult'}:
        from src.backtesting import models

        return getattr(models, name)
    if name == 'run_backtest_suite':
        from src.backtesting.pipeline import run_backtest_suite

        return run_backtest_suite
    raise AttributeError(name)
