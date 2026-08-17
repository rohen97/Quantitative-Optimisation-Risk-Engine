from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
import json
import logging
from pathlib import Path
import re
import time

import numpy as np
import pandas as pd

from src.alternative_data.alt_features import run_alternative_data_pipeline
from src.data.config import load_data_config
from src.data.lineage import new_model_run_metadata
from src.data_ingestion.fundamental_ingestion import load_fundamentals
from src.data_ingestion.mock_data import prepare_synthetic_test_universe
from src.features.risk_features import build_price_risk_base, finalise_price_risk_features
from src.narrative.pipeline import run_narrative_pipeline
from src.pipeline import run_pipeline_from_inputs
from src.pipeline_inputs import (
    load_duckdb_universe,
    load_observed_fundamentals,
    load_recent_duckdb_prices,
)
from src.portfolio.portfolio_loader import load_current_portfolio
from src.regime.chaos_index import calculate_wolf_chaos_index_from_returns
from src.utils.config import ROOT, load_yaml


LOGGER = logging.getLogger(__name__)
ARTIFACT_VERSION = 3
CORE_BATCH_FILES = (
    "price_risk_base.parquet",
    "recent_returns.parquet",
    "alt_features_monthly.parquet",
    "narrative_reframing_features.parquet",
)


@dataclass(frozen=True)
class TwoPhaseConfig:
    artifact_dir: Path = ROOT / "data/interim/observed_full_universe_pipeline"
    output_dir: Path = ROOT / "reports/outputs"
    input_mode: str = "observed"
    batch_size: int = 2500
    min_price_rows: int = 120
    max_securities: int = 0
    regions: tuple[str, ...] = ()
    price_lookback_rows: int = 253
    regime_lookback_rows: int = 126
    resume: bool = True
    force: bool = False
    retain_intermediates: bool = False
    max_workers: int = 2
    max_inflight_securities: int = 5000


@dataclass(frozen=True)
class BatchSpec:
    batch_id: str
    region: str
    security_ids: tuple[str, ...]
    security_hash: str


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "unknown"


def _hash_strings(values: list[str] | tuple[str, ...]) -> str:
    payload = "|".join(str(value) for value in values).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _universe_hash(universe: pd.DataFrame) -> str:
    columns = ["security_id", "region", "price_rows", "latest_trade_date"]
    values = universe[columns].astype(str).agg("|".join, axis=1).tolist()
    return _hash_strings(values)


def _batch_specs(universe: pd.DataFrame, batch_size: int) -> list[BatchSpec]:
    specs: list[BatchSpec] = []
    for region, region_frame in universe.groupby("region", sort=False):
        security_ids = region_frame["security_id"].astype(str).tolist()
        for ordinal, start in enumerate(range(0, len(security_ids), batch_size), start=1):
            chunk = tuple(security_ids[start : start + batch_size])
            specs.append(
                BatchSpec(
                    batch_id=f"{_slug(str(region))}-{ordinal:04d}",
                    region=str(region),
                    security_ids=chunk,
                    security_hash=_hash_strings(chunk),
                )
            )
    return specs


def _atomic_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    temporary.replace(path)


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False, compression="zstd")
    temporary.replace(path)


def _atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _manifest_payload(config: TwoPhaseConfig, universe: pd.DataFrame, specs: list[BatchSpec]) -> dict:
    return {
        "artifact_version": ARTIFACT_VERSION,
        "input_data_mode": config.input_mode,
        "universe_hash": _universe_hash(universe),
        "security_count": len(universe),
        "regions": list(config.regions),
        "batch_size": config.batch_size,
        "min_price_rows": config.min_price_rows,
        "max_securities": config.max_securities,
        "price_lookback_rows": config.price_lookback_rows,
        "regime_lookback_rows": config.regime_lookback_rows,
        "phase1_max_workers": config.max_workers,
        "phase1_max_inflight_securities": config.max_inflight_securities,
        "batches": [
            {
                "batch_id": spec.batch_id,
                "region": spec.region,
                "security_count": len(spec.security_ids),
                "security_hash": spec.security_hash,
            }
            for spec in specs
        ],
    }


def _validate_or_write_manifest(config: TwoPhaseConfig, payload: dict) -> None:
    path = config.artifact_dir / "manifest.json"
    current = _read_json(path)
    identity_keys = [
        "artifact_version",
        "input_data_mode",
        "universe_hash",
        "batch_size",
        "min_price_rows",
        "max_securities",
        "price_lookback_rows",
        "regime_lookback_rows",
    ]
    mismatch = current and any(current.get(key) != payload.get(key) for key in identity_keys)
    if mismatch and not config.force:
        raise RuntimeError(
            f"Existing batch manifest at {path} does not match this run. "
            "Use a new artifact directory or force the run."
        )
    _atomic_json(payload, path)


