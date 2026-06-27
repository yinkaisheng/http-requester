#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from log_util import logger
from models.collection_models import Collection
from storage.paths import COLLECTION_FILE


class CollectionStore:
    """Persist collections to a single JSON file.

    Follows the SessionStore single-file pattern (not index+records),
    since collections are few and each one already nests its tree structure.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or COLLECTION_FILE
        self._cache: Optional[List[Collection]] = None

    def _ensure_dir(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[Collection]:
        if self._cache is not None:
            return self._cache
        if not self.path.exists():
            self._cache = []
            return self._cache
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning(f'Failed to load collections from {self.path}')
            self._cache = []
            return self._cache
        entries = data.get('collections', []) if isinstance(data, dict) else []
        self._cache = [Collection.from_dict(c) for c in entries if isinstance(c, dict)]
        return self._cache

    def _write(self, collections: List[Collection]) -> None:
        self._ensure_dir()
        payload: Dict[str, Any] = {
            'version': 1,
            'collections': [c.to_dict() for c in collections],
        }
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            self._cache = collections
        except OSError:
            logger.warning(f'Failed to save collections to {self.path}')

    def get(self, collection_id: str) -> Optional[Collection]:
        for c in self.load():
            if c.id == collection_id:
                return c
        return None

    def add(self, collection: Collection) -> None:
        collections = self.load()
        collections = [c for c in collections if c.id != collection.id]
        collections.append(collection)
        self._write(collections)

    def delete(self, collection_id: str) -> bool:
        collections = self.load()
        new_collections = [c for c in collections if c.id != collection_id]
        if len(new_collections) == len(collections):
            return False
        self._write(new_collections)
        return True

    def rename(self, collection_id: str, new_name: str) -> Optional[Collection]:
        collections = self.load()
        for c in collections:
            if c.id == collection_id:
                c.name = new_name
                self._write(collections)
                return c
        return None
