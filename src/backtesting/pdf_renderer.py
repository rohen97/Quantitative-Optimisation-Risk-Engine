from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render a backtest HTML report to PDF.')
    parser.add_argument('html_path', type=Path)
    parser.add_argument('pdf_path', type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from weasyprint import HTML

    args.pdf_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(
        filename=str(args.html_path),
        base_url=str(args.html_path.parent),
    ).write_pdf(str(args.pdf_path))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
