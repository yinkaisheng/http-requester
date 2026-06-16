#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication

# Solarized Light palette
SOL_BASE03 = '#002b36'
SOL_BASE02 = '#073642'
SOL_BASE01 = '#586e75'
SOL_BASE00 = '#657b83'
SOL_BASE0 = '#839496'
SOL_BASE1 = '#93a2a1'
SOL_BASE2 = '#eee8d5'
SOL_BASE3 = '#fdf6e3'
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


def _body_text_font_family() -> str:
    if sys.platform == 'win32':
        return f'{BODY_TEXT_FONT_FAMILY_WIN}, "Courier New", monospace'
    return ', '.join(f'"{name}"' if ' ' in name else name for name in BODY_TEXT_FONT_FALLBACKS)


def apply_app_theme(app: QApplication) -> None:
    base_font = app.font()
    pixel_size = base_font.pixelSize()
    if pixel_size > 0:
        base_font.setPixelSize(pixel_size + FONT_SIZE_DELTA_PX)
    else:
        base_font.setPointSize(base_font.pointSize() + 1)
    app.setFont(base_font)
    app.setStyleSheet(_build_stylesheet(base_font))


def _build_stylesheet(font: QFont) -> str:
    size_px = font.pixelSize() if font.pixelSize() > 0 else int(font.pointSize() * 1.33)
    body_text_font_size = size_px + BODY_TEXT_FONT_DELTA_PX
    body_text_font_family = _body_text_font_family()
    return f'''
* {{
    font-size: {size_px}px;
}}

QMainWindow, QWidget {{
    background-color: {SOL_BASE3};
    color: {SOL_BASE00};
}}

QMenuBar {{
    background-color: {SOL_BASE2};
    border-bottom: 1px solid {SOL_BASE1};
    padding: 2px;
}}

QMenuBar::item:selected {{
    background-color: {SOL_BASE1};
    border-radius: 3px;
}}

QMenu {{
    background-color: {SOL_BASE3};
    border: 1px solid {SOL_BASE1};
    padding: 4px;
}}

QMenu::item:selected {{
    background-color: {SOL_BASE2};
}}

QStatusBar {{
    background-color: {SOL_BASE2};
    color: {SOL_BASE01};
    border-top: 1px solid {SOL_BASE1};
}}

QSplitter::handle {{
    background-color: {SOL_BASE1};
    width: 2px;
}}

QSplitter::handle:hover {{
    background-color: {SOL_BLUE};
}}

QTabWidget::pane {{
    border: 1px solid {SOL_BASE1};
    border-radius: 4px;
    background-color: {SOL_BASE3};
    top: -1px;
}}

QTabBar::tab {{
    background-color: {SOL_BASE2};
    color: {SOL_BASE01};
    border: 1px solid {SOL_BASE1};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 6px 14px;
    margin-right: 2px;
    min-width: 80px;
}}

QTabBar::tab:selected {{
    background-color: {SOL_BASE3};
    color: {SOL_BASE00};
    border-bottom: 1px solid {SOL_BASE3};
}}

QTabBar::tab:hover:!selected {{
    background-color: #f5efdc;
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
    background-color: {SOL_RED};
}}

QLabel#sectionTitle {{
    font-weight: bold;
    color: {SOL_BASE01};
    padding: 2px 0;
    margin: 0;
}}

QPushButton#headerModeButton {{
    background-color: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: {SOL_BASE0};
    font-weight: bold;
    padding: 2px 8px;
    margin: 0;
    min-height: 0;
}}

QPushButton#headerModeButton:checked {{
    color: {SOL_BASE01};
    border-bottom: 2px solid {SOL_BLUE};
}}

QPushButton#headerModeButton:hover {{
    color: {SOL_BASE00};
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
    color: {SOL_BASE0};
    padding: 0;
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
    border-radius: 3px;
}}

QPushButton#tabCloseButton:hover {{
    background-color: {SOL_RED};
    color: {SOL_BASE3};
}}

QPushButton {{
    background-color: {SOL_BASE2};
    color: {SOL_BASE00};
    border: 1px solid {SOL_BASE1};
    border-radius: 4px;
    padding: 5px 12px;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: #e8e2cf;
    border-color: {SOL_BASE0};
}}

QPushButton:pressed {{
    background-color: {SOL_BASE1};
}}

QPushButton:disabled {{
    color: {SOL_BASE1};
    background-color: {SOL_BASE2};
}}

QPushButton#primaryButton {{
    background-color: {SOL_BLUE};
    color: {SOL_BASE3};
    border: 1px solid {SOL_BLUE};
    font-weight: bold;
}}

QPushButton#primaryButton:hover {{
    background-color: #2f9ee0;
}}

QPushButton#primaryButton:pressed {{
    background-color: #1f7bb8;
}}

QPushButton#historyDeleteButton {{
    background-color: transparent;
    border: none;
    color: {SOL_BASE0};
    padding: 2px 6px;
    min-width: 22px;
    max-width: 22px;
    border-radius: 3px;
}}

QPushButton#historyDeleteButton:hover {{
    background-color: {SOL_RED};
    color: {SOL_BASE3};
}}

QLineEdit, QPlainTextEdit, QComboBox, QSpinBox {{
    background-color: {SOL_BASE3};
    color: {SOL_BASE00};
    border: 1px solid {SOL_BASE1};
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: {SOL_BLUE};
    selection-color: {SOL_BASE3};
}}

QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border-color: {SOL_BLUE};
}}

QPlainTextEdit#bodyTextEdit {{
    font-family: {body_text_font_family};
    font-size: {body_text_font_size}px;
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: {SOL_BASE3};
    border: 1px solid {SOL_BASE1};
    selection-background-color: {SOL_BASE2};
    selection-color: {SOL_BASE00};
}}

QTableWidget, QTableView {{
    background-color: {SOL_BASE3};
    alternate-background-color: #faf4e6;
    gridline-color: {SOL_BASE2};
    border: 1px solid {SOL_BASE1};
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
    background-color: {SOL_BASE3};
    selection-background-color: {SOL_BLUE};
    selection-color: {SOL_BASE3};
}}

QHeaderView::section {{
    background-color: {SOL_BASE2};
    color: {SOL_BASE01};
    border: none;
    border-bottom: 1px solid {SOL_BASE1};
    border-right: 1px solid {SOL_BASE1};
    padding: 2px 6px;
    margin: 0;
}}

QHeaderView::horizontal {{
    min-height: 24px;
    max-height: 24px;
}}

QListWidget {{
    background-color: {SOL_BASE3};
    border: 1px solid {SOL_BASE1};
    border-radius: 4px;
    outline: none;
}}

QListWidget::item {{
    border-bottom: 1px solid {SOL_BASE2};
}}

QListWidget::item:selected {{
    background-color: {SOL_BASE2};
    color: {SOL_BASE00};
}}

QListWidget::item:hover {{
    background-color: #f5efdc;
}}

QScrollBar:vertical {{
    background: {SOL_BASE2};
    width: 10px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background: {SOL_BASE1};
    border-radius: 5px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background: {SOL_BASE0};
}}

QScrollBar:horizontal {{
    background: {SOL_BASE2};
    height: 10px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal {{
    background: {SOL_BASE1};
    border-radius: 5px;
    min-width: 24px;
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}

QPushButton#checkMarkToggle {{
    background-color: {SOL_BASE3};
    border: 1px solid {SOL_BASE1};
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
    border-color: {SOL_BASE0};
    background-color: #faf4e6;
}}

QPushButton#checkMarkToggle:checked {{
    background-color: {SOL_BLUE};
    border-color: {SOL_BLUE};
    color: {SOL_BASE3};
}}

QPushButton#checkMarkToggle:checked:hover {{
    background-color: #2f9ee0;
    border-color: #2f9ee0;
}}

QPushButton#checkMarkToggleCompact {{
    background-color: {SOL_BASE3};
    border: 1px solid {SOL_BASE1};
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
    border-color: {SOL_BASE0};
    background-color: #faf4e6;
}}

QPushButton#checkMarkToggleCompact:checked {{
    background-color: {SOL_BLUE};
    border-color: {SOL_BLUE};
    color: {SOL_BASE3};
}}

QPushButton#checkMarkToggleCompact:checked:hover {{
    background-color: #2f9ee0;
    border-color: #2f9ee0;
}}

QRadioButton {{
    spacing: 6px;
}}

QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {SOL_BASE1};
    border-radius: 7px;
    background: {SOL_BASE3};
}}

QRadioButton::indicator:checked {{
    background: {SOL_BLUE};
    border-color: {SOL_BLUE};
}}

QLabel#panelTitle {{
    font-weight: bold;
    color: {SOL_BASE01};
    padding: 4px 0;
}}

QLabel#historyItemLabel {{
    color: {SOL_BASE00};
    background: transparent;
}}

QLabel#statusOk {{
    padding: 0;
    margin: 0;
    color: {SOL_GREEN};
    font-size: {max(size_px - 2, 10)}px;
    font-weight: normal;
}}

QLabel#statusWarn {{
    padding: 0;
    margin: 0;
    color: {SOL_ORANGE};
    font-size: {max(size_px - 2, 10)}px;
    font-weight: normal;
}}

QLabel#statusError {{
    padding: 0;
    margin: 0;
    color: {SOL_RED};
    font-size: {max(size_px - 2, 10)}px;
    font-weight: normal;
}}

QLabel#statusPending {{
    padding: 0;
    margin: 0;
    color: {SOL_BASE01};
    font-size: {max(size_px - 2, 10)}px;
    font-weight: normal;
}}
'''
