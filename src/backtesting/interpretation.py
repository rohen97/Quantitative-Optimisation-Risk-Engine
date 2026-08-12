from __future__ import annotations

import pandas as pd


def _percent(value: object) -> str:
    return f'{float(value):.2%}' if pd.notna(value) else 'not available'


def _number(value: object) -> str:
    return f'{float(value):.2f}' if pd.notna(value) else 'not available'


def _money(value: object) -> str:
    return '$' + f'{float(value):,.0f}' if pd.notna(value) else 'not available'


def _best(frame: pd.DataFrame, column: str) -> pd.Series | None:
    if frame.empty or column not in frame or frame[column].dropna().empty:
        return None
    return frame.loc[frame[column].idxmax()]


def _row(frame: pd.DataFrame, strategy: str) -> pd.Series | None:
    if 'strategy' not in frame:
        return None
    selected = frame.loc[frame['strategy'].eq(strategy)]
    return selected.iloc[0] if not selected.empty else None


def _regime_interpretation(
    frame: pd.DataFrame,
    dimension_description: str,
) -> str:
    focus = frame.loc[frame['strategy'].eq('final_portfolio')]
    if focus.empty:
        focus = frame
    leader = _best(focus, 'annualised_geometric_return')
    text = (
        f'This table groups non-contiguous months by {dimension_description} and '
        'annualizes the observations in each group. It is a conditional description, '
        'not a continuous investable path or a causal estimate. '
    )
    if leader is not None:
        text += (
            f'For {leader.strategy_label}, the strongest group is '
            f'{leader.environment}, with a conditional geometric return of '
            f'{_percent(leader.annualised_geometric_return)} across '
            f'{int(leader.observations)} months.'
        )
    return text


