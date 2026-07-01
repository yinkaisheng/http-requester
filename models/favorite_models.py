#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from models.http_models import HttpRequest


@dataclass
class FavoriteItem:
    """A node in a favorite tree.

    A folder has ``children`` but no ``request``.
    A request leaf has ``request`` but no ``children``.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ''
    request: Optional[HttpRequest] = None
    children: List[FavoriteItem] = field(default_factory=list)

    def is_folder(self) -> bool:
        return self.request is None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {'id': self.id, 'name': self.name}
        if self.request is not None:
            d['request'] = self.request.to_dict()
        if self.children:
            d['children'] = [c.to_dict() for c in self.children]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FavoriteItem:
        request = None
        req_data = data.get('request')
        if req_data is not None:
            request = HttpRequest.from_dict(req_data)
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', ''),
            request=request,
            children=[cls.from_dict(c) for c in data.get('children', [])],
        )
