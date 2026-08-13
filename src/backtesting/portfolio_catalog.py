from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from src.backtesting.models import PortfolioSpec


PORTFOLIO_METADATA_FILES = (
    'current_portfolio_enriched.csv',
    'final_portfolio_weights.csv',
    'optimiser_input_dataset.csv',
    'recommendations_clean_sheet.csv',
    'recommendations_portfolio_aware.csv',
)

OPTIMISER_LABELS = {
    'cvar_constrained': 'CVaR-Constrained Optimiser',
    'dividend_income': 'Dividend-Income Optimiser',
    'mean_variance': 'Mean-Variance Optimiser',
    'regime_aware': 'Regime-Aware Optimiser',
    'risk_parity': 'Risk-Parity Optimiser',
    'score_weighted': 'Score-Weighted Optimiser',
}

YFINANCE_SUFFIXES = {
    'US': '',
    'SHE': 'SZ',
    'SHG': 'SS',
    'XETRA': 'DE',
    'LSE': 'L',
    'SW': 'SW',
    'PA': 'PA',
    'AS': 'AS',
    'BR': 'BR',
    'MI': 'MI',
    'MC': 'MC',
    'ST': 'ST',
    'OL': 'OL',
    'CO': 'CO',
    'HE': 'HE',
    'VI': 'VI',
    'LS': 'LS',
    'IR': 'IR',
}


def fallback_yfinance_symbol(ticker: str) -> str:
    value = str(ticker).strip()
    if not value or '.' not in value:
        return value
    code, suffix = value.rsplit('.', 1)
    replacement = YFINANCE_SUFFIXES.get(suffix.upper())
    if replacement is None:
        return value
    if not replacement:
        return code
    return f'{code}.{replacement}'


def _identifier_mapping(database_path: Path, tickers: Iterable[str]) -> dict[str, str]:
    values = sorted({str(value) for value in tickers})
    if not database_path.exists() or not values:
        return {}
    try:
        import duckdb

        connection = duckdb.connect(str(database_path), read_only=True)
        placeholders = ','.join('?' for _ in values)
        query = f'''
            SELECT e.identifier_value AS source_ticker,
                   y.identifier_value AS yfinance_ticker
            FROM security_identifiers e
            JOIN security_identifiers y
              ON e.security_id = y.security_id
             AND y.identifier_type = 'yfinance_ticker'
             AND y.valid_to IS NULL
            WHERE e.identifier_type = 'eodhd_ticker'
              AND e.valid_to IS NULL
              AND e.identifier_value IN ({placeholders})
        '''
        frame = connection.execute(query, values).df()
        connection.close()
        return dict(zip(frame['source_ticker'], frame['yfinance_ticker']))
    except Exception:
        return {}


def _metadata_catalog(output_directory: Path) -> pd.DataFrame:
    wanted = [
        'ticker',
        'security_id',
        'company_name',
        'country',
        'region',
        'currency',
        'sector',
        'market_cap_usd',
        'average_daily_value_usd',
    ]
    frames: list[pd.DataFrame] = []
    for name in PORTFOLIO_METADATA_FILES:
        path = output_directory / name
        if not path.exists():
            continue
        data = pd.read_csv(path)
        if 'ticker' not in data:
            continue
        available = [column for column in wanted if column in data]
        frames.append(data[available].copy())
    if not frames:
        return pd.DataFrame(columns=wanted)
    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined['ticker'] = combined['ticker'].astype(str)
    combined = combined.replace({'': np.nan})
    rows = []
    for ticker, group in combined.groupby('ticker', sort=False):
        row = {'ticker': ticker}
        for column in wanted[1:]:
            values = group[column].dropna() if column in group else pd.Series(dtype=object)
            row[column] = values.iloc[0] if not values.empty else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def _build_holdings(
    weights: pd.DataFrame,
    metadata: pd.DataFrame,
    identifier_map: dict[str, str],
) -> pd.DataFrame:
    required = {'ticker', 'weight'}
    if not required.issubset(weights):
        raise ValueError(f'Portfolio weights require columns {sorted(required)}.')
    frame = weights.copy()
    frame['ticker'] = frame['ticker'].astype(str).str.strip()
    frame['weight'] = pd.to_numeric(frame['weight'], errors='coerce')
    frame = frame.dropna(subset=['ticker', 'weight'])
    frame = frame.loc[frame['weight'].gt(1e-12)]
    frame = frame.groupby('ticker', as_index=False, sort=False)['weight'].sum()
    explicit_cash = frame['ticker'].str.upper().isin({'CASH', 'CASH.USD'})
    frame = frame.loc[~explicit_cash].copy()
    total = float(frame['weight'].sum())
    if frame.empty or total <= 0 or total > 1.00001:
        raise ValueError(f'Portfolio has invalid invested weight {total:.8f}.')
    frame = frame.merge(metadata, on='ticker', how='left')
    frame['security_id'] = frame['security_id'].fillna(frame['ticker'])
    frame['company_name'] = frame['company_name'].fillna(frame['ticker'])
    frame['yfinance_ticker'] = frame['ticker'].map(identifier_map)
    frame['yfinance_ticker'] = frame['yfinance_ticker'].fillna(
        frame['ticker'].map(fallback_yfinance_symbol)
    )
    missing = frame['yfinance_ticker'].isna() | frame['yfinance_ticker'].eq('')
    if missing.any():
        missing_tickers = frame.loc[missing, 'ticker'].tolist()
        raise ValueError(f'Missing yfinance identifiers: {missing_tickers}')
    return frame.sort_values('weight', ascending=False).reset_index(drop=True)


