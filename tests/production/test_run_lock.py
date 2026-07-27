from __future__ import annotations

import pytest

from src.production.run_lock import ProductionRunAlreadyActive, ProductionRunLock


def test_run_lock_blocks_concurrent_run(tmp_path):
    path = tmp_path / "wolf.lock"
    first = ProductionRunLock(path, "run-1", stale_after_seconds=3600)
    second = ProductionRunLock(path, "run-2", stale_after_seconds=3600)
    first.acquire()
    try:
        with pytest.raises(ProductionRunAlreadyActive):
            second.acquire(force_stale_recovery=False)
    finally:
        first.release()


def test_run_lock_releases_owner_lock(tmp_path):
    path = tmp_path / "wolf.lock"
    lock = ProductionRunLock(path, "run-1", stale_after_seconds=3600)
    lock.acquire()
    lock.release()
    assert not path.exists()
