#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
from typing import Callable, Dict, List, Optional, Tuple

from PyQt5.QtCore import QPointF, QPoint, Qt, QEvent, QObject
from PyQt5.QtGui import QClipboard, QFontMetrics, QKeyEvent, QPaintEvent, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QButtonGroup,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.http_models import HeaderItem, HttpRequest, is_valid_header_name
from services.curl_import import parse_curl_command
from services.powershell_import import parse_powershell_command
from ui.dialogs import prompt_basic_auth, prompt_bearer_token
from ui.theme import check_mark_color, table_font_size_px

TABLE_HEADER_HEIGHT = 22
SECTION_HEADER_LAYOUT_MARGIN_V = 2
TABLE_ROW_EXTRA_PADDING = 12
HEADER_TABLE_ROW_EXTRA_PADDING = 6
HEADER_TABLE_EDITABLE_MIN_HEIGHT = 24
TOGGLE_CELL_MARGIN_V = 1
HEADER_TABLE_TOGGLE_SIZE = 16

COPY_CURL_MENU_TEXT = 'Copy as Curl Command'
COPY_POWERSHELL_MENU_TEXT = 'Copy as PowerShell Command'
COPY_SELECTED_HEADERS_MENU_TEXT = 'Copy Selected Headers (Ctrl+C)'
PASTE_HEADERS_MENU_TEXT = 'Paste Headers (Ctrl+V)'
PASTE_CURL_MENU_TEXT = 'Paste from Curl Command'
PASTE_POWERSHELL_MENU_TEXT = 'Paste from PowerShell Command'
DELETE_SELECTED_HEADERS_MENU_TEXT = 'Delete Selected Headers'
BASIC_AUTH_MENU_TEXT = 'Basic Auth...'
BEARER_TOKEN_MENU_TEXT = 'Bearer Token...'


def configure_section_header_layout(layout: QHBoxLayout) -> None:
    layout.setContentsMargins(0, SECTION_HEADER_LAYOUT_MARGIN_V, 0, SECTION_HEADER_LAYOUT_MARGIN_V)
    layout.setSpacing(8)
    layout.setAlignment(Qt.AlignVCenter)


def add_section_header_widget(layout: QHBoxLayout, widget: QWidget) -> None:
    layout.addWidget(widget, 0, Qt.AlignVCenter)


def _compact_action_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName('compactButton')
    btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    return btn


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
        if key and is_valid_header_name(key):
            rows.append((key, value))
    return rows


def _apply_header_table_font(table: QTableWidget, *, header_table: bool = False) -> None:
    font = table.font()
    font.setPixelSize(table_font_size_px(header_table=header_table))
    table.setFont(font)
    table.horizontalHeader().setFont(font)


def _table_row_height(table: QTableWidget, editable: bool = False, *, header_table: bool = False) -> int:
    metrics = QFontMetrics(table.font())
    extra_padding = HEADER_TABLE_ROW_EXTRA_PADDING if header_table else TABLE_ROW_EXTRA_PADDING
    base = metrics.height() + extra_padding
    if editable:
        editable_min = HEADER_TABLE_EDITABLE_MIN_HEIGHT if header_table else 30
        return max(base, editable_min)
    return base


def _set_compact_table_header(table: QTableWidget, editable: bool = False, *, header_table: bool = False) -> None:
    _apply_header_table_font(table, header_table=header_table)
    h_header = table.horizontalHeader()
    h_header.setFixedHeight(TABLE_HEADER_HEIGHT)
    row_height = _table_row_height(table, editable, header_table=header_table)
    v_header = table.verticalHeader()
    v_header.setDefaultSectionSize(row_height)
    v_header.setMinimumSectionSize(row_height)
    v_header.setVisible(False)
    if header_table:
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)


def _selected_rows(table: QTableWidget) -> List[int]:
    return sorted({index.row() for index in table.selectedIndexes()})


