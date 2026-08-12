from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtesting.models import MarketDataBundle, PortfolioSpec, ReplayResult


def _monthly_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if prices.empty:
        return prices.copy()
    return prices.sort_index().resample('ME').last()


def _monthly_dollar_volume(volume: pd.DataFrame) -> pd.DataFrame:
    if volume.empty:
        return volume.copy()
    return volume.sort_index().resample('ME').median()


def _monthly_cash_returns(cash_returns: pd.Series) -> pd.Series:
    values = pd.to_numeric(cash_returns, errors='coerce').fillna(0.0)
    return (1.0 + values).resample('ME').prod() - 1.0


def _annual_bank_fee_rate(
    fee_config: dict | None,
    end_date: pd.Timestamp,
) -> float:
    settings = fee_config or {}
    if not settings.get('enabled', False):
        return 0.0
    if int(end_date.month) != int(settings.get('charge_month', 12)):
        return 0.0
    return float(settings.get('annual_rate', 0.0))


def _execution_cost(
    asset_delta: np.ndarray,
    adv: np.ndarray,
    portfolio_value: float,
    config: dict,
) -> tuple[float, float, int]:
    notionals = np.abs(asset_delta) * portfolio_value
    active = notionals > 1e-8
    if not active.any():
        return 0.0, 0.0, 0
    base_bps = sum(
        float(config[key])
        for key in ('commission_bps', 'half_spread_bps', 'slippage_bps')
    )
    reference = max(float(config['impact_reference_participation']), 1e-8)
    participation = np.divide(
        notionals,
        adv,
        out=np.full_like(notionals, np.nan),
        where=np.isfinite(adv) & (adv > 0),
    )
    impact = float(config['market_impact_bps']) * np.sqrt(
        np.maximum(participation, 0.0) / reference
    )
    impact = np.minimum(impact, float(config['maximum_impact_bps']))
    missing = ~np.isfinite(participation)
    impact[missing] = float(config['missing_liquidity_penalty_bps'])
    costs = notionals * (base_bps + impact) / 10_000.0
    maximum_participation = (
        float(np.nanmax(participation[active]))
        if np.isfinite(participation[active]).any()
        else np.nan
    )
    maximum_allowed = float(config['maximum_adv_participation'])
    breaches = int(
        np.sum(
            active
            & np.isfinite(participation)
            & (participation > maximum_allowed + 1e-10)
        )
    )
    return float(costs[active].sum()), maximum_participation, breaches


def _liquidity_constrained_target(
    desired_assets: np.ndarray,
    pre_trade_assets: np.ndarray,
    adv: np.ndarray,
    portfolio_value: float,
    maximum_participation: float,
) -> tuple[np.ndarray, float, int]:
    desired_delta = desired_assets - pre_trade_assets
    allowed = np.divide(
        maximum_participation * adv,
        max(portfolio_value, 1e-12),
        out=np.full_like(desired_delta, np.inf),
        where=np.isfinite(adv) & (adv > 0),
    )
    breaches = int(np.sum(np.isfinite(allowed) & (np.abs(desired_delta) > allowed + 1e-12)))
    executed = pre_trade_assets.copy()
    sell = desired_delta < 0
    executed[sell] += np.maximum(desired_delta[sell], -allowed[sell])
    buy = desired_delta > 0
    proposed_buys = np.minimum(desired_delta[buy], allowed[buy])
    available_cash = max(0.0, 1.0 - float(executed.sum()))
    if proposed_buys.sum() > available_cash and proposed_buys.sum() > 0:
        proposed_buys *= available_cash / proposed_buys.sum()
    executed[buy] += proposed_buys
    executed = np.clip(executed, 0.0, 1.0)
    executed_cash = 1.0 - float(executed.sum())
    desired_cash = 1.0 - float(desired_assets.sum())
    unfilled = 0.5 * (
        float(np.abs(desired_assets - executed).sum())
        + abs(desired_cash - executed_cash)
    )
    return executed, unfilled, breaches


