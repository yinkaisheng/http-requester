#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    body_type: BodyType = BodyType.NONE
    body_text: str = ''
    form_fields: List[FormField] = field(default_factory=list)
    file_path: str = ''
    ssl_verify: bool = False

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
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HttpRequest':
        return cls(
            method=data.get('method', 'GET'),
            url=data.get('url', ''),
            headers=[HeaderItem.from_dict(h) for h in data.get('headers', [])],
            body_type=BodyType(data.get('body_type', BodyType.NONE.value)),
            body_text=data.get('body_text', ''),
            form_fields=[FormField.from_dict(f) for f in data.get('form_fields', [])],
            file_path=data.get('file_path', ''),
            ssl_verify=data.get('ssl_verify', False),
        )


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
    last_status: Optional[int] = None
    last_status_reason: str = ''
    last_elapsed_ms: Optional[float] = None
    response_headers: Dict[str, str] = field(default_factory=dict)
    response_body: str = ''

    def display_name(self) -> str:
        if self.name:
            return self.name
        url = self.request.url.strip()
        return url or 'Untitled Request'

    def full_url(self) -> str:
        return self.request.url.strip()

    def list_text(self) -> str:
        text = f'{self.request.method} {self.display_name()}'
        if self.last_status is not None:
            text += f' [{self.last_status}]'
        return text

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'request': self.request.to_dict(),
            'sent_headers': dict(self.sent_headers),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_status': self.last_status,
            'last_status_reason': self.last_status_reason,
            'last_elapsed_ms': self.last_elapsed_ms,
            'response_headers': dict(self.response_headers),
            'response_body': self.response_body,
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
            last_status=data.get('last_status'),
            last_status_reason=data.get('last_status_reason', ''),
            last_elapsed_ms=data.get('last_elapsed_ms'),
            response_headers=dict(data.get('response_headers', {})),
            response_body=data.get('response_body', ''),
        )
