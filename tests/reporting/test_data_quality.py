from pathlib import Path

import pandas as pd

from src.reporting.data_quality import (
    build_data_quality_report,
    build_report_data_quality,
    report_is_valid,
)
from src.reporting.models import ICDataBundle


def test_data_quality_flags_missing_required_frames():
    quality = build_data_quality_report(ICDataBundle({"final_recommendations": pd.DataFrame({"x": [1]})}))
    assert not report_is_valid(quality)
    assert "missing_or_empty" in set(quality["status"])


def test_data_quality_uses_repository_relative_paths():
    root = Path(__file__).resolve().parents[2]
    bundle = ICDataBundle(
        {"final_recommendations": pd.DataFrame({"x": [1]})},
        source_root=root / "reports" / "outputs",
    )
    quality = build_data_quality_report(bundle)
    assert quality["file_path"].str.startswith("reports/outputs/").all()


def test_wolf_chaos_index_is_not_validated_as_probability():
    bundle = ICDataBundle(
        {
            "chaos_regime_probabilities": pd.DataFrame(
                {
                    "wolf_chaos_index": [72.0],
                    "low_chaos_probability": [0.2],
                    "high_chaos_probability": [0.8],
                }
            )
        }
    )
    final = pd.DataFrame({"security_id": ["sec-1"], "target_weight": [1.0]})
    quality = build_report_data_quality(bundle, final, pd.Timestamp("2026-07-24"))
    row = quality.loc[quality["rule"].eq("probability_bounds")].iloc[0]
    assert row["status"] == "pass"


def test_synthetic_investment_inputs_block_report_readiness():
    bundle = ICDataBundle({}, model_run_id="test-run")
    final = pd.DataFrame(
        {
            "security_id": ["sec-1"],
            "ticker": ["AAA"],
            "issuer_id": ["issuer-1"],
            "target_weight": [1.0],
            "sector": ["Utilities"],
            "country": ["United States"],
            "region": ["US"],
            "currency": ["USD"],
            "final_recommendation": ["Buy"],
            "is_synthetic_data": [True],
            "is_synthetic_fundamentals": [False],
            "optimisation_feasible": [True],
        }
    )
    quality = build_report_data_quality(bundle, final, pd.Timestamp("2026-07-24"))
    row = quality.loc[quality["rule"].eq("observed_investment_inputs")].iloc[0]
    assert row["status"] == "fail"
