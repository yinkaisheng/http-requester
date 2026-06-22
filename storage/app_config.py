#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from log_util import logger
from storage.paths import CONFIG_FILE
from ui.theme_defaults import DEFAULT_THEMES, DEFAULT_THEME_NAMES, merge_theme_colors

CONFIG_VERSION = 1

INT_CONFIG_DEFAULTS: Dict[str, int] = {
    'version': CONFIG_VERSION,
    'json_format_max_bytes': 5 * 1024 * 1024,
    'binary_hex_preview_bytes': 1024 * 10,
    'binary_hex_line_width': 8,
    'tab_title_max_width': 400,
}

_INT_CONFIG_BOUNDS: Dict[str, tuple[int, int]] = {
    'version': (1, 9999),
    'json_format_max_bytes': (1024, 100 * 1024 * 1024),
    'binary_hex_preview_bytes': (64, 10 * 1024 * 1024),
    'binary_hex_line_width': (1, 32),
    'tab_title_max_width': (100, 2000),
}


@dataclass(frozen=True)
class AppConfig:
    json_format_max_bytes: int
    binary_hex_preview_bytes: int
    binary_hex_line_width: int
    tab_title_max_width: int
    themes: Dict[str, Dict[str, str]]


_config_cache: Optional[AppConfig] = None


def _clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _default_themes() -> Dict[str, Dict[str, str]]:
    return {name: dict(DEFAULT_THEMES[name]) for name in DEFAULT_THEME_NAMES}


def _normalize_themes(raw_themes: Any) -> Dict[str, Dict[str, str]]:
    if not isinstance(raw_themes, dict):
        raw_themes = {}
    normalized: Dict[str, Dict[str, str]] = {}
    for theme_name in DEFAULT_THEME_NAMES:
        theme_raw = raw_themes.get(theme_name, {})
        if not isinstance(theme_raw, dict):
            theme_raw = {}
        normalized[theme_name] = merge_theme_colors(theme_name, theme_raw)
    return normalized


def _normalize_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, default in INT_CONFIG_DEFAULTS.items():
        minimum, maximum = _INT_CONFIG_BOUNDS[key]
        normalized[key] = _clamp_int(raw.get(key), default, minimum, maximum)
    normalized['themes'] = _normalize_themes(raw.get('themes'))
    return normalized


def _default_config() -> Dict[str, Any]:
    config = dict(INT_CONFIG_DEFAULTS)
    config['themes'] = _default_themes()
    return config


def _to_app_config(data: Dict[str, Any]) -> AppConfig:
    return AppConfig(
        json_format_max_bytes=data['json_format_max_bytes'],
        binary_hex_preview_bytes=data['binary_hex_preview_bytes'],
        binary_hex_line_width=data['binary_hex_line_width'],
        tab_title_max_width=data['tab_title_max_width'],
        themes=data['themes'],
    )


def _save_config(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        logger.warning(f'Failed to save app config to {path}')


def _config_needs_save(raw: Dict[str, Any], normalized: Dict[str, Any]) -> bool:
    for key in INT_CONFIG_DEFAULTS:
        if raw.get(key) != normalized[key]:
            return True
    raw_themes = raw.get('themes')
    if not isinstance(raw_themes, dict):
        return True
    for theme_name in DEFAULT_THEME_NAMES:
        if theme_name not in raw_themes:
            return True
        theme_raw = raw_themes.get(theme_name)
        if not isinstance(theme_raw, dict):
            return True
        if merge_theme_colors(theme_name, theme_raw) != normalized['themes'][theme_name]:
            return True
    return False


def _load_config(path: Path = CONFIG_FILE) -> AppConfig:
    if not path.exists():
        normalized = _default_config()
        _save_config(path, normalized)
        return _to_app_config(normalized)

    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning(f'Failed to load app config from {path}; using defaults')
        normalized = _default_config()
        _save_config(path, normalized)
        return _to_app_config(normalized)

    if not isinstance(raw, dict):
        raw = {}

    normalized = _normalize_config(raw)
    if _config_needs_save(raw, normalized):
        _save_config(path, normalized)
    return _to_app_config(normalized)


def get_app_config() -> AppConfig:
    global _config_cache
    if _config_cache is None:
        _config_cache = _load_config()
    return _config_cache


def init_app_config() -> AppConfig:
    """Load or create config.json; safe to call at application startup."""
    global _config_cache
    _config_cache = _load_config()
    return _config_cache
