from src.data.config import DataLayerConfig
from src.data.repository.csv_repository import CSVRepository
from src.data.repository.duckdb_repository import DuckDBRepository
from src.data.repository.repository_router import ShadowRepository, build_repository, repository_for_mode


def test_repository_router_defaults_to_legacy_csv_and_supports_duckdb(tmp_path):
    legacy = repository_for_mode(DataLayerConfig(backend="legacy_csv"), csv_root=tmp_path)
    assert isinstance(legacy, CSVRepository)
    duck = repository_for_mode(DataLayerConfig(backend="duckdb", duckdb_database_path=tmp_path / "router.duckdb"))
    assert isinstance(duck, DuckDBRepository)
    duck.close()


def test_build_repository_supports_dict_settings_and_shadow(tmp_path):
    legacy = build_repository({"data": {"backend": "legacy_csv"}, "output_root": tmp_path})
    assert isinstance(legacy, CSVRepository)
    shadow = build_repository(
        {
            "data": {
                "backend": "shadow",
                "duckdb": {"database_path": tmp_path / "shadow.duckdb", "read_only_for_models": False},
                "comparison": {"relative_tolerance": 1e-6},
            },
            "output_root": tmp_path,
        }
    )
    assert isinstance(shadow, ShadowRepository)
