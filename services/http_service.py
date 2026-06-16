#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from typing import Dict, Optional, Tuple, Union

import requests

from models.http_models import BodyType, DEFAULT_REQUEST_TIMEOUT_SECONDS, HttpRequest, HttpResponse


def _enabled_headers(req: HttpRequest) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    for item in req.headers:
        if item.enabled and item.key.strip():
            headers[item.key.strip()] = item.value
    return headers


def _prepare_body(req: HttpRequest) -> Tuple[Optional[Union[str, bytes, Dict]], Optional[object], Optional[Dict]]:
    """Return (data, json, files) kwargs for requests."""
    data = None
    json_body = None
    files = None

    if req.body_type == BodyType.RAW:
        data = req.body_text.encode('utf-8')
    elif req.body_type == BodyType.JSON:
        text = req.body_text.strip()
        if text:
            try:
                json_body = json.loads(text)
            except json.JSONDecodeError:
                data = req.body_text.encode('utf-8')
    elif req.body_type == BodyType.FORM:
        data = {}
        files = {}
        for field in req.form_fields:
            if not field.key.strip():
                continue
            key = field.key.strip()
            if field.is_file and field.file_path and os.path.isfile(field.file_path):
                files[key] = open(field.file_path, 'rb')
            else:
                data[key] = field.value
        if not data:
            data = None
        if not files:
            files = None
    elif req.body_type == BodyType.FILE:
        if req.file_path and os.path.isfile(req.file_path):
            filename = os.path.basename(req.file_path)
            files = {'file': (filename, open(req.file_path, 'rb'))}

    return data, json_body, files


def _actual_request_headers(response: requests.Response) -> Dict[str, str]:
    """Return headers actually sent on the wire (from PreparedRequest)."""
    if response.request is None:
        return {}
    return dict(response.request.headers)


def send_request(req: HttpRequest) -> HttpResponse:
    url = req.url.strip()
    if not url:
        return HttpResponse(error='URL is required')

    method = req.method.upper()
    headers = _enabled_headers(req)
    data, json_body, files = _prepare_body(req)

    if req.body_type == BodyType.JSON and 'Content-Type' not in headers:
        headers['Content-Type'] = 'application/json'
    elif req.body_type == BodyType.RAW and 'Content-Type' not in headers:
        headers['Content-Type'] = 'text/plain'

    opened_files = []
    if files:
        for value in files.values():
            if hasattr(value, 'read'):
                opened_files.append(value[1] if isinstance(value, tuple) else value)

    timeout = req.timeout_seconds if req.timeout_seconds > 0 else DEFAULT_REQUEST_TIMEOUT_SECONDS

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            data=data,
            json=json_body,
            files=files,
            timeout=timeout,
            allow_redirects=True,
            verify=req.ssl_verify,
        )
        elapsed_ms = response.elapsed.total_seconds() * 1000
        return HttpResponse(
            status_code=response.status_code,
            reason=response.reason or '',
            headers=dict(response.headers),
            body=response.content,
            elapsed_ms=elapsed_ms,
            request_headers=_actual_request_headers(response),
        )
    except requests.RequestException as exc:
        request_headers: Dict[str, str] = {}
        if exc.response is not None:
            request_headers = _actual_request_headers(exc.response)
        return HttpResponse(error=str(exc), request_headers=request_headers)
    finally:
        for f in opened_files:
            try:
                f.close()
            except Exception:
                pass
