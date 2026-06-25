#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt5.QtCore import QObject, QPoint, Qt, pyqtSignal, QSize, QEvent
from PyQt5.QtGui import QFontMetrics, QMouseEvent, QResizeEvent
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from models.http_models import HistoryRecord
from storage.history_store import HistoryStore
from i18n import tr
from ui.dialog_i18n import ask_yes_no
from ui.dialogs import prompt_text

DELETE_BUTTON_WIDTH = 28
ITEM_HORIZONTAL_MARGIN = 16


class HistoryItemWidget(QWidget):
    clicked = pyqtSignal()
    delete_clicked = pyqtSignal()

    def __init__(
        self,
        full_text: str,
        tooltip: str = '',
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._full_text = full_text

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(4)

        self.label = QLabel(full_text)
        self.label.setObjectName('historyItemLabel')
        self.label.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.label, 1)

        self.delete_btn = QPushButton('×') # not x
        self.delete_btn.setObjectName('historyDeleteButton')
        self.delete_btn.setFixedSize(DELETE_BUTTON_WIDTH, DELETE_BUTTON_WIDTH)
        self.delete_btn.setToolTip(tr('history.delete_tooltip'))
        self.delete_btn.clicked.connect(self.delete_clicked.emit)
        layout.addWidget(self.delete_btn)

        self.setToolTip(tooltip)
        self.label.setToolTip(tooltip)

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

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_elision()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.pos())
            if child is not self.delete_btn:
                self.clicked.emit()
        super().mouseReleaseEvent(event)