def _drift_weights(weights: np.ndarray, returns: np.ndarray) -> np.ndarray:
    gross = weights * (1.0 + returns)
    total = float(gross.sum())
    if not np.isfinite(total) or total <= 0:
        raise ValueError('Invalid portfolio value while drifting weights.')
    return gross / total


def replay_portfolio(
    spec: PortfolioSpec,
    bundle: MarketDataBundle,
    config: dict,
) -> ReplayResult:
    symbols = spec.holdings['yfinance_ticker'].astype(str).tolist()
    target_values = spec.holdings.set_index('yfinance_ticker')['weight'].reindex(symbols)
    targets = target_values.to_numpy(dtype=float)
    prices = _monthly_prices(bundle.prices_usd.reindex(columns=symbols))
    adv = _monthly_dollar_volume(bundle.volume_usd.reindex(columns=symbols)).reindex(prices.index)
    cash = _monthly_cash_returns(bundle.cash_returns).reindex(prices.index).fillna(0.0)
    if len(prices) < 2:
        raise ValueError(f'Insufficient monthly history for {spec.key}.')

    asset_returns = prices.pct_change(fill_method=None)
    pre_trade = np.zeros(len(symbols) + 1, dtype=float)
    pre_trade[-1] = 1.0
    net_value = float(spec.initial_capital_usd)
    gross_value = float(spec.initial_capital_usd)
    pre_bank_fee_value = float(spec.initial_capital_usd)
    rows = []
    execution = config['execution']
    fee_config = (
        config.get('annual_bank_fee', {})
        if config.get('annual_bank_fee', {}).get('apply_to_portfolios', True)
        else {}
    )
    minimum_live = float(config['backtest']['minimum_live_weight'])
    intended_invested_weight = float(targets.sum())
    full_investment_start = None

    for index in range(1, len(prices)):
        start_date = prices.index[index - 1]
        end_date = prices.index[index]
        start_available = prices.iloc[index - 1].notna().to_numpy()
        desired_assets = targets * start_available
        available_target_weight = float(desired_assets.sum())
        period_assets = asset_returns.iloc[index].to_numpy(dtype=float)
        allocated_missing = (desired_assets > 1e-12) & ~np.isfinite(period_assets)
        if allocated_missing.any():
            missing_symbols = np.asarray(symbols)[allocated_missing].tolist()
            raise ValueError(
                f'Missing end-of-month returns for allocated {spec.key} holdings: '
                f'{missing_symbols} at {end_date.date()}.'
            )

        period_adv = adv.iloc[index - 1].to_numpy(dtype=float)
        target_assets, unfilled_weight, attempted_breaches = _liquidity_constrained_target(
            desired_assets,
            pre_trade[:-1],
            period_adv,
            net_value,
            float(execution['maximum_adv_participation']),
        )
        target_cash = 1.0 - float(target_assets.sum())
        target = np.concatenate([target_assets, [target_cash]])
        asset_delta = target_assets - pre_trade[:-1]
        cost_usd, max_participation, liquidity_breaches = _execution_cost(
            asset_delta,
            period_adv,
            net_value,
            execution,
        )
        cost_fraction = min(cost_usd / max(net_value, 1e-12), 0.99)
        turnover = 0.5 * float(np.abs(target - pre_trade).sum())
        period_returns = np.concatenate(
            [np.nan_to_num(period_assets, nan=0.0), [float(cash.iloc[index])]]
        )
        gross_return = float(target @ period_returns)
        pre_bank_fee_return = (1.0 - cost_fraction) * (1.0 + gross_return) - 1.0
        fee_rate = _annual_bank_fee_rate(fee_config, end_date)
        value_before_bank_fee = net_value * (1.0 + pre_bank_fee_return)
        bank_fee_usd = value_before_bank_fee * fee_rate
        net_return = (1.0 + pre_bank_fee_return) * (1.0 - fee_rate) - 1.0
        gross_value *= 1.0 + gross_return
        pre_bank_fee_value *= 1.0 + pre_bank_fee_return
        net_value = value_before_bank_fee - bank_fee_usd
        pre_trade = _drift_weights(target, period_returns)
        live_weight = float(target_assets.sum())
        required_live_weight = minimum_live * intended_invested_weight
        if full_investment_start is None and live_weight >= required_live_weight:
            full_investment_start = start_date
        rows.append(
            {
                'date': end_date,
                'period_start': start_date,
                'strategy': spec.key,
                'strategy_label': spec.label,
                'gross_return': gross_return,
                'pre_bank_fee_return': pre_bank_fee_return,
                'net_return': net_return,
                'turnover': turnover,
                'transaction_cost_usd': cost_usd,
                'transaction_cost_return': cost_fraction,
                'bank_fee_usd': bank_fee_usd,
                'bank_fee_return': fee_rate,
                'bank_fee_assessment_aum_usd': value_before_bank_fee if fee_rate else 0.0,
                'total_cost_usd': cost_usd + bank_fee_usd,
                'gross_value_usd': gross_value,
                'pre_bank_fee_value_usd': pre_bank_fee_value,
                'net_value_usd': net_value,
                'live_weight': live_weight,
                'available_target_weight': available_target_weight,
                'cash_weight': target_cash,
                'unfilled_target_weight': unfilled_weight,
                'holding_count': int((target_assets > 1e-12).sum()),
                'maximum_adv_participation': max_participation,
                'liquidity_breaches': liquidity_breaches + attempted_breaches,
                'initial_capital_usd': spec.initial_capital_usd,
                'capital_source': spec.capital_source,
                'evidence_type': spec.evidence_type,
            }
        )
    monthly = pd.DataFrame(rows)
    return ReplayResult(
        strategy=spec.key,
        label=spec.label,
        monthly=monthly,
        initial_capital_usd=spec.initial_capital_usd,
        capital_source=spec.capital_source,
        evidence_type=spec.evidence_type,
        full_investment_start=full_investment_start,
        source_files=spec.source_files,
    )


