#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class BodyType(str, Enum):
    NONE = 'none'
    RAW = 'raw'
    JSON = 'json'
    FORM = 'form'
    FILE = 'file'


HTTP_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def url_without_query(url: str) -> str:
    url = url.strip()
    query_index = url.find('?')
    if query_index >= 0:
        return url[:query_index]
    return url


def _parse_body_type(value: Any) -> BodyType:
    try:
        return BodyType(value)
    except (ValueError, TypeError):
        return BodyType.RAW


def is_text_body(body: bytes) -> bool:
    if not body:
        return True
    if b'\x00' in body:
        return False
    for encoding in ('utf-8', 'gbk'):
        try:
            body.decode(encoding)
            return True
        except UnicodeDecodeError:
            continue
    return False


def encode_response_body_for_storage(body: str, raw_body: bytes) -> tuple[str, bool]:
    """Return (stored_body, is_binary). Binary payloads are base64-encoded."""
    if is_text_body(raw_body):
        return body, False
    return base64.b64encode(raw_body).decode('ascii'), True


def decode_stored_response_body(body: str, is_binary: bool) -> str:
    if not is_binary:
        return body
    if not body:
        return ''
    try:
        data = base64.b64decode(body)
    except Exception:
        return body
    return f'[Binary data, {len(data)} bytes]'


@dataclass
class HeaderItem:
    key: str = ''
    value: str = ''
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {'key': self.key, 'value': self.value, 'enabled': self.enabled}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HeaderItem':
        return cls(
            key=data.get('key', ''),
            value=data.get('value', ''),
            enabled=data.get('enabled', True),
        )


@dataclass
class FormField:
    key: str = ''
    value: str = ''
    is_file: bool = False
    file_path: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'value': self.value,
            'is_file': self.is_file,
            'file_path': self.file_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FormField':
        return cls(
            key=data.get('key', ''),
            value=data.get('value', ''),
            is_file=data.get('is_file', False),
            file_path=data.get('file_path', ''),
        )


@dataclass
class HttpRequest:
    method: str = 'GET'
    url: str = ''
    headers: List[HeaderItem] = field(default_factory=list)
    body_type: BodyType = BodyType.RAW
    body_text: str = ''
    form_fields: List[FormField] = field(default_factory=list)
    file_path: str = ''
    ssl_verify: bool = False
    timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS

    def to_dict(self) -> Dict[str, Any]:
        return {
            'method': self.method,
            'url': self.url,
            'headers': [h.to_dict() for h in self.headers],
            'body_type': self.body_type.value,
            'body_text': self.body_text,
            'form_fields': [f.to_dict() for f in self.form_fields],
            'file_path': self.file_path,
            'ssl_verify': self.ssl_verify,
            'timeout_seconds': self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HttpRequest':
        timeout = data.get('timeout_seconds', DEFAULT_REQUEST_TIMEOUT_SECONDS)
        try:
            timeout = int(timeout)
        except (TypeError, ValueError):
            timeout = DEFAULT_REQUEST_TIMEOUT_SECONDS
        if timeout <= 0:
            timeout = DEFAULT_REQUEST_TIMEOUT_SECONDS
        return cls(
            method=data.get('method', 'GET'),
            url=data.get('url', ''),
            headers=[HeaderItem.from_dict(h) for h in data.get('headers', [])],
            body_type=_parse_body_type(data.get('body_type', BodyType.RAW.value)),
            body_text=data.get('body_text', ''),
            form_fields=[FormField.from_dict(f) for f in data.get('form_fields', [])],
            file_path=data.get('file_path', ''),
            ssl_verify=data.get('ssl_verify', False),
            timeout_seconds=timeout,
        )

    def has_body(self) -> bool:
        if self.body_type in (BodyType.RAW, BodyType.JSON):
            return bool(self.body_text.strip())
        if self.body_type == BodyType.FORM:
            return any(
                field.key.strip() or field.value or field.file_path
                for field in self.form_fields
            )
        if self.body_type == BodyType.FILE:
            return bool(self.file_path.strip())
        return False


@dataclass
class HttpResponse:
    status_code: int = 0
    reason: str = ''
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b''
    elapsed_ms: float = 0.0
    error: str = ''
    request_headers: Dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.error and 200 <= self.status_code < 300

    def body_text(self) -> str:
        if not self.body:
            return ''
        for encoding in ('utf-8', 'gbk', 'latin-1'):
            try:
                return self.body.decode(encoding)
            except UnicodeDecodeError:
                continue
        return self.body.decode('utf-8', errors='replace')


@dataclass
class HistoryRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ''
    request: HttpRequest = field(default_factory=HttpRequest)
    sent_headers: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    status_code: Optional[int] = None
    status_reason: str = ''
    elapsed_ms: Optional[float] = None
    response_headers: Dict[str, str] = field(default_factory=dict)
    response_body: str = ''
    response_body_is_binary: bool = False
    error: str = ''

    def display_name(self) -> str:
        if self.name:
            return self.name
        url = self.request.url.strip()
        return url or 'Untitled Request'

    def full_url(self) -> str:
        return self.request.url.strip()

    def list_text(self) -> str:
        text = f'{self.request.method} {self.display_name()}'
        if self.status_code is not None:
            text += f' [{self.status_code}]'
        return text

    def item_tooltip(self) -> str:
        time_text = self.created_at
        if time_text:
            try:
                dt = datetime.fromisoformat(time_text.replace('Z', '+00:00'))
                if dt.tzinfo is not None:
                    dt = dt.astimezone()
                time_text = dt.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        lines = [time_text, self.full_url()]
        status_line = self.tooltip_status_line()
        if status_line:
            lines.append(status_line)
        return '\n'.join(lines)

    def tooltip_status_line(self) -> str:
        if self.status_code:
            if self.status_reason:
                return f'{self.status_code} {self.status_reason}'
            return str(self.status_code)
        if self.error:
            return self.error
        if self.status_reason:
            return self.status_reason
        return ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'request': self.request.to_dict(),
            'sent_headers': dict(self.sent_headers),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'status_code': self.status_code,
            'status_reason': self.status_reason,
            'elapsed_ms': self.elapsed_ms,
            'response_headers': dict(self.response_headers),
            'response_body': self.response_body,
            'response_body_is_binary': self.response_body_is_binary,
            'error': self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HistoryRecord':
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', ''),
            request=HttpRequest.from_dict(data.get('request', {})),
            sent_headers=dict(data.get('sent_headers', {})),
            created_at=data.get('created_at', _now_iso()),
            updated_at=data.get('updated_at', _now_iso()),
            status_code=data.get('status_code'),
            status_reason=data.get('status_reason', ''),
            elapsed_ms=data.get('elapsed_ms'),
            response_headers=dict(data.get('response_headers', {})),
            response_body=data.get('response_body', ''),
            response_body_is_binary=data.get('response_body_is_binary', False),
            error=data.get('error', ''),
        )