class HistoryPanel(QWidget):
    record_selected = pyqtSignal(str)
    record_deleted = pyqtSignal(str)
    records_bulk_deleted = pyqtSignal(list)
    record_renamed = pyqtSignal(str, str)
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

        self._title_label = QLabel(tr('history.title'))
        self._title_label.setObjectName('panelTitle')

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.addWidget(self._title_label)
        title_layout.addStretch()

        self._filter_edit = QLineEdit()
        self._filter_edit.setObjectName('historyFilterEdit')
        self._filter_edit.setPlaceholderText(tr('history.filter_placeholder'))
        self._filter_edit.setClearButtonEnabled(False)
        self._filter_edit.textChanged.connect(self._filter_changed)
        title_layout.addWidget(self._filter_edit, 0, Qt.AlignVCenter)

        self._clear_filter_btn = QPushButton('×') # not x
        self._clear_filter_btn.setObjectName('historyClearFilterButton')
        self._clear_filter_btn.setMaximumWidth(36)
        self._clear_filter_btn.setToolTip(tr('history.clear_filter_tooltip'))
        self._clear_filter_btn.clicked.connect(self._clear_filter)
        title_layout.addWidget(self._clear_filter_btn, 0, Qt.AlignVCenter)

        layout.addLayout(title_layout)

        self.list_widget = QListWidget()
        self.list_widget.setSpacing(0)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.viewport().installEventFilter(self)
        layout.addWidget(self.list_widget)

    def retranslate_ui(self) -> None:
        self._title_label.setText(tr('history.title'))
        self._filter_edit.setPlaceholderText(tr('history.filter_placeholder'))
        self._clear_filter_btn.setToolTip(tr('history.clear_filter_tooltip'))
        for widget in self._item_widgets.values():
            widget.delete_btn.setToolTip(tr('history.delete_tooltip'))

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self.list_widget.viewport() and event.type() == QEvent.Resize:
            self._refresh_item_elision()
        return super().eventFilter(obj, event)

    def reload(self) -> None:
        self._records = self.history_store.load()
        self._rebuild_list()

    def _rebuild_list(self) -> None:
        self.list_widget.clear()
        self._item_widgets.clear()
        for record in self._records:
            self._add_record_item(record)
        # Re-apply current filter text
        current_text = self._filter_edit.text()
        if current_text:
            self._filter_changed(current_text)

    def prepend_record(self, record: HistoryRecord) -> None:
        self._records = [r for r in self._records if r.id != record.id]
        self._records.insert(0, record)

        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item.data(Qt.UserRole) == record.id:
                self.list_widget.takeItem(index)
                self._item_widgets.pop(record.id, None)
                break

        item = QListWidgetItem()
        item.setData(Qt.UserRole, record.id)
        item.setSizeHint(QSize(0, 36))
        widget = HistoryItemWidget(record.list_text(), record.item_tooltip())
        widget.clicked.connect(lambda rid=record.id: self.record_selected.emit(rid))
        widget.delete_clicked.connect(lambda rid=record.id: self._delete_record(rid, confirm=False))
        self.list_widget.insertItem(0, item)
        self.list_widget.setItemWidget(item, widget)
        self._item_widgets[record.id] = widget
        # Apply current filter to the new item
        filter_text = self._filter_edit.text().strip().lower()
        if filter_text and filter_text not in record.list_text().lower():
            item.setHidden(True)
        self.select_record(record.id)

    def select_record(self, record_id: Optional[str]) -> None:
        if not record_id:
            self.list_widget.clearSelection()
            self.list_widget.setCurrentRow(-1)
            return
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item.data(Qt.UserRole) == record_id:
                self.list_widget.setCurrentRow(index)
                return
        self.list_widget.clearSelection()
        self.list_widget.setCurrentRow(-1)

    def update_record_name(self, record_id: str, new_name: str) -> None:
        for record in self._records:
            if record.id == record_id:
                record.name = new_name
                widget = self._item_widgets.get(record_id)
                if widget is not None:
                    widget.set_full_text(record.list_text())
                return

    def _filter_changed(self, text: str) -> None:
        text = text.strip().lower()
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item is None:
                continue
            record_id = item.data(Qt.UserRole)
            widget = self._item_widgets.get(record_id)
            if widget:
                matches = not text or text in widget.full_text().lower()
                item.setHidden(not matches)

    def _clear_filter(self) -> None:
        self._filter_edit.clear()

    def _add_record_item(self, record: HistoryRecord) -> None:
        item = QListWidgetItem()
        item.setData(Qt.UserRole, record.id)
        item.setSizeHint(QSize(0, 36))

        widget = HistoryItemWidget(record.list_text(), record.item_tooltip())
        widget.clicked.connect(lambda rid=record.id: self.record_selected.emit(rid))
        widget.delete_clicked.connect(lambda rid=record.id: self._delete_record(rid, confirm=False))

        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)
        self._item_widgets[record.id] = widget

    def _refresh_item_elision(self) -> None:
        for widget in self._item_widgets.values():
            widget._apply_elision()

    def _show_context_menu(self, pos: 'QPoint') -> None:
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        record_id = item.data(Qt.UserRole)
        if not record_id:
            return

        menu = QMenu(self)
        rename_action = menu.addAction(tr('tab.rename'))
        delete_action = menu.addAction(tr('history.delete'))
        menu.addSeparator()
        delete_others_action = menu.addAction(tr('history.delete_others'))
        delete_same_action = menu.addAction(tr('history.delete_same'))
        delete_all_action = menu.addAction(tr('history.delete_all'))
        action = menu.exec_(self.list_widget.mapToGlobal(pos))

        if action == rename_action:
            self._rename_record(record_id)
        elif action == delete_action:
            self._delete_record(record_id, confirm=False)
        elif action == delete_others_action:
            self._delete_others_except(record_id, confirm=False)
        elif action == delete_same_action:
            self._delete_same_method_url_except(record_id, confirm=False)
        elif action == delete_all_action:
            self._delete_all(confirm=True)

    def _rename_record(self, record_id: str) -> None:
        record = self.history_store.get(record_id)
        if not record:
            return
        new_name = prompt_text(
            self,
            tr('tab.rename_title'),
            tr('tab.rename_label'),
            record.name or record.display_name(),
            allow_empty=True,
        )
        if new_name is None:
            return
        updated = self.history_store.rename(record_id, new_name)
        if updated:
            self.update_record_name(record_id, new_name)
            self.record_renamed.emit(record_id, new_name)
            self.records_changed.emit()

    def _confirm(self, message: str, title: str = '') -> bool:
        if not title:
            title = tr('history.confirm_delete')
        return ask_yes_no(self, title, message)

    def _delete_records(self, record_ids: List[str], confirm: bool, message: str) -> None:
        if not record_ids:
            return
        if confirm and not self._confirm(message):
            return
        deleted = self.history_store.delete_many(record_ids)
        if not deleted:
            return
        self.reload()
        if len(deleted) == 1:
            self.record_deleted.emit(deleted[0])
        else:
            self.records_bulk_deleted.emit(deleted)
        self.records_changed.emit()

    def _delete_record(self, record_id: str, confirm: bool = False) -> None:
        self._delete_records(
            [record_id],
            confirm,
            tr('history.confirm_delete_one'),
        )

    def _delete_others_except(self, record_id: str, confirm: bool = False) -> None:
        ids = self.history_store.ids_except(record_id)
        self._delete_records(
            ids,
            confirm,
            tr('history.confirm_delete_others', count=len(ids)),
        )

    def _delete_same_method_url_except(self, record_id: str, confirm: bool = False) -> None:
        ids = self.history_store.ids_same_method_url_except(record_id)
        self._delete_records(
            ids,
            confirm,
            tr('history.confirm_delete_same', count=len(ids)),
        )

    def _delete_all(self, confirm: bool = False) -> None:
        ids = self.history_store.all_ids()
        self._delete_records(
            ids,
            confirm,
            tr('history.confirm_delete_all', count=len(ids)),
        )

    def get_record(self, record_id: str) -> Optional[HistoryRecord]:
        return self.history_store.get(record_id)
