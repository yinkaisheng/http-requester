#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.http_models import BodyType, FormField
from ui.headers_editor import HEADER_ROW_HEIGHT, TableEditDelegate, _compact_action_button, _set_compact_table_header, _table_row_height

FORM_CELL_MARGIN_V = 2
FORM_CELL_MARGIN_H = 4

_BODY_TYPE_TO_STACK_INDEX = {
    0: 0,  # Raw
    1: 0,  # JSON (shares text page)
    2: 1,  # Form Data
    3: 2,  # File Upload
}


class BodyEditor(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.type_group = QButtonGroup(self)
        self.radio_raw = QRadioButton('Raw')
        self.radio_json = QRadioButton('JSON')
        self.radio_form = QRadioButton('Form Data')
        self.radio_file = QRadioButton('File Upload')
        self.radio_raw.setChecked(True)
        for i, radio in enumerate([
            self.radio_raw, self.radio_json,
            self.radio_form, self.radio_file,
        ]):
            self.type_group.addButton(radio, i)

        layout.addWidget(self._build_header_row())

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self._init_text_page()
        self._init_form_page()
        self._init_file_page()

        self.type_group.buttonClicked.connect(self._on_type_changed)
        self._on_type_changed()

    def _build_header_row(self) -> QWidget:
        row = QWidget()
        row.setFixedHeight(HEADER_ROW_HEIGHT)
        header_layout = QHBoxLayout(row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        title = QLabel('Request Body')
        title.setObjectName('sectionTitle')
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header_layout.addWidget(title)
        for radio in (
            self.radio_raw, self.radio_json,
            self.radio_form, self.radio_file,
        ):
            header_layout.addWidget(radio)
        header_layout.addStretch()
        return row

    @staticmethod
    def section_header_height() -> int:
        return HEADER_ROW_HEIGHT

    def _init_text_page(self) -> None:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setObjectName('bodyTextEdit')
        self.text_edit.setPlaceholderText('Request body content')
        page_layout.addWidget(self.text_edit)
        self.stack.addWidget(page)

    def _init_form_page(self) -> None:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)

        self.form_table = QTableWidget(0, 4)
        self.form_table.setHorizontalHeaderLabels(['Key', 'Value', 'File', 'File Path'])
        self.form_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.form_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.form_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.form_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.form_table.verticalHeader().setVisible(False)
        _set_compact_table_header(self.form_table, editable=True)
        self.form_table.setItemDelegateForColumn(0, TableEditDelegate(self.form_table))
        self.form_table.setItemDelegateForColumn(1, TableEditDelegate(self.form_table))
        self.form_table.horizontalHeader().setMinimumSectionSize(48)
        page_layout.addWidget(self.form_table)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 2, 0, 0)
        btn_layout.setSpacing(6)
        add_btn = _compact_action_button('+ Add')
        remove_btn = _compact_action_button('- Remove')
        add_btn.clicked.connect(self._add_form_row)
        remove_btn.clicked.connect(self._remove_form_rows)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        page_layout.addLayout(btn_layout)

        self._add_form_row()
        self.stack.addWidget(page)

    def _init_file_page(self) -> None:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)

        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel('File:'))
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText('Select a file to upload')
        browse_btn = QPushButton('Select File')
        browse_btn.clicked.connect(self._browse_single_file)
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(browse_btn)
        page_layout.addLayout(file_layout)
        page_layout.addStretch()
        self.stack.addWidget(page)

    def _on_type_changed(self) -> None:
        btn_id = self.type_group.checkedId()
        self.stack.setCurrentIndex(_BODY_TYPE_TO_STACK_INDEX.get(btn_id, 0))

    def _form_row_height(self) -> int:
        return _table_row_height(self.form_table, editable=True)

    def _form_cell_widget_height(self) -> int:
        return self._form_row_height() - FORM_CELL_MARGIN_V * 2

    def _add_form_row(self, field: Optional[FormField] = None) -> None:
        row = self.form_table.rowCount()
        self.form_table.insertRow(row)
        row_height = self._form_row_height()
        cell_height = self._form_cell_widget_height() + 2
        self.form_table.setRowHeight(row, row_height)

        key_item = QTableWidgetItem(field.key if field else '')
        value_item = QTableWidgetItem(field.value if field else '')
        self.form_table.setItem(row, 0, key_item)
        self.form_table.setItem(row, 1, value_item)

        is_file_widget = QWidget()
        is_file_layout = QHBoxLayout(is_file_widget)
        is_file_layout.setContentsMargins(2, FORM_CELL_MARGIN_V, 2, FORM_CELL_MARGIN_V)
        is_file_btn = QPushButton('Yes' if (field and field.is_file) else 'No')
        is_file_btn.setObjectName('formCellButton')
        is_file_btn.setCheckable(True)
        is_file_btn.setChecked(field.is_file if field else False)
        is_file_btn.setFixedSize(32, cell_height)
        is_file_btn.toggled.connect(self._on_file_toggle_from_sender)
        is_file_layout.addWidget(is_file_btn, 0, Qt.AlignCenter)
        self.form_table.setCellWidget(row, 2, is_file_widget)

        path_widget = QWidget()
        path_layout = QHBoxLayout(path_widget)
        path_layout.setContentsMargins(
            FORM_CELL_MARGIN_H, FORM_CELL_MARGIN_V, FORM_CELL_MARGIN_H, FORM_CELL_MARGIN_V
        )
        path_layout.setSpacing(4)
        path_edit = QLineEdit(field.file_path if field else '')
        path_edit.setObjectName('formCellLineEdit')
        path_edit.setReadOnly(True)
        path_edit.setFixedHeight(cell_height)
        browse_btn = QPushButton('...')
        browse_btn.setObjectName('formCellButton')
        browse_btn.setFixedSize(32, cell_height)
        browse_btn.clicked.connect(self._browse_form_file_from_sender)
        path_layout.addWidget(path_edit, 1)
        path_layout.addWidget(browse_btn, 0, Qt.AlignCenter)
        self.form_table.setCellWidget(row, 3, path_widget)

        if field and field.is_file:
            value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)

    def _row_for_cell_widget(self, widget: QWidget) -> int:
        target = widget
        while target is not None and target is not self.form_table:
            for row in range(self.form_table.rowCount()):
                for col in (2, 3):
                    cell = self.form_table.cellWidget(row, col)
                    if cell is target:
                        return row
            target = target.parentWidget()
        return -1

    def _on_file_toggle_from_sender(self, checked: bool) -> None:
        sender = self.sender()
        if sender is None:
            return
        row = self._row_for_cell_widget(sender)
        if row >= 0:
            self._on_file_toggle(row, checked)

    def _browse_form_file_from_sender(self) -> None:
        sender = self.sender()
        if sender is None:
            return
        row = self._row_for_cell_widget(sender)
        if row >= 0:
            self._browse_form_file(row)

    def _on_file_toggle(self, row: int, is_file: bool) -> None:
        widget = self.form_table.cellWidget(row, 2)
        btn = widget.findChild(QPushButton)
        if btn:
            btn.setText('Yes' if is_file else 'No')
        value_item = self.form_table.item(row, 1)
        if value_item:
            if is_file:
                value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
                value_item.setText('')
            else:
                value_item.setFlags(value_item.flags() | Qt.ItemIsEditable)

    def _browse_form_file(self, row: int) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Select File')
        if not path:
            return
        path_widget = self.form_table.cellWidget(row, 3)
        path_edit = path_widget.findChild(QLineEdit)
        if path_edit:
            path_edit.setText(path)

    def _browse_single_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Select File')
        if path:
            self.file_path_edit.setText(path)

    def _remove_form_rows(self) -> None:
        rows = sorted({idx.row() for idx in self.form_table.selectedIndexes()}, reverse=True)
        if not rows:
            row = self.form_table.currentRow()
            if row >= 0:
                rows = [row]
        for row in rows:
            self.form_table.removeRow(row)
        if self.form_table.rowCount() == 0:
            self._add_form_row()

    def _get_form_path_edit(self, row: int) -> Optional[QLineEdit]:
        path_widget = self.form_table.cellWidget(row, 3)
        if path_widget:
            return path_widget.findChild(QLineEdit)
        return None

    def _get_form_is_file(self, row: int) -> bool:
        widget = self.form_table.cellWidget(row, 2)
        if widget:
            btn = widget.findChild(QPushButton)
            if btn:
                return btn.isChecked()
        return False

    def get_body_type(self) -> BodyType:
        mapping = {
            0: BodyType.RAW,
            1: BodyType.JSON,
            2: BodyType.FORM,
            3: BodyType.FILE,
        }
        return mapping.get(self.type_group.checkedId(), BodyType.RAW)

    def get_body_text(self) -> str:
        return self.text_edit.toPlainText()

    def get_form_fields(self) -> List[FormField]:
        fields: List[FormField] = []
        for row in range(self.form_table.rowCount()):
            key_item = self.form_table.item(row, 0)
            value_item = self.form_table.item(row, 1)
            key = key_item.text().strip() if key_item else ''
            value = value_item.text() if value_item else ''
            is_file = self._get_form_is_file(row)
            path_edit = self._get_form_path_edit(row)
            file_path = path_edit.text() if path_edit else ''
            if key or value or file_path:
                fields.append(FormField(key=key, value=value, is_file=is_file, file_path=file_path))
        return fields

    def get_file_path(self) -> str:
        return self.file_path_edit.text().strip()

    def set_body(
        self,
        body_type: BodyType,
        body_text: str = '',
        form_fields: Optional[List[FormField]] = None,
        file_path: str = '',
    ) -> None:
        radio_map = {
            BodyType.NONE: self.radio_raw,
            BodyType.RAW: self.radio_raw,
            BodyType.JSON: self.radio_json,
            BodyType.FORM: self.radio_form,
            BodyType.FILE: self.radio_file,
        }
        radio = radio_map.get(body_type, self.radio_raw)
        radio.setChecked(True)
        self._on_type_changed()

        self.text_edit.setPlainText(body_text)
        self.file_path_edit.setText(file_path)

        self.form_table.setRowCount(0)
        if form_fields:
            for field in form_fields:
                self._add_form_row(field)
        else:
            self._add_form_row()
