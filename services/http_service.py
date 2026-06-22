#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple, Union

import requests

from log_util import logger
from models.http_models import (
    BodyType,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    HttpRequest,
    HttpResponse,
    decode_bytes_to_text,
    validate_json_body_text,
)

MAX_LOG_BODY_BYTES = 64 * 1024


def _enabled_headers(req: HttpRequest) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    for item in req.headers:
        if item.enabled and item.key.strip():
            headers[item.key.strip()] = item.value
    return headers


def _prepare_body(req: HttpRequest) -> Tuple[Optional[Union[str, bytes, Dict]], Optional[object], Optional[Dict], List]:
    """Return (data, json, files, opened_files) kwargs for requests."""
    data = None
    json_body = None
    files = None
    opened_files: List = []

    if req.body_type == BodyType.RAW:
        if req.body_text:
            data = req.body_text.encode('utf-8')
    elif req.body_type == BodyType.JSON:
        text = req.body_text.strip()
        if text:
            json_body = json.loads(text)
    elif req.body_type == BodyType.FORM:
        data = {}
        files = {}
        for field in req.form_fields:
            if not field.key.strip():
                continue
            key = field.key.strip()
            if field.is_file and field.file_path and os.path.isfile(field.file_path):
                fh = open(field.file_path, 'rb')
                files[key] = fh
                opened_files.append(fh)
            else:
                data[key] = field.value
        if not data:
            data = None
        if not files:
            files = None
    elif req.body_type == BodyType.FILE:
        if req.file_path and os.path.isfile(req.file_path):
            filename = os.path.basename(req.file_path)
            fh = open(req.file_path, 'rb')
            files = {'file': (filename, fh)}
            opened_files.append(fh)

    return data, json_body, files, opened_files


def _actual_request_headers(response: requests.Response) -> Dict[str, str]:
    """Return headers actually sent on the wire (from PreparedRequest)."""
    if response.request is None:
        return {}
    return dict(response.request.headers)


def _format_headers(headers: Dict[str, str]) -> str:
    if not headers:
        return '  (none)'
    return '\n'.join(f'  {key}: {value}' for key, value in headers.items())


def _body_for_log(body: bytes) -> str:
    if not body:
        return '(empty)'
    if len(body) > MAX_LOG_BODY_BYTES:
        text = decode_bytes_to_text(body[:MAX_LOG_BODY_BYTES])
        return f'{text}\n... ({len(body)} bytes total, truncated)'
    return decode_bytes_to_text(body)


def send_request(req: HttpRequest) -> HttpResponse:
    url = req.url.strip()
    if not url:
        logger.error('HTTP request failed: URL is required')
        return HttpResponse(error='URL is required')

    method = req.method.upper()
    headers = _enabled_headers(req)

    if req.body_type == BodyType.JSON and req.body_text.strip():
        json_error = validate_json_body_text(req.body_text)
        if json_error:
            logger.error(f'HTTP request failed: invalid JSON body: {json_error}')
            return HttpResponse(error=f'Invalid JSON body: {json_error}')

    data, json_body, files, opened_files = _prepare_body(req)

    has_content_type = any(k.lower() == 'content-type' for k in headers)
    if req.body_type == BodyType.JSON and not has_content_type:
        headers['Content-Type'] = 'application/json'
    elif req.body_type == BodyType.RAW and req.body_text.strip() and not has_content_type:
        headers['Content-Type'] = 'text/plain'

    timeout = req.timeout_seconds if req.timeout_seconds > 0 else DEFAULT_REQUEST_TIMEOUT_SECONDS
    logger.info(
        f'HTTP {method} {url}\n'
        f'Request headers:\n{_format_headers(headers)}'
    )

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
        resp_headers = dict(response.headers)
        resp_body = response.content
        logger.info(
            f'result of HTTP {method} {url}\n'
            f'status_code: {response.status_code}\n'
            f'reason: {response.reason or ""}\n'
            f'elapsed_ms: {elapsed_ms:.0f}\n'
            f'Response headers:\n{_format_headers(resp_headers)}\n'
            f'Response body:\n{_body_for_log(resp_body)}'
        )
        return HttpResponse(
            status_code=response.status_code,
            reason=response.reason or '',
            headers=resp_headers,
            body=resp_body,
            elapsed_ms=elapsed_ms,
            request_headers=_actual_request_headers(response),
        )
    except requests.RequestException as exc:
        request_headers: Dict[str, str] = {}
        if exc.response is not None:
            response = exc.response
            request_headers = _actual_request_headers(response)
            resp_headers = dict(response.headers)
            resp_body = response.content
            elapsed_ms = response.elapsed.total_seconds() * 1000
            logger.error(
                f'HTTP {method} {url} failed: {exc}\n'
                f'status_code: {response.status_code}\n'
                f'Response headers:\n{_format_headers(resp_headers)}\n'
                f'Response body:\n{_body_for_log(resp_body)}'
            )
            return HttpResponse(
                status_code=response.status_code,
                reason=response.reason or '',
                headers=resp_headers,
                body=resp_body,
                elapsed_ms=elapsed_ms,
                error=repr(exc),
                request_headers=request_headers,
            )
        logger.error(f'HTTP {method} {url} failed: {exc!r}')
        return HttpResponse(error=repr(exc), request_headers=request_headers)
    finally:
        for f in opened_files:
            try:
                f.close()
            except Exception:
                pass
