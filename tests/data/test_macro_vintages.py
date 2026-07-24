import pandas as pd

from src.data.point_in_time import point_in_time_macro
from src.data.repository.duckdb_repository import DuckDBRepository


def test_macro_vintages_do_not_leak_later_revisions():
    macro = pd.DataFrame(
        {
            "series_id": ["GDP", "GDP"],
            "observation_date": ["2026-03-31", "2026-03-31"],
            "vintage_date": ["2026-04-15", "2026-07-15"],
            "value": [1.0, 2.0],
        }
    )
    as_of = point_in_time_macro(macro, "2026-05-01")
    assert len(as_of) == 1
    assert as_of.loc[0, "value"] == 1.0


def test_duckdb_macro_revisions_insert_as_new_vintages(tmp_path):
    repo = DuckDBRepository(tmp_path / "macro_vintages.duckdb")
    repo.execute_migrations("sql/migrations")
    repo.save_macro_observations(
        pd.DataFrame(
            {
                "series_id": ["GDP", "GDP"],
                "observation_date": ["2026-03-31", "2026-03-31"],
                "vintage_date": ["2026-04-15", "2026-07-15"],
                "available_from": ["2026-04-16", "2026-07-16"],
                "value": [1.0, 2.0],
                "source": ["mock", "mock"],
            }
        )
    )

    stored = repo.read_table("macro_observations")
    early = repo.load_point_in_time_macro(["GDP"], pd.Timestamp("2026-05-01"))
    later = repo.load_point_in_time_macro(["GDP"], pd.Timestamp("2026-08-01"))

    assert len(stored) == 2
    assert early.loc[0, "value"] == 1.0
    assert later["value"].max() == 2.0
