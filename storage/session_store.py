#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from storage.paths import SESSION_FILE


class SessionStore:
    def __init__(self, path: Optional[Path] = None):
        if path is None:
            path = SESSION_FILE
        self.path = path

    def _ensure_dir(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, session: Dict[str, Any]) -> None:
        self._ensure_dir()
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(session, f, ensure_ascii=False, indent=2)

    def get_window_size(self) -> Optional[List[int]]:
        window = self.load().get('window', {})
        width = window.get('width')
        height = window.get('height')
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            return [width, height]
        return None

    def get_main_splitter_sizes(self) -> Optional[List[int]]:
        sizes = self.load().get('window', {}).get('main_splitter')
        if isinstance(sizes, list) and len(sizes) == 2:
            return sizes
        return None

    def get_content_splitter_sizes(self) -> Optional[List[int]]:
        sizes = self.load().get('window', {}).get('content_splitter')
        if isinstance(sizes, list) and len(sizes) == 2:
            return sizes
        return None

    def get_tabs(self) -> List[Dict[str, Any]]:
        tabs = self.load().get('tabs', [])
        return tabs if isinstance(tabs, list) else []

    def get_current_tab_index(self) -> int:
        index = self.load().get('current_tab_index', 0)
        return index if isinstance(index, int) and index >= 0 else 0
