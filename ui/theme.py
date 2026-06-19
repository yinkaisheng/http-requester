#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, Literal

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication

# Solarized accent colors (shared across themes)
SOL_BLUE = '#268bd2'
SOL_CYAN = '#2aa198'
SOL_GREEN = '#859900'
SOL_YELLOW = '#b58900'
SOL_ORANGE = '#cb4b16'
SOL_RED = '#dc322f'
SOL_VIOLET = '#6c71c4'

FONT_SIZE_DELTA_PX = 2
BODY_TEXT_FONT_DELTA_PX = 4
BODY_TEXT_FONT_FAMILY_WIN = 'Consolas'
BODY_TEXT_FONT_FALLBACKS = ('Cascadia Mono', 'Menlo', 'Monaco', 'Courier New', 'monospace')

ThemeName = Literal['light', 'dark']
THEME_LIGHT: ThemeName = 'light'
THEME_DARK: ThemeName = 'dark'
THEME_LABELS: Dict[ThemeName, str] = {
    THEME_LIGHT: 'Light',
    THEME_DARK: 'Dark',
}
THEME_OPTIONS = [THEME_LIGHT, THEME_DARK]


@dataclass(frozen=True)
class ThemePalette:
    window_bg: str
    window_fg: str
    surface: str
    surface_alt: str
    border: str
    border_strong: str
    text_muted: str
    text_subtle: str
    hover_bg: str
    hover_bg_soft: str
    hover_bg_toggle: str
    accent: str
    accent_hover: str
    accent_pressed: str
    on_accent: str
    error: str
    success: str
    warning: str
    pending: str
    gridline: str


LIGHT_PALETTE = ThemePalette(
    window_bg='#fdf6e3',
    window_fg='#657b83',
    surface='#eee8d5',
    surface_alt='#faf4e6',
    border='#93a2a1',
    border_strong='#839496',
    text_muted='#586e75',
    text_subtle='#839496',
    hover_bg='#e8e2cf',
    hover_bg_soft='#f5efdc',
    hover_bg_toggle='#faf4e6',
    accent=SOL_BLUE,
    accent_hover='#2f9ee0',
    accent_pressed='#1f7bb8',
    on_accent='#fdf6e3',
    error=SOL_RED,
    success=SOL_GREEN,
    warning=SOL_ORANGE,
    pending='#586e75',
    gridline='#eee8d5',
)

DARK_PALETTE = ThemePalette(
    window_bg='#002b36',
    window_fg='#839496',
    surface='#073642',
    surface_alt='#0a3d4a',
    border='#586e75',
    border_strong='#657b83',
    text_muted='#93a2a1',
    text_subtle='#839496',
    hover_bg='#0e4d5c',
    hover_bg_soft='#0a3d4a',
    hover_bg_toggle='#0a3d4a',
    accent=SOL_BLUE,
    accent_hover='#2f9ee0',
    accent_pressed='#1f7bb8',
    on_accent='#fdf6e3',
    error=SOL_RED,
    success=SOL_GREEN,
    warning=SOL_ORANGE,
    pending='#93a2a1',
    gridline='#073642',
)

THEME_PALETTES: Dict[ThemeName, ThemePalette] = {
    THEME_LIGHT: LIGHT_PALETTE,
    THEME_DARK: DARK_PALETTE,
}


def normalize_theme_name(theme: str | None) -> ThemeName:
    if theme == THEME_DARK:
        return THEME_DARK
    return THEME_LIGHT


def _body_text_font_family() -> str:
    if sys.platform == 'win32':
        return f'{BODY_TEXT_FONT_FAMILY_WIN}, "Courier New", monospace'
    return ', '.join(f'"{name}"' if ' ' in name else name for name in BODY_TEXT_FONT_FALLBACKS)


def apply_app_font(app: QApplication) -> None:
    """Apply the app-wide font adjustment once at startup."""
    base_font = app.font()
    pixel_size = base_font.pixelSize()
    if pixel_size > 0:
        base_font.setPixelSize(pixel_size + FONT_SIZE_DELTA_PX)
    else:
        base_font.setPointSize(base_font.pointSize() + 1)
    app.setFont(base_font)


def apply_app_theme(app: QApplication, theme: str | None = THEME_LIGHT) -> None:
    palette = THEME_PALETTES[normalize_theme_name(theme)]
    app.setStyleSheet(_build_stylesheet(app.font(), palette))


