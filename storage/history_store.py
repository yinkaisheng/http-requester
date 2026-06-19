#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from log_util import logger
from models.http_models import HistoryRecord, HttpRequest
from storage.paths import HISTORY_INDEX_FILE, RECORDS_DIR, STORAGE_VERSION


class HistoryStore:
    def __init__(
        self,
        index_path: Optional[Path] = None,
        records_dir: Optional[Path] = None,
    ):
        if index_path is None:
            index_path = HISTORY_INDEX_FILE
        if records_dir is None:
            records_dir = RECORDS_DIR
        self.index_path = index_path
        self.records_dir = records_dir
        self._index_cache: Optional[List[Dict[str, Any]]] = None

    def _ensure_dirs(self) -> None:
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

    def _record_path(self, record_id: str) -> Path:
        return self.records_dir / f'{record_id}.json'

    def _load_index_entries(self) -> List[Dict[str, Any]]:
        if self._index_cache is not None:
            return self._index_cache
        if not self.index_path.exists():
            self._index_cache = []
            return self._index_cache
        try:
            with open(self.index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._index_cache = []
            return self._index_cache
        entries = data.get('entries', []) if isinstance(data, dict) else []
        if not isinstance(entries, list):
            entries = []
        entries.sort(key=lambda e: e.get('created_at', ''), reverse=True)
        self._index_cache = entries
        return self._index_cache

    def _save_index_entries(self, entries: List[Dict[str, Any]]) -> None:
        self._ensure_dirs()
        payload = {'version': STORAGE_VERSION, 'entries': entries}
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            self._index_cache = entries
        except OSError:
            logger.warning(f'Failed to save history index to {self.index_path}')

    def _save_record_file(self, record: HistoryRecord) -> None:
        self._ensure_dirs()
        path = self._record_path(record.id)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)
        except OSError:
            logger.warning(f'Failed to save history record to {path}')

    def _index_entry_from_record(self, record: HistoryRecord) -> Dict[str, Any]:
        return {
            'id': record.id,
            'name': record.name,
            'method': record.request.method,
            'url': record.request.url,
            'created_at': record.created_at,
            'last_status': record.last_status,
        }

    def _record_from_index_entry(self, entry: Dict[str, Any]) -> HistoryRecord:
        return HistoryRecord(
            id=entry.get('id', ''),
            name=entry.get('name', ''),
            request=HttpRequest(
                method=entry.get('method', 'GET'),
                url=entry.get('url', ''),
            ),
            created_at=entry.get('created_at', ''),
            updated_at=entry.get('created_at', ''),
            last_status=entry.get('last_status'),
        )

    def load(self) -> List[HistoryRecord]:
        return [self._record_from_index_entry(entry) for entry in self._load_index_entries()]

    def get(self, record_id: str) -> Optional[HistoryRecord]:
        path = self._record_path(record_id)
        if not path.exists():
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return HistoryRecord.from_dict(data)
        except (json.JSONDecodeError, OSError):
            return None

    def add(self, record: HistoryRecord) -> None:
        if not record.created_at:
            record.created_at = datetime.now(timezone.utc).isoformat()
        record.updated_at = record.created_at
        self._save_record_file(record)
        entries = self._load_index_entries()
        entries = [e for e in entries if e.get('id') != record.id]
        entries.insert(0, self._index_entry_from_record(record))
        self._save_index_entries(entries)

    def delete(self, record_id: str) -> bool:
        entries = self._load_index_entries()
        new_entries = [e for e in entries if e.get('id') != record_id]
        if len(new_entries) == len(entries):
            return False
        path = self._record_path(record_id)
        try:
            if path.exists():
                path.unlink()
        except OSError:
            logger.warning(f'Failed to delete history record file {path}')
        self._save_index_entries(new_entries)
        return True

    def rename(self, record_id: str, new_name: str) -> Optional[HistoryRecord]:
        record = self.get(record_id)
        if record is None:
            return None
        record.name = new_name
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_record_file(record)
        entries = self._load_index_entries()
        for entry in entries:
            if entry.get('id') == record_id:
                entry['name'] = new_name
                break
        self._save_index_entries(entries)
        return record

    def delete_many(self, record_ids: List[str]) -> List[str]:
        if not record_ids:
            return []
        id_set = set(record_ids)
        entries = self._load_index_entries()
        existing_ids = {e.get('id') for e in entries}
        to_delete = [rid for rid in record_ids if rid in existing_ids]
        if not to_delete:
            return []
        delete_set = set(to_delete)
        for rid in to_delete:
            path = self._record_path(rid)
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                logger.warning(f'Failed to delete history record file {path}')
        new_entries = [e for e in entries if e.get('id') not in delete_set]
        self._save_index_entries(new_entries)
        return to_delete

    def ids_except(self, keep_id: str) -> List[str]:
        return [e['id'] for e in self._load_index_entries() if e.get('id') and e.get('id') != keep_id]

    def ids_same_method_url_except(self, keep_id: str) -> List[str]:
        entries = self._load_index_entries()
        keep = next((e for e in entries if e.get('id') == keep_id), None)
        if keep is None:
            return []
        method = str(keep.get('method', '')).upper()
        url = str(keep.get('url', '')).strip()
        return [
            e['id'] for e in entries
            if e.get('id') and e.get('id') != keep_id
            and str(e.get('method', '')).upper() == method
            and str(e.get('url', '')).strip() == url
        ]

    def all_ids(self) -> List[str]:
        return [e['id'] for e in self._load_index_entries() if e.get('id')]