def replay_all_portfolios(
    specs: list[PortfolioSpec],
    bundle: MarketDataBundle,
    config: dict,
) -> list[ReplayResult]:
    return [replay_portfolio(spec, bundle, config) for spec in specs]


def _replay_weight_schedule(
    key: str,
    label: str,
    asset_returns: pd.DataFrame,
    weights: pd.DataFrame,
    cash_returns: pd.Series,
    initial_capital: float,
    evidence_type: str,
    linear_cost_bps: float = 0.0,
    annual_bank_fee: dict | None = None,
) -> ReplayResult:
    aligned_weights = weights.reindex(asset_returns.index).fillna(0.0)
    cash = cash_returns.reindex(asset_returns.index).fillna(0.0)
    pre_trade = np.zeros(len(asset_returns.columns) + 1)
    pre_trade[-1] = 1.0
    net_value = float(initial_capital)
    gross_value = float(initial_capital)
    pre_bank_fee_value = float(initial_capital)
    rows = []
    first_live = None
    for index in range(1, len(asset_returns)):
        end_date = asset_returns.index[index]
        start_date = asset_returns.index[index - 1]
        target_assets = aligned_weights.iloc[index - 1].to_numpy(dtype=float)
        target_cash = 1.0 - float(target_assets.sum())
        target = np.concatenate([target_assets, [target_cash]])
        period_assets = asset_returns.iloc[index].to_numpy(dtype=float)
        missing = (target_assets > 1e-12) & ~np.isfinite(period_assets)
        if missing.any():
            target_assets = target_assets.copy()
            target_assets[missing] = 0.0
            target_cash = 1.0 - float(target_assets.sum())
            target = np.concatenate([target_assets, [target_cash]])
        period_returns = np.concatenate(
            [np.nan_to_num(period_assets, nan=0.0), [float(cash.iloc[index])]]
        )
        turnover = 0.5 * float(np.abs(target - pre_trade).sum())
        traded_weight = float(np.abs(target_assets - pre_trade[:-1]).sum())
        cost_fraction = traded_weight * linear_cost_bps / 10_000.0
        gross_return = float(target @ period_returns)
        pre_bank_fee_return = (1.0 - cost_fraction) * (1.0 + gross_return) - 1.0
        fee_rate = _annual_bank_fee_rate(annual_bank_fee, end_date)
        value_before_bank_fee = net_value * (1.0 + pre_bank_fee_return)
        bank_fee_usd = value_before_bank_fee * fee_rate
        net_return = (1.0 + pre_bank_fee_return) * (1.0 - fee_rate) - 1.0
        cost_usd = net_value * cost_fraction
        gross_value *= 1.0 + gross_return
        pre_bank_fee_value *= 1.0 + pre_bank_fee_return
        net_value = value_before_bank_fee - bank_fee_usd
        pre_trade = _drift_weights(target, period_returns)
        live_weight = float(target_assets.sum())
        if first_live is None and live_weight >= 0.80:
            first_live = start_date
        rows.append(
            {
                'date': end_date,
                'period_start': start_date,
                'strategy': key,
                'strategy_label': label,
                'gross_return': gross_return,
                'pre_bank_fee_return': pre_bank_fee_return,
                'net_return': net_return,
                'turnover': turnover,
                'transaction_cost_usd': cost_usd,
                'transaction_cost_return': cost_fraction,
                'bank_fee_usd': bank_fee_usd,
                'bank_fee_return': fee_rate,
                'bank_fee_assessment_aum_usd': value_before_bank_fee if fee_rate else 0.0,
                'total_cost_usd': cost_usd + bank_fee_usd,
                'gross_value_usd': gross_value,
                'pre_bank_fee_value_usd': pre_bank_fee_value,
                'net_value_usd': net_value,
                'live_weight': live_weight,
                'cash_weight': target_cash,
                'holding_count': int((target_assets > 1e-12).sum()),
                'maximum_adv_participation': np.nan,
                'liquidity_breaches': 0,
                'initial_capital_usd': initial_capital,
                'capital_source': 'fixed_research_capital',
                'evidence_type': evidence_type,
            }
        )
    return ReplayResult(
        strategy=key,
        label=label,
        monthly=pd.DataFrame(rows),
        initial_capital_usd=initial_capital,
        capital_source='fixed_research_capital',
        evidence_type=evidence_type,
        full_investment_start=first_live,
    )