def _build_stylesheet(font: QFont, palette: ThemePalette) -> str:
    size_px = font.pixelSize() if font.pixelSize() > 0 else int(font.pointSize() * 1.33)
    body_text_font_size = size_px + BODY_TEXT_FONT_DELTA_PX
    body_text_font_family = _body_text_font_family()
    p = palette
    return f'''
* {{
    font-size: {size_px}px;
}}

QMainWindow, QWidget {{
    background-color: {p.window_bg};
    color: {p.window_fg};
}}

QMenuBar {{
    background-color: {p.surface};
    border-bottom: 1px solid {p.border};
    padding: 2px;
}}

QMenuBar::item:selected {{
    background-color: {p.border};
    border-radius: 3px;
}}

QMenu {{
    background-color: {p.window_bg};
    border: 1px solid {p.border};
    padding: 4px;
}}

QMenu::item:selected {{
    background-color: {p.surface};
}}

QStatusBar {{
    background-color: {p.surface};
    color: {p.text_muted};
    border-top: 1px solid {p.border};
}}

QSplitter::handle {{
    background-color: {p.border};
    width: 2px;
}}

QSplitter::handle:hover {{
    background-color: {p.accent};
}}

QTabWidget::pane {{
    border: 1px solid {p.border};
    border-radius: 4px;
    background-color: {p.window_bg};
    top: -1px;
}}

QTabBar::tab {{
    background-color: {p.surface};
    color: {p.text_muted};
    border: 1px solid {p.border};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 6px 14px;
    margin-right: 2px;
    min-width: 80px;
}}

QTabBar::tab:selected {{
    background-color: {p.window_bg};
    color: {p.window_fg};
    border-bottom: 1px solid {p.window_bg};
}}

QTabBar::tab:hover:!selected {{
    background-color: {p.hover_bg_soft};
}}

QTabBar::close-button {{
    subcontrol-origin: padding;
    subcontrol-position: right;
    width: 16px;
    height: 16px;
    margin: 2px;
    border-radius: 3px;
}}

QTabBar::close-button:hover {{
    background-color: {p.error};
}}

QLabel#sectionTitle {{
    font-weight: bold;
    color: {p.text_muted};
    padding: 2px 0;
    margin: 0;
}}

QPushButton#headerModeButton {{
    background-color: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: {p.text_subtle};
    font-weight: bold;
    padding: 2px 8px;
    margin: 0;
    min-height: 0;
}}

QPushButton#headerModeButton:checked {{
    color: {p.text_muted};
    border-bottom: 2px solid {p.accent};
}}

QPushButton#headerModeButton:hover {{
    color: {p.window_fg};
}}

QPushButton#compactButton {{
    padding: 1px 10px;
    min-height: 0px;
    margin: 0;
}}

QPushButton#formCellButton {{
    padding: 1px 0px;
    min-height: 0px;
    margin: 0;
}}

QTableWidget QLineEdit#formCellLineEdit {{
    padding: 1px 4px;
    margin: 0px;
    min-height: 0px;
    border: none;
}}

QPushButton#tabCloseButton {{
    background-color: transparent;
    border: none;
    color: {p.text_subtle};
    padding: 0;
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
    border-radius: 3px;
}}

QPushButton#tabCloseButton:hover {{
    background-color: {p.error};
    color: {p.on_accent};
}}

QPushButton {{
    background-color: {p.surface};
    color: {p.window_fg};
    border: 1px solid {p.border};
    border-radius: 4px;
    padding: 5px 12px;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {p.hover_bg};
    border-color: {p.border_strong};
}}

QPushButton:pressed {{
    background-color: {p.border};
}}

QPushButton:disabled {{
    color: {p.border};
    background-color: {p.surface};
}}

QPushButton#primaryButton {{
    background-color: {p.accent};
    color: {p.on_accent};
    border: 1px solid {p.accent};
    font-weight: bold;
}}

QPushButton#primaryButton:hover {{
    background-color: {p.accent_hover};
}}

QPushButton#primaryButton:pressed {{
    background-color: {p.accent_pressed};
}}

QPushButton#historyDeleteButton {{
    background-color: transparent;
    border: none;
    color: {p.text_subtle};
    padding: 2px 6px;
    min-width: 22px;
    max-width: 22px;
    border-radius: 3px;
}}

QPushButton#historyDeleteButton:hover {{
    background-color: {p.error};
    color: {p.on_accent};
}}

QLineEdit, QPlainTextEdit {{
    background-color: {p.window_bg};
    color: {p.window_fg};
    border: 1px solid {p.border};
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
}}

QComboBox, QSpinBox {{
    background-color: {p.window_bg};
    color: {p.window_fg};
    border: 1px solid {p.border};
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
}}

QComboBox {{
    padding-right: 4px;
}}

QSpinBox {{
    padding-right: 2px;
}}

QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border-color: {p.accent};
}}

QPlainTextEdit#bodyTextEdit {{
    font-family: {body_text_font_family};
    font-size: {body_text_font_size}px;
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border: none;
    border-left: 1px solid {p.border};
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
    background-color: {p.surface};
}}

QComboBox::drop-down:hover {{
    background-color: {p.hover_bg};
}}

QComboBox::down-arrow {{
    image: none;
    width: 14px;
    height: 14px;
}}

QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border;
    width: 20px;
    border: none;
    border-left: 1px solid {p.border};
    background-color: {p.surface};
}}

QSpinBox::up-button {{
    subcontrol-position: top right;
    border-bottom: 1px solid {p.border};
    border-top-right-radius: 3px;
}}

QSpinBox::up-button:hover {{
    background-color: {p.hover_bg};
}}

QSpinBox::down-button {{
    subcontrol-position: bottom right;
    border-bottom-right-radius: 3px;
}}

QSpinBox::down-button:hover {{
    background-color: {p.hover_bg};
}}

QComboBox QAbstractItemView {{
    background-color: {p.window_bg};
    border: 1px solid {p.border};
    selection-background-color: {p.surface};
    selection-color: {p.window_fg};
}}

QTableWidget, QTableView {{
    background-color: {p.window_bg};
    alternate-background-color: {p.surface_alt};
    gridline-color: {p.gridline};
    border: 1px solid {p.border};
    border-radius: 4px;
}}

QTableWidget::item {{
    padding: 2px 4px;
}}

QTableWidget#headerTable::item {{
    padding: 1px 4px;
}}

QTableWidget QLineEdit#tableCellEditor {{
    padding: 0px 4px;
    margin: 0px;
    border: none;
    background-color: {p.window_bg};
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
}}

QHeaderView::section {{
    background-color: {p.surface};
    color: {p.text_muted};
    border: none;
    border-bottom: 1px solid {p.border};
    border-right: 1px solid {p.border};
    padding: 2px 6px;
    margin: 0;
}}

QHeaderView::horizontal {{
    min-height: 24px;
    max-height: 24px;
}}

QListWidget {{
    background-color: {p.window_bg};
    border: 1px solid {p.border};
    border-radius: 4px;
    outline: none;
}}

QListWidget::item {{
    border-bottom: 1px solid {p.gridline};
}}

QListWidget::item:selected {{
    background-color: {p.surface};
    color: {p.window_fg};
}}

QListWidget::item:hover {{
    background-color: {p.hover_bg_soft};
}}

QScrollBar:vertical {{
    background: {p.surface};
    width: 10px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background: {p.border};
    border-radius: 5px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background: {p.border_strong};
}}

QScrollBar:horizontal {{
    background: {p.surface};
    height: 10px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal {{
    background: {p.border};
    border-radius: 5px;
    min-width: 24px;
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}

QPushButton#checkMarkToggle {{
    background-color: {p.window_bg};
    border: 1px solid {p.border};
    border-radius: 3px;
    color: transparent;
    font-weight: bold;
    font-size: {max(size_px - 3, 11)}px;
    padding: 0;
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
}}

QPushButton#checkMarkToggle:hover {{
    border-color: {p.border_strong};
    background-color: {p.hover_bg_toggle};
}}

QPushButton#checkMarkToggle:checked {{
    background-color: {p.accent};
    border-color: {p.accent};
    color: {p.on_accent};
}}

QPushButton#checkMarkToggle:checked:hover {{
    background-color: {p.accent_hover};
    border-color: {p.accent_hover};
}}

QPushButton#checkMarkToggleCompact {{
    background-color: {p.window_bg};
    border: 1px solid {p.border};
    border-radius: 3px;
    color: transparent;
    font-weight: bold;
    font-size: {max(size_px - 4, 10)}px;
    padding: 0;
    min-width: 16px;
    max-width: 16px;
    min-height: 16px;
    max-height: 16px;
}}

QPushButton#checkMarkToggleCompact:hover {{
    border-color: {p.border_strong};
    background-color: {p.hover_bg_toggle};
}}

QPushButton#checkMarkToggleCompact:checked {{
    background-color: {p.accent};
    border-color: {p.accent};
    color: {p.on_accent};
}}

QPushButton#checkMarkToggleCompact:checked:hover {{
    background-color: {p.accent_hover};
    border-color: {p.accent_hover};
}}

QRadioButton {{
    spacing: 6px;
}}

QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {p.border};
    border-radius: 7px;
    background: {p.window_bg};
}}

QRadioButton::indicator:checked {{
    background: {p.accent};
    border-color: {p.accent};
}}

QLabel#panelTitle {{
    font-weight: bold;
    color: {p.text_muted};
    padding: 4px 0;
}}

QLabel#historyItemLabel {{
    color: {p.window_fg};
    background: transparent;
}}

QLabel#statusOk {{
    padding: 0;
    margin: 0;
    color: {p.success};
    font-size: {max(size_px - 2, 10)}px;
    font-weight: normal;
}}

QLabel#statusWarn {{
    padding: 0;
    margin: 0;
    color: {p.warning};
    font-size: {max(size_px - 2, 10)}px;
    font-weight: normal;
}}

QLabel#statusError {{
    padding: 0;
    margin: 0;
    color: {p.error};
    font-size: {max(size_px - 2, 10)}px;
    font-weight: normal;
}}

QLabel#statusPending {{
    padding: 0;
    margin: 0;
    color: {p.pending};
    font-size: {max(size_px - 2, 10)}px;
    font-weight: normal;
}}
'''