def build_report_interpretations(
    frames: dict[str, pd.DataFrame],
    manifest: dict,
) -> dict[str, str]:
    performance = frames['performance_summary']
    requested = performance.loc[
        performance['window'].eq('requested_1997_window')
    ]
    common = performance.loc[
        performance['window'].eq('common_investable_window')
    ]
    current = _row(requested, 'current_portfolio')
    best_cagr = _best(common, 'cagr')
    best_sharpe = _best(common, 'sharpe')
    requested_years = float(manifest.get('requested_years', 0.0))
    output_count = int(manifest.get('portfolio_output_count', 0))

    overall = (
        f'The test covers {requested_years:.1f} years and '
        f'{output_count} portfolio outputs. '
    )
    if current is not None:
        overall += (
            f'The current portfolio starts at {_money(current.initial_capital_usd)} '
            f'and finishes at {_money(current.ending_value_usd)} after modeled costs, '
            f'a net PnL of {_money(current.pnl_usd)}. '
        )
    if best_sharpe is not None:
        overall += (
            f'On the common investable window, {best_sharpe.strategy_label} has '
            f'the highest Sharpe ratio at {_number(best_sharpe.sharpe)}. '
        )
    overall += (
        'The long results replay securities selected with today\'s information, so they '
        'describe exposure and path behavior rather than proving historical selection skill.'
    )

    executive = (
        'The performance table converts each assigned starting balance into a fully net '
        'ending balance. CAGR is the smooth annual growth rate, volatility measures return '
        'variation, Sharpe compares excess return with total variability, and maximum '
        'drawdown is the deepest peak-to-trough loss. '
    )
    if best_cagr is not None:
        executive += (
            f'{best_cagr.strategy_label} records the highest common-window CAGR at '
            f'{_percent(best_cagr.cagr)} alongside a '
            f'{_percent(best_cagr.maximum_drawdown)} maximum drawdown.'
        )

    ratios = frames['paper_ratio_summary']
    ratio_best = _best(ratios, 'lo_adjusted_sharpe')
    ratio_text = (
        'Sharpe uses all volatility; Lo-adjusted Sharpe allows for serially related '
        'monthly returns; Sortino counts downside variability; and Calmar divides CAGR '
        'by maximum drawdown. Monthly VaR is the 5% loss threshold, while expected '
        'shortfall is the average loss beyond it. PSR measures confidence that Sharpe '
        'clears a hurdle, MinTRL estimates the required history, and DSR discounts '
        'non-normal returns and multiple trials. '
    )
    if ratio_best is not None:
        ratio_text += (
            f'{ratio_best.strategy_label} has the strongest Lo-adjusted Sharpe '
            f'at {_number(ratio_best.lo_adjusted_sharpe)}.'
        )

    fee = frames['annual_bank_fee_assumption'].iloc[0]
    fee_assumption = (
        f'The bank charge is {float(fee.annual_rate_bps):.0f} basis points, assessed '
        f'once in month {int(fee.charge_month)} on then-current AUM. At reference '
        f'AUM of {_money(fee.reference_aum_usd)}, the configured and calculated '
        f'charges equal {_money(fee.calculated_reference_charge_usd)} and differ by '
        f'{_money(fee.reconciliation_difference_usd)}. The same percentage, not the '
        'full reference-dollar amount, applies to each portfolio; external benchmarks '
        'remain uncharged.'
    )

    costs = frames['cost_liquidity_summary']
    largest_fee = _best(costs, 'total_bank_fee_usd')
    fee_impact = (
        'The fee-impact table separates trading costs from the annual bank charge and '
        'compares ending value before bank fees with the fully net result. '
    )
    if largest_fee is not None:
        fee_impact += (
            f'{largest_fee.strategy} pays the largest cumulative bank charge at '
            f'{_money(largest_fee.total_bank_fee_usd)}, with ending-value fee drag '
            f'of {_money(largest_fee.ending_value_bank_fee_drag_usd)}.'
        )

    benchmarks = frames['standalone_benchmark_performance']
    benchmark_common = benchmarks.loc[
        benchmarks['window'].eq('common_investable_window')
    ]
    best_index = _best(benchmark_common, 'cagr')
    benchmark_text = (
        'Each standalone index is converted to USD and replayed as an uncharged '
        'buy-and-hold reference on $100,000. Price-index and total-return conventions '
        'differ, so these are broad path comparisons rather than perfectly '
        'dividend-consistent alpha tests. '
    )
    if best_index is not None:
        benchmark_text += (
            f'{best_index.strategy_label} has the highest common-window CAGR at '
            f'{_percent(best_index.cagr)}.'
        )

    relative = frames['benchmark_relative_summary']
    relative = relative.loc[relative['window'].eq('common_investable_window')]
    relative_best = _best(relative, 'information_ratio')
    relative_text = (
        'Each portfolio is compared with an index blend matching its regional weights. '
        'Alpha is annualized return not explained by beta, tracking error is active-return '
        'volatility, and information ratio is active return per unit of tracking error. '
    )
    if relative_best is not None:
        relative_text += (
            f'{relative_best.strategy_label} has the highest information ratio at '
            f'{_number(relative_best.information_ratio)} and relative PnL of '
            f'{_money(relative_best.relative_pnl_usd)}.'
        )

    events = frames['macro_event_performance']
    event_focus = events.loc[events['strategy'].eq('final_portfolio')]
    worst_event = (
        event_focus.loc[event_focus['cumulative_return'].idxmin()]
        if not event_focus.empty
        else None
    )
    event_definitions_text = (
        'The event-definition table supplies source-backed windows shaded on the charts. '
        'They are market-response intervals for monthly analysis, not claims about legal '
        'war dates, and overlapping events can share return months.'
    )
    event_text = (
        'Event return compounds all overlapping monthly observations, event drawdown '
        'measures the loss within that window, and event PnL applies the return to actual '
        'simulated AUM at the start of the window. '
    )
    if worst_event is not None:
        event_text += (
            f'The weakest configured event for the final portfolio is '
            f'{worst_event.event_label}, returning '
            f'{_percent(worst_event.cumulative_return)} with a '
            f'{_percent(worst_event.maximum_drawdown)} within-window drawdown.'
        )

    significance = frames['statistical_significance']
    significant_count = int(significance['sidak_significant'].fillna(False).sum())
    significance_text = (
        f'PSR and MinTRL evaluate reliability, Sidak controls family-wise error across '
        f'tested strategies, and DSR penalizes multiple trials and non-normal returns. '
        f'{significant_count} of {len(significance)} results clear Sidak; significance '
        'does not remove retrospective selection look-ahead.'
    )

    alpha_tests = frames['benchmark_alpha_significance']
    common_alpha = alpha_tests.loc[
        alpha_tests['window'].eq('common_investable_window')
    ]
    reality = frames['strategy_reality_check']
    overfitting = frames['strategy_overfitting_summary']
    alpha_overfitting = (
        'Newey-West regressions test alpha against each portfolio-specific regional '
        'index blend while allowing serial correlation. The block-bootstrap max-t '
        'test controls selection across the whole strategy family, and CSCV repeatedly '
        'selects in one half of the history and ranks that winner in the other half. '
    )
    if not overfitting.empty:
        audit = overfitting.iloc[0]
        alpha_overfitting += (
            f'{int(reality.familywise_significant.fillna(False).sum())} unique results '
            f'clear the max-t family-wise test. CSCV estimates PBO at '
            f'{_percent(audit.probability_of_backtest_overfitting)}, while the median '
            f'selected information ratio falls from '
            f'{_number(audit.median_selected_is_information_ratio)} in-sample to '
            f'{_number(audit.median_selected_oos_information_ratio)} out-of-sample. '
        )
    if not common_alpha.empty:
        best_alpha = common_alpha.loc[common_alpha['annualised_alpha'].idxmax()]
        alpha_overfitting += (
            f'The largest measured common-window alpha is '
            f'{_percent(best_alpha.annualised_alpha)} for '
            f'{best_alpha.strategy_label}. Every long portfolio path is still a '
            'retrospective holdings replay, so these tests measure path robustness, '
            'not deployable stock-selection alpha.'
        )

    block = frames['block_resampling_summary']
    block_low = block.loc[block['cagr_p05'].idxmin()] if not block.empty else None
    resampling = (
        'The moving-block bootstrap rearranges 12-month blocks while preserving '
        'short-run dependence and cross-strategy alignment. Its 5th, median, and 95th '
        'percentiles show sensitivity to historical path order. '
    )
    if block_low is not None:
        resampling += (
            f'The lowest 5th-percentile CAGR is {block_low.strategy} at '
            f'{_percent(block_low.cagr_p05)}.'
        )

    simulation = frames['monte_carlo_summary']
    simulation_low = (
        simulation.loc[simulation['cagr_p05'].idxmin()]
        if not simulation.empty
        else None
    )
    monte_carlo = (
        'Monte Carlo uses correlated Student-t shocks, AR(1) persistence, and EWMA '
        'volatility to create fat-tailed, volatility-clustered paths. It is a modeled '
        'stress distribution, not a forecast promise. '
    )
    if simulation_low is not None:
        monte_carlo += (
            f'The lowest simulated 5th-percentile CAGR is '
            f'{simulation_low.strategy} at {_percent(simulation_low.cagr_p05)}.'
        )

    repairs = frames['price_quality_adjustments']
    repair_word = 'repairs' if len(repairs) != 1 else 'repair'
    point_in_time_months = int(manifest.get('point_in_time_months', 0))
    pit_alpha = frames.get('point_in_time_alpha_significance', pd.DataFrame())
    pit_text = (
        f'The point-in-time table contains {point_in_time_months} '
        'dated decision months and remains separate from the long holdings replay. '
        'It is the more relevant evidence for decisions made with contemporaneous data. '
    )
    if not pit_alpha.empty:
        equal_weight = pit_alpha.loc[
            pit_alpha['benchmark'].eq('equal_weight_eligible')
        ]
        cap_weight = pit_alpha.loc[
            pit_alpha['benchmark'].eq('cap_weight_eligible')
        ]
        if not equal_weight.empty:
            row = equal_weight.iloc[0]
            pit_text += (
                f'Against equal-weight eligible stocks, annualised active return is '
                f'{_percent(row.annualised_active_return)} and the alpha verdict is '
                f'{row.alpha_evidence_verdict}. '
            )
        if not cap_weight.empty:
            row = cap_weight.iloc[0]
            pit_text += (
                f'Against cap-weight eligible stocks, annualised active return is '
                f'{_percent(row.annualised_active_return)} and the verdict is '
                f'{row.alpha_evidence_verdict}. Native live evidence and at least '
                f'{int(row.minimum_required_months)} months are required before alpha '
                'can be considered deployable.'
            )
    return {
        'overall': overall,
        'executive': executive,
        'ratios': ratio_text,
        'fee_assumption': fee_assumption,
        'fee_impact': fee_impact,
        'benchmarks': benchmark_text,
        'relative_benchmarks': relative_text,
        'rate_level': _regime_interpretation(
            frames['interest_rate_level_performance'],
            'the lagged 3-month Treasury-bill yield level',
        ),
        'rate_direction': _regime_interpretation(
            frames['interest_rate_direction_performance'],
            'the prior 12-month change in the Treasury-bill yield',
        ),
        'market_regime': _regime_interpretation(
            frames['market_regime_performance'],
            'lagged S&P 500 momentum and volatility',
        ),
        'economic_cycle': _regime_interpretation(
            frames['economic_cycle_performance'],
            'the retrospective NBER recession indicator',
        ),
        'event_definitions': event_definitions_text,
        'events': event_text,
        'significance': significance_text,
        'alpha_overfitting': alpha_overfitting,
        'resampling': (
            resampling
        ),
        'monte_carlo': monte_carlo,
        'embargo': (
            'The embargo table compares the development sample with the final untouched '
            '36 months. A sharp fall in Sharpe or return signals instability; agreement '
            'is encouraging but cannot cure retrospective selection bias.'
        ),
        'execution': (
            'Execution rows show dollar costs, turnover, peak ADV participation, '
            'constrained trades, and unfilled weight. Large current-derived AUM can leave '
            'low-liquidity targets partly in cash, making these results capacity-aware.'
        ),
        'repairs': (
            f'The adjusted-price process made {len(repairs)} explicit {repair_word}. '
            'Each row records the raw move, rule, repaired return, and scale factor so '
            'provider anomalies remain auditable.'
        ),
        'limitations': (
            'The limitation register distinguishes modeled, controlled, separated, and '
            'unresolved risks. The critical issue is that current holdings survived long '
            'enough to be selected today, so the 1997 replay cannot prove selection skill.'
        ),
        'pit': pit_text,
    }


