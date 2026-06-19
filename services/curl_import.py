#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import shlex
from typing import List, Optional

from models.http_models import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    BodyType,
    FormField,
    HeaderItem,
    HttpRequest,
)
from services.path_import import normalize_imported_file_paths


def _normalize_curl_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r'^\$\s*', '', text)
    text = re.sub(r'\\\s*\r?\n', ' ', text)
    return text.strip()


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


def parse_curl_command(text: str) -> Optional[HttpRequest]:
    normalized = _normalize_curl_text(text)
    if 'curl' not in normalized.lower():
        return None

    try:
        tokens = shlex.split(normalized, posix=True)
    except ValueError:
        return None

    curl_idx = next(
        (i for i, token in enumerate(tokens) if token.lower() in ('curl', 'curl.exe')),
        None,
    )
    if curl_idx is None:
        return None

    tokens = tokens[curl_idx + 1:]
    url = ''
    method = 'GET'
    headers: List[HeaderItem] = []
    body_text = ''
    body_type = BodyType.NONE
    form_fields: List[FormField] = []
    ssl_verify = True
    timeout_seconds = DEFAULT_REQUEST_TIMEOUT_SECONDS

    index = 0
    while index < len(tokens):
        token = tokens[index]
        lower = token.lower()

        if lower in ('-x', '--request'):
            index += 1
            if index < len(tokens):
                method = tokens[index].upper()
            index += 1
            continue

        if lower in ('-h', '--header'):
            index += 1
            if index < len(tokens) and ':' in tokens[index]:
                key, _, value = tokens[index].partition(':')
                headers.append(HeaderItem(key=key.strip(), value=value.strip(), enabled=True))
            index += 1
            continue

        if lower in ('-d', '--data', '--data-raw', '--data-binary', '--data-urlencode'):
            index += 1
            if index < len(tokens):
                body_text = tokens[index]
                body_type = BodyType.RAW
            index += 1
            continue

        if lower in ('-f', '--form'):
            index += 1
            if index < len(tokens) and '=' in tokens[index]:
                key, _, value = tokens[index].partition('=')
                if value.startswith('@'):
                    form_fields.append(
                        FormField(key=key.strip(), value='', is_file=True, file_path=value[1:].strip())
                    )
                else:
                    form_fields.append(FormField(key=key.strip(), value=value, is_file=False))
                body_type = BodyType.FORM
            index += 1
            continue

        if lower in ('--max-time',):
            index += 1
            if index < len(tokens):
                try:
                    timeout_seconds = max(1, int(float(tokens[index])))
                except ValueError:
                    pass
            index += 1
            continue

        if lower in ('-k', '--insecure'):
            ssl_verify = False
            index += 1
            continue

        if not token.startswith('-') and not url and (
            token.startswith('http://') or token.startswith('https://')
        ):
            url = token
            index += 1
            continue

        index += 1

    if not url:
        return None

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
