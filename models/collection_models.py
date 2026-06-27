#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models.http_models import HttpRequest


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CollectionItem:
    """A node in a collection tree.

    A folder has ``children`` but no ``request``.
    A request leaf has ``request`` but no ``children``.
    """
    name: str = ''
    request: Optional[HttpRequest] = None
    children: List[CollectionItem] = field(default_factory=list)

    def is_folder(self) -> bool:
        return self.request is None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {'name': self.name}
        if self.request is not None:
            d['request'] = self.request.to_dict()
        if self.children:
            d['children'] = [c.to_dict() for c in self.children]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CollectionItem:
        request = None
        req_data = data.get('request')
        if req_data is not None:
            request = HttpRequest.from_dict(req_data)
        return cls(
            name=data.get('name', ''),
            request=request,
            children=[cls.from_dict(c) for c in data.get('children', [])],
        )


@dataclass
class Collection:
    """A named top-level collection containing a tree of items."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ''
    items: List[CollectionItem] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'items': [item.to_dict() for item in self.items],
            'created_at': self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Collection:
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', ''),
            items=[CollectionItem.from_dict(item) for item in data.get('items', [])],
            created_at=data.get('created_at', _now_iso()),
        )
