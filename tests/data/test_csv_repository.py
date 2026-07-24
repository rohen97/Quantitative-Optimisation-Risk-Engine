import pandas as pd

from src.data.repository.csv_repository import CSVRepository


def test_csv_repository_reads_and_writes_tables(tmp_path):
    repo = CSVRepository(tmp_path)
    repo.write_table("sample", pd.DataFrame({"a": [1], "b": [2]}))
    loaded = repo.read_table("sample")
    assert loaded.to_dict("records") == [{"a": 1, "b": 2}]
    assert repo.read_table("missing").empty


def test_csv_repository_exposes_legacy_price_loader(tmp_path):
    repo = CSVRepository(output_root=tmp_path)
    repo.write_table(
        "prices_daily_sample",
        pd.DataFrame(
            {
                "security_id": ["AAA", "BBB"],
                "trade_date": ["2026-01-01", "2026-01-02"],
                "adjusted_close": [100.0, 50.0],
            }
        ),
    )
    loaded = repo.load_prices(["AAA"], pd.Timestamp("2026-01-01").date(), pd.Timestamp("2026-01-31").date())
    assert loaded["security_id"].tolist() == ["AAA"]
