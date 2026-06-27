#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""URL query parameter editor dialog."""
from __future__ import annotations

import urllib.parse
from typing import List, Optional, Tuple

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from i18n import tr
from ui.widgets import ArrowComboBox

_URL_PARAM_TYPE_IDS = ('query', 'number', 'bool')


def _is_valid_number_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    try:
        float(stripped)
        return True
    except ValueError:
        return False


def _infer_url_param_type(value: str) -> str:
    text = value.strip()
    if not text:
        return 'query'
    lowered = text.lower()
    if lowered in ('true', 'false'):
        return 'bool'
    if _is_valid_number_text(text):
        return 'number'
    return 'query'


def _row_for_type_combo(table: QTableWidget, combo: QComboBox) -> int:
    for row in range(table.rowCount()):
        if table.cellWidget(row, 1) is combo:
            return row
    return -1


def _collect_params(table: QTableWidget) -> List[Tuple[str, str]]:
    """Read all rows from the table and return (name, value) pairs."""
    result: List[Tuple[str, str]] = []
    for row in range(table.rowCount()):
        name_item = table.item(row, 0)
        name = name_item.text().strip() if name_item else ''
        if not name:
            continue
        type_combo = table.cellWidget(row, 1)
        type_id = type_combo.currentData() if isinstance(type_combo, QComboBox) else 'query'
        if not isinstance(type_id, str):
            type_id = 'query'
        if type_id == 'bool':
            value_combo = table.cellWidget(row, 2)
            if isinstance(value_combo, QComboBox):
                value = 'true' if value_combo.currentText() == tr('url_params.bool_true') else 'false'
            else:
                value = ''
        elif type_id == 'number':
            line_edit = table.cellWidget(row, 2)
            if isinstance(line_edit, QLineEdit):
                raw = line_edit.text().strip()
                value = raw if _is_valid_number_text(raw) else ''
            else:
                value_item = table.item(row, 2)
                raw = value_item.text().strip() if value_item else ''
                value = raw if _is_valid_number_text(raw) else ''
        else:
            value_item = table.item(row, 2)
            value = value_item.text().strip() if value_item else ''
        result.append((name, value))
    return result


def _focus_value_editor(table: QTableWidget, row: int, type_id: str) -> None:
    if type_id == 'bool':
        widget = table.cellWidget(row, 2)
        if isinstance(widget, QComboBox):
            widget.setFocus()
    elif type_id == 'number':
        widget = table.cellWidget(row, 2)
        if isinstance(widget, QLineEdit):
            widget.setFocus()
    else:
        item = table.item(row, 2)
        if item is not None:
            table.setFocus()
            table.setCurrentCell(row, 2)
            QTimer.singleShot(0, lambda: table.editItem(item))


def _update_value_editor(table: QTableWidget, row: int, type_id: str) -> None:
    """Swap the value cell: Bool→combo, Number→QLineEdit+validator, else→plain item."""
    if type_id == 'bool':
        table.removeCellWidget(row, 2)
        combo = ArrowComboBox()
        combo.addItems([tr('url_params.bool_true'), tr('url_params.bool_false')])
        item = table.item(row, 2)
        if item:
            text = item.text().strip()
            if text.lower() in ('true', 'false'):
                combo.setCurrentIndex(0 if text.lower() == 'true' else 1)
        table.setCellWidget(row, 2, combo)

    elif type_id == 'number':
        table.removeCellWidget(row, 2)
        line_edit = QLineEdit()
        number_validator = QDoubleValidator()
        number_validator.setNotation(QDoubleValidator.StandardNotation)
        line_edit.setValidator(number_validator)
        item = table.item(row, 2)
        if item:
            text = item.text().strip()
            if _is_valid_number_text(text):
                line_edit.setText(text)
        table.setCellWidget(row, 2, line_edit)

    else:
        table.removeCellWidget(row, 2)
        if table.item(row, 2) is None:
            table.setItem(row, 2, QTableWidgetItem(''))


