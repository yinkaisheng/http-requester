#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
from typing import List, Optional, Tuple

from models.http_models import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    BodyType,
    FormField,
    HeaderItem,
    HttpRequest,
)
from services.path_import import normalize_imported_file_paths

_INVOKE_PATTERN = re.compile(r'Invoke-(?:WebRequest|RestMethod)', re.I)


def _detect_json_body(body_text: str, headers: List[HeaderItem]) -> BodyType:
    for item in headers:
        if item.key.lower() == 'content-type' and 'json' in item.value.lower():
            return BodyType.JSON
    stripped = body_text.strip()
    if not stripped:
        return BodyType.RAW
    try:
        json.loads(stripped)
        return BodyType.JSON
    except json.JSONDecodeError:
        return BodyType.RAW


def _extract_quoted(text: str, flag: str) -> Optional[str]:
    single = re.search(rf"-{flag}\s+'([^']*(?:''[^']*)*)'", text, re.I | re.S)
    if single:
        return single.group(1).replace("''", "'")
    double = re.search(rf'-{flag}\s+"([^"]*(?:\\"[^"]*)*)"', text, re.I | re.S)
    if double:
        return double.group(1).replace('\\"', '"')
    return None


def _extract_hashtable_block(text: str, flag: str) -> Optional[str]:
    match = re.search(rf'-{flag}\s+@\{{', text, re.I)
    if not match:
        return None
    start = match.end()
    depth = 1
    index = start
    while index < len(text) and depth > 0:
        char = text[index]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
        index += 1
    if depth != 0:
        return None
    return text[start:index - 1]


def _parse_hashtable_pairs(content: str) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for key, value in re.findall(r"'((?:''|[^'])*)'\s*=\s*'((?:''|[^'])*)'", content):
        pairs.append((key.replace("''", "'"), value.replace("''", "'")))
    if pairs:
        return pairs
    for key, value in re.findall(r'"((?:\\"|[^"])*)"\s*=\s*"((?:\\"|[^"])*)"', content):
        pairs.append((key.replace('\\"', '"'), value.replace('\\"', '"')))
    return pairs


def _parse_form_fields(content: str) -> List[FormField]:
    fields: List[FormField] = []
    for key, value in _parse_hashtable_pairs(content):
        file_match = re.search(r"Get-Item\s+-LiteralPath\s+'((?:''|[^'])*)'", value, re.I)
        if file_match:
            file_path = file_match.group(1).replace("''", "'")
            fields.append(FormField(key=key, value='', is_file=True, file_path=file_path))
        else:
            fields.append(FormField(key=key, value=value, is_file=False))
    return fields


def _command_section(text: str) -> str:
    lines: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('$response.') and _INVOKE_PATTERN.search(stripped) is None:
            break
        if stripped.startswith('$response ='):
            stripped = stripped.split('=', 1)[1].strip()
        stripped = stripped.rstrip('`').strip()
        if _INVOKE_PATTERN.search(stripped) or lines:
            lines.append(stripped)
    return '\n'.join(lines) if lines else text


def parse_powershell_command(text: str) -> Optional[HttpRequest]:
    if _INVOKE_PATTERN.search(text) is None:
        return None

    command = _command_section(text)
    url = _extract_quoted(command, 'Uri')
    if not url:
        return None

    method = 'GET'
    method_match = re.search(r'-Method\s+(\w+)', command, re.I)
    if method_match:
        method = method_match.group(1).upper()

    timeout_seconds = DEFAULT_REQUEST_TIMEOUT_SECONDS
    timeout_match = re.search(r'-TimeoutSec\s+(\d+)', command, re.I)
    if timeout_match:
        try:
            timeout_seconds = max(1, int(timeout_match.group(1)))
        except ValueError:
            pass

    ssl_verify = False

    headers: List[HeaderItem] = []
    headers_block = _extract_hashtable_block(command, 'Headers')
    if headers_block:
        for key, value in _parse_hashtable_pairs(headers_block):
            headers.append(HeaderItem(key=key, value=value, enabled=True))

    body_text = _extract_quoted(command, 'Body') or ''
    body_type = BodyType.NONE
    form_fields: List[FormField] = []

    form_block = _extract_hashtable_block(command, 'Form')
    if form_block:
        form_fields = _parse_form_fields(form_block)
        body_type = BodyType.FORM
    elif body_text:
        body_type = BodyType.RAW

    content_type = _extract_quoted(command, 'ContentType')
    if content_type and not any(h.key.lower() == 'content-type' for h in headers):
        headers.append(HeaderItem(key='Content-Type', value=content_type, enabled=True))

    if body_type == BodyType.RAW and body_text:
        body_type = _detect_json_body(body_text, headers)

    if method == 'GET' and (
        (body_type in (BodyType.RAW, BodyType.JSON) and body_text)
        or (body_type == BodyType.FORM and form_fields)
    ):
        method = 'POST'

    return normalize_imported_file_paths(
        HttpRequest(
            method=method,
            url=url,
            headers=headers,
            body_type=body_type,
            body_text=body_text,
            form_fields=form_fields,
            ssl_verify=ssl_verify,
            timeout_seconds=timeout_seconds,
        )
    )
