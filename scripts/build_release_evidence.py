from __future__ import annotations

import argparse
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.reporting.release_evidence import build_release_evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Build a compact, checksummed release-evidence package.'
    )
    parser.add_argument(
        '--release-id',
        default='2026-08-07-full-universe',
        help='Directory name under reports/releases/.',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_release_evidence(args.release_id)
    print(f'Release evidence: {result.output_directory}')
    print(f'Files: {result.file_count}')
    print(f'Validation run: {result.validation_run_id}')
    print(f'Status: {result.approval_status}')
    print(f'Score: {result.overall_score:.1f}')


if __name__ == '__main__':
    main()
