#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QPushButton, QTabBar, QTabWidget, QWidget

from models.http_models import HistoryRecord
from pyqt_async_task import AsyncTask
from storage.history_store import HistoryStore
from ui.request_tab import RequestTab

TAB_CLOSE_BUTTON_TEXT = '\u00d7'


class RequestTabWidget(QTabWidget):
    tab_title_changed = pyqtSignal()
    record_bound = pyqtSignal(str)
    record_saved = pyqtSignal(object)

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
        self.tabBar().tabMoved.connect(self._rebuild_map)
        self.tabBarDoubleClicked.connect(self._on_tab_bar_double_clicked)

    def addTab(self, widget: QWidget, label: str) -> int:
        index = super().addTab(widget, label)
        self._install_tab_close_button(index)
        return index

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
        tab.record_bound.connect(self._on_record_bound)
        return tab

    def restore_session(
        self,
        tabs: List[dict],
        current_index: int = 0,
    ) -> None:
        while self.count() > 0:
            self.removeTab(0)
        self._record_tab_map.clear()

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

    def close_record_tab(self, record_id: str) -> None:
        if record_id in self._record_tab_map:
            index = self._record_tab_map[record_id]
            if 0 <= index < self.count():
                self._close_tab_at_index(index)
                return
        self._ensure_at_least_one_tab()

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

    def _on_tab_bar_double_clicked(self, index: int) -> None:
        if index >= 0:
            self._close_tab_at_index(index)

    def _rebuild_map(self) -> None:
        self._record_tab_map.clear()
        for i in range(self.count()):
            widget = self.widget(i)
            if isinstance(widget, RequestTab):
                record_id = widget.get_record_id()
                if record_id:
                    self._record_tab_map[record_id] = i

    def _on_tab_saved(self, record: HistoryRecord) -> None:
        for i in range(self.count()):
            widget = self.widget(i)
            if isinstance(widget, RequestTab) and widget.get_record_id() == record.id:
                self.setTabText(i, widget.tab_title())
                break
        self.tab_title_changed.emit()

    def _on_record_bound(self, record_id: str) -> None:
        current_widget = self.currentWidget()
        if isinstance(current_widget, RequestTab):
            self._rebuild_map()
            for i in range(self.count()):
                if self.widget(i) is current_widget:
                    self._record_tab_map[record_id] = i
                    self.setTabText(i, current_widget.tab_title())
                    break
        self.record_bound.emit(record_id)