def _read_table_rows_for_rows(
    table: QTableWidget,
    key_col: int,
    value_col: int,
    rows: List[int],
) -> List[Tuple[str, str]]:
    result: List[Tuple[str, str]] = []
    for row in rows:
        key_item = table.item(row, key_col)
        value_item = table.item(row, value_col)
        key = key_item.text().strip() if key_item else ''
        value = value_item.text() if value_item else ''
        if key:
            result.append((key, value))
    return result


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


def _show_paste_error(parent: QWidget, message: str) -> None:
    QMessageBox.information(parent, 'Paste failed', message)


class HeaderTableInteraction(QObject):
    def __init__(
        self,
        table: QTableWidget,
        *,
        key_col: int = 0,
        value_col: int = 1,
        paste_callback: Optional[Callable[[List[Tuple[str, str]]], None]] = None,
        paste_request_callback: Optional[Callable[[HttpRequest], None]] = None,
        curl_callback: Optional[Callable[[], None]] = None,
        powershell_callback: Optional[Callable[[], None]] = None,
        delete_rows_callback: Optional[Callable[[List[int]], None]] = None,
        basic_auth_callback: Optional[Callable[[], None]] = None,
        bearer_auth_callback: Optional[Callable[[], None]] = None,
    ):
        super().__init__(table)
        self._table = table
        self._viewport = table.viewport()
        self._key_col = key_col
        self._value_col = value_col
        self._paste_callback = paste_callback
        self._paste_request_callback = paste_request_callback
        self._curl_callback = curl_callback
        self._powershell_callback = powershell_callback
        self._delete_rows_callback = delete_rows_callback
        self._basic_auth_callback = basic_auth_callback
        self._bearer_auth_callback = bearer_auth_callback

        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self._on_context_menu)
        table.installEventFilter(self)
        self._viewport.installEventFilter(self)
        table.destroyed.connect(self._on_table_destroyed)

    def _on_table_destroyed(self, _obj: Optional[QObject] = None) -> None:
        self._detach_filters()
        self._table = None
        self._viewport = None

    def _detach_filters(self) -> None:
        table = self._table
        viewport = self._viewport
        if table is not None:
            try:
                table.removeEventFilter(self)
            except RuntimeError:
                pass
        if viewport is not None:
            try:
                viewport.removeEventFilter(self)
            except RuntimeError:
                pass

    def _is_active(self) -> bool:
        table = self._table
        if table is None:
            return False
        try:
            table.objectName()
        except RuntimeError:
            self._on_table_destroyed()
            return False
        return True

    def eventFilter(self, obj, event) -> bool:
        if not self._is_active():
            return False

        table = self._table
        viewport = self._viewport
        if viewport is not None and obj is viewport and event.type() == QEvent.MouseButtonPress:
            mouse_event = event
            try:
                if mouse_event.button() == Qt.LeftButton and table.rowAt(mouse_event.pos().y()) < 0:
                    table.clearSelection()
            except RuntimeError:
                self._on_table_destroyed()
            return False

        if table is None or obj is not table or event.type() != QEvent.KeyPress:
            return super().eventFilter(obj, event)

        key_event = event
        if not isinstance(key_event, QKeyEvent):
            return super().eventFilter(obj, event)
        try:
            if table.state() == QAbstractItemView.EditingState:
                return super().eventFilter(obj, event)

            if key_event.key() == Qt.Key_A and key_event.modifiers() & Qt.ControlModifier:
                table.selectAll()
                return True
            if key_event.key() == Qt.Key_C and key_event.modifiers() & Qt.ControlModifier:
                if self._copy_selected():
                    return True
            if (
                key_event.key() == Qt.Key_V
                and key_event.modifiers() & Qt.ControlModifier
                and self._paste_callback is not None
            ):
                if self._paste_headers():
                    return True
            if key_event.key() == Qt.Key_Delete and self._delete_rows_callback is not None:
                rows = _selected_rows(table)
                if rows:
                    self._delete_rows_callback(rows)
                    return True
        except RuntimeError:
            self._on_table_destroyed()
            return False
        return super().eventFilter(obj, event)

    def _copy_selected(self) -> bool:
        if not self._is_active():
            return False
        table = self._table
        try:
            if table.state() == QAbstractItemView.EditingState:
                return False
            rows = _selected_rows(table)
            if not rows:
                return False
            text = format_headers_text(
                _read_table_rows_for_rows(table, self._key_col, self._value_col, rows)
            )
            if text:
                _copy_to_clipboard(text)
                return True
        except RuntimeError:
            self._on_table_destroyed()
        return False

    def _paste_headers(self) -> bool:
        if not self._is_active() or self._paste_callback is None:
            return False
        table = self._table
        try:
            if table.state() == QAbstractItemView.EditingState:
                return False
            parsed = parse_headers_text(QApplication.clipboard().text())
            if parsed:
                self._paste_callback(parsed)
                return True
        except RuntimeError:
            self._on_table_destroyed()
        return False

    def _on_context_menu(self, pos: 'QPoint') -> None:
        if not self._is_active():
            return
        table = self._table
        try:
            selected_rows = _selected_rows(table)
        except RuntimeError:
            self._on_table_destroyed()
            return
        menu = QMenu(table)

        copy_action = menu.addAction(COPY_SELECTED_HEADERS_MENU_TEXT)
        copy_action.setEnabled(bool(selected_rows))
        copy_all_action = menu.addAction('Copy All Headers')
        delete_action = None
        if self._delete_rows_callback is not None:
            delete_action = menu.addAction(DELETE_SELECTED_HEADERS_MENU_TEXT)
            delete_action.setEnabled(bool(selected_rows))
        basic_auth_action = None
        bearer_auth_action = None
        if self._basic_auth_callback is not None or self._bearer_auth_callback is not None:
            menu.addSeparator()
        if self._basic_auth_callback is not None:
            basic_auth_action = menu.addAction(BASIC_AUTH_MENU_TEXT)
        if self._bearer_auth_callback is not None:
            bearer_auth_action = menu.addAction(BEARER_TOKEN_MENU_TEXT)
        paste_action = None
        paste_curl_action = None
        paste_powershell_action = None
        if self._paste_callback is not None or self._paste_request_callback is not None:
            menu.addSeparator()
        if self._paste_callback is not None:
            paste_action = menu.addAction(PASTE_HEADERS_MENU_TEXT)
        if self._paste_request_callback is not None:
            paste_curl_action = menu.addAction(PASTE_CURL_MENU_TEXT)
            paste_powershell_action = menu.addAction(PASTE_POWERSHELL_MENU_TEXT)
        curl_action = None
        powershell_action = None
        if self._curl_callback is not None or self._powershell_callback is not None:
            menu.addSeparator()
        if self._curl_callback is not None:
            curl_action = menu.addAction(COPY_CURL_MENU_TEXT)
        if self._powershell_callback is not None:
            powershell_action = menu.addAction(COPY_POWERSHELL_MENU_TEXT)

        action = menu.exec_(table.viewport().mapToGlobal(pos))
        if action is None:
            return

        if action == copy_action:
            self._copy_selected()
        elif delete_action is not None and action == delete_action:
            if selected_rows:
                self._delete_rows_callback(selected_rows)
        elif basic_auth_action is not None and action == basic_auth_action:
            self._basic_auth_callback()
        elif bearer_auth_action is not None and action == bearer_auth_action:
            self._bearer_auth_callback()
        elif action == copy_all_action:
            text = format_headers_text(_read_table_rows(table, self._key_col, self._value_col))
            if text:
                _copy_to_clipboard(text)
        elif paste_action is not None and action == paste_action:
            self._paste_headers()
        elif paste_curl_action is not None and action == paste_curl_action:
            req = parse_curl_command(QApplication.clipboard().text())
            if req is not None:
                self._paste_request_callback(req)
            else:
                _show_paste_error(table, 'Could not parse a curl command from the clipboard.')
        elif paste_powershell_action is not None and action == paste_powershell_action:
            req = parse_powershell_command(QApplication.clipboard().text())
            if req is not None:
                self._paste_request_callback(req)
            else:
                _show_paste_error(table, 'Could not parse a PowerShell command from the clipboard.')
        elif curl_action is not None and action == curl_action:
            self._curl_callback()
        elif powershell_action is not None and action == powershell_action:
            self._powershell_callback()


