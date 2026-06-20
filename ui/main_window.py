#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from typing import Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QCloseEvent, QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QShortcut,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pyqt_async_task import AsyncTask
from storage.history_store import HistoryStore
from models.http_models import HistoryRecord
from storage.session_store import SessionStore
from ui.dialogs import prompt_editor_settings
from ui.history_panel import HistoryPanel
from ui.request_tab import splitter_ratio_to_sizes, splitter_sizes_to_ratio
from ui.request_tab_widget import RequestTabWidget
from ui.theme import (
    CURRENT_THEME_VERSION,
    THEME_LABELS,
    THEME_OPTIONS,
    apply_app_theme,
    default_body_text_font_family,
    default_body_text_font_size_px,
    migrate_session_theme,
    normalize_body_text_font_family,
    normalize_body_text_font_size,
    normalize_theme_name,
)
from ui.widgets import ArrowComboBox


class MainWindow(QMainWindow):
    DEFAULT_WIDTH = 1600
    DEFAULT_HEIGHT = 900
    DEFAULT_MAIN_SPLITTER_RATIO = round(280 / (280 + 920), 3)

    def __init__(self):
        super().__init__()
        self.history_store = HistoryStore()
        self.session_store = SessionStore()
        self.async_task = AsyncTask()
        self.async_task.debugPrint = False
        self._session_save_timer = QTimer(self)
        self._session_save_timer.setSingleShot(True)
        self._session_save_timer.setInterval(500)
        self._session_save_timer.timeout.connect(self._save_session)
        self.setWindowTitle('HTTP Requester')
        self._main_splitter: Optional[QSplitter] = None
        self._body_text_font_size = default_body_text_font_size_px()
        self._body_text_font_family = default_body_text_font_family()
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

        self.theme_combo = ArrowComboBox()
        self.theme_combo.setObjectName('themeCombo')
        self.theme_combo.setMinimumWidth(130)
        for theme_name in THEME_OPTIONS:
            self.theme_combo.addItem(THEME_LABELS[theme_name], theme_name)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        top_layout.addWidget(self.theme_combo)

        self.settings_btn = QToolButton()
        self.settings_btn.setObjectName('settingsButton')
        self.settings_btn.setText('\u2699')
        self.settings_btn.setToolTip('Settings')
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        top_layout.addWidget(self.settings_btn)
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
        self._setup_tab_close_shortcut()

    def _setup_tab_close_shortcut(self) -> None:
        key = 'Ctrl+F4' if sys.platform == 'win32' else 'Ctrl+W'
        shortcut = QShortcut(QKeySequence(key), self)
        shortcut.activated.connect(self.request_tabs.close_current_tab)

    def _connect_signals(self) -> None:
        self.history_panel.record_selected.connect(self._on_record_selected)
        self.history_panel.record_deleted.connect(self.request_tabs.close_record_tab)
        self.history_panel.records_bulk_deleted.connect(self.request_tabs.close_record_tabs)
        self.history_panel.record_renamed.connect(self._on_record_renamed)
        self.request_tabs.record_renamed.connect(self._on_record_renamed)
        self.request_tabs.record_saved.connect(self._on_record_saved)
        self.request_tabs.currentChanged.connect(self._schedule_session_save)
        self.request_tabs.tab_title_changed.connect(self._schedule_session_save)
        self.request_tabs.workspace_changed.connect(self._schedule_session_save)
        self.request_tabs.record_saved.connect(self._schedule_session_save)

    def _schedule_session_save(self, *_args) -> None:
        self._session_save_timer.start()

    def _on_record_renamed(self, record_id: str, new_name: str) -> None:
        self.history_panel.update_record_name(record_id, new_name)
        self.request_tabs.update_tab_title_for_record(record_id, new_name)

    def _restore_session(self) -> None:
        session = self.session_store.load()
        window = session.get('window', {})

        theme = normalize_theme_name(
            migrate_session_theme(session.get('theme'), session.get('theme_version'))
        )
        theme_index = THEME_OPTIONS.index(theme)
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(theme_index)
        self.theme_combo.blockSignals(False)
        self._body_text_font_size = normalize_body_text_font_size(session.get('body_text_font_size'))
        self._body_text_font_family = normalize_body_text_font_family(session.get('body_text_font_family'))
        self._apply_appearance()

        width = window.get('width', self.DEFAULT_WIDTH)
        height = window.get('height', self.DEFAULT_HEIGHT)
        if not isinstance(width, int) or width <= 0:
            width = self.DEFAULT_WIDTH
        if not isinstance(height, int) or height <= 0:
            height = self.DEFAULT_HEIGHT
        self.resize(width, height)
        self._center_on_screen()

        main_ratio = window.get('main_splitter')
        if isinstance(main_ratio, (int, float)) and 0.0 <= main_ratio <= 1.0 and self._main_splitter:
            QTimer.singleShot(0, lambda r=float(main_ratio): self._apply_main_splitter_ratio(r))

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

    def _apply_main_splitter_ratio(self, ratio: float) -> None:
        if not self._main_splitter:
            return
        width = self._main_splitter.width()
        if width <= 0:
            QTimer.singleShot(50, lambda: self._apply_main_splitter_ratio(ratio))
            return
        self._main_splitter.setSizes(splitter_ratio_to_sizes(width, ratio))

    def _save_session(self) -> None:
        tab_state = self.request_tabs.get_session_state()
        window_state = {
            'width': self.width(),
            'height': self.height(),
            'main_splitter': (
                splitter_sizes_to_ratio(self._main_splitter.sizes())
                if self._main_splitter
                else self.DEFAULT_MAIN_SPLITTER_RATIO
            ),
        }
        self.session_store.save({
            'version': 1,
            'theme': self._current_theme(),
            'theme_version': CURRENT_THEME_VERSION,
            'body_text_font_size': self._body_text_font_size,
            'body_text_font_family': self._body_text_font_family,
            'window': window_state,
            'tabs': tab_state.get('tabs', []),
            'current_tab_index': tab_state.get('current_tab_index', 0),
        })

    def closeEvent(self, event: 'QCloseEvent') -> None:
        self._save_session()
        super().closeEvent(event)

    def _on_new_request(self) -> None:
        self.request_tabs.new_request()

    def _current_theme(self) -> str:
        return normalize_theme_name(self.theme_combo.currentData())

    def _apply_appearance(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        apply_app_theme(
            app,
            self._current_theme(),
            self._body_text_font_size,
            self._body_text_font_family,
        )

    def _on_settings_clicked(self) -> None:
        settings = prompt_editor_settings(
            self,
            self._body_text_font_size,
            self._body_text_font_family,
        )
        if settings is None:
            return
        if (
            settings.size == self._body_text_font_size
            and settings.family == self._body_text_font_family
        ):
            return
        self._body_text_font_size = settings.size
        self._body_text_font_family = settings.family
        self._apply_appearance()
        self._save_session()

    def _on_theme_changed(self, _index: int) -> None:
        self._apply_appearance()
        self._save_session()

    def _on_record_selected(self, record_id: str) -> None:
        record = self.history_panel.get_record(record_id)
        if record:
            self.request_tabs.open_record(record)

    def _on_record_saved(self, record: HistoryRecord) -> None:
        self.history_panel.prepend_record(record)
