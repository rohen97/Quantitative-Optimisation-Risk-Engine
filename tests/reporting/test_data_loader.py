import pandas as pd

from src.reporting import data_loader
from src.reporting.data_loader import load_ic_data


def test_data_loader_reads_existing_outputs(tmp_path):
    pd.DataFrame({"ticker": ["AAA"]}).to_csv(tmp_path / "final_recommendations.csv", index=False)
    bundle = load_ic_data(tmp_path)
    assert bundle.frames["final_recommendations"]["ticker"].tolist() == ["AAA"]
    assert bundle.source_root == tmp_path
    assert any(source.name == "current_portfolio" and not source.available for source in bundle.sources)
    assert any(source.name == "final_recommendations" and source.source_hash for source in bundle.sources)


def test_data_loader_requires_current_or_target_portfolio(tmp_path):
    try:
        load_ic_data(tmp_path)
    except FileNotFoundError as error:
        assert "current portfolio or at least one target" in str(error)
    else:
        raise AssertionError("Expected missing critical portfolio inputs to fail clearly.")


def test_large_optimiser_source_keeps_only_active_weights(tmp_path, monkeypatch):
    path = tmp_path / "optimised_portfolio_cvar_constrained.csv"
    pd.DataFrame(
        {
            "security_id": ["A", "B", "C"],
            "ticker": ["AAA", "BBB", "CCC"],
            "target_weight": [0.6, 0.0, 0.0],
            "current_weight": [0.0, 0.0, 0.4],
            "expected_total_return_12m": [0.1, 0.2, 0.3],
            "unused_full_model_column": [1, 2, 3],
        }
    ).to_csv(path, index=False)
    monkeypatch.setattr(data_loader, "_LARGE_SOURCE_BYTES", 0)

    frame, source = data_loader.safe_read_csv(path, "optimised_portfolio_cvar_constrained")

    assert frame["ticker"].tolist() == ["AAA", "CCC"]
    assert "unused_full_model_column" not in frame
    assert source.row_count == 3
