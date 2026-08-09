from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from src.alternative_data.alt_features import run_alternative_data_pipeline
from src.data_ingestion.mock_data import generate_mock_prices, generate_mock_universe
from src.features.risk_features import (
    build_price_risk_base,
    build_price_risk_features,
    finalise_price_risk_features,
)
from src.narrative.pipeline import run_narrative_pipeline
import src.two_phase_pipeline as two_phase
from src.two_phase_pipeline import TwoPhaseConfig
from src.utils.config import load_yaml


def _model_inputs(count: int = 18) -> tuple[pd.DataFrame, pd.DataFrame]:
    universe = generate_mock_universe(count)
    universe["ticker"] = universe["security_id"]
    universe["instrument_type"] = "Equity"
    universe["listing_status"] = "Active"
    universe["exchange_code"] = "MOCK"
    universe["price_rows"] = 756
    universe["latest_trade_date"] = pd.Timestamp.today().normalize()
    universe["_pipeline_index"] = range(len(universe))
    return universe, generate_mock_prices(universe)


def _ordered(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values("ticker").reset_index(drop=True).sort_index(axis=1)


def test_batched_price_statistics_preserve_global_ranks():
    universe, prices = _model_inputs(16)
    expected = build_price_risk_features(prices)
    bases = []
    for start in range(0, len(universe), 5):
        tickers = universe.iloc[start : start + 5]["ticker"]
        bases.append(build_price_risk_base(prices[prices["ticker"].isin(tickers)]))
    actual = finalise_price_risk_features(pd.concat(bases, ignore_index=True))
    assert_frame_equal(_ordered(actual), _ordered(expected), check_exact=False, rtol=1e-12, atol=1e-12)


def test_mock_text_features_are_batch_invariant():
    universe, _ = _model_inputs(12)
    sentiment_config = load_yaml("configs/sentiment.yaml")
    alt_config = load_yaml("configs/alternative_data.yaml")
    narrative_config = load_yaml("configs/narrative.yaml")
    expected_alt = run_alternative_data_pipeline(universe, sentiment_config, alt_config)["alt_features_monthly"]
    expected_narrative = run_narrative_pipeline(universe, narrative_config)["narrative_reframing_features"]
    alt_batches = []
    narrative_batches = []
    for start in range(0, len(universe), 4):
        batch = universe.iloc[start : start + 4]
        alt_batches.append(run_alternative_data_pipeline(batch, sentiment_config, alt_config)["alt_features_monthly"])
        narrative_batches.append(run_narrative_pipeline(batch, narrative_config)["narrative_reframing_features"])
    assert_frame_equal(_ordered(pd.concat(alt_batches)), _ordered(expected_alt), check_dtype=False)
    assert_frame_equal(_ordered(pd.concat(narrative_batches)), _ordered(expected_narrative), check_dtype=False)


def test_two_phase_pipeline_resumes_and_finalises_globally(tmp_path, monkeypatch):
    universe, prices = _model_inputs(128)
    full_history_means = prices.groupby("ticker")["return"].mean()

    def fake_universe(**_kwargs) -> pd.DataFrame:
        return universe.copy()

    def fake_recent_prices(tickers, lookback_rows=253, repository=None) -> pd.DataFrame:
        del repository
        frame = (
            prices[prices["ticker"].isin(tickers)]
            .sort_values(["ticker", "date"])
            .groupby("ticker", group_keys=False)
            .tail(lookback_rows)
            .copy()
        )
        frame["full_history_daily_return"] = frame["ticker"].map(full_history_means)
        return frame

    monkeypatch.setattr(two_phase, "load_duckdb_universe", fake_universe)
    monkeypatch.setattr(two_phase, "load_recent_duckdb_prices", fake_recent_prices)
    config = TwoPhaseConfig(
        artifact_dir=Path(tmp_path) / "artifacts",
        output_dir=Path(tmp_path) / "outputs",
        batch_size=32,
        input_mode="synthetic_test",
    )
    first = two_phase.run_phase_one(config)
    resumed = two_phase.run_phase_one(config)
    outputs = two_phase.run_phase_two(config)
    assert first["completed_batches"] == first["batch_count"]
    assert resumed["completed_batches"] == 0
    assert resumed["skipped_batches"] == first["batch_count"]
    assert len(outputs["scorecard"]) == len(universe)
    assert len(outputs["final_recommendations"]) == len(universe)
    assert (config.artifact_dir / "PHASE1_SUCCESS.json").exists()
    assert (config.artifact_dir / "PHASE2_SUCCESS.json").exists()
    assert (config.output_dir / "final_recommendations.csv").exists()


def test_price_outlier_is_quarantined_from_systemic_returns():
    universe, prices = _model_inputs(2)
    bad_ticker = universe.iloc[0]["ticker"]
    bad_index = prices.index[prices["ticker"].eq(bad_ticker)][-1]
    prices.loc[bad_index, "return"] = 5.0
    prices["return_outlier_flag"] = prices["return"].abs().gt(1.0)
    base = build_price_risk_base(prices)
    bad = base.loc[base["ticker"].eq(bad_ticker)].iloc[0]
    assert bool(bad["price_data_exclusion_flag"])
    assert int(bad["price_return_outlier_count"]) == 1
