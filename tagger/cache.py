"""File-based cache: one JSON file per tagged product."""

import json
import os
from pathlib import Path


class Cache:
    def __init__(self, cache_dir: str) -> None:
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, product_id: str) -> Path:
        safe = str(product_id).replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe}.json"

    def get(self, product_id: str) -> dict | None:
        p = self._path(product_id)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def set(self, product_id: str, scores: dict) -> None:
        p = self._path(product_id)
        p.write_text(json.dumps(scores, ensure_ascii=False), encoding="utf-8")
