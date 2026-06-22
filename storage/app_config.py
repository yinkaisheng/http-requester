#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from log_util import logger
from storage.paths import CONFIG_FILE
from ui.appearance_defaults import (
    DEFAULT_BODY_TEXT_FONT_FAMILIES,
    DEFAULT_BODY_TEXT_FONT_FAMILY,
    DEFAULT_BODY_TEXT_FONT_FALLBACKS,
    DEFAULT_THEME,
    DEFAULT_UI_FONT_FAMILIES_WIN,
    _APPEARANCE_INT_BOUNDS,
    _APPEARANCE_INT_DEFAULTS,
    default_appearance,
)
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

_VALID_THEMES = frozenset(DEFAULT_THEME_NAMES)


@dataclass(frozen=True)
class AppearanceConfig:
    """Runtime appearance from config.json appearance.* (restart to apply file edits)."""

    # 当前配色主题名（solarized / light / dark）；决定 config.json themes.* 中的全局 QSS 颜色。
    theme: str

    # 通用 UI 字号（px）：QApplication 默认字体 + 全局 QSS「* { font-size }」；
    # 按钮、Tab 标题、标签、菜单、URL 输入框、下拉框、请求/响应 Headers 表格等。
    ui_font_size_px: int

    # Form Data 等可编辑表格单元格字号（px）；Headers 表格使用 ui_font_size_px。
    table_font_size_px: int

    # 响应状态行字号（px）：QLabel#statusOk / statusWarn / statusError / statusPending。
    status_font_size_px: int

    # 请求 Tab 关闭按钮字号（px）：QPushButton#tabCloseButton。
    tab_close_font_size_px: int

    # 工具栏图标按钮字号（px）：QToolButton#settingsButton / aboutButton（⚙、ⓘ）。
    toolbar_icon_font_size_px: int

    # Windows UI 字体候选列表（按顺序取第一个系统已安装的字体作为 QApplication 默认 font-family）。
    ui_font_families_win: Tuple[str, ...]

    # Request Body / Response Body 编辑器（QPlainTextEdit#bodyTextEdit）font-family。
    body_text_font_family: str

    # 上述 Body 编辑器的 font-size（px）；设置界面可改，重启 config 文件修改后生效。
    body_text_font_size_px: int

    # 设置界面「Editor Font Size」及 body_text_font_size_px 校验允许的最小字号（px）。
    body_text_font_size_min: int

    # 设置界面「Editor Font Size」及 body_text_font_size_px 校验允许的最大字号（px）。
    body_text_font_size_max: int

    # 设置界面「Editor Font Family」下拉框中的等宽字体候选列表。
    body_text_font_families: Tuple[str, ...]

    # Body 编辑器 CSS font-family 回退链；主字体缺字时使用。
    body_text_font_fallbacks: Tuple[str, ...]


@dataclass(frozen=True)
class AppConfig:
    json_format_max_bytes: int
    binary_hex_preview_bytes: int
    binary_hex_line_width: int
    tab_title_max_width: int
    themes: Dict[str, Dict[str, str]]
    appearance: AppearanceConfig


_config_cache: Optional[AppConfig] = None
_raw_config_cache: Optional[Dict[str, Any]] = None


def _clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _normalize_string_list(
    value: Any,
    default: Tuple[str, ...],
    *,
    strip_quotes: bool = False,
) -> Tuple[str, ...]:
    if not isinstance(value, list):
        return default
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if strip_quotes:
            text = text.replace('"', '')
        if text and text not in items:
            items.append(text)
    return tuple(items) if items else default


def _normalize_theme_name(value: Any) -> str:
    if isinstance(value, str) and value in _VALID_THEMES:
        return value
    return DEFAULT_THEME


def _normalize_font_family(value: Any, default: str, candidates: Tuple[str, ...]) -> str:
    if isinstance(value, str):
        name = value.strip().replace('"', '')
        if name in candidates:
            return name
        if name:
            return name
    return default


def _normalize_appearance(raw: Any) -> Dict[str, Any]:
    defaults = default_appearance()
    raw = raw if isinstance(raw, dict) else {}
    candidates = _normalize_string_list(
        raw.get('body_text_font_families'),
        DEFAULT_BODY_TEXT_FONT_FAMILIES,
        strip_quotes=True,
    )
    normalized: Dict[str, Any] = {
        'theme': _normalize_theme_name(raw.get('theme')),
        'ui_font_families_win': list(_normalize_string_list(
            raw.get('ui_font_families_win'),
            DEFAULT_UI_FONT_FAMILIES_WIN,
            strip_quotes=True,
        )),
        'body_text_font_family': _normalize_font_family(
            raw.get('body_text_font_family'),
            DEFAULT_BODY_TEXT_FONT_FAMILY,
            candidates,
        ),
        'body_text_font_families': list(candidates),
        'body_text_font_fallbacks': list(_normalize_string_list(
            raw.get('body_text_font_fallbacks'),
            DEFAULT_BODY_TEXT_FONT_FALLBACKS,
            strip_quotes=True,
        )),
    }
    for key, default in _APPEARANCE_INT_DEFAULTS.items():
        minimum, maximum = _APPEARANCE_INT_BOUNDS[key]
        normalized[key] = _clamp_int(raw.get(key), default, minimum, maximum)
    if normalized['body_text_font_size_min'] > normalized['body_text_font_size_max']:
        normalized['body_text_font_size_min'] = defaults['body_text_font_size_min']
        normalized['body_text_font_size_max'] = defaults['body_text_font_size_max']
    normalized['body_text_font_size_px'] = _clamp_int(
        raw.get('body_text_font_size_px'),
        defaults['body_text_font_size_px'],
        normalized['body_text_font_size_min'],
        normalized['body_text_font_size_max'],
    )
    return normalized


