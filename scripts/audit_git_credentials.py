from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.credential_audit import scan_git_credentials, write_credential_audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit known provider credential assignments without emitting values."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/outputs/validation/credential_history_audit.json"),
    )
    parser.add_argument("--fail-on-history", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = scan_git_credentials(ROOT)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    write_credential_audit(report, output)
    print(f"Current tree: {report['current_tree_status']}")
    print(f"Git history: {report['history_status']}")
    print(f"Commits scanned: {report['commits_scanned']}")
    print(f"Report: {output}")
    if report["current_tree_status"] != "PASS":
        return 3
    if args.fail_on_history and report["history_status"] != "PASS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
