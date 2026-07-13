from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class VendorAdapter:
    name: str

    def load(self, path: str | Path | None = None) -> pd.DataFrame:
        raise NotImplementedError


class CsvAdapter(VendorAdapter):
    def load(self, path: str | Path | None = None) -> pd.DataFrame:
        if path is None:
            raise ValueError("CSV adapter requires a path.")
        return pd.read_csv(path)


class PlaceholderMarketDataAdapter(VendorAdapter):
    def load(self, path: str | Path | None = None) -> pd.DataFrame:
        raise NotImplementedError(f"{self.name} is a placeholder; configure credentials externally before use.")
