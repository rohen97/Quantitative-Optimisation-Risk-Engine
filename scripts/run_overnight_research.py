from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.production.overnight import run_overnight_plan
from src.utils.config import load_yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run the research pipeline unattended with checkpoints and memory guardrails.'
    )
    parser.add_argument('--config', type=Path, default=Path('configs/overnight.yaml'))
    parser.add_argument('--max-hours', type=float, default=None)
    parser.add_argument('--no-resume', action='store_true')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    config = load_yaml(config_path)
    return run_overnight_plan(
        config,
        ROOT,
        resume=not args.no_resume,
        max_hours=args.max_hours,
    )


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s - %(message)s',
    )
    raise SystemExit(main())
