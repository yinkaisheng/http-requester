#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List, Tuple

from models.http_models import HttpRequest


def has_header(headers: List[Tuple[str, str]], name: str) -> bool:
    """Check if a header name exists in a list of (key, value) tuples, case-insensitive."""
    lower = name.lower()
    return any(key.lower() == lower for key, _ in headers)


def user_headers_ordered(req: HttpRequest) -> List[Tuple[str, str]]:
    """Return enabled headers as an ordered list of (key, value) tuples."""
    rows: List[Tuple[str, str]] = []
    for item in req.headers:
        if item.enabled and item.key.strip():
            rows.append((item.key.strip(), item.value))
    return rows
