from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import yfinance as yf

from src.backtesting.models import MarketDataBundle, PortfolioSpec


LOGGER = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _cache_key(symbols: list[str], start: pd.Timestamp, end: pd.Timestamp) -> str:
    payload = '|'.join([start.date().isoformat(), end.date().isoformat(), *symbols])
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]


def _normalise_yfinance(raw: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    columns = ['date', 'symbol', 'adjusted_close', 'volume']
    if raw is None or raw.empty:
        return pd.DataFrame(columns=columns)
    data = raw.copy()
    if isinstance(data.columns, pd.MultiIndex):
        first = data.columns.get_level_values(0)
        second = data.columns.get_level_values(1)
        if 'Close' not in first and 'Close' in second:
            data = data.swaplevel(0, 1, axis=1).sort_index(axis=1)
        frames = []
        available = set(data.columns.get_level_values(1))
        for symbol in symbols:
            if symbol not in available or ('Close', symbol) not in data:
                continue
            close = pd.to_numeric(data[('Close', symbol)], errors='coerce')
            volume = (
                pd.to_numeric(data[('Volume', symbol)], errors='coerce')
                if ('Volume', symbol) in data
                else pd.Series(np.nan, index=data.index)
            )
            frames.append(
                pd.DataFrame(
                    {
                        'date': data.index,
                        'symbol': symbol,
                        'adjusted_close': close.to_numpy(),
                        'volume': volume.to_numpy(),
                    }
                )
            )
        result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)
    else:
        close_column = 'Close' if 'Close' in data else 'Adj Close' if 'Adj Close' in data else None
        if close_column is None:
            return pd.DataFrame(columns=columns)
        symbol = symbols[0]
        result = pd.DataFrame(
            {
                'date': data.index,
                'symbol': symbol,
                'adjusted_close': pd.to_numeric(data[close_column], errors='coerce').to_numpy(),
                'volume': pd.to_numeric(
                    data['Volume'] if 'Volume' in data else np.nan,
                    errors='coerce',
                ),
            }
        )
    result['date'] = pd.to_datetime(result['date']).dt.tz_localize(None).dt.normalize()
    result['adjusted_close'] = pd.to_numeric(result['adjusted_close'], errors='coerce')
    result['volume'] = pd.to_numeric(result['volume'], errors='coerce')
    result = result.loc[result['adjusted_close'].gt(0)].copy()
    return result.sort_values(['symbol', 'date']).drop_duplicates(
        ['symbol', 'date'],
        keep='last',
    ).reset_index(drop=True)


