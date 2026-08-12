from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.reporting.investment_principal_deck import (
    build_investment_principal_deck,
    register_rendered_pdf,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Build the Wolf investment committee PowerPoint.'
    )
    parser.add_argument(
        '--repo-root',
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help='Repository root containing reports and model outputs.',
    )
    parser.add_argument(
        '--output-directory',
        type=Path,
        default=None,
        help='Optional output directory.',
    )
    parser.add_argument(
        '--register-rendered-pdf',
        action='store_true',
        help='Register an existing PowerPoint-rendered PDF in the manifest.',
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    args = parse_args()
    if args.register_rendered_pdf:
        manifest = register_rendered_pdf(
            args.repo_root,
            args.output_directory,
        )
        logging.info('Registered rendered PDF: %s', manifest)
        return 0
    result = build_investment_principal_deck(
        args.repo_root,
        args.output_directory,
    )
    logging.info(
        'Built %s slides: %s',
        result.slide_count,
        result.pptx_path,
    )
    logging.info('Published report: %s', result.report_path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
