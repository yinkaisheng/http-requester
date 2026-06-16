#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QClipboard, QFontMetrics
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QPushButton,
    QStackedWidget,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.http_models import HeaderItem

TABLE_HEADER_HEIGHT = 24
HEADER_ROW_HEIGHT = 26
TABLE_ROW_EXTRA_PADDING = 12
TABLE_FONT_DELTA_PX = 1


def format_header_line(key: str, value: str) -> str:
    return f'{key}: {value}'


def format_headers_text(rows: List[Tuple[str, str]]) -> str:
    lines = [format_header_line(k, v) for k, v in rows if k.strip()]
    return '\n'.join(lines)


def parse_headers_text(text: str) -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' not in line:
            continue
        key, _, value = line.partition(':')
        key = key.strip()
        value = value.strip()
        if key:
            rows.append((key, value))
    return rows


def _apply_header_table_font(table: QTableWidget) -> None:
    font = table.font()
    pixel_size = font.pixelSize()
    if pixel_size > 0:
        font.setPixelSize(pixel_size + TABLE_FONT_DELTA_PX)
    else:
        font.setPointSize(font.pointSize() + 1)
    table.setFont(font)
    table.horizontalHeader().setFont(font)


def _table_row_height(table: QTableWidget, editable: bool = False) -> int:
    metrics = QFontMetrics(table.font())
    base = metrics.height() + TABLE_ROW_EXTRA_PADDING
    if editable:
        return max(base, 30)
    return max(base, HEADER_ROW_HEIGHT)


def _set_compact_table_header(table: QTableWidget, editable: bool = False) -> None:
    _apply_header_table_font(table)
    h_header = table.horizontalHeader()
    h_header.setFixedHeight(TABLE_HEADER_HEIGHT)
    row_height = _table_row_height(table, editable)
    v_header = table.verticalHeader()
    v_header.setDefaultSectionSize(row_height)
    v_header.setMinimumSectionSize(row_height)
    v_header.setVisible(False)


def _read_table_rows(table: QTableWidget, key_col: int, value_col: int) -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = []
    for row in range(table.rowCount()):
        key_item = table.item(row, key_col)
        value_item = table.item(row, value_col)
        key = key_item.text().strip() if key_item else ''
        value = value_item.text() if value_item else ''
        if key:
            rows.append((key, value))
    return rows


def _copy_to_clipboard(text: str) -> None:
    clipboard = QApplication.clipboard()
    clipboard.setText(text, QClipboard.Clipboard)


def attach_header_table_menu(
    table: QTableWidget,
    key_col: int = 0,
    value_col: int = 1,
    paste_callback: Optional[Callable[[List[Tuple[str, str]]], None]] = None,
) -> None:
    table.setContextMenuPolicy(Qt.CustomContextMenu)

    def _on_context_menu(pos) -> None:
        row = table.rowAt(pos.y())
        menu = QMenu(table)

        copy_action = menu.addAction('Copy')
        copy_all_action = menu.addAction('Copy All')
        paste_action = None
        if paste_callback is not None:
            paste_action = menu.addAction('Paste')

        action = menu.exec_(table.viewport().mapToGlobal(pos))
        if action is None:
            return

        if action == copy_action:
            if row < 0:
                return
            key_item = table.item(row, key_col)
            value_item = table.item(row, value_col)
            key = key_item.text().strip() if key_item else ''
            value = value_item.text() if value_item else ''
            if key:
                _copy_to_clipboard(format_header_line(key, value))
        elif action == copy_all_action:
            text = format_headers_text(_read_table_rows(table, key_col, value_col))
            if text:
                _copy_to_clipboard(text)
        elif paste_action is not None and action == paste_action:
            clipboard = QApplication.clipboard()
            parsed = parse_headers_text(clipboard.text())
            if parsed:
                paste_callback(parsed)

    table.customContextMenuRequested.connect(_on_context_menu)


class TableEditDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setFrame(False)
        editor.setObjectName('tableCellEditor')
        return editor

    def updateEditorGeometry(self, editor, option, index):
        rect = option.rect
        editor.setGeometry(rect.adjusted(2, 2, -2, -2))


def fill_key_value_table(table: QTableWidget, headers: Dict[str, str]) -> None:
    items = list(headers.items())
    table.clearContents()
    table.setRowCount(len(items))
    for row, (key, value) in enumerate(items):
        key_item = QTableWidgetItem(str(key))
        value_item = QTableWidgetItem(str(value))
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        key_item.setFlags(flags)
        value_item.setFlags(flags)
        table.setItem(row, 0, key_item)
        table.setItem(row, 1, value_item)