def _weight_frame(data: pd.DataFrame, weight_column: str) -> pd.DataFrame:
    return data[['ticker', weight_column]].rename(columns={weight_column: 'weight'})


def _current_nav(
    current: pd.DataFrame,
    configured_file: Path,
    configured_aum: float | None = None,
) -> float:
    if configured_aum is not None and float(configured_aum) > 0:
        return float(configured_aum)
    configured = pd.read_csv(configured_file) if configured_file.exists() else pd.DataFrame()
    for frame in (current, configured):
        if 'market_value_usd' in frame:
            value = float(pd.to_numeric(frame['market_value_usd'], errors='coerce').sum())
            if value > 0:
                return value
    raise ValueError('Current portfolio NAV is unavailable or non-positive.')


def build_portfolio_catalog(config: dict) -> list[PortfolioSpec]:
    root = Path(config['_meta']['repository_root'])
    output = root / 'reports' / 'outputs'
    current_path = output / 'current_portfolio_enriched.csv'
    if not current_path.exists():
        raise FileNotFoundError(current_path)
    current = pd.read_csv(current_path)
    metadata = _metadata_catalog(output)

    selected_tickers: set[str] = set(current['ticker'].astype(str))
    source_frames: dict[str, tuple[pd.DataFrame, Path]] = {}
    for suffix in OPTIMISER_LABELS:
        path = output / f'optimised_portfolio_{suffix}.csv'
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        source_frames[f'optimised_{suffix}'] = (
            _weight_frame(frame, 'target_weight'),
            path,
        )
        positive = frame['target_weight'].gt(1e-12)
        selected_tickers.update(frame.loc[positive, 'ticker'].astype(str))

    proposed_path = output / 'proposed_portfolio.csv'
    proposed = pd.read_csv(proposed_path)
    proposed_weights = _weight_frame(proposed, 'target_weight')
    overlay_fraction = float(proposed_weights['weight'].sum())
    current_overlay = _weight_frame(current, 'weight')
    current_overlay['weight'] *= max(0.0, 1.0 - overlay_fraction)
    overlay = pd.concat([current_overlay, proposed_weights], ignore_index=True)
    selected_tickers.update(overlay['ticker'].astype(str))

    clean_path = output / 'recommendations_clean_sheet.csv'
    clean = pd.read_csv(clean_path)
    clean_weights = _weight_frame(clean, 'clean_sheet_target_weight')
    clean_weights = clean_weights.loc[clean_weights['weight'].gt(1e-12)]
    selected_tickers.update(clean_weights['ticker'].astype(str))

    llm_path = output / 'recommendations_llm_benchmark.csv'
    llm = pd.read_csv(llm_path)
    llm_buys = llm.loc[llm['llm_recommendation'].eq('Buy')].nlargest(
        20,
        'qualitative_score',
    )[['ticker']]
    if llm_buys.empty:
        raise ValueError('LLM benchmark contains no Buy recommendations.')
    llm_buys = llm_buys.copy()
    llm_buys['weight'] = min(0.05, 1.0 / len(llm_buys))
    selected_tickers.update(llm_buys['ticker'].astype(str))

    final_path = output / 'final_portfolio_weights.csv'
    final = pd.read_csv(final_path)
    final_column = next(
        column
        for column in ('final_weight', 'final_selected_weight', 'target_weight')
        if column in final
    )
    final_weights = _weight_frame(final, final_column)
    positive = final_weights['weight'].gt(1e-12)
    selected_tickers.update(final_weights.loc[positive, 'ticker'].astype(str))

    baseline_path = output / 'drl_baseline_portfolio.csv'
    baseline = pd.read_csv(baseline_path)
    baseline_weights = _weight_frame(baseline, 'baseline_weight')
    positive = baseline_weights['weight'].gt(1e-12)
    selected_tickers.update(baseline_weights.loc[positive, 'ticker'].astype(str))

    challenger_path = output / 'drl_challenger_portfolio.csv'
    challenger = pd.read_csv(challenger_path)
    challenger_weights = _weight_frame(challenger, 'projected_drl_weight')
    positive = challenger_weights['weight'].gt(1e-12)
    selected_tickers.update(challenger_weights.loc[positive, 'ticker'].astype(str))

    identifier_map = _identifier_mapping(
        root / 'data' / 'database' / 'wolf.duckdb',
        selected_tickers,
    )
    default_capital = float(config['backtest']['default_capital_usd'])
    current_nav = _current_nav(
        current,
        Path(config['backtest']['current_portfolio_file']),
        config['backtest'].get('current_aum_usd'),
    )

    specs: list[PortfolioSpec] = []

    def add(
        key: str,
        label: str,
        weights: pd.DataFrame,
        capital: float,
        capital_source: str,
        evidence_type: str,
        paths: tuple[Path, ...],
        description: str,
    ) -> None:
        specs.append(
            PortfolioSpec(
                key=key,
                label=label,
                holdings=_build_holdings(weights, metadata, identifier_map),
                initial_capital_usd=capital,
                capital_source=capital_source,
                evidence_type=evidence_type,
                source_files=paths,
                description=description,
            )
        )

    add(
        'current_portfolio',
        'Current Portfolio',
        _weight_frame(current, 'weight'),
        current_nav,
        'current_portfolio_nav',
        'retrospective_holdings_replay',
        (current_path,),
        'Current positions replayed at their present weights.',
    )
    add(
        'portfolio_aware_overlay',
        'Portfolio-Aware Overlay',
        overlay,
        current_nav,
        'current_portfolio_nav',
        'retrospective_holdings_replay',
        (current_path, proposed_path),
        'Current portfolio plus the documented proposed-position overlay.',
    )
    add(
        'clean_sheet',
        'Clean-Sheet Quant',
        clean_weights,
        default_capital,
        'fixed_research_capital',
        'retrospective_holdings_replay',
        (clean_path,),
        'Qualified clean-sheet Buy names; unused allocation remains in cash.',
    )
    add(
        'llm_benchmark',
        'LLM Analyst Benchmark',
        llm_buys,
        default_capital,
        'fixed_research_capital',
        'retrospective_holdings_replay',
        (llm_path,),
        'Top mock-LLM Buy recommendations at the model 5% name cap.',
    )
    for key, (weights, path) in source_frames.items():
        suffix = key.removeprefix('optimised_')
        method = suffix.replace('_', ' ')
        add(
            key,
            OPTIMISER_LABELS[suffix],
            weights,
            default_capital,
            'fixed_research_capital',
            'retrospective_holdings_replay',
            (path,),
            f'Current target allocation from the {method} optimiser.',
        )
    add(
        'final_portfolio',
        'Final Resolved Portfolio',
        final_weights,
        current_nav,
        'current_portfolio_nav',
        'retrospective_holdings_replay',
        (final_path,),
        'Final governed allocation resolved by the full model pipeline.',
    )
    add(
        'drl_baseline',
        'DRL Baseline Portfolio',
        baseline_weights,
        current_nav,
        'current_portfolio_nav',
        'retrospective_holdings_replay',
        (baseline_path,),
        'Classical optimiser baseline supplied to the DRL overlay.',
    )
    add(
        'drl_challenger_raw',
        'DRL Raw Challenger',
        challenger_weights,
        current_nav,
        'current_portfolio_nav',
        'research_challenger_replay',
        (challenger_path,),
        'Projected DRL challenger before the governance rejection fallback.',
    )
    return specs


def portfolio_definitions(specs: list[PortfolioSpec], root: Path) -> pd.DataFrame:
    rows = []
    for spec in specs:
        invested = float(spec.holdings['weight'].sum())
        for row in spec.holdings.itertuples(index=False):
            rows.append(
                {
                    'strategy': spec.key,
                    'strategy_label': spec.label,
                    'ticker': row.ticker,
                    'yfinance_ticker': row.yfinance_ticker,
                    'security_id': row.security_id,
                    'company_name': row.company_name,
                    'region': row.region,
                    'country': row.country,
                    'currency': row.currency,
                    'sector': row.sector,
                    'target_weight': row.weight,
                    'cash_weight': 1.0 - invested,
                    'initial_capital_usd': spec.initial_capital_usd,
                    'capital_source': spec.capital_source,
                    'evidence_type': spec.evidence_type,
                    'source_files': ';'.join(
                        str(path.relative_to(root)).replace(chr(92), '/')
                        for path in spec.source_files
                    ),
                }
            )
    return pd.DataFrame(rows)
