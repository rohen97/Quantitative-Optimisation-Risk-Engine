from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.config import ROOT


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the full equity model as resumable batch preprocessing plus one global allocation phase."
    )
    parser.add_argument("phase", choices=["phase1", "phase2", "all", "status"])
    parser.add_argument("--artifact-dir", default="data/interim/observed_full_universe_pipeline")
    parser.add_argument("--output-dir", default="reports/outputs")
    parser.add_argument("--input-mode", choices=["observed", "synthetic_test"], default="observed")
    parser.add_argument("--batch-size", type=int, default=2500)
    parser.add_argument("--min-price-rows", type=int, default=120)
    parser.add_argument("--max-securities", type=int, default=0)
    parser.add_argument("--price-lookback-rows", type=int, default=253)
    parser.add_argument("--regime-lookback-rows", type=int, default=126)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-inflight-securities", type=int, default=5000)
    parser.add_argument("--regions", nargs="*", default=[])
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--retain-intermediates", action="store_true")
    parser.add_argument("--with-governance", action="store_true")
    return parser


def _config(args: argparse.Namespace):
    from src.two_phase_pipeline import TwoPhaseConfig

    return TwoPhaseConfig(
        artifact_dir=_path(args.artifact_dir),
        output_dir=_path(args.output_dir),
        input_mode=args.input_mode,
        batch_size=args.batch_size,
        min_price_rows=args.min_price_rows,
        max_securities=args.max_securities,
        regions=tuple(args.regions),
        price_lookback_rows=args.price_lookback_rows,
        regime_lookback_rows=args.regime_lookback_rows,
        resume=not args.no_resume,
        force=args.force,
        retain_intermediates=args.retain_intermediates,
        max_workers=args.workers,
        max_inflight_securities=args.max_inflight_securities,
    )


def _status(artifact_dir: Path) -> None:
    manifest_path = artifact_dir / "manifest.json"
    if not manifest_path.exists():
        print(json.dumps({"status": "not_started", "artifact_dir": str(artifact_dir)}, indent=2))
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    batches = manifest.get("batches", [])
    completed = sum((artifact_dir / "batches" / entry["batch_id"] / "_SUCCESS.json").exists() for entry in batches)
    remaining = len(batches) - completed
    if (artifact_dir / "PHASE2_SUCCESS.json").exists():
        status = "phase2_completed"
    elif remaining == 0:
        status = "phase1_completed"
    else:
        status = "phase1_in_progress"
    payload = {
        "status": status,
        "security_count": manifest.get("security_count", 0),
        "completed_batches": completed,
        "total_batches": len(batches),
        "remaining_batches": remaining,
        "regions": sorted({entry["region"] for entry in batches}),
    }
    print(json.dumps(payload, indent=2))


def _run_governance(output_dir: Path) -> None:
    from src.reporting.ic_pipeline import run_ic_reporting
    from src.validation.validation_pipeline import run_validation_pipeline

    logging.info("Governance: Investment Committee reporting begins.")
    bundle = run_ic_reporting(output_root=output_dir)
    logging.info("Governance: IC report=%s readiness=%s.", bundle.html_path, bundle.readiness_status)
    logging.info("Governance: validation pipeline begins.")
    result = run_validation_pipeline(execution_mode="smoke", run_sensitivity=False, run_ablation=False)
    logging.info(
        "Governance completed: approval=%s score=%.1f output=%s.",
        result.approval_status,
        result.overall_score,
        result.output_directory,
    )


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.phase == "status":
        _status(_path(args.artifact_dir))
    else:
        from src.two_phase_pipeline import run_phase_one, run_phase_two

        config = _config(args)
        if args.phase in {"phase1", "all"}:
            summary = run_phase_one(config)
            logging.info("Phase 1 summary: %s", summary)
        if args.phase in {"phase2", "all"}:
            outputs = run_phase_two(config)
            logging.info("Phase 2 produced %s output frames.", len(outputs))
            if args.with_governance:
                _run_governance(config.output_dir)
