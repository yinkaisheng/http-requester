#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal, QSize, QEvent
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from models.http_models import HistoryRecord
from storage.history_store import HistoryStore

DELETE_BUTTON_WIDTH = 28
ITEM_HORIZONTAL_MARGIN = 16


class HistoryItemWidget(QWidget):
    clicked = pyqtSignal()
    delete_clicked = pyqtSignal()

    def __init__(self, full_text: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._full_text = full_text

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(4)

        self.label = QLabel(full_text)
        self.label.setObjectName('historyItemLabel')
        self.label.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.label, 1)

        self.delete_btn = QPushButton('×')
        self.delete_btn.setObjectName('historyDeleteButton')
        self.delete_btn.setFixedSize(DELETE_BUTTON_WIDTH, DELETE_BUTTON_WIDTH)
        self.delete_btn.setToolTip('Delete')
        self.delete_btn.clicked.connect(self.delete_clicked.emit)
        layout.addWidget(self.delete_btn)

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self._apply_elision()

    def full_text(self) -> str:
        return self._full_text

    def _apply_elision(self) -> None:
        available = self.width() - DELETE_BUTTON_WIDTH - ITEM_HORIZONTAL_MARGIN
        if available <= 0:
            self.label.setText(self._full_text)
            return
        metrics = QFontMetrics(self.label.font())
        if metrics.horizontalAdvance(self._full_text) <= available:
            self.label.setText(self._full_text)
        else:
            self.label.setText(metrics.elidedText(self._full_text, Qt.ElideRight, available))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_elision()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.pos())
            if child is not self.delete_btn:
                self.clicked.emit()
        super().mouseReleaseEvent(event)


class HistoryPanel(QWidget):
    record_selected = pyqtSignal(str)
    record_deleted = pyqtSignal(str)
    records_changed = pyqtSignal()

    def __init__(self, history_store: HistoryStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.history_store = history_store
        self._records: List[HistoryRecord] = []
        self._item_widgets: Dict[str, HistoryItemWidget] = {}
        self._init_ui()
        self.reload()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel('History')
        title.setObjectName('panelTitle')
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.setSpacing(0)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.viewport().installEventFilter(self)
        layout.addWidget(self.list_widget)

    def eventFilter(self, obj, event) -> bool:
        if obj is self.list_widget.viewport() and event.type() == QEvent.Resize:
            self._refresh_item_elision()
        return super().eventFilter(obj, event)

    def reload(self) -> None:
        self._records = self.history_store.load()
        self.list_widget.clear()
        self._item_widgets.clear()
        for record in self._records:
            self._add_record_item(record)

    def upsert_record(self, record: HistoryRecord) -> None:
        found = False
        for i, existing in enumerate(self._records):
            if existing.id == record.id:
                self._records[i] = record
                found = True
                break
        if not found:
            self._records.insert(0, record)
        self._records.sort(key=lambda r: r.updated_at, reverse=True)
        self.reload()

    def _add_record_item(self, record: HistoryRecord) -> None:
        item = QListWidgetItem()
        item.setData(Qt.UserRole, record.id)
        item.setSizeHint(QSize(0, 36))

        widget = HistoryItemWidget(record.list_text())
        widget.clicked.connect(lambda rid=record.id: self.record_selected.emit(rid))
        widget.delete_clicked.connect(lambda rid=record.id: self._delete_record(rid, confirm=False))

        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)
        self._item_widgets[record.id] = widget

    def _refresh_item_elision(self) -> None:
        for widget in self._item_widgets.values():
            widget._apply_elision()

    def _show_context_menu(self, pos) -> None:
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        record_id = item.data(Qt.UserRole)
        if not record_id:
            return

        menu = QMenu(self)
        rename_action = menu.addAction('Rename')
        delete_action = menu.addAction('Delete')
        action = menu.exec_(self.list_widget.mapToGlobal(pos))

        if action == rename_action:
            self._rename_record(record_id)
        elif action == delete_action:
            self._delete_record(record_id, confirm=True)

    def _rename_record(self, record_id: str) -> None:
        record = self.history_store.get(record_id)
        if not record:
            return
        new_name, ok = QInputDialog.getText(
            self, 'Rename', 'Request name:', text=record.name or record.display_name()
        )
        if ok and new_name.strip():
            updated = self.history_store.rename(record_id, new_name.strip())
            if updated:
                self.reload()
                self.records_changed.emit()

    def _delete_record(self, record_id: str, confirm: bool = False) -> None:
        if confirm:
            from PyQt5.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                'Confirm Delete',
                'Are you sure you want to delete this history record?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        if self.history_store.delete(record_id):
            self._records = [r for r in self._records if r.id != record_id]
            self._item_widgets.pop(record_id, None)
            self.reload()
            self.record_deleted.emit(record_id)
            self.records_changed.emit()

    def get_record(self, record_id: str) -> Optional[HistoryRecord]:
        return self.history_store.get(record_id)
