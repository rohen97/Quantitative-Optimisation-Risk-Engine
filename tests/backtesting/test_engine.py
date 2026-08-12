from pathlib import Path

import numpy as np
import pandas as pd

from src.backtesting.engine import _liquidity_constrained_target, replay_portfolio
from src.backtesting.models import MarketDataBundle, PortfolioSpec


def _config() -> dict:
    return {
        'backtest': {'minimum_live_weight': 0.80},
        'execution': {
            'commission_bps': 1.0,
            'half_spread_bps': 5.0,
            'slippage_bps': 4.0,
            'market_impact_bps': 10.0,
            'impact_reference_participation': 0.01,
            'maximum_impact_bps': 50.0,
            'maximum_adv_participation': 0.05,
            'missing_liquidity_penalty_bps': 15.0,
        },
    }


def _bundle(prices: pd.DataFrame) -> MarketDataBundle:
    calendar = pd.date_range('1997-01-01', '1997-03-31', freq='D')
    volume = pd.DataFrame(10_000_000.0, index=prices.index, columns=prices.columns)
    return MarketDataBundle(
        prices_usd=prices,
        volume_usd=volume,
        cash_returns=pd.Series(0.0, index=calendar),
        benchmark_prices_usd=pd.DataFrame(),
        benchmark_metadata=pd.DataFrame(),
        data_coverage=pd.DataFrame(),
        source_manifest={},
    )


def _spec(holdings: pd.DataFrame) -> PortfolioSpec:
    return PortfolioSpec(
        key='test',
        label='Test Portfolio',
        holdings=holdings,
        initial_capital_usd=100_000.0,
        capital_source='test',
        evidence_type='test',
        source_files=(Path('test.csv'),),
    )


def test_replay_portfolio_applies_returns_and_opening_cost() -> None:
    dates = pd.to_datetime(['1997-01-31', '1997-02-28', '1997-03-31'])
    prices = pd.DataFrame({'AAA': [100.0, 110.0, 99.0]}, index=dates)
    holdings = pd.DataFrame(
        {
            'ticker': ['AAA'],
            'yfinance_ticker': ['AAA'],
            'weight': [1.0],
        }
    )
    result = replay_portfolio(_spec(holdings), _bundle(prices), _config())
    assert len(result.monthly) == 2
    assert np.isclose(result.monthly.iloc[0]['gross_return'], 0.10)
    assert result.monthly.iloc[0]['net_return'] < 0.10
    assert np.isclose(result.monthly.iloc[1]['gross_return'], -0.10)
    assert result.monthly['liquidity_breaches'].sum() == 0


def test_prelisting_weight_remains_cash_until_price_exists() -> None:
    dates = pd.to_datetime(['1997-01-31', '1997-02-28', '1997-03-31'])
    prices = pd.DataFrame(
        {
            'AAA': [100.0, 110.0, 121.0],
            'BBB': [np.nan, 10.0, 11.0],
        },
        index=dates,
    )
    holdings = pd.DataFrame(
        {
            'ticker': ['AAA', 'BBB'],
            'yfinance_ticker': ['AAA', 'BBB'],
            'weight': [0.5, 0.5],
        }
    )
    result = replay_portfolio(_spec(holdings), _bundle(prices), _config())
    assert np.isclose(result.monthly.iloc[0]['live_weight'], 0.5)
    assert np.isclose(result.monthly.iloc[0]['cash_weight'], 0.5)
    assert np.isclose(result.monthly.iloc[1]['live_weight'], 1.0)
    assert result.full_investment_start == pd.Timestamp('1997-02-28')


def test_liquidity_cap_leaves_unfilled_weight_in_cash() -> None:
    executed, unfilled, breaches = _liquidity_constrained_target(
        desired_assets=np.array([0.50]),
        pre_trade_assets=np.array([0.0]),
        adv=np.array([1000.0]),
        portfolio_value=100_000.0,
        maximum_participation=0.05,
    )
    assert np.isclose(executed[0], 0.0005)
    assert unfilled > 0.49
    assert breaches == 1
