import pandas as pd

from src.data.ingestion.base import IngestionRequest
from src.data.ingestion.raw_archive import RawArchiver, archive_parquet


def test_raw_archiver_writes_hashed_parquet_metadata(tmp_path):
    request = IngestionRequest(source_name="yfinance", dataset_name="prices_daily")
    archiver = RawArchiver(tmp_path)
    metadata = archiver.archive(pd.DataFrame({"x": [1]}), request, "run-1")
    assert metadata.archive_path.exists()
    assert metadata.payload_hash
    assert metadata.row_count == 1


def test_archive_parquet_uses_price_partitions(tmp_path):
    path = archive_parquet(
        pd.DataFrame({"source": ["yfinance"], "trade_date": ["2025-01-02"], "adjusted_close": [100.0]}),
        tmp_path,
        "prices_daily",
    )
    assert "source=yfinance" in str(path)
    assert "trade_year=2025" in str(path)
