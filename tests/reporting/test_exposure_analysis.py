import pandas as pd

from src.reporting.exposure_analysis import build_exposure_tables
from src.reporting.models import ICDataBundle


def test_exposure_analysis_returns_available_tables():
    bundle = ICDataBundle({"sector_exposure": pd.DataFrame({"sector": ["Tech"]})})
    assert "sector_exposure" in build_exposure_tables(bundle)
