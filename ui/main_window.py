#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pyqt_async_task import AsyncTask
from storage.history_store import HistoryStore
from storage.session_store import SessionStore
from ui.history_panel import HistoryPanel
from ui.request_tab_widget import RequestTabWidget
from ui.theme import (
    THEME_LABELS,
    THEME_OPTIONS,
    apply_app_theme,
    normalize_theme_name,
)


class MainWindow(QMainWindow):
    DEFAULT_WIDTH = 1600
    DEFAULT_HEIGHT = 900

    def __init__(self):
        super().__init__()
        self.history_store = HistoryStore()
        self.session_store = SessionStore()
        self.async_task = AsyncTask()
        self.async_task.debugPrint = False
        self.setWindowTitle('HTTP Requester')
        self._main_splitter: Optional[QSplitter] = None
        self._init_ui()
        self._connect_signals()
        self._restore_session()

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(8, 4, 8, 4)
        self.new_btn = QPushButton('+ New Request')
        self.new_btn.setObjectName('primaryButton')
        self.new_btn.clicked.connect(self._on_new_request)
        top_layout.addWidget(self.new_btn)

        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName('themeCombo')
        self.theme_combo.setFixedWidth(88)
        for theme_name in THEME_OPTIONS:
            self.theme_combo.addItem(THEME_LABELS[theme_name], theme_name)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        top_layout.addWidget(self.theme_combo)
        top_layout.addStretch()

        self._main_splitter = QSplitter(Qt.Horizontal)
        self.history_panel = HistoryPanel(self.history_store)
        self.request_tabs = RequestTabWidget(self.history_store, self.async_task)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(top_bar)
        left_layout.addWidget(self.history_panel)

        self._main_splitter.addWidget(left_container)
        self._main_splitter.addWidget(self.request_tabs)
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 3)
        self._main_splitter.setSizes([280, 920])

        main_layout.addWidget(self._main_splitter)

    def _connect_signals(self) -> None:
        self.history_panel.record_selected.connect(self._on_record_selected)
        self.history_panel.record_deleted.connect(self.request_tabs.close_record_tab)
        self.request_tabs.record_bound.connect(self._on_record_bound)
        self.request_tabs.record_saved.connect(self._on_record_saved)

    def _restore_session(self) -> None:
        session = self.session_store.load()
        window = session.get('window', {})

        theme = normalize_theme_name(session.get('theme'))
        theme_index = THEME_OPTIONS.index(theme)
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(theme_index)
        self.theme_combo.blockSignals(False)
        apply_app_theme(QApplication.instance(), theme)

        width = window.get('width', self.DEFAULT_WIDTH)
        height = window.get('height', self.DEFAULT_HEIGHT)
        if not isinstance(width, int) or width <= 0:
            width = self.DEFAULT_WIDTH
        if not isinstance(height, int) or height <= 0:
            height = self.DEFAULT_HEIGHT
        self.resize(width, height)
        self._center_on_screen()

        main_sizes = window.get('main_splitter')
        if isinstance(main_sizes, list) and len(main_sizes) == 2 and self._main_splitter:
            self._main_splitter.setSizes(main_sizes)

        tabs = session.get('tabs', [])
        current_index = session.get('current_tab_index', 0)
        if isinstance(tabs, list) and tabs:
            self.request_tabs.restore_session(tabs, current_index)
        elif self.request_tabs.count() == 0:
            self.request_tabs.new_request()

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if not screen:
            return
        available = screen.availableGeometry()
        x = available.x() + max(0, (available.width() - self.width()) // 2)
        y = available.y() + max(0, (available.height() - self.height()) // 2)
        self.move(x, y)

    def _save_session(self) -> None:
        tab_state = self.request_tabs.get_session_state()
        window_state = {
            'width': self.width(),
            'height': self.height(),
            'main_splitter': self._main_splitter.sizes() if self._main_splitter else [280, 920],
        }
        self.session_store.save({
            'theme': self._current_theme(),
            'window': window_state,
            'tabs': tab_state.get('tabs', []),
            'current_tab_index': tab_state.get('current_tab_index', 0),
        })

    def closeEvent(self, event) -> None:
        self._save_session()
        super().closeEvent(event)

    def _on_new_request(self) -> None:
        self.request_tabs.new_request()

    def _current_theme(self) -> str:
        return normalize_theme_name(self.theme_combo.currentData())

    def _on_theme_changed(self, _index: int) -> None:
        app = QApplication.instance()
        if app is None:
            return
        apply_app_theme(app, self._current_theme())
        self._save_session()

    def _on_record_selected(self, record_id: str) -> None:
        record = self.history_panel.get_record(record_id)
        if record:
            self.request_tabs.open_record(record)

    def _on_record_bound(self, record_id: str) -> None:
        record = self.history_store.get(record_id)
        if record:
            self.history_panel.upsert_record(record)

    def _on_record_saved(self, record) -> None:
        self.history_panel.upsert_record(record)
