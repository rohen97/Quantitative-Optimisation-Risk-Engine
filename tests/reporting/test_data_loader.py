import pandas as pd

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