class CheckMarkToggle(QPushButton):
    CHECK_MARK = '✓'

    def __init__(self, checked: bool = True, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName('checkMarkToggle')
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(18, 18)
        self.setFocusPolicy(Qt.NoFocus)
        self._update_display()
        self.toggled.connect(self._update_display)

    def _update_display(self) -> None:
        self.setText(self.CHECK_MARK if self.isChecked() else '')


class RawHeadersEditor(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Enable', 'Header', 'Value'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        _set_compact_table_header(self.table, editable=True)
        self.table.setItemDelegateForColumn(1, TableEditDelegate(self.table))
        self.table.setItemDelegateForColumn(2, TableEditDelegate(self.table))
        attach_header_table_menu(
            self.table,
            key_col=1,
            value_col=2,
            paste_callback=self._paste_headers,
        )
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 2, 0, 0)
        btn_layout.setSpacing(6)
        self.add_btn = QPushButton('+ Add')
        self.remove_btn = QPushButton('- Remove')
        self.add_btn.setObjectName('compactButton')
        self.remove_btn.setObjectName('compactButton')
        self.add_btn.clicked.connect(self._add_row)
        self.remove_btn.clicked.connect(self._remove_selected_rows)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._add_row()

    def _add_row(self, item: Optional[HeaderItem] = None) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setRowHeight(row, _table_row_height(self.table, editable=True))

        toggle = CheckMarkToggle(item.enabled if item else True)
        toggle_widget = QWidget()
        toggle_layout = QHBoxLayout(toggle_widget)
        toggle_layout.addWidget(toggle)
        toggle_layout.setAlignment(Qt.AlignCenter)
        toggle_layout.setContentsMargins(0, 3, 0, 3)
        self.table.setCellWidget(row, 0, toggle_widget)

        key_item = QTableWidgetItem(item.key if item else '')
        value_item = QTableWidgetItem(item.value if item else '')
        self.table.setItem(row, 1, key_item)
        self.table.setItem(row, 2, value_item)

    def _find_empty_row(self) -> Optional[int]:
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 1)
            value_item = self.table.item(row, 2)
            key = key_item.text().strip() if key_item else ''
            value = value_item.text().strip() if value_item else ''
            if not key and not value:
                return row
        return None

    def _paste_headers(self, parsed: List[Tuple[str, str]]) -> None:
        key_to_row: Dict[str, int] = {}
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 1)
            if key_item and key_item.text().strip():
                key_to_row[key_item.text().strip().lower()] = row

        for key, value in parsed:
            lower_key = key.lower()
            if lower_key in key_to_row:
                row = key_to_row[lower_key]
                self.table.item(row, 1).setText(key)
                self.table.item(row, 2).setText(value)
            else:
                empty_row = self._find_empty_row()
                if empty_row is None:
                    self._add_row(HeaderItem(key=key, value=value, enabled=True))
                    key_to_row[lower_key] = self.table.rowCount() - 1
                else:
                    self.table.item(empty_row, 1).setText(key)
                    self.table.item(empty_row, 2).setText(value)
                    toggle = self._get_toggle(empty_row)
                    if toggle:
                        toggle.setChecked(True)
                    key_to_row[lower_key] = empty_row

    def _remove_selected_rows(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            row = self.table.currentRow()
            if row >= 0:
                rows = [row]
        for row in rows:
            self.table.removeRow(row)
        if self.table.rowCount() == 0:
            self._add_row()

    def _get_toggle(self, row: int) -> Optional[CheckMarkToggle]:
        widget = self.table.cellWidget(row, 0)
        if widget:
            return widget.findChild(CheckMarkToggle)
        return None

    def get_headers(self) -> List[HeaderItem]:
        headers: List[HeaderItem] = []
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 1)
            value_item = self.table.item(row, 2)
            toggle = self._get_toggle(row)
            key = key_item.text().strip() if key_item else ''
            value = value_item.text() if value_item else ''
            enabled = toggle.isChecked() if toggle else True
            if key or value:
                headers.append(HeaderItem(key=key, value=value, enabled=enabled))
        return headers

    def set_headers(self, headers: List[HeaderItem]) -> None:
        self.table.setRowCount(0)
        if headers:
            for item in headers:
                self._add_row(item)
        else:
            self._add_row()


class SentHeadersView(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['Header', 'Value'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        _set_compact_table_header(self.table)
        attach_header_table_menu(self.table, key_col=0, value_col=1)
        layout.addWidget(self.table)

    def set_headers(self, headers: Dict[str, str]) -> None:
        fill_key_value_table(self.table, headers)


class RequestHeadersPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._sent_headers: Dict[str, str] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header_row = QWidget()
        header_row.setFixedHeight(HEADER_ROW_HEIGHT)
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        self.mode_group = QButtonGroup(self)
        self.raw_btn = QPushButton('Request Headers User')
        self.sent_btn = QPushButton('Request Headers Sent')
        for btn in (self.raw_btn, self.sent_btn):
            btn.setObjectName('headerModeButton')
            btn.setCheckable(True)
            btn.setFlat(True)
            self.mode_group.addButton(btn)
        self.raw_btn.setChecked(True)
        self.raw_btn.clicked.connect(lambda: self._switch_mode('raw'))
        self.sent_btn.clicked.connect(lambda: self._switch_mode('sent'))

        header_layout.addWidget(self.raw_btn)
        header_layout.addWidget(self.sent_btn)
        header_layout.addStretch()
        layout.addWidget(header_row)

        self.stack = QStackedWidget()
        self.raw_editor = RawHeadersEditor()
        self.sent_view = SentHeadersView()
        self.stack.addWidget(self.raw_editor)
        self.stack.addWidget(self.sent_view)
        layout.addWidget(self.stack, 1)

    def _switch_mode(self, mode: str) -> None:
        if mode == 'sent':
            self.stack.setCurrentWidget(self.sent_view)
            self.sent_btn.setChecked(True)
        else:
            self.stack.setCurrentWidget(self.raw_editor)
            self.raw_btn.setChecked(True)

    def show_raw_mode(self) -> None:
        self._switch_mode('raw')

    def show_sent_mode(self) -> None:
        self._switch_mode('sent')

    def get_headers(self) -> List[HeaderItem]:
        return self.raw_editor.get_headers()

    def set_raw_headers(self, headers: List[HeaderItem]) -> None:
        self.raw_editor.set_headers(headers)

    def set_sent_headers(self, headers: Dict[str, str]) -> None:
        self._sent_headers = dict(headers)
        self.sent_view.set_headers(self._sent_headers)

    def get_sent_headers(self) -> Dict[str, str]:
        return dict(self._sent_headers)


# Backward-compatible alias
HeadersEditor = RequestHeadersPanel
