#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
from typing import List, Tuple

from models.http_models import BodyType, HttpRequest
from services.curl_export import _has_header, _user_headers_ordered

FILE_PATH_PLACEHOLDER_WIN = r'C:\path\to\file'
FILE_PATH_PLACEHOLDER_UNIX = '/path/to/file'

pretty_header = True


def _ps_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _file_path_placeholder() -> str:
    if sys.platform == 'win32':
        return FILE_PATH_PLACEHOLDER_WIN
    return FILE_PATH_PLACEHOLDER_UNIX


def _native_file_path(path: str) -> str:
    normalized = path.strip()
    if not normalized:
        return _file_path_placeholder()
    return os.path.normpath(normalized)


def _join_ps_lines(lines: List[str]) -> str:
    if not lines:
        return ''
    parts: List[str] = []
    for index, line in enumerate(lines):
        if index < len(lines) - 1:
            parts.append(f'{line} `')
        else:
            parts.append(line)
    return '\n  '.join(parts)


def _format_headers_block(headers: List[Tuple[str, str]]) -> str:
    if not headers:
        return ''
    entries = [
        f'{_ps_single_quote(key)} = {_ps_single_quote(value)}'
        for key, value in headers
    ]
    return '@{\n    ' + '\n    '.join(entries) + '\n  }'


def _append_body_lines(lines: List[str], req: HttpRequest) -> None:
    if req.body_type == BodyType.RAW:
        if req.body_text:
            lines.append(f'-Body {_ps_single_quote(req.body_text)}')
        return

    if req.body_type == BodyType.JSON:
        text = req.body_text.strip()
        if text:
            lines.append(f'-Body {_ps_single_quote(text)}')
        return

    if req.body_type == BodyType.FORM:
        fields = [field for field in req.form_fields if field.key.strip()]
        if not fields:
            return
        entries: List[str] = []
        for field in fields:
            key = field.key.strip()
            if field.is_file:
                file_path = _native_file_path(field.file_path)
                entries.append(
                    f'{key} = (Get-Item -LiteralPath {_ps_single_quote(file_path)})'
                )
            else:
                entries.append(f'{key} = {_ps_single_quote(field.value)}')
        lines.append('-Form @{\n    ' + '\n    '.join(entries) + '\n  }')
        return

    if req.body_type == BodyType.FILE:
        file_path = _native_file_path(req.file_path)
        lines.append(
            '-Form @{\n    '
            f'file = (Get-Item -LiteralPath {_ps_single_quote(file_path)})\n  }}'
        )


def _response_output_suffix() -> str:
    if pretty_header:
        headers_line = (
            '$response.Headers.GetEnumerator() '
            '| ForEach-Object { "$($_.Key): $($_.Value)" }'
        )
    else:
        headers_line = '$response.Headers'
    return f'\n$response.StatusCode\n{headers_line}\n$response.Content\n'


def format_powershell_command(req: HttpRequest) -> str:
    url = req.url.strip()
    if not url:
        return ''

    lines = ['$response = Invoke-WebRequest', f'-Uri {_ps_single_quote(url)}']

    if req.timeout_seconds > 0:
        lines.append(f'-TimeoutSec {req.timeout_seconds}')

    if not req.ssl_verify:
        lines.append('-SkipCertificateCheck')

    method = req.method.upper()
    if method != 'GET':
        lines.append(f'-Method {method}')

    headers = _user_headers_ordered(req)
    content_type = None
    if req.body_type == BodyType.JSON and not _has_header(headers, 'Content-Type'):
        content_type = 'application/json'
    elif req.body_type == BodyType.RAW and req.body_text and not _has_header(headers, 'Content-Type'):
        content_type = 'text/plain'

    header_block = _format_headers_block(headers)
    if header_block:
        lines.append(f'-Headers {header_block}')

    if content_type:
        lines.append(f'-ContentType {_ps_single_quote(content_type)}')

    _append_body_lines(lines, req)
    return _join_ps_lines(lines) + _response_output_suffix()