def attach_header_table_menu(
    table: QTableWidget,
    key_col: int = 0,
    value_col: int = 1,
    paste_callback: Optional[Callable[[List[Tuple[str, str]]], None]] = None,
    paste_request_callback: Optional[Callable[[HttpRequest], None]] = None,
    curl_callback: Optional[Callable[[], None]] = None,
    powershell_callback: Optional[Callable[[], None]] = None,
    delete_rows_callback: Optional[Callable[[List[int]], None]] = None,
    basic_auth_callback: Optional[Callable[[], None]] = None,
    bearer_auth_callback: Optional[Callable[[], None]] = None,
) -> HeaderTableInteraction:
    interaction = HeaderTableInteraction(
        table,
        key_col=key_col,
        value_col=value_col,
        paste_callback=paste_callback,
        paste_request_callback=paste_request_callback,
        curl_callback=curl_callback,
        powershell_callback=powershell_callback,
        delete_rows_callback=delete_rows_callback,
        basic_auth_callback=basic_auth_callback,
        bearer_auth_callback=bearer_auth_callback,
    )
    table._header_table_interaction = interaction
    return interaction


class TableEditDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setFrame(False)
        editor.setObjectName('tableCellEditor')
        return editor

    def updateEditorGeometry(self, editor, option, index):
        rect = option.rect
        editor.setGeometry(rect.adjusted(2, 2, -2, -2))


