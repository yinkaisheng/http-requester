#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from typing import List, Tuple

from models.http_models import BodyType, HttpRequest

FILE_PATH_PLACEHOLDER = '/path/to/file'


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def _has_header(headers: List[Tuple[str, str]], name: str) -> bool:
    lower = name.lower()
    return any(key.lower() == lower for key, _ in headers)


def _user_headers_ordered(req: HttpRequest) -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = []
    for item in req.headers:
        if item.enabled and item.key.strip():
            rows.append((item.key.strip(), item.value))
    return rows


def _windows_path_to_wsl(path: str) -> str:
    normalized = path.strip().replace('\\', '/')
    if not normalized:
        return FILE_PATH_PLACEHOLDER

    if normalized.startswith('/'):
        return normalized

    lower = normalized.lower()
    for prefix in ('//wsl$/', '//wsl.localhost/'):
        if lower.startswith(prefix):
            remainder = normalized[len(prefix):]
            slash = remainder.find('/')
            if slash >= 0:
                wsl_path = remainder[slash:]
                return wsl_path or '/'
            break

    if len(normalized) >= 2 and normalized[1] == ':':
        drive = normalized[0].lower()
        rest = normalized[2:].lstrip('/')
        if rest:
            return f'/mnt/{drive}/{rest}'
        return f'/mnt/{drive}'

    return normalized


def _file_upload_path(path: str) -> str:
    normalized = path.strip()
    if not normalized:
        return FILE_PATH_PLACEHOLDER
    if sys.platform.startswith('linux'):
        return normalized.replace('\\', '/')
    if sys.platform == 'win32':
        return _windows_path_to_wsl(normalized)
    return FILE_PATH_PLACEHOLDER


def _append_body_args(parts: List[str], req: HttpRequest) -> None:
    if req.body_type == BodyType.RAW:
        if req.body_text:
            parts.append(f'--data-raw {_shell_quote(req.body_text)}')
        return

    if req.body_type == BodyType.JSON:
        text = req.body_text.strip()
        if text:
            parts.append(f'--data {_shell_quote(text)}')
        return

    if req.body_type == BodyType.FORM:
        fields = [field for field in req.form_fields if field.key.strip()]
        if not fields:
            return
        has_file = any(field.is_file for field in fields)
        for field in fields:
            key = field.key.strip()
            if field.is_file:
                file_path = _file_upload_path(field.file_path)
                parts.append(f'-F {_shell_quote(f"{key}=@{file_path}")}')
            elif has_file:
                parts.append(f'-F {_shell_quote(f"{key}={field.value}")}')
            else:
                parts.append(f'-d {_shell_quote(f"{key}={field.value}")}')
        return

    if req.body_type == BodyType.FILE:
        file_path = _file_upload_path(req.file_path)
        parts.append(f'-F {_shell_quote(f"file=@{file_path}")}')


def format_curl_linux_command(req: HttpRequest) -> str:
    url = req.url.strip()
    if not url:
        return ''

    segments = ['curl', _shell_quote(url)]

    if req.timeout_seconds > 0:
        segments.append(f'--max-time {req.timeout_seconds}')

    if not req.ssl_verify:
        segments.append('--insecure')

    method = req.method.upper()
    if method != 'GET':
        segments.append(f'-X {method}')

    headers = _user_headers_ordered(req)
    if req.body_type == BodyType.JSON and not _has_header(headers, 'Content-Type'):
        headers.append(('Content-Type', 'application/json'))
    elif req.body_type == BodyType.RAW and req.body_text and not _has_header(headers, 'Content-Type'):
        headers.append(('Content-Type', 'text/plain'))

    for key, value in headers:
        segments.append(f'-H {_shell_quote(f"{key}: {value}")}')

    body_parts: List[str] = []
    _append_body_args(body_parts, req)
    segments.extend(body_parts)

    return ' \\\n  '.join(segments)
