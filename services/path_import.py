#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
from typing import List, Optional

from models.http_models import BodyType, FormField, HttpRequest


def _unique_paths(paths: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for path in paths:
        normalized = os.path.normpath(path) if path else ''
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _wsl_mount_to_windows(path: str) -> Optional[str]:
    normalized = path.strip().replace('\\', '/')
    parts = normalized.strip('/').split('/')
    if len(parts) >= 2 and parts[0] == 'mnt' and len(parts[1]) == 1:
        drive = parts[1].upper()
        rest = '/'.join(parts[2:])
        if rest:
            return f'{drive}:\\{rest.replace("/", os.sep)}'
        return f'{drive}:\\'
    return None


def _wsl_unc_to_windows(path: str) -> Optional[str]:
    normalized = path.strip().replace('\\', '/')
    lower = normalized.lower()
    if lower.startswith('//wsl.localhost/'):
        remainder = normalized[len('//wsl.localhost/'):]
        return '\\\\wsl.localhost\\' + remainder.replace('/', '\\')
    if lower.startswith('//wsl$/'):
        remainder = normalized[len('//wsl$/'):]
        return '\\\\wsl$\\' + remainder.replace('/', '\\')
    return None


def _windows_to_wsl_mount(path: str) -> Optional[str]:
    normalized = path.strip().replace('\\', '/')
    if len(normalized) >= 2 and normalized[1] == ':':
        drive = normalized[0].lower()
        rest = normalized[2:].lstrip('/')
        if rest:
            return f'/mnt/{drive}/{rest}'
        return f'/mnt/{drive}'
    return None


def _candidate_paths_on_windows(path: str) -> List[str]:
    normalized = path.strip()
    if not normalized:
        return []

    candidates: List[str] = [normalized.replace('/', '\\')]

    wsl_mount = _wsl_mount_to_windows(normalized)
    if wsl_mount:
        candidates.append(wsl_mount)

    wsl_unc = _wsl_unc_to_windows(normalized)
    if wsl_unc:
        candidates.append(wsl_unc)

    if normalized.startswith('/'):
        candidates.append(normalized)

    return _unique_paths(candidates)


def _candidate_paths_on_linux(path: str) -> List[str]:
    normalized = path.strip()
    if not normalized:
        return []

    candidates: List[str] = [normalized.replace('\\', '/')]

    wsl_mount = _windows_to_wsl_mount(normalized)
    if wsl_mount:
        candidates.append(wsl_mount)

    if normalized.startswith('/'):
        candidates.append(normalized)

    return _unique_paths(candidates)


def resolve_import_file_path(path: str) -> Optional[str]:
    """Return a local path only when the file exists on the current platform."""
    if not path or not path.strip():
        return None

    if sys.platform == 'win32':
        candidates = _candidate_paths_on_windows(path)
    elif sys.platform.startswith('linux'):
        candidates = _candidate_paths_on_linux(path)
    else:
        candidates = [path.strip()]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.normpath(candidate)
    return None


def _resolve_form_field_file(field: FormField) -> FormField:
    if not field.is_file:
        return field
    resolved = resolve_import_file_path(field.file_path)
    if resolved:
        return FormField(
            key=field.key,
            value=field.value,
            is_file=True,
            file_path=resolved,
        )
    return FormField(key=field.key, value=field.value, is_file=True, file_path='')


def normalize_imported_file_paths(req: HttpRequest) -> HttpRequest:
    if req.body_type == BodyType.FORM:
        req.form_fields = [_resolve_form_field_file(field) for field in req.form_fields]
    elif req.body_type == BodyType.FILE:
        resolved = resolve_import_file_path(req.file_path)
        req.file_path = resolved if resolved else ''
    return req
