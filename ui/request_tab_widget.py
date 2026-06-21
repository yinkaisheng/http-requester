#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal, QEvent
from PyQt5.QtGui import QFontMetrics, QMouseEvent
from PyQt5.QtWidgets import QMenu, QPushButton, QTabBar, QTabWidget, QWidget

from models.http_models import HistoryRecord
from pyqt_async_task import AsyncTask
from storage.history_store import HistoryStore
from ui.dialogs import prompt_text
from ui.request_tab import RequestTab

TAB_CLOSE_BUTTON_TEXT = '\u00d7'
TAB_TITLE_MAX_WIDTH = 500


class RequestTabWidget(QTabWidget):
    tab_title_changed = pyqtSignal()
    workspace_changed = pyqtSignal()
    record_saved = pyqtSignal(object)
    record_renamed = pyqtSignal(str, str)

    def __init__(
        self,
        history_store: HistoryStore,
        async_task: AsyncTask,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.history_store = history_store
        self.async_task = async_task
        self._record_tab_map: Dict[str, int] = {}
        self.setTabsClosable(False)
        self.setMovable(True)
        self.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabBar().customContextMenuRequested.connect(self._on_tab_context_menu)
        self.tabBar().tabMoved.connect(self._rebuild_map)
        self.tabBar().tabMoved.connect(self.workspace_changed.emit)
        self.tabBarDoubleClicked.connect(self._on_tab_bar_double_clicked)
        self.tabBar().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if obj is self.tabBar() and event.type() == QEvent.MouseButtonRelease:
            mouse_event = event
            if isinstance(mouse_event, QMouseEvent) and mouse_event.button() == Qt.MiddleButton:
                index = self.tabBar().tabAt(mouse_event.pos())
                if index >= 0:
                    self._close_tab_at_index(index)
                    return True
        return super().eventFilter(obj, event)

    def addTab(self, widget: QWidget, label: str) -> int:
        if isinstance(widget, RequestTab):
            label = self._format_tab_bar_title(widget.tab_title())
        index = super().addTab(widget, label)
        self._install_tab_close_button(index)
        return index

    def _format_tab_bar_title(self, title: str) -> str:
        metrics = QFontMetrics(self.font())
        if metrics.horizontalAdvance(title) <= TAB_TITLE_MAX_WIDTH:
            return title
        return metrics.elidedText(title, Qt.ElideRight, TAB_TITLE_MAX_WIDTH)

    def _update_tab_text(self, index: int, tab: RequestTab) -> None:
        full_title = tab.tab_title()
        display_title = self._format_tab_bar_title(full_title)
        self.setTabText(index, display_title)
        self.setTabToolTip(index, full_title if display_title != full_title else '')

    def _install_tab_close_button(self, index: int) -> None:
        btn = QPushButton(TAB_CLOSE_BUTTON_TEXT, self)
        btn.setObjectName('tabCloseButton')
        btn.setFixedSize(18, 18)
        btn.setFlat(True)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.clicked.connect(self._on_tab_close_button_clicked)
        self.tabBar().setTabButton(index, QTabBar.RightSide, btn)

    def _on_tab_close_button_clicked(self) -> None:
        btn = self.sender()
        if btn is None:
            return
        tab_bar = self.tabBar()
        for index in range(tab_bar.count()):
            if tab_bar.tabButton(index, QTabBar.RightSide) is btn:
                self._close_tab_at_index(index)
                return

    def open_record(self, record: HistoryRecord) -> None:
        if record.id in self._record_tab_map:
            index = self._record_tab_map[record.id]
            if 0 <= index < self.count():
                self.setCurrentIndex(index)
                return
            del self._record_tab_map[record.id]

        tab = self._create_tab(record=record)
        index = self.addTab(tab, tab.tab_title())
        self._record_tab_map[record.id] = index
        self.setCurrentIndex(index)

    def new_request(self) -> RequestTab:
        tab = self._create_tab()
        tab.apply_default_splitter_sizes()
        index = self.addTab(tab, tab.tab_title())
        self.setCurrentIndex(index)
        self.workspace_changed.emit()
        return tab

    def _create_tab(
        self,
        record: Optional[HistoryRecord] = None,
        session_state: Optional[dict] = None,
    ) -> RequestTab:
        if session_state is not None:
            tab = RequestTab(self.history_store, self.async_task)
            tab.restore_session_state(session_state)
        else:
            tab = RequestTab(self.history_store, self.async_task, record=record)
        tab.record_saved.connect(self._on_tab_saved)
        tab.record_saved.connect(self.record_saved.emit)
        return tab

    def restore_session(
        self,
        tabs: List[dict],
        current_index: int = 0,
    ) -> None:
        self._remove_all_tabs()

        if not tabs:
            self.new_request()
            return

        for state in tabs:
            tab = self._create_tab(session_state=state)
            self.addTab(tab, tab.tab_title())
        self._rebuild_map()

        if 0 <= current_index < self.count():
            self.setCurrentIndex(current_index)
        elif self.count() > 0:
            self.setCurrentIndex(0)
        self.workspace_changed.emit()

    def get_session_state(self) -> dict:
        tabs = []
        for i in range(self.count()):
            widget = self.widget(i)
            if isinstance(widget, RequestTab):
                tabs.append(widget.get_session_state())
        return {
            'tabs': tabs,
            'current_tab_index': self.currentIndex(),
        }

    def _remove_all_tabs(self) -> None:
        while self.count() > 0:
            self.removeTab(0)
        self._record_tab_map.clear()

    def close_current_tab(self) -> None:
        index = self.currentIndex()
        if index >= 0:
            self._close_tab_at_index(index)

    def close_record_tab(self, record_id: str) -> None:
        if record_id in self._record_tab_map:
            index = self._record_tab_map[record_id]
            if 0 <= index < self.count():
                self._close_tab_at_index(index)
                return
        self._ensure_at_least_one_tab()

    def close_record_tabs(self, record_ids: List[str]) -> None:
        id_set = set(record_ids)
        indices = []
        for i in range(self.count()):
            widget = self.widget(i)
            if isinstance(widget, RequestTab):
                rid = widget.get_record_id()
                if rid and rid in id_set:
                    indices.append(i)
        for index in sorted(indices, reverse=True):
            self._close_tab_at_index(index)

    def _ensure_at_least_one_tab(self) -> None:
        if self.count() == 0:
            self.new_request()

    def _close_tab_at_index(self, index: int) -> None:
        if index < 0 or index >= self.count():
            return
        widget = self.widget(index)
        if isinstance(widget, RequestTab):
            record_id = widget.get_record_id()
            if record_id and record_id in self._record_tab_map:
                del self._record_tab_map[record_id]
        self.removeTab(index)
        self._rebuild_map()
        self._ensure_at_least_one_tab()
        self.workspace_changed.emit()

    def _close_other_tabs_at_index(self, keep_index: int) -> None:
        if keep_index < 0 or keep_index >= self.count() or self.count() <= 1:
            return
        keep_widget = self.widget(keep_index)
        if not isinstance(keep_widget, RequestTab):
            return
        indices_to_close = [i for i in range(self.count()) if i != keep_index]
        for index in sorted(indices_to_close, reverse=True):
            self._close_tab_at_index(index)
        for i in range(self.count()):
            if self.widget(i) is keep_widget:
                self.setCurrentIndex(i)
                break

    def _on_tab_bar_double_clicked(self, index: int) -> None:
        if index >= 0:
            self._close_tab_at_index(index)

    def _on_tab_context_menu(self, pos) -> None:
        index = self.tabBar().tabAt(pos)
        if index < 0:
            return
        widget = self.widget(index)
        if not isinstance(widget, RequestTab):
            return

        menu = QMenu(self)
        rename_action = menu.addAction('Rename')
        close_others_action = None
        if self.count() > 1:
            menu.addSeparator()
            close_others_action = menu.addAction('Close Other Tabs')
        action = menu.exec_(self.tabBar().mapToGlobal(pos))
        if action == rename_action:
            self._rename_tab_at_index(index)
        elif close_others_action is not None and action == close_others_action:
            self._close_other_tabs_at_index(index)

    def _rename_tab_at_index(self, index: int) -> None:
        widget = self.widget(index)
        if not isinstance(widget, RequestTab):
            return
        new_name = prompt_text(
            self,
            'Rename',
            'Request name:',
            widget.tab_title(),
            allow_empty=True,
        )
        if new_name is None:
            return
        record_id = widget.get_record_id()
        if record_id:
            updated = self.history_store.rename(record_id, new_name)
            if not updated:
                return
            widget.apply_record_name(new_name)
            self.record_renamed.emit(record_id, new_name)
        else:
            widget.set_draft_name(new_name)
        self._update_tab_text(index, widget)
        self.tab_title_changed.emit()
        self.workspace_changed.emit()

    def update_tab_title_for_record(self, record_id: str, new_name: str) -> None:
        if record_id not in self._record_tab_map:
            return
        index = self._record_tab_map[record_id]
        if index < 0 or index >= self.count():
            return
        widget = self.widget(index)
        if not isinstance(widget, RequestTab):
            return
        widget.apply_record_name(new_name)
        self._update_tab_text(index, widget)
        self.tab_title_changed.emit()
        self.workspace_changed.emit()

    def _rebuild_map(self) -> None:
        self._record_tab_map.clear()
        for i in range(self.count()):
            widget = self.widget(i)
            if isinstance(widget, RequestTab):
                record_id = widget.get_record_id()
                if record_id:
                    self._record_tab_map[record_id] = i

    def _on_tab_saved(self, record: HistoryRecord) -> None:
        sender_tab = self.sender()
        for i in range(self.count()):
            widget = self.widget(i)
            if widget is sender_tab and isinstance(widget, RequestTab):
                self._update_tab_text(i, widget)
                break
        self._rebuild_map()
        self.tab_title_changed.emit()
        self.workspace_changed.emit()
