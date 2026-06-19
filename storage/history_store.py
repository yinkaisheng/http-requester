#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from log_util import logger
from models.http_models import HistoryRecord
from storage.paths import HISTORY_FILE


class HistoryStore:
    def __init__(self, path: Optional[Path] = None):
        if path is None:
            path = HISTORY_FILE
        self.path = path
        self._cache: Optional[List[HistoryRecord]] = None

    def _ensure_dir(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[HistoryRecord]:
        if self._cache is not None:
            return self._cache
        if not self.path.exists():
            self._cache = []
            return self._cache
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._cache = []
            return self._cache
        records = [HistoryRecord.from_dict(item) for item in data.get('records', [])]
        records.sort(key=lambda r: r.updated_at, reverse=True)
        self._cache = records
        return self._cache

    def _save_all(self, records: List[HistoryRecord]) -> None:
        self._ensure_dir()
        payload = {'records': [r.to_dict() for r in records]}
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            self._cache = records
        except OSError:
            logger.warning(f'Failed to save history to {self.path}')

    def upsert(self, record: HistoryRecord) -> None:
        records = self.load()
        record.updated_at = datetime.now(timezone.utc).isoformat()
        found = False
        for i, existing in enumerate(records):
            if existing.id == record.id:
                if not record.created_at:
                    record.created_at = existing.created_at
                records[i] = record
                found = True
                break
        if not found:
            records.insert(0, record)
        self._save_all(records)

    def delete(self, record_id: str) -> bool:
        records = self.load()
        new_records = [r for r in records if r.id != record_id]
        if len(new_records) == len(records):
            return False
        self._save_all(new_records)
        return True

    def rename(self, record_id: str, new_name: str) -> Optional[HistoryRecord]:
        records = self.load()
        for record in records:
            if record.id == record_id:
                record.name = new_name
                record.updated_at = datetime.now(timezone.utc).isoformat()
                self._save_all(records)
                return record
        return None

    def get(self, record_id: str) -> Optional[HistoryRecord]:
        for record in self.load():
            if record.id == record_id:
                return record
        return None