def written_interpretation_markdown(
    interpretations: dict[str, str],
) -> str:
    sections = [
        ('Overall Result', 'overall'),
        ('Portfolio Performance', 'executive'),
        ('Performance Ratios', 'ratios'),
        ('Annual Bank Fee Assumption', 'fee_assumption'),
        ('Annual Bank Fee Impact', 'fee_impact'),
        ('Major Index Benchmarks', 'benchmarks'),
        ('Portfolio-Relative Benchmarks', 'relative_benchmarks'),
        ('Interest-Rate Levels', 'rate_level'),
        ('Interest-Rate Direction', 'rate_direction'),
        ('Market Regimes', 'market_regime'),
        ('Economic Cycle', 'economic_cycle'),
        ('Macro-Event Definitions', 'event_definitions'),
        ('Macro-Event Performance', 'events'),
        ('Statistical Significance', 'significance'),
        ('Alpha and Overfitting', 'alpha_overfitting'),
        ('Block Resampling', 'resampling'),
        ('Monte Carlo', 'monte_carlo'),
        ('Embargo Test', 'embargo'),
        ('Execution and Liquidity', 'execution'),
        ('Price Repairs', 'repairs'),
        ('Bias and Limitations', 'limitations'),
        ('Point-in-Time Evidence', 'pit'),
    ]
    lines = ['# Plain-Language Backtest Interpretation', '']
    for title, key in sections:
        lines.extend([f'## {title}', '', interpretations[key], ''])
    return '\n'.join(lines)
