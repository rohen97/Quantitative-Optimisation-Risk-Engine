from __future__ import annotations

import argparse
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.production.supervised_alpha_shadow import freeze_supervised_alpha_research
from src.utils.config import ROOT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Freeze the governed supervised-alpha version for prospective shadow evidence.'
    )
    parser.add_argument('--config', default='configs/ml_forecasting.yaml')
    parser.add_argument('--effective-date', default=None)
    parser.add_argument('--output-directory', default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = Path(args.config)
    if not config.is_absolute():
        config = ROOT / config
    output = Path(args.output_directory) if args.output_directory else None
    if output is not None and not output.is_absolute():
        output = ROOT / output
    path = freeze_supervised_alpha_research(
        config_path=config,
        output_directory=output,
        effective_date=args.effective_date,
    )
    print(f'Frozen supervised-alpha research manifest: {path}')


if __name__ == '__main__':
    main()
