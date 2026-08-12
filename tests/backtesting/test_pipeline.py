import pandas as pd

from src.backtesting.pipeline import _load_point_in_time_evidence


def test_point_in_time_evidence_prefers_current_outputs(tmp_path):
    latest = tmp_path / 'reports' / 'outputs' / 'validation' / 'latest'
    walk_forward = tmp_path / 'reports' / 'outputs' / 'walk_forward'
    release = (
        tmp_path
        / 'reports'
        / 'releases'
        / '2026-08-07-full-universe'
        / 'validation'
    )
    latest.mkdir(parents=True)
    walk_forward.mkdir(parents=True)
    release.mkdir(parents=True)
    pd.DataFrame([{'strategy': 'current', 'observations': 60}]).to_csv(
        latest / 'portfolio_strategy_comparison.csv', index=False
    )
    pd.DataFrame([{'strategy': 'stale', 'observations': 25}]).to_csv(
        release / 'portfolio_strategy_comparison.csv', index=False
    )
    pd.DataFrame(
        [{'date': '2026-01-31', 'strategy': 'current', 'net_return': 0.01}]
    ).to_parquet(walk_forward / 'historical_portfolio_returns.parquet', index=False)
    pd.DataFrame(
        [{'date': '2024-01-31', 'strategy': 'stale', 'net_return': 0.02}]
    ).to_csv(release / 'portfolio_monthly_returns.csv', index=False)

    summary, monthly = _load_point_in_time_evidence(tmp_path)

    assert summary.loc[0, 'strategy'] == 'current'
    assert monthly.loc[0, 'strategy'] == 'current'
