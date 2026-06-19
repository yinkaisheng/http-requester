#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from log_util import logger
from storage.paths import SESSION_FILE


class SessionStore:
    def __init__(self, path: Optional[Path] = None):
        if path is None:
            path = SESSION_FILE
        self.path = path
        self._cache: Optional[Dict[str, Any]] = None

    def _ensure_dir(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        if self._cache is not None:
            return self._cache
        if not self.path.exists():
            self._cache = {}
            return self._cache
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._cache = data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            self._cache = {}
        return self._cache

    def save(self, session: Dict[str, Any]) -> None:
        self._ensure_dir()
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(session, f, ensure_ascii=False, indent=2)
            self._cache = session
        except OSError:
            logger.warning(f'Failed to save session to {self.path}')