def _appearance_to_config(appearance: Dict[str, Any]) -> AppearanceConfig:
    return AppearanceConfig(
        theme=appearance['theme'],
        ui_font_size_px=appearance['ui_font_size_px'],
        table_font_size_px=appearance['table_font_size_px'],
        status_font_size_px=appearance['status_font_size_px'],
        tab_close_font_size_px=appearance['tab_close_font_size_px'],
        toolbar_icon_font_size_px=appearance['toolbar_icon_font_size_px'],
        ui_font_families_win=tuple(appearance['ui_font_families_win']),
        body_text_font_family=appearance['body_text_font_family'],
        body_text_font_size_px=appearance['body_text_font_size_px'],
        body_text_font_size_min=appearance['body_text_font_size_min'],
        body_text_font_size_max=appearance['body_text_font_size_max'],
        body_text_font_families=tuple(appearance['body_text_font_families']),
        body_text_font_fallbacks=tuple(appearance['body_text_font_fallbacks']),
    )


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
    normalized['appearance'] = _normalize_appearance(raw.get('appearance'))
    return normalized


def _default_config() -> Dict[str, Any]:
    config = dict(INT_CONFIG_DEFAULTS)
    config['themes'] = _default_themes()
    config['appearance'] = default_appearance()
    return config


def _to_app_config(data: Dict[str, Any]) -> AppConfig:
    return AppConfig(
        json_format_max_bytes=data['json_format_max_bytes'],
        binary_hex_preview_bytes=data['binary_hex_preview_bytes'],
        binary_hex_line_width=data['binary_hex_line_width'],
        tab_title_max_width=data['tab_title_max_width'],
        themes=data['themes'],
        appearance=_appearance_to_config(data['appearance']),
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
    if raw.get('appearance') != normalized['appearance']:
        return True
    return False


def _load_config(path: Path = CONFIG_FILE) -> AppConfig:
    global _raw_config_cache
    if not path.exists():
        normalized = _default_config()
        _save_config(path, normalized)
        _raw_config_cache = normalized
        return _to_app_config(normalized)

    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning(f'Failed to load app config from {path}; using defaults')
        normalized = _default_config()
        _save_config(path, normalized)
        _raw_config_cache = normalized
        return _to_app_config(normalized)

    if not isinstance(raw, dict):
        raw = {}

    normalized = _normalize_config(raw)
    if _config_needs_save(raw, normalized):
        _save_config(path, normalized)
    _raw_config_cache = normalized
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


def save_appearance_settings(
    *,
    theme: str,
    body_text_font_family: str,
    body_text_font_size_px: int,
    path: Path = CONFIG_FILE,
) -> AppearanceConfig:
    """Persist appearance choices to config.json and refresh the in-memory cache."""
    global _config_cache, _raw_config_cache
    cfg = get_app_config()
    current = cfg.appearance
    appearance = _normalize_appearance({
        'theme': theme,
        'ui_font_size_px': current.ui_font_size_px,
        'table_font_size_px': current.table_font_size_px,
        'status_font_size_px': current.status_font_size_px,
        'tab_close_font_size_px': current.tab_close_font_size_px,
        'toolbar_icon_font_size_px': current.toolbar_icon_font_size_px,
        'ui_font_families_win': list(current.ui_font_families_win),
        'body_text_font_family': body_text_font_family,
        'body_text_font_size_px': body_text_font_size_px,
        'body_text_font_size_min': current.body_text_font_size_min,
        'body_text_font_size_max': current.body_text_font_size_max,
        'body_text_font_families': list(current.body_text_font_families),
        'body_text_font_fallbacks': list(current.body_text_font_fallbacks),
    })
    if _raw_config_cache is None:
        _raw_config_cache = _normalize_config(_default_config())
    data = dict(_raw_config_cache)
    data['appearance'] = appearance
    _save_config(path, data)
    _raw_config_cache = data
    _config_cache = _to_app_config(data)
    return _config_cache.appearance