def _capped_weights(values: pd.Series, maximum: float) -> pd.Series:
    weights = pd.Series(0.0, index=values.index)
    remaining = values.clip(lower=0.0).copy()
    budget = 1.0
    while budget > 1e-12 and remaining.gt(0).any():
        proposal = remaining / remaining.sum() * budget
        capped = proposal.clip(upper=maximum)
        newly_capped = proposal.ge(maximum - 1e-12)
        weights += capped.where(newly_capped, 0.0)
        budget = 1.0 - float(weights.sum())
        remaining = remaining.where(~newly_capped, 0.0)
        if not newly_capped.any():
            weights += proposal
            break
    return weights.clip(lower=0.0, upper=maximum)


def _benchmark_key(prefix: str, value: str) -> str:
    slug = ''.join(character.lower() if character.isalnum() else '_' for character in value)
    return prefix + '_' + '_'.join(part for part in slug.split('_') if part)


def build_index_results(
    specs: list[PortfolioSpec],
    bundle: MarketDataBundle,
    config: dict,
) -> tuple[list[ReplayResult], ReplayResult]:
    prices = _monthly_prices(bundle.benchmark_prices_usd)
    returns = prices.pct_change(fill_method=None)
    cash = _monthly_cash_returns(bundle.cash_returns).reindex(prices.index).fillna(0.0)
    benchmark_config = config['benchmarks']
    region_symbols = {
        region: definition['symbol']
        for region, definition in benchmark_config['regions'].items()
    }
    benchmark_results = []
    for spec in specs:
        region_weights = spec.holdings.groupby('region')['weight'].sum()
        symbols = [region_symbols[region] for region in region_weights.index]
        static = pd.Series(
            [float(region_weights[region]) for region in region_weights.index],
            index=symbols,
        )
        schedule = pd.DataFrame(
            np.tile(static.to_numpy(), (len(prices), 1)),
            index=prices.index,
            columns=static.index,
        )
        result = _replay_weight_schedule(
            f'{spec.key}__regional_index',
            f'{spec.label} Regional Index Blend',
            returns.reindex(columns=symbols),
            schedule,
            cash,
            spec.initial_capital_usd,
            'regional_index_benchmark',
        )
        benchmark_results.append(result)

    for key, definition in (
        ('common_index', benchmark_config['common']),
        ('total_return_proxy', benchmark_config['total_return_proxy']),
    ):
        symbol = definition['symbol']
        schedule = pd.DataFrame(1.0, index=prices.index, columns=[symbol])
        benchmark_results.append(
            _replay_weight_schedule(
                key,
                definition['label'],
                returns[[symbol]],
                schedule,
                cash,
                float(config['backtest']['default_capital_usd']),
                'common_market_benchmark',
            )
        )

    standalone_definitions = [
        (_benchmark_key('region_index', region), definition)
        for region, definition in benchmark_config['regions'].items()
    ]
    standalone_definitions.extend(benchmark_config.get('additional', {}).items())
    for key, definition in standalone_definitions:
        symbol = definition['symbol']
        schedule = pd.DataFrame(1.0, index=prices.index, columns=[symbol])
        benchmark_results.append(
            _replay_weight_schedule(
                key,
                definition['label'],
                returns[[symbol]],
                schedule,
                cash,
                float(config['backtest']['default_capital_usd']),
                'standalone_market_benchmark',
            )
        )

    regional = list(region_symbols.values())
    equal_schedule = pd.DataFrame(
        1.0 / len(regional),
        index=prices.index,
        columns=regional,
    )
    benchmark_results.append(
        _replay_weight_schedule(
            'equal_weight_regional_indices',
            'Equal-Weight Regional Index Basket',
            returns[regional],
            equal_schedule,
            cash,
            float(config['backtest']['default_capital_usd']),
            'index_benchmark',
        )
    )

    challenger_config = config['index_challenger']
    momentum = prices[regional].pct_change(
        int(challenger_config['momentum_lookback_months']),
        fill_method=None,
    )
    volatility = returns[regional].rolling(
        int(challenger_config['volatility_lookback_months'])
    ).std() * np.sqrt(12.0)
    schedule = pd.DataFrame(0.0, index=prices.index, columns=regional)
    covariance_window = int(challenger_config['covariance_lookback_months'])
    for index in range(len(prices)):
        signal = momentum.iloc[index].gt(0) & volatility.iloc[index].gt(0)
        inverse_volatility = (1.0 / volatility.iloc[index]).where(signal, 0.0).fillna(0.0)
        weights = _capped_weights(
            inverse_volatility,
            float(challenger_config['maximum_region_weight']),
        )
        history = returns[regional].iloc[max(0, index - covariance_window + 1) : index + 1]
        if len(history.dropna(how='all')) >= 6 and weights.sum() > 0:
            covariance = history.cov(min_periods=6).fillna(0.0).to_numpy() * 12.0
            risk = float(np.sqrt(max(weights.to_numpy() @ covariance @ weights.to_numpy(), 0.0)))
            if risk > 0:
                weights *= min(1.0, float(challenger_config['target_volatility']) / risk)
        schedule.iloc[index] = weights
    challenger = _replay_weight_schedule(
        'trend_risk_controlled_indices',
        'Trend and Risk-Controlled Regional Indices',
        returns[regional],
        schedule,
        cash,
        float(config['backtest']['default_capital_usd']),
        'point_in_time_index_challenger',
        float(challenger_config['linear_cost_bps']),
        (
            config.get('annual_bank_fee', {})
            if config.get('annual_bank_fee', {}).get(
                'apply_to_research_challenger',
                True,
            )
            else None
        ),
    )
    return benchmark_results, challenger
