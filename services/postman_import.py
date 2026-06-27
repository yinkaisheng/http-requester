#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Postman Collection v2.0 / v2.1 JSON parser.

Converts Postman collections into the app's ``Collection`` model,
preserving folder hierarchy as a nested ``CollectionItem`` tree.

See ``docs/postman_collection_import.md`` for the field mapping spec.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from models.collection_models import Collection, CollectionItem
from models.http_models import (
    BodyType,
    FormField,
    HeaderItem,
    HttpRequest,
    detect_import_body_type,
)


def parse_postman_collection_file(file_path: str) -> Collection:
    """Read a Postman Collection JSON file and return a ``Collection``."""
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    return parse_postman_collection_text(text)


def parse_postman_collection_text(text: str) -> Collection:
    """Parse a Postman Collection JSON string into a ``Collection``."""
    data = json.loads(text)
    info = data.get('info', {})
    name = info.get('name', 'Imported Collection')
    items = data.get('item', [])
    return Collection(
        name=name,
        items=[_parse_item(item) for item in items],
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_item(item_data: Dict[str, Any]) -> CollectionItem:
    """Recursively parse a Postman item (folder or request)."""
    name = item_data.get('name', '')

    # Folder: has an "item" array
    if 'item' in item_data:
        children = [_parse_item(child) for child in item_data['item']]
        return CollectionItem(name=name, children=children)

    # Request leaf: has a "request" object
    request_data = item_data.get('request')
    if request_data:
        request = _parse_request(request_data)
        return CollectionItem(name=name, request=request)

    # Unknown shape — return a bare folder
    return CollectionItem(name=name)


def _parse_request(request_data: Dict[str, Any]) -> HttpRequest:
    method = request_data.get('method', 'GET').upper()
    headers = [_parse_header(h) for h in request_data.get('header', [])]

    url = _parse_url(request_data.get('url', {}))
    body_type, body_text, form_fields, file_path = _parse_body(
        request_data.get('body'),
        headers,
    )

    return HttpRequest(
        method=method,
        url=url,
        headers=headers,
        body_type=body_type,
        body_text=body_text,
        form_fields=form_fields,
        file_path=file_path,
    )


def _parse_header(header_data: Dict[str, Any]) -> HeaderItem:
    return HeaderItem(
        key=header_data.get('key', ''),
        value=header_data.get('value', ''),
        enabled=not header_data.get('disabled', False),
    )


def _parse_url(url_data: Any) -> str:
    if not url_data:
        return ''
    if isinstance(url_data, str):
        return url_data

    raw = url_data.get('raw', '')
    if raw:
        return raw

    # Build from components
    protocol = url_data.get('protocol', 'https')
    host_list = url_data.get('host', [])
    host = '.'.join(host_list) if isinstance(host_list, list) else str(host_list)
    port = url_data.get('port')
    path_list = url_data.get('path', [])
    path = '/'.join(path_list) if isinstance(path_list, list) else str(path_list)

    result = f'{protocol}://{host}'
    if port:
        result += f':{port}'
    if path:
        result += '/' if not path.startswith('/') else ''
        result += path

    # Append query parameters
    query_list = url_data.get('query', [])
    if query_list:
        from urllib.parse import urlencode
        params = []
        for q in query_list:
            if isinstance(q, dict) and not q.get('disabled', False):
                params.append((q.get('key', ''), q.get('value', '')))
        if params:
            result += '?' + urlencode(params)

    return result


def _parse_body(body_data: Any, headers: List[HeaderItem]) -> tuple:
    """Parse Postman body into (BodyType, body_text, form_fields, file_path)."""
    if not body_data or not isinstance(body_data, dict):
        return BodyType.NONE, '', [], ''

    mode = body_data.get('mode', '')
    body_text = ''
    form_fields: List[FormField] = []
    file_path = ''

    if mode == 'raw':
        body_text = body_data.get('raw', '')
        options = body_data.get('options', {})
        language = ''
        if isinstance(options, dict):
            raw_opts = options.get('raw', {})
            if isinstance(raw_opts, dict):
                language = raw_opts.get('language', '')
        if language == 'json':
            body_type = BodyType.JSON
        else:
            body_type = detect_import_body_type(body_text, headers)

    elif mode == 'urlencoded':
        body_type = BodyType.FORM
        for item in body_data.get('urlencoded', []):
            if isinstance(item, dict):
                form_fields.append(FormField(
                    key=item.get('key', ''),
                    value=item.get('value', ''),
                ))

    elif mode == 'formdata':
        body_type = BodyType.FORM
        for item in body_data.get('formdata', []):
            if isinstance(item, dict):
                is_file = item.get('type') == 'file'
                form_fields.append(FormField(
                    key=item.get('key', ''),
                    value=item.get('value', '') if not is_file else '',
                    is_file=is_file,
                    file_path=item.get('src', '') if is_file else '',
                ))

    elif mode == 'file':
        body_type = BodyType.FILE
        file_path = body_data.get('src', '')

    elif mode == 'graphql':
        query = body_data.get('query', '')
        variables = body_data.get('variables', '')
        if query:
            import json as _json
            body_text = _json.dumps({
                'query': query,
                'variables': variables,
            }, ensure_ascii=False)
        else:
            body_text = body_data.get('raw', '')
        body_type = detect_import_body_type(body_text, headers)

    else:
        body_type = BodyType.RAW
        body_text = body_data.get('raw', '')

    return body_type, body_text, form_fields, file_path
