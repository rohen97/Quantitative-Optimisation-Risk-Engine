from __future__ import annotations

from src.production.health import run_health_checks


def test_health_checks_repository_write_and_disk(tmp_path):
    checks = run_health_checks(tmp_path, {"health": {"minimum_free_disk_gb": 0, "database_connection_required": False}})
    names = {check.check_name for check in checks}
    assert "disk_free_space" in names
    assert "repository_write" in names
    assert all(check.status == "PASS" for check in checks)