def prompt_url_params(parent: QWidget, url_text: str, on_save) -> None:
    """Open a dialog to view and edit URL query parameters.

    Args:
        parent: Parent widget for the dialog.
        url_text: The full URL string to parse parameters from.
        on_save: Callable accepting the new URL string after Save.
    """
    params: List[List[str]] = []
    base_url = url_text
    fragment = ''
    query_string = ''

    # Properly separate base URL, query string, and fragment.
    # urllib.parse.urlsplit requires a scheme to parse netloc correctly,
    # but user-provided URLs may omit it — handle both cases with manual split.
    if '#' in url_text:
        url_text, _, fragment = url_text.partition('#')
    if '?' in url_text:
        base_url, _, query_string = url_text.partition('?')

    if query_string:
        for name, value in urllib.parse.parse_qsl(query_string, keep_blank_values=True):
            params.append([name, _infer_url_param_type(value), value])

    dialog = QDialog(parent)
    dialog.setWindowTitle(tr('url_params.title'))
    dialog.setMinimumWidth(680)
    dialog.setMinimumHeight(380)
    dialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    layout = QVBoxLayout(dialog)

    # ---------- table ----------
    table = QTableWidget(0, 3)
    table.setHorizontalHeaderLabels([
        tr('url_params.name'),
        tr('url_params.type'),
        tr('url_params.value'),
    ])
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
    table.setColumnWidth(1, 120)
    table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
    table.verticalHeader().setVisible(False)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    layout.addWidget(table, 1)

    # ---------- placeholder when empty ----------
    no_params_label = QLabel(tr('url_params.no_params'))
    no_params_label.setAlignment(Qt.AlignCenter)
    no_params_label.setStyleSheet('color: #888; font-size: 14px;')
    layout.addWidget(no_params_label)

    # ---------- button row ----------
    btn_layout = QHBoxLayout()
    add_btn = QPushButton(tr('url_params.add'))
    delete_btn = QPushButton(tr('url_params.remove'))
    btn_layout.addWidget(add_btn)
    btn_layout.addWidget(delete_btn)
    btn_layout.addStretch()
    save_btn = QPushButton(tr('dialog.save'))
    save_btn.setObjectName('primaryButton')
    close_btn = QPushButton(tr('dialog.close'))
    btn_layout.addWidget(save_btn)
    btn_layout.addWidget(close_btn)
    layout.addLayout(btn_layout)

    # ---------- helpers ----------
    def _save_params() -> None:
        pairs = _collect_params(table)
        if pairs:
            new_query = urllib.parse.urlencode(pairs)
            result = f'{base_url}?{new_query}'
        else:
            result = base_url
        if fragment:
            result += f'#{fragment}'
        on_save(result)
        dialog.accept()

    def on_type_changed(_index: int) -> None:
        combo = table.sender()
        if not isinstance(combo, QComboBox):
            return
        row = _row_for_type_combo(table, combo)
        type_id = combo.currentData()
        if row >= 0 and isinstance(type_id, str):
            _update_value_editor(table, row, type_id)
            _focus_value_editor(table, row, type_id)

    def setup_type_combo(row: int, initial_type: str) -> None:
        combo = ArrowComboBox()
        for type_id in _URL_PARAM_TYPE_IDS:
            combo.addItem(tr(f'url_params.type_{type_id}'), type_id)
        idx = combo.findData(initial_type)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.currentIndexChanged.connect(on_type_changed)
        table.setCellWidget(row, 1, combo)
        _update_value_editor(table, row, initial_type)

    def update_placeholder_visibility() -> None:
        has_rows = table.rowCount() > 0
        no_params_label.setVisible(not has_rows)
        table.setVisible(has_rows)

    def add_row(name: str = '', param_type: str = '', value: str = '') -> None:
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(name))
        table.setItem(row, 2, QTableWidgetItem(value))
        type_to_use = param_type if param_type in _URL_PARAM_TYPE_IDS else 'query'
        setup_type_combo(row, type_to_use)
        update_placeholder_visibility()
        # Auto-edit Name cell when adding a blank row via "+ Add" button
        if not name:
            table.setCurrentCell(row, 0)
            QTimer.singleShot(0, lambda r=row: table.editItem(table.item(r, 0)))

    def remove_selected() -> None:
        selected = sorted({index.row() for index in table.selectedIndexes()}, reverse=True)
        if not selected:
            return
        first = selected[-1]  # smallest index before removal
        for row in selected:
            table.removeRow(row)
        update_placeholder_visibility()
        # Select the row at the same position, or the last row
        count = table.rowCount()
        if count > 0:
            target = min(first, count - 1)
            table.selectRow(target)

    add_btn.clicked.connect(lambda: add_row())
    delete_btn.clicked.connect(remove_selected)
    save_btn.clicked.connect(_save_params)
    close_btn.clicked.connect(dialog.reject)

    # ---------- populate ----------
    for name, ptype, value in params:
        add_row(name, ptype, value)
    update_placeholder_visibility()

    dialog.exec_()
