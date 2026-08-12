import pandas as pd

from src.backtesting.interpretation import build_report_interpretations
from src.backtesting.reporting import _format_value, _meaningful_pdf_stderr


def test_report_interpretation_renders_all_sections() -> None:
    performance = pd.DataFrame(
        [
            {
                'window': 'requested_1997_window',
                'strategy': 'current_portfolio',
                'strategy_label': 'Current Portfolio',
                'initial_capital_usd': 186_060_522.0,
                'ending_value_usd': 200_000_000.0,
                'pnl_usd': 13_939_478.0,
                'cagr': 0.08,
                'sharpe': 0.60,
                'maximum_drawdown': -0.30,
            },
            {
                'window': 'common_investable_window',
                'strategy': 'final_portfolio',
                'strategy_label': 'Final Portfolio',
                'initial_capital_usd': 186_060_522.0,
                'ending_value_usd': 210_000_000.0,
                'pnl_usd': 23_939_478.0,
                'cagr': 0.10,
                'sharpe': 0.75,
                'maximum_drawdown': -0.25,
            },
        ]
    )
    regime = pd.DataFrame(
        [
            {
                'strategy': 'final_portfolio',
                'strategy_label': 'Final Portfolio',
                'environment': 'Low',
                'annualised_geometric_return': 0.10,
                'observations': 24,
            }
        ]
    )
    frames = {
        'performance_summary': performance,
        'paper_ratio_summary': pd.DataFrame(
            [
                {
                    'strategy_label': 'Final Portfolio',
                    'lo_adjusted_sharpe': 0.70,
                }
            ]
        ),
        'annual_bank_fee_assumption': pd.DataFrame(
            [
                {
                    'annual_rate_bps': 25.0,
                    'charge_month': 12,
                    'reference_aum_usd': 186_060_522.0,
                    'calculated_reference_charge_usd': 465_151.305,
                    'reconciliation_difference_usd': 0.0,
                }
            ]
        ),
        'cost_liquidity_summary': pd.DataFrame(
            [
                {
                    'strategy': 'final_portfolio',
                    'total_bank_fee_usd': 1_000_000.0,
                    'ending_value_bank_fee_drag_usd': 1_100_000.0,
                }
            ]
        ),
        'standalone_benchmark_performance': pd.DataFrame(
            [
                {
                    'window': 'common_investable_window',
                    'strategy_label': 'DAX',
                    'cagr': 0.07,
                }
            ]
        ),
        'benchmark_relative_summary': pd.DataFrame(
            [
                {
                    'window': 'common_investable_window',
                    'strategy_label': 'Final Portfolio',
                    'information_ratio': 0.40,
                    'relative_pnl_usd': 2_000_000.0,
                }
            ]
        ),
        'macro_event_performance': pd.DataFrame(
            [
                {
                    'strategy': 'final_portfolio',
                    'event_label': 'Test crisis',
                    'cumulative_return': -0.10,
                    'maximum_drawdown': -0.12,
                }
            ]
        ),
        'statistical_significance': pd.DataFrame(
            [{'sidak_significant': True}]
        ),
        'benchmark_alpha_significance': pd.DataFrame(
            [
                {
                    'window': 'common_investable_window',
                    'strategy_label': 'Final Portfolio',
                    'annualised_alpha': 0.04,
                }
            ]
        ),
        'strategy_reality_check': pd.DataFrame(
            [{'familywise_significant': True}]
        ),
        'strategy_overfitting_summary': pd.DataFrame(
            [
                {
                    'probability_of_backtest_overfitting': 0.20,
                    'median_selected_is_information_ratio': 1.20,
                    'median_selected_oos_information_ratio': 0.60,
                }
            ]
        ),
        'block_resampling_summary': pd.DataFrame(
            [{'strategy': 'final_portfolio', 'cagr_p05': 0.02}]
        ),
        'monte_carlo_summary': pd.DataFrame(
            [{'strategy': 'final_portfolio', 'cagr_p05': -0.01}]
        ),
        'price_quality_adjustments': pd.DataFrame(),
        'interest_rate_level_performance': regime,
        'interest_rate_direction_performance': regime,
        'market_regime_performance': regime,
        'economic_cycle_performance': regime,
        'point_in_time_summary': pd.DataFrame(),
        'point_in_time_alpha_significance': pd.DataFrame(),
    }
    interpretations = build_report_interpretations(
        frames,
        {
            'requested_years': 29.5,
            'portfolio_output_count': 5,
            'point_in_time_months': 25,
        },
    )

    assert len(interpretations) == 22
    assert '25 basis points' in interpretations['fee_assumption']
    assert '$465,151' in interpretations['fee_assumption']
    assert '29.5 years' in interpretations['overall']


def test_pdf_stderr_filter_keeps_real_errors() -> None:
    stderr = (
        'GLib-GIO-WARNING: Unexpectedly, UWP app Outlook supports extensions\n'
        'real renderer failure\n'
    )

    assert _meaningful_pdf_stderr(stderr) == 'real renderer failure'


def test_report_formatter_preserves_alpha_status_text() -> None:
    assert _format_value('alpha_claim_status', 'RETROSPECTIVE_ONLY') == (
        'RETROSPECTIVE_ONLY'
    )
    assert _format_value('annualised_cost_drag', 0.0197) == '1.97%'
    assert _format_value('cscv_selection_frequency', 0.484) == '48.40%'
