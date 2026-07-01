#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from log_util import logger
from models.favorite_models import FavoriteItem
from storage.paths import FAVORITES_FILE


class FavoriteStore:
    """Persist a flat list of root ``FavoriteItem`` nodes to a single JSON file.

    The JSON structure::

        {
            "version": 1,
            "items": [ { "id": "…", "name": "…", … }, … ]
        }

    Each item is either a folder (has ``children``, no ``request``)
    or a favorite/leaf (has ``request``, no ``children``).
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else FAVORITES_FILE
        self._cache: Optional[List[FavoriteItem]] = None

    # ------------------------------------------------------------------
    #  Load / save
    # ------------------------------------------------------------------

    def load(self) -> List[FavoriteItem]:
        if self._cache is not None:
            return self._cache
        if not self.path.exists():
            self._cache = []
            return self._cache
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning(f'Failed to load favorites from {self.path}')
            self._cache = []
            return self._cache

        if not isinstance(data, dict):
            self._cache = []
            return self._cache

        items_data = data.get('items', [])
        self._cache = [FavoriteItem.from_dict(d) for d in items_data if isinstance(d, dict)]
        return self._cache

    def save_items(self, items: List[FavoriteItem]) -> None:
        """Persist the full item list to disk and update the in-memory cache."""
        self._ensure_dir()
        payload: Dict[str, Any] = {
            'version': 1,
            'items': [item.to_dict() for item in items],
        }
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            self._cache = items
        except OSError:
            logger.warning(f'Failed to save favorites to {self.path}')

    # ------------------------------------------------------------------
    #  Internal
    # ------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
