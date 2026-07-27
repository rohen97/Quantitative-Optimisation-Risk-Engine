from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


class ProductionRunAlreadyActive(RuntimeError):
    """Raised when another non-stale production run owns the lock."""


class ProductionRunLock:
    def __init__(self, lock_path: Path, production_run_id: str, stale_after_seconds: int) -> None:
        self.lock_path = lock_path
        self.production_run_id = production_run_id
        self.stale_after_seconds = stale_after_seconds
        self.acquired = False

    def _lock_payload(self) -> dict:
        return {
            "production_run_id": self.production_run_id,
            "pid": os.getpid(),
            "acquired_at": datetime.now(timezone.utc).isoformat(),
        }

    def _is_stale(self) -> bool:
        if not self.lock_path.exists():
            return False
        try:
            payload = json.loads(self.lock_path.read_text(encoding="utf-8"))
            acquired_at = datetime.fromisoformat(payload["acquired_at"])
        except Exception:
            return True
        age = (datetime.now(timezone.utc) - acquired_at.astimezone(timezone.utc)).total_seconds()
        return age > self.stale_after_seconds

    def acquire(self, force_stale_recovery: bool = True) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        if self.lock_path.exists():
            if not (force_stale_recovery and self._is_stale()):
                raise ProductionRunAlreadyActive(f"Production lock is active: {self.lock_path}")
            self.lock_path.unlink()
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        descriptor = os.open(str(self.lock_path), flags)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(self._lock_payload(), handle, indent=2)
        self.acquired = True

    def release(self) -> None:
        if self.acquired and self.lock_path.exists():
            try:
                payload = json.loads(self.lock_path.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
            if payload.get("production_run_id") == self.production_run_id:
                self.lock_path.unlink()
        self.acquired = False
