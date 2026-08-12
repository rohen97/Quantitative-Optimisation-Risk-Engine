from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run the complete 1997 portfolio-output backtest evidence suite.',
    )
    parser.add_argument(
        '--config',
        default='configs/backtest.yaml',
        help='Backtest YAML path relative to the repository root.',
    )
    parser.add_argument(
        '--refresh-data',
        action='store_true',
        help='Ignore the local Yahoo Finance and FRED caches.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from src.backtesting.pipeline import run_backtest_suite

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
    )
    for logger_name in ('fontTools', 'weasyprint', 'matplotlib', 'PIL'):
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    result = run_backtest_suite(args.config, refresh_data=args.refresh_data)
    summary = result['frames']['performance_summary']
    requested = summary.loc[summary['window'].eq('requested_1997_window')]
    requested = requested.sort_values('sharpe', ascending=False)
    columns = ['strategy_label', 'cagr', 'sharpe', 'maximum_drawdown', 'ending_value_usd']
    print(requested[columns].to_string(index=False))
    html_report = result['paths']['html_report']
    pdf_report = result['paths']['pdf_report']
    print(f'HTML report: {html_report}')
    print(f'PDF report: {pdf_report}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