def download_yfinance_history(
    symbols: list[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    config: dict,
    cache_directory: Path,
) -> tuple[pd.DataFrame, Path]:
    clean = sorted({str(symbol).strip() for symbol in symbols if str(symbol).strip()})
    if not clean:
        raise ValueError('No market-data symbols were requested.')
    cache_directory.mkdir(parents=True, exist_ok=True)
    key = _cache_key(clean, start, end)
    cache_path = cache_directory / f'yfinance_{key}.parquet'
    refresh = bool(config.get('refresh_cache', False))
    if cache_path.exists() and not refresh:
        return pd.read_parquet(cache_path), cache_path

    batch_size = max(1, int(config.get('batch_size', 40)))
    retries = max(1, int(config.get('retries', 3)))
    wait_seconds = float(config.get('retry_wait_seconds', 2.0))
    frames: list[pd.DataFrame] = []
    requested_end = end + pd.Timedelta(days=1)
    for offset in range(0, len(clean), batch_size):
        batch = clean[offset : offset + batch_size]
        pending = list(batch)
        for attempt in range(retries):
            if not pending:
                break
            LOGGER.info(
                'Downloading yfinance batch %s-%s, attempt %s, symbols=%s.',
                offset + 1,
                min(offset + batch_size, len(clean)),
                attempt + 1,
                len(pending),
            )
            try:
                raw = yf.download(
                    tickers=pending,
                    start=start.date().isoformat(),
                    end=requested_end.date().isoformat(),
                    interval='1d',
                    auto_adjust=True,
                    progress=False,
                    group_by='column',
                    threads=True,
                    repair=True,
                )
                normalised = _normalise_yfinance(raw, pending)
            except Exception as exc:
                LOGGER.warning('yfinance batch attempt failed: %s', exc)
                normalised = pd.DataFrame()
            if not normalised.empty:
                frames.append(normalised)
                returned = set(normalised['symbol'])
                pending = [symbol for symbol in pending if symbol not in returned]
            if pending and attempt + 1 < retries:
                time.sleep(wait_seconds * (attempt + 1))
        if pending:
            LOGGER.warning('No yfinance history returned for: %s', ', '.join(pending))
    if not frames:
        raise RuntimeError('yfinance returned no usable history.')
    result = pd.concat(frames, ignore_index=True)
    result = result.sort_values(['symbol', 'date']).drop_duplicates(
        ['symbol', 'date'],
        keep='last',
    )
    result.to_parquet(cache_path, index=False)
    return result.reset_index(drop=True), cache_path


def download_fred_history(
    series_ids: list[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    config: dict,
    cache_directory: Path,
) -> tuple[pd.DataFrame, Path]:
    clean = sorted({str(value) for value in series_ids})
    cache_directory.mkdir(parents=True, exist_ok=True)
    key = _cache_key(clean, start, end)
    cache_path = cache_directory / f'fred_{key}.parquet'
    if cache_path.exists() and not bool(config.get('refresh_cache', False)):
        return pd.read_parquet(cache_path), cache_path
    frames = []
    base_url = str(config['fred_csv_url'])
    for series_id in clean:
        query = urlencode(
            {
                'id': series_id,
                'cosd': start.date().isoformat(),
                'coed': end.date().isoformat(),
            }
        )
        frame = pd.read_csv(f'{base_url}?{query}')
        date_column = next(column for column in frame if 'date' in column.lower())
        value_column = next(column for column in frame if column != date_column)
        frame = frame.rename(columns={date_column: 'date', value_column: 'value'})
        frame['date'] = pd.to_datetime(frame['date']).dt.normalize()
        frame['value'] = pd.to_numeric(frame['value'], errors='coerce')
        frame['series_id'] = series_id
        frames.append(frame[['date', 'series_id', 'value']])
    result = pd.concat(frames, ignore_index=True)
    result.to_parquet(cache_path, index=False)
    return result, cache_path


def _benchmark_metadata(config: dict) -> pd.DataFrame:
    values = config['benchmarks']
    rows = []
    for key in ('common', 'total_return_proxy'):
        row = dict(values[key])
        row['benchmark_key'] = key
        rows.append(row)
    for region, definition in values['regions'].items():
        row = dict(definition)
        row['benchmark_key'] = f'region_{region}'
        row['region'] = region
        rows.append(row)
    for key, definition in values.get('additional', {}).items():
        row = dict(definition)
        row['benchmark_key'] = key
        rows.append(row)
    return pd.DataFrame(rows).drop_duplicates('benchmark_key')


def _symbol_metadata(specs: list[PortfolioSpec]) -> pd.DataFrame:
    frames = []
    for spec in specs:
        frame = spec.holdings[['yfinance_ticker', 'currency', 'region']].copy()
        frame = frame.rename(columns={'yfinance_ticker': 'symbol'})
        frames.append(frame)
    metadata = pd.concat(frames, ignore_index=True)
    conflicts = metadata.groupby('symbol')['currency'].nunique(dropna=True)
    if conflicts.gt(1).any():
        symbols = conflicts.loc[conflicts.gt(1)].index.tolist()
        raise ValueError(f'Conflicting currencies for market symbols: {symbols}')
    return metadata.drop_duplicates('symbol')


def _fred_wide(fred: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    data = fred.copy()
    data['date'] = pd.to_datetime(data['date']).dt.normalize()
    wide = data.pivot_table(index='date', columns='series_id', values='value', aggfunc='last')
    return wide.reindex(index).ffill(limit=10)


def _fx_factors(
    fred: pd.DataFrame,
    currencies: set[str],
    index: pd.DatetimeIndex,
    config: dict,
) -> pd.DataFrame:
    wide = _fred_wide(fred, index)
    factors = pd.DataFrame(index=index)
    factors['USD'] = 1.0
    definitions = config['market_data']['fx_series']
    for currency in sorted(currencies - {'USD'}):
        definition = definitions.get(currency)
        if definition is None:
            raise KeyError(f'No FX definition configured for {currency}.')
        primary = wide.get(definition['primary'], pd.Series(np.nan, index=index))
        values = primary.copy()
        pre_euro = definition.get('pre_euro')
        if pre_euro:
            earlier = wide.get(pre_euro, pd.Series(np.nan, index=index))
            values = values.combine_first(earlier)
        values = values.ffill(limit=10)
        if definition['direction'] == 'units_per_usd':
            values = 1.0 / values
        elif definition['direction'] != 'usd_per_unit':
            raise ValueError(f'Unsupported FX direction for {currency}.')
        values *= float(definition.get('unit_scale', 1.0))
        factors[currency] = values
    return factors


def _convert_prices_to_usd(
    bars: pd.DataFrame,
    metadata: pd.DataFrame,
    fx: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    prices = bars.pivot_table(
        index='date',
        columns='symbol',
        values='adjusted_close',
        aggfunc='last',
    ).sort_index()
    volumes = bars.pivot_table(
        index='date',
        columns='symbol',
        values='volume',
        aggfunc='last',
    ).reindex(prices.index)
    output_columns = {}
    volume_columns = {}
    currency_by_symbol = metadata.set_index('symbol')['currency'].to_dict()
    for symbol in prices:
        currency = str(currency_by_symbol[symbol])
        factor = fx[currency].reindex(prices.index)
        converted = prices[symbol] * factor
        output_columns[symbol] = converted
        volume_columns[symbol] = volumes.get(symbol, np.nan) * converted
    output = pd.DataFrame(output_columns, index=prices.index)
    dollar_volume = pd.DataFrame(volume_columns, index=prices.index)
    return output, dollar_volume


def _coverage_table(
    bars: pd.DataFrame,
    metadata: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    rows = []
    lookup = metadata.drop_duplicates('symbol').set_index('symbol')
    for symbol in sorted(metadata['symbol'].unique()):
        group = bars.loc[bars['symbol'].eq(symbol)].sort_values('date')
        returns = group['adjusted_close'].pct_change(fill_method=None)
        first = group['date'].min() if not group.empty else pd.NaT
        last = group['date'].max() if not group.empty else pd.NaT
        row = lookup.loc[symbol]
        rows.append(
            {
                'symbol': symbol,
                'role': row.get('role', 'holding'),
                'currency': row.get('currency'),
                'region': row.get('region'),
                'requested_start': start,
                'requested_end': end,
                'first_observation': first,
                'last_observation': last,
                'observations': len(group),
                'available_at_1997_start': bool(pd.notna(first) and first <= start + pd.Timedelta(days=10)),
                'history_years': (
                    (last - first).days / 365.25
                    if pd.notna(first) and pd.notna(last)
                    else 0.0
                ),
                'absolute_daily_return_over_50pct': int(returns.abs().gt(0.50).sum()),
            }
        )
    return pd.DataFrame(rows)


def repair_adjusted_price_outliers(
    bars: pd.DataFrame,
    maximum_absolute_return: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = bars.sort_values(['symbol', 'date']).copy().reset_index(drop=True)
    adjustments = []
    for symbol, group in data.groupby('symbol', sort=False):
        locations = group.index.to_numpy()
        prices = group['adjusted_close'].to_numpy(dtype=float).copy()
        dates = pd.to_datetime(group['date']).to_numpy()
        for index in range(1, len(prices)):
            previous = prices[index - 1]
            current = prices[index]
            if not np.isfinite(previous) or not np.isfinite(current) or previous <= 0:
                continue
            raw_return = current / previous - 1.0
            if abs(raw_return) <= maximum_absolute_return:
                continue
            isolated = False
            next_price = np.nan
            if index + 1 < len(prices) and current > 0:
                next_price = prices[index + 1]
                next_return = next_price / current - 1.0 if np.isfinite(next_price) else np.nan
                round_trip = next_price / previous - 1.0 if np.isfinite(next_price) else np.nan
                isolated = (
                    np.isfinite(next_return)
                    and abs(next_return) > maximum_absolute_return
                    and np.isfinite(round_trip)
                    and abs(round_trip) <= maximum_absolute_return
                )
            if isolated:
                repaired = float(np.sqrt(previous * next_price))
                prices[index] = repaired
                adjustment_type = 'isolated_spike_log_interpolation'
                factor = repaired / current
                repaired_return = repaired / previous - 1.0
            else:
                factor = current / previous
                prices[:index] *= factor
                repaired = current
                adjustment_type = 'persistent_level_shift_historical_rescale'
                repaired_return = 0.0
            adjustments.append(
                {
                    'symbol': symbol,
                    'date': pd.Timestamp(dates[index]),
                    'raw_previous_close': previous,
                    'raw_event_close': current,
                    'raw_daily_return': raw_return,
                    'repaired_daily_return': repaired_return,
                    'adjustment_type': adjustment_type,
                    'adjustment_factor': factor,
                    'repaired_event_close': repaired,
                    'threshold': maximum_absolute_return,
                }
            )
        data.loc[locations, 'adjusted_close'] = prices
    adjustment_frame = pd.DataFrame(adjustments)
    return data, adjustment_frame


def build_market_data_bundle(
    specs: list[PortfolioSpec],
    config: dict,
    bars: pd.DataFrame,
    fred: pd.DataFrame,
    source_manifest: dict | None = None,
) -> MarketDataBundle:
    start = pd.Timestamp(config['backtest']['start_date'])
    end = pd.Timestamp(config['backtest']['end_date'])
    stock_metadata = _symbol_metadata(specs)
    stock_metadata['role'] = 'holding'
    benchmarks = _benchmark_metadata(config)
    benchmark_symbols = benchmarks[['symbol', 'currency', 'region']].copy()
    benchmark_symbols['role'] = 'benchmark'
    all_metadata = pd.concat([stock_metadata, benchmark_symbols], ignore_index=True)
    all_metadata = all_metadata.drop_duplicates('symbol', keep='first')

    maximum_return = float(config['market_data'].get('maximum_absolute_daily_return', 0.50))
    raw_coverage = _coverage_table(bars, all_metadata, start, end)
    clean_bars, price_adjustments = repair_adjusted_price_outliers(
        bars,
        maximum_return,
    )
    calendar = pd.date_range(start, end, freq='D')
    currencies = set(all_metadata['currency'].dropna().astype(str))
    fx = _fx_factors(fred, currencies, calendar, config)
    stock_bars = clean_bars.loc[clean_bars['symbol'].isin(stock_metadata['symbol'])]
    benchmark_bars = clean_bars.loc[clean_bars['symbol'].isin(benchmark_symbols['symbol'])]
    prices_usd, volume_usd = _convert_prices_to_usd(stock_bars, stock_metadata, fx)
    benchmark_prices, _ = _convert_prices_to_usd(
        benchmark_bars,
        benchmark_symbols.drop_duplicates('symbol'),
        fx,
    )

    risk_free_id = config['market_data']['risk_free_series']
    fred_daily = _fred_wide(fred, calendar)
    annual_yield = fred_daily.get(risk_free_id, pd.Series(0.0, index=calendar))
    annual_yield = annual_yield.fillna(0.0).clip(lower=-0.99)
    cash_returns = (1.0 + annual_yield / 100.0).pow(1.0 / 365.0) - 1.0
    cash_returns.name = 'cash_return'

    coverage = _coverage_table(clean_bars, all_metadata, start, end)
    coverage = coverage.rename(
        columns={'absolute_daily_return_over_50pct': 'post_repair_absolute_daily_return_over_50pct'}
    )
    raw_counts = raw_coverage.set_index('symbol')['absolute_daily_return_over_50pct']
    coverage['raw_absolute_daily_return_over_50pct'] = coverage['symbol'].map(raw_counts).fillna(0).astype(int)
    common_symbol = config['benchmarks']['common']['symbol']
    if common_symbol not in benchmark_prices or benchmark_prices[common_symbol].dropna().empty:
        raise RuntimeError(f'Common benchmark history is unavailable for {common_symbol}.')
    manifest = dict(source_manifest or {})
    manifest['outlier_policy'] = config['market_data'].get(
        'outlier_policy',
        'explicit_level_shift_repair',
    )
    manifest['price_adjustment_count'] = len(price_adjustments)
    return MarketDataBundle(
        prices_usd=prices_usd,
        volume_usd=volume_usd,
        cash_returns=cash_returns,
        benchmark_prices_usd=benchmark_prices,
        benchmark_metadata=benchmarks,
        data_coverage=coverage,
        source_manifest=manifest,
        price_adjustments=price_adjustments,
        macro_series=fred_daily,
    )


def load_market_data(
    specs: list[PortfolioSpec],
    config: dict,
    bars: pd.DataFrame | None = None,
    fred: pd.DataFrame | None = None,
) -> MarketDataBundle:
    start = pd.Timestamp(config['backtest']['start_date'])
    end = pd.Timestamp(config['backtest']['end_date'])
    stock_metadata = _symbol_metadata(specs)
    benchmarks = _benchmark_metadata(config)
    symbols = sorted(set(stock_metadata['symbol']) | set(benchmarks['symbol']))
    fx_definitions = config['market_data']['fx_series'].values()
    series_ids = {config['market_data']['risk_free_series']}
    macro_config = config.get('macro_regimes', {})
    series_ids.update(
        value
        for key, value in macro_config.items()
        if key.endswith('_series') and isinstance(value, str)
    )
    for definition in fx_definitions:
        series_ids.add(definition['primary'])
        if definition.get('pre_euro'):
            series_ids.add(definition['pre_euro'])
    cache_directory = Path(config['backtest']['cache_directory'])
    cache_paths: list[Path] = []
    if bars is None:
        bars, price_cache = download_yfinance_history(
            symbols,
            start,
            end,
            config['market_data'],
            cache_directory,
        )
        cache_paths.append(price_cache)
    if fred is None:
        fred, fred_cache = download_fred_history(
            sorted(series_ids),
            start,
            end,
            config['market_data'],
            cache_directory,
        )
        cache_paths.append(fred_cache)
    manifest = {
        'provider': config['market_data']['provider'],
        'requested_symbol_count': len(symbols),
        'returned_symbol_count': int(bars['symbol'].nunique()),
        'fred_series': sorted(series_ids),
        'cache_artifacts': [
            {'name': path.name, 'sha256': _sha256(path)}
            for path in cache_paths
            if path.exists()
        ],
    }
    return build_market_data_bundle(specs, config, bars, fred, manifest)
