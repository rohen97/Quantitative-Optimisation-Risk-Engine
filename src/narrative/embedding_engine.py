from __future__ import annotations

import hashlib
import numpy as np
import pandas as pd


def _mock_embedding(text: str, dimensions: int = 16) -> list[float]:
    digest = hashlib.sha256(text.lower().encode("utf-8")).digest()
    values = np.frombuffer(digest[:dimensions], dtype=np.uint8).astype(float)
    norm = np.linalg.norm(values)
    return (values / norm).tolist() if norm else values.tolist()


def embed_texts(texts: pd.Series | list[str], provider: str = "mock") -> list[list[float]]:
    """Embed texts with a deterministic mock provider placeholder."""
    if provider != "mock":
        raise NotImplementedError(f"Embedding provider {provider} is a placeholder.")
    return [_mock_embedding(str(text)) for text in texts]