class HeaderTableEditDelegate(TableEditDelegate):
    def updateEditorGeometry(self, editor, option, index):
        rect = option.rect
        editor.setGeometry(rect.adjusted(2, 1, -2, -1))


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
    def __init__(
        self,
        checked: bool = True,
        parent: Optional[QWidget] = None,
        *,
        size: int = 18,
    ):
        super().__init__(parent)
        object_name = 'checkMarkToggleCompact' if size <= 16 else 'checkMarkToggle'
        self.setObjectName(object_name)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(size, size)
        self.setFocusPolicy(Qt.NoFocus)
        self.setText('')
        self.toggled.connect(self.update)

    def paintEvent(self, event: 'QPaintEvent') -> None:
        super().paintEvent(event)
        if not self.isChecked():
            return

        side = min(self.width(), self.height())
        margin = side * 0.2
        x0 = margin
        y0 = side * 0.54
        x1 = side * 0.4
        y1 = side * 0.74
        x2 = side - margin
        y2 = side * 0.3

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            pen = QPen(check_mark_color())
            pen.setWidthF(max(1.6, side * 0.12))
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(QPointF(x0, y0), QPointF(x1, y1))
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        finally:
            painter.end()


class RawHeadersEditor(QWidget):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        curl_copy_callback: Optional[Callable[[], None]] = None,
        powershell_copy_callback: Optional[Callable[[], None]] = None,
        paste_request_callback: Optional[Callable[[HttpRequest], None]] = None,
    ):
        super().__init__(parent)
        self._curl_copy_callback = curl_copy_callback
        self._powershell_copy_callback = powershell_copy_callback
        self._paste_request_callback = paste_request_callback
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 3)
        self.table.setObjectName('headerTable')
        self.table.setHorizontalHeaderLabels(['Enable', 'Header', 'Value'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        _set_compact_table_header(self.table, editable=True, header_table=True)
        self.table.setItemDelegateForColumn(1, HeaderTableEditDelegate(self.table))
        self.table.setItemDelegateForColumn(2, HeaderTableEditDelegate(self.table))
        attach_header_table_menu(
            self.table,
            key_col=1,
            value_col=2,
            paste_callback=self._paste_headers,
            paste_request_callback=self._paste_request_callback,
            curl_callback=self._curl_copy_callback,
            powershell_callback=self._powershell_copy_callback,
            delete_rows_callback=self._delete_rows,
            basic_auth_callback=self._apply_basic_auth,
            bearer_auth_callback=self._apply_bearer_auth,
        )
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 2, 0, 0)
        btn_layout.setSpacing(6)
        self.add_btn = _compact_action_button('+ Add')
        self.remove_btn = _compact_action_button('- Remove')
        self.add_btn.clicked.connect(self._add_row)
        self.remove_btn.clicked.connect(self._remove_selected_rows)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addStretch()
        layout.addWidget(self.table, 1)
        layout.addLayout(btn_layout, 0)

        self._add_row()

    def _add_row(self, item: Optional[HeaderItem] = None) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setRowHeight(row, _table_row_height(self.table, editable=True, header_table=True))

        toggle = CheckMarkToggle(
            item.enabled if item else True,
            size=HEADER_TABLE_TOGGLE_SIZE,
        )
        toggle_widget = QWidget()
        toggle_layout = QHBoxLayout(toggle_widget)
        toggle_layout.addWidget(toggle)
        toggle_layout.setAlignment(Qt.AlignCenter)
        toggle_layout.setContentsMargins(0, TOGGLE_CELL_MARGIN_V, 0, TOGGLE_CELL_MARGIN_V)
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

    def _apply_basic_auth(self) -> None:
        creds = prompt_basic_auth(self)
        if creds is None:
            return
        username, password = creds
        encoded = base64.b64encode(f'{username}:{password}'.encode()).decode('ascii')
        self._paste_headers([('Authorization', f'Basic {encoded}')])

    def _apply_bearer_auth(self) -> None:
        token = prompt_bearer_token(self)
        if token is None:
            return
        self._paste_headers([('Authorization', f'Bearer {token}')])

    def _delete_rows(self, rows: List[int]) -> None:
        for row in sorted(rows, reverse=True):
            if 0 <= row < self.table.rowCount():
                self.table.removeRow(row)
        if self.table.rowCount() == 0:
            self._add_row()

    def _remove_selected_rows(self) -> None:
        rows = _selected_rows(self.table)
        if not rows:
            row = self.table.currentRow()
            if row >= 0:
                rows = [row]
        self._delete_rows(rows)

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
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        curl_copy_callback: Optional[Callable[[], None]] = None,
        powershell_copy_callback: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 2)
        self.table.setObjectName('headerTable')
        self.table.setHorizontalHeaderLabels(['Header', 'Value'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        _set_compact_table_header(self.table, header_table=True)
        attach_header_table_menu(
            self.table,
            key_col=0,
            value_col=1,
            curl_callback=curl_copy_callback,
            powershell_callback=powershell_copy_callback,
        )
        layout.addWidget(self.table)

    def set_headers(self, headers: Dict[str, str]) -> None:
        fill_key_value_table(self.table, headers)


class RequestHeadersPanel(QWidget):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        curl_copy_callback: Optional[Callable[[], None]] = None,
        powershell_copy_callback: Optional[Callable[[], None]] = None,
        paste_request_callback: Optional[Callable[[HttpRequest], None]] = None,
    ):
        super().__init__(parent)
        self._sent_headers: Dict[str, str] = {}
        self._curl_copy_callback = curl_copy_callback
        self._powershell_copy_callback = powershell_copy_callback
        self._paste_request_callback = paste_request_callback
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header_row = QWidget()
        header_layout = QHBoxLayout(header_row)
        configure_section_header_layout(header_layout)

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

        header_layout.addWidget(self.raw_btn, 0, Qt.AlignVCenter)
        header_layout.addWidget(self.sent_btn, 0, Qt.AlignVCenter)
        header_layout.addStretch()
        layout.addWidget(header_row)

        self.stack = QStackedWidget()
        self.raw_editor = RawHeadersEditor(
            curl_copy_callback=self._curl_copy_callback,
            powershell_copy_callback=self._powershell_copy_callback,
            paste_request_callback=self._paste_request_callback,
        )
        self.sent_view = SentHeadersView(
            curl_copy_callback=self._curl_copy_callback,
            powershell_copy_callback=self._powershell_copy_callback,
        )
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
