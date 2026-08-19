from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository
from src.utils.config import ROOT
from src.utils.env import get_env


LOGGER = logging.getLogger(__name__)
PHASES = (
    "macro",
    "sec",
    "openfigi",
    "openbb",
    "yfinance",
    "akshare",
)


def _openfigi_key_configured() -> bool:
    return bool(get_env("OPENFIGI_API_KEY", "") or get_env("OPEN_FIGI_API_KEY", ""))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the free PIT/market-data stack in checkpointed, bounded phases."
    )
    parser.add_argument("--phases", nargs="+", choices=PHASES, default=list(PHASES))
    parser.add_argument("--start", default="1994-01-01")
    parser.add_argument("--end", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--max-sec-symbols", type=int, default=100)
    parser.add_argument("--max-openfigi-symbols", type=int, default=0)
    parser.add_argument("--max-yfinance-symbols", type=int, default=0)
    parser.add_argument("--max-akshare-symbols", type=int, default=0)
    parser.add_argument("--yfinance-batch-size", type=int, default=20)
    parser.add_argument("--akshare-batch-size", type=int, default=10)
    parser.add_argument("--sec-user-agent", default=get_env("SEC_USER_AGENT", "") or "")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument(
        "--status-path",
        type=Path,
        default=Path("reports/outputs/validation/free_data_stack_status.json"),
    )
    return parser.parse_args(argv)


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _read_status(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"phases": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {"phases": {}}
    except (OSError, ValueError, json.JSONDecodeError):
        return {"phases": {}}


def _write_status(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def _command_hash(command: list[str], environment_overrides: dict[str, str]) -> str:
    payload = json.dumps(
        {"command": command, "environment": environment_overrides},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _commands(args: argparse.Namespace) -> dict[str, tuple[list[str], dict[str, str]]]:
    python = sys.executable
    macro = [
        python,
        str(ROOT / "scripts" / "run_macro_vintage_backfill.py"),
        "--start",
        args.start,
        "--end",
        args.end,
        "--skip-migrations",
    ]
    sec = [
        python,
        str(ROOT / "scripts" / "run_point_in_time_evidence_backfill.py"),
        "--sources",
        "sec",
        "--start-year",
        str(int(args.start[:4])),
        "--end-year",
        str(int(args.end[:4])),
        "--max-us-symbols",
        str(args.max_sec_symbols),
        "--skip-migrations",
    ]
    openfigi = [
        python,
        str(ROOT / "scripts" / "run_openfigi_backfill.py"),
        "--max-symbols",
        str(args.max_openfigi_symbols),
        "--skip-migrations",
    ]
    openbb = [
        python,
        str(ROOT / "scripts" / "run_openbb_benchmark_validation.py"),
        "--start",
        max(args.start, "1997-01-01"),
        "--end",
        args.end,
    ]
    yfinance = [
        python,
        str(ROOT / "scripts" / "run_price_backfill.py"),
        "--regions",
        "Mainland China",
        "Hong Kong",
        "--listing-status",
        "Active",
        "Inactive",
        "--batch-size",
        str(max(args.yfinance_batch_size, 1)),
        "--max-symbols",
        str(args.max_yfinance_symbols),
        "--sleep-seconds",
        "0.25",
        "--refresh-missing-volume",
        "--minimum-volume-rows",
        "120",
        "--ignore-skip-list",
        "--skip-migrations",
    ]
    akshare = [
        python,
        str(ROOT / "scripts" / "run_price_backfill.py"),
        "--regions",
        "Mainland China",
        "Hong Kong",
        "--listing-status",
        "Active",
        "Inactive",
        "--batch-size",
        str(max(args.akshare_batch_size, 1)),
        "--max-symbols",
        str(args.max_akshare_symbols),
        "--sleep-seconds",
        "0.15",
        "--refresh-missing-volume",
        "--minimum-volume-rows",
        "120",
        "--ignore-skip-list",
        "--skip-migrations",
    ]
    return {
        "macro": (macro, {}),
        "sec": (sec, {"SEC_USER_AGENT": args.sec_user_agent}),
        "openfigi": (openfigi, {}),
        "openbb": (openbb, {"OPENBB_ENABLED": "true"}),
        "yfinance": (
            yfinance,
            {
                "DATA_PRICE_PROVIDERS": "yfinance",
                "USE_ALL_AVAILABLE_DATA_SOURCES": "true",
                "YFINANCE_LOOKBACK_DAYS": str(
                    max(
                        (datetime.now(UTC).date() - date.fromisoformat(args.start[:10])).days,
                        756,
                    )
                ),
                "YFINANCE_PROGRESS": "false",
            },
        ),
        "akshare": (
            akshare,
            {
                "DATA_PRICE_PROVIDERS": "akshare",
                "USE_ALL_AVAILABLE_DATA_SOURCES": "true",
            },
        ),
    }


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    status_path = _resolve(args.status_path)
    status = _read_status(status_path)
    status["started_at"] = datetime.now(UTC).isoformat()
    status["requested_phases"] = list(args.phases)
    phase_status = status.setdefault("phases", {})
    if not isinstance(phase_status, dict):
        phase_status = {}
        status["phases"] = phase_status

    data_config = load_data_config()
    repository = DuckDBRepository(data_config.duckdb_path)
    repository.execute_migrations(data_config.migrations_path)
    commands = _commands(args)
    failures = 0
    for phase in args.phases:
        command, overrides = commands[phase]
        digest = _command_hash(command, overrides)
        previous = phase_status.get(phase, {})
        if (
            not args.force
            and isinstance(previous, dict)
            and previous.get("status") == "completed"
            and previous.get("command_hash") == digest
        ):
            LOGGER.info("Skipping completed free-data phase %s.", phase)
            continue
        if phase == "sec" and not args.sec_user_agent:
            phase_status[phase] = {
                "status": "blocked",
                "command_hash": digest,
                "reason": "SEC_USER_AGENT must identify the application and a contact.",
            }
            failures += 1
            _write_status(status_path, status)
            if args.stop_on_error:
                break
            continue

        LOGGER.info("Starting free-data phase %s.", phase)
        started = time.monotonic()
        environment = os.environ.copy()
        environment.update(overrides)
        completed = subprocess.run(command, cwd=ROOT, env=environment, check=False)
        elapsed = time.monotonic() - started
        phase_status[phase] = {
            "status": "completed" if completed.returncode == 0 else "failed",
            "command_hash": digest,
            "return_code": completed.returncode,
            "runtime_seconds": round(elapsed, 3),
            "completed_at": datetime.now(UTC).isoformat(),
        }
        if phase == "openfigi" and not _openfigi_key_configured():
            phase_status[phase]["limitation"] = (
                "Anonymous safety limits apply; this phase does not imply complete-universe mapping."
            )
        if completed.returncode != 0:
            failures += 1
        _write_status(status_path, status)
        if completed.returncode != 0 and args.stop_on_error:
            break

    status["completed_at"] = datetime.now(UTC).isoformat()
    status["status"] = "completed" if failures == 0 else "completed_with_blockers"
    _write_status(status_path, status)
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