def _batch_complete(batch_dir: Path, spec: BatchSpec, resume: bool) -> bool:
    if not resume:
        return False
    status = _read_json(batch_dir / "_SUCCESS.json")
    return (
        status.get("artifact_version") == ARTIFACT_VERSION
        and status.get("security_hash") == spec.security_hash
        and all((batch_dir / filename).exists() for filename in CORE_BATCH_FILES)
    )


def build_batch_frames(
    universe: pd.DataFrame,
    fundamentals: pd.DataFrame,
    prices: pd.DataFrame,
    regime_lookback_rows: int,
    sentiment_config: dict,
    alternative_data_config: dict,
    narrative_config: dict,
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """Build only ticker-local artifacts; global ranks are deliberately deferred."""
    price_base = build_price_risk_base(prices)
    excluded_tickers = set(
        price_base.loc[price_base["price_data_exclusion_flag"].fillna(False), "ticker"].astype(str)
    )
    recent_returns = (
        prices.sort_values(["ticker", "date"])
        .groupby("ticker", group_keys=False)
        .tail(regime_lookback_rows)[["ticker", "date", "return"]]
        .loc[lambda frame: ~frame["ticker"].astype(str).isin(excluded_tickers)]
        .reset_index(drop=True)
    )
    alt_outputs = run_alternative_data_pipeline(universe, sentiment_config, alternative_data_config)
    narrative_outputs = run_narrative_pipeline(universe, narrative_config)
    core = {
        "price_risk_base": price_base,
        "recent_returns": recent_returns,
        "alt_features_monthly": alt_outputs["alt_features_monthly"],
        "narrative_reframing_features": narrative_outputs["narrative_reframing_features"],
    }
    return core, alt_outputs, narrative_outputs


def _write_batch_frames(
    batch_dir: Path,
    core: dict[str, pd.DataFrame],
    alt_outputs: dict[str, pd.DataFrame],
    narrative_outputs: dict[str, pd.DataFrame],
    retain_intermediates: bool,
) -> None:
    for name, frame in core.items():
        _atomic_parquet(frame, batch_dir / f"{name}.parquet")
    if not retain_intermediates:
        return
    for group, outputs in [("alt", alt_outputs), ("narrative", narrative_outputs)]:
        detail_dir = batch_dir / group
        for name, frame in outputs.items():
            if name not in core:
                _atomic_parquet(frame, detail_dir / f"{name}.parquet")


def _run_phase_one_batch(
    config: TwoPhaseConfig,
    spec: BatchSpec,
    universe_by_id: pd.DataFrame,
    fundamentals_by_id: pd.DataFrame,
    sentiment_config: dict,
    alternative_data_config: dict,
    narrative_config: dict,
) -> dict[str, object]:
    batch_started = time.perf_counter()
    batch_dir = config.artifact_dir / "batches" / spec.batch_id
    batch_universe = universe_by_id.loc[list(spec.security_ids)].reset_index(drop=True)
    batch_fundamentals = fundamentals_by_id.loc[list(spec.security_ids)].reset_index(drop=True)
    prices = load_recent_duckdb_prices(spec.security_ids, config.price_lookback_rows)
    loaded_tickers = set(prices["ticker"].astype(str))
    missing = set(spec.security_ids).difference(loaded_tickers)
    if missing:
        raise RuntimeError(f"Batch {spec.batch_id} is missing price rows for {len(missing)} securities.")
    core, alt_outputs, narrative_outputs = build_batch_frames(
        batch_universe,
        batch_fundamentals,
        prices,
        config.regime_lookback_rows,
        sentiment_config,
        alternative_data_config,
        narrative_config,
    )
    _write_batch_frames(
        batch_dir,
        core,
        alt_outputs,
        narrative_outputs,
        config.retain_intermediates,
    )
    status = {
        "artifact_version": ARTIFACT_VERSION,
        "batch_id": spec.batch_id,
        "region": spec.region,
        "security_hash": spec.security_hash,
        "security_count": len(spec.security_ids),
        "price_rows_loaded": len(prices),
        "runtime_seconds": time.perf_counter() - batch_started,
        "completed_at": pd.Timestamp.now(tz="UTC").isoformat(),
    }
    _atomic_json(status, batch_dir / "_SUCCESS.json")
    return status


def _bounded_phase_one_workers(config: TwoPhaseConfig, pending: list[BatchSpec]) -> int:
    if not pending:
        return 0
    requested = max(int(config.max_workers), 1)
    largest_batch = max(len(spec.security_ids) for spec in pending)
    memory_bound = max(int(config.max_inflight_securities) // max(largest_batch, 1), 1)
    return min(requested, memory_bound, len(pending))


def run_phase_one(config: TwoPhaseConfig) -> dict:
    """Extract and preprocess region-partitioned, resumable security batches."""
    if config.batch_size <= 0:
        raise ValueError("batch_size must be positive.")
    if config.input_mode not in {"observed", "synthetic_test"}:
        raise ValueError("input_mode must be 'observed' or 'synthetic_test'.")
    if config.max_workers <= 0:
        raise ValueError("max_workers must be positive.")
    if config.max_inflight_securities <= 0:
        raise ValueError("max_inflight_securities must be positive.")
    started = time.perf_counter()
    universe = load_duckdb_universe(
        max_securities=config.max_securities,
        min_price_rows=config.min_price_rows,
        regions=config.regions,
    )
    if config.input_mode == "synthetic_test":
        universe = prepare_synthetic_test_universe(universe)
        fundamentals = load_fundamentals(universe, use_mock=True)
        fundamentals["fundamentals_data_source"] = "synthetic_test"
        fundamentals["is_synthetic_fundamentals"] = True
    else:
        fundamentals = load_observed_fundamentals(universe)
        observed_ids = set(fundamentals["security_id"].astype(str)) if not fundamentals.empty else set()
        known_sector = ~universe["sector"].fillna("Unknown").astype(str).str.lower().isin(
            {"", "unknown", "none", "nan", "n/a"}
        )
        usable_reference = (
            pd.to_numeric(universe["market_cap_usd"], errors="coerce").gt(0)
            & pd.to_numeric(universe["avg_daily_traded_value_usd"], errors="coerce").gt(0)
            & known_sector
            & universe["security_id"].astype(str).isin(observed_ids)
        )
        universe = universe.loc[usable_reference].copy().reset_index(drop=True)
        if universe.empty:
            raise RuntimeError(
                "No securities have complete observed metadata and annual fundamentals. "
                "Run scripts/run_free_equity_enrichment.py all first."
            )
        universe["_pipeline_index"] = np.arange(len(universe), dtype=np.int64)
        fundamentals = (
            fundamentals.loc[fundamentals["security_id"].astype(str).isin(universe["security_id"].astype(str))]
            .copy()
            .reset_index(drop=True)
        )
        LOGGER.info(
            "Observed Phase 1 universe: securities=%s regions=%s.",
            len(universe),
            universe.groupby("region").size().to_dict(),
        )
    specs = _batch_specs(universe, config.batch_size)
    manifest = _manifest_payload(config, universe, specs)
    _validate_or_write_manifest(config, manifest)
    _atomic_parquet(universe, config.artifact_dir / "universe.parquet")
    _atomic_parquet(fundamentals, config.artifact_dir / "fundamentals.parquet")

    sentiment_config = load_yaml("configs/sentiment.yaml")
    alternative_data_config = load_yaml("configs/alternative_data.yaml")
    narrative_config = load_yaml("configs/narrative.yaml")
    universe_by_id = universe.set_index("security_id", drop=False)
    fundamentals_by_id = fundamentals.set_index("security_id", drop=False)
    completed = 0
    skipped = 0
    pending: list[tuple[int, BatchSpec]] = []
    for position, spec in enumerate(specs, start=1):
        batch_dir = config.artifact_dir / "batches" / spec.batch_id
        if _batch_complete(batch_dir, spec, config.resume and not config.force):
            skipped += 1
            LOGGER.info(
                "Phase 1 batch %s/%s %s skipped (checkpoint complete).",
                position,
                len(specs),
                spec.batch_id,
            )
            continue
        pending.append((position, spec))
    worker_count = _bounded_phase_one_workers(config, [spec for _, spec in pending])
    LOGGER.info(
        "Phase 1 bounded executor: workers=%s pending_batches=%s max_inflight_securities=%s.",
        worker_count,
        len(pending),
        config.max_inflight_securities,
    )
    if pending:
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="wolf-phase1") as executor:
            futures: dict[Future, tuple[int, BatchSpec]] = {
                executor.submit(
                    _run_phase_one_batch,
                    config,
                    spec,
                    universe_by_id,
                    fundamentals_by_id,
                    sentiment_config,
                    alternative_data_config,
                    narrative_config,
                ): (position, spec)
                for position, spec in pending
            }
            try:
                for future in as_completed(futures):
                    position, spec = futures[future]
                    status = future.result()
                    completed += 1
                    LOGGER.info(
                        "Phase 1 batch %s/%s %s completed: securities=%s price_rows=%s runtime=%.1fs.",
                        position,
                        len(specs),
                        spec.batch_id,
                        status["security_count"],
                        status["price_rows_loaded"],
                        status["runtime_seconds"],
                    )
            except Exception:
                for future in futures:
                    future.cancel()
                raise
    summary = {
        "status": "completed",
        "input_data_mode": config.input_mode,
        "security_count": len(universe),
        "batch_count": len(specs),
        "completed_batches": completed,
        "skipped_batches": skipped,
        "worker_count": worker_count,
        "max_inflight_securities": config.max_inflight_securities,
        "runtime_seconds": time.perf_counter() - started,
    }
    _atomic_json(summary, config.artifact_dir / "PHASE1_SUCCESS.json")
    return summary


def _load_phase_one_artifacts(
    config: TwoPhaseConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    manifest = _read_json(config.artifact_dir / "manifest.json")
    if manifest.get("artifact_version") != ARTIFACT_VERSION:
        raise RuntimeError("Phase 1 manifest is missing or has an unsupported artifact version.")
    universe = pd.read_parquet(config.artifact_dir / "universe.parquet")
    fundamentals = pd.read_parquet(config.artifact_dir / "fundamentals.parquet")
    specs = _batch_specs(universe, int(manifest["batch_size"]))
    manifest_batches = {entry["batch_id"]: entry for entry in manifest["batches"]}
    price_bases: list[pd.DataFrame] = []
    return_matrices: list[pd.DataFrame] = []
    alt_features: list[pd.DataFrame] = []
    narrative_features: list[pd.DataFrame] = []
    for spec in specs:
        entry = manifest_batches.get(spec.batch_id, {})
        if entry.get("security_hash") != spec.security_hash:
            raise RuntimeError(f"Manifest security hash mismatch for {spec.batch_id}.")
        batch_dir = config.artifact_dir / "batches" / spec.batch_id
        if not _batch_complete(batch_dir, spec, True):
            raise RuntimeError(f"Phase 1 batch {spec.batch_id} is incomplete.")
        price_bases.append(pd.read_parquet(batch_dir / "price_risk_base.parquet"))
        recent = pd.read_parquet(batch_dir / "recent_returns.parquet")
        recent["date"] = pd.to_datetime(recent["date"])
        return_matrices.append(recent.pivot(index="date", columns="ticker", values="return"))
        alt_features.append(pd.read_parquet(batch_dir / "alt_features_monthly.parquet"))
        narrative_features.append(pd.read_parquet(batch_dir / "narrative_reframing_features.parquet"))
    price_base = pd.concat(price_bases, ignore_index=True)
    returns = pd.concat(return_matrices, axis=1).sort_index().tail(int(manifest["regime_lookback_rows"])).fillna(0)
    alt = pd.concat(alt_features, ignore_index=True)
    narrative = pd.concat(narrative_features, ignore_index=True)
    expected = set(universe["ticker"].astype(str))
    for name, frame in [("price risk", price_base), ("alternative data", alt), ("narrative", narrative)]:
        actual = set(frame["ticker"].astype(str))
        if actual != expected:
            raise RuntimeError(f"Merged {name} artifacts do not match the Phase 1 universe.")
    return universe, fundamentals, price_base, returns, alt, narrative


def _compact_validation_targets(universe: pd.DataFrame) -> pd.DataFrame:
    targets = universe[["ticker", "latest_trade_date"]].rename(columns={"latest_trade_date": "date"}).copy()
    targets["date"] = pd.to_datetime(targets["date"])
    for months in [3, 6, 9, 12]:
        targets[f"forward_total_return_{months}m"] = np.nan
    return targets


def _risk_prices(returns: pd.DataFrame) -> pd.DataFrame:
    base_config = load_yaml("configs/base.yaml")
    portfolio = load_current_portfolio(
        base_config.get("current_portfolio_path", "data/external/current_portfolio_template.csv")
    )
    held = set(portfolio["ticker"].astype(str))
    columns = [column for column in returns.columns if str(column) in held]
    selected = returns[columns].copy() if columns else returns.mean(axis=1).to_frame("_MARKET_CONTEXT")
    prices = selected.stack().rename("return").reset_index()
    prices.columns = ["date", "ticker", "return"]
    prices["close"] = 100 * (1 + prices["return"]).groupby(prices["ticker"]).cumprod()
    return prices[["ticker", "date", "close", "return"]]


def _minimal_upstream_outputs(
    alt_features: pd.DataFrame,
    narrative_features: pd.DataFrame,
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    alt_outputs = {
        "alt_text_documents": pd.DataFrame(),
        "alt_entity_mentions": pd.DataFrame(),
        "alt_sentiment_scores": pd.DataFrame(),
        "alt_event_signals": pd.DataFrame(),
        "alt_features_monthly": alt_features,
    }
    narrative_outputs = {
        "narrative_documents": pd.DataFrame(),
        "narrative_concepts": pd.DataFrame(),
        "narrative_occurrences": pd.DataFrame(),
        "narrative_frames": pd.DataFrame(),
        "narrative_semantic_distances": pd.DataFrame(),
        "narrative_temporal_features": pd.DataFrame(),
        "narrative_markov_transitions": pd.DataFrame(),
        "narrative_reframing_features": narrative_features,
    }
    return alt_outputs, narrative_outputs


def _write_model_lineage(
    config: TwoPhaseConfig,
    manifest: dict,
    universe_hash: str,
    runtime_seconds: float,
) -> str:
    data_config = load_data_config()
    metadata = new_model_run_metadata(
        model_name="wolf_quant_two_phase_pipeline",
        model_version="local",
        backend=data_config.backend,
        mode=f"{manifest.get('input_data_mode', 'unknown')}_two_phase",
        config={
            key: manifest.get(key)
            for key in [
                "input_data_mode",
                "batch_size",
                "min_price_rows",
                "max_securities",
                "regions",
                "price_lookback_rows",
                "regime_lookback_rows",
            ]
        },
        input_snapshot_hash=universe_hash,
        repository_root=ROOT,
    )
    row = {
        **metadata.to_dict(),
        "status": "completed",
        "completed_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "runtime_seconds": runtime_seconds,
        "output_path": str(config.output_dir),
    }
    _atomic_csv(pd.DataFrame([row]), config.output_dir / "model_run_lineage.csv")
    return metadata.model_run_id


def run_phase_two(config: TwoPhaseConfig) -> dict[str, pd.DataFrame]:
    """Merge every universe, apply global ranks, and run allocation/risk/DRL once."""
    started = time.perf_counter()
    LOGGER.info("Phase 2 loading and validating Phase 1 artifacts.")
    universe, fundamentals, price_base, returns, alt_features, narrative_features = _load_phase_one_artifacts(config)
    LOGGER.info(
        "Phase 2 global merge complete: securities=%s return_dates=%s.",
        len(universe),
        len(returns),
    )
    price_risk_features = finalise_price_risk_features(price_base)
    chaos_index = calculate_wolf_chaos_index_from_returns(returns)
    alt_outputs, narrative_outputs = _minimal_upstream_outputs(alt_features, narrative_features)
    model_universe = universe.drop(columns=["_pipeline_index"], errors="ignore")
    outputs = run_pipeline_from_inputs(
        config.output_dir,
        universe=model_universe,
        prices=_risk_prices(returns),
        fundamentals=fundamentals,
        alt_outputs=alt_outputs,
        narrative_outputs=narrative_outputs,
        price_risk_features=price_risk_features,
        chaos_index=chaos_index,
        ml_targets=_compact_validation_targets(model_universe),
    )
    runtime_seconds = time.perf_counter() - started
    manifest = _read_json(config.artifact_dir / "manifest.json")
    model_run_id = _write_model_lineage(config, manifest, _universe_hash(universe), runtime_seconds)
    summary = {
        "status": "completed",
        "model_run_id": model_run_id,
        "security_count": len(model_universe),
        "input_data_mode": manifest.get("input_data_mode", "unknown"),
        "scorecard_rows": len(outputs["scorecard"]),
        "final_recommendation_rows": len(outputs["final_recommendations"]),
        "runtime_seconds": runtime_seconds,
        "completed_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "output_dir": str(config.output_dir),
    }
    _atomic_json(summary, config.artifact_dir / "PHASE2_SUCCESS.json")
    LOGGER.info(
        "Phase 2 completed: recommendations=%s runtime=%.1fs.",
        summary["final_recommendation_rows"],
        summary["runtime_seconds"],
    )
    return outputs
