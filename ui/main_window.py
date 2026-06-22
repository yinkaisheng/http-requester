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
from storage.app_config import get_app_config, save_app_preferences
from ui.dialogs import AppSettings, prompt_app_settings, show_about_dialog
from ui.history_panel import HistoryPanel
from ui.request_tab import RequestTab, splitter_ratio_to_sizes, splitter_sizes_to_ratio, MSG_HTTP_DONE
from ui.request_tab_widget import RequestTabWidget
from i18n import register_retranslator, set_language, tr
from ui.theme import (
    apply_app_theme,
    normalize_body_text_font_family,
    normalize_body_text_font_size,
    normalize_theme_name,
)


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
        self.async_task.setMsgIDName(MSG_HTTP_DONE, 'MSG_HTTP_DONE')
        self._session_save_timer = QTimer(self)
        self._session_save_timer.setSingleShot(True)
        self._session_save_timer.setInterval(500)
        self._session_save_timer.timeout.connect(self._save_session)
        self.setWindowTitle(tr('main.window_title'))
        self._main_splitter: Optional[QSplitter] = None
        self._init_ui()
        register_retranslator(self.retranslate_ui)
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
        top_layout.setAlignment(Qt.AlignVCenter)
        self.new_btn = QPushButton(tr('main.new_request'))
        self.new_btn.setObjectName('primaryButton')
        self.new_btn.clicked.connect(self._on_new_request)
        top_layout.addWidget(self.new_btn, 0, Qt.AlignVCenter)

        self.settings_btn = QToolButton()
        self.settings_btn.setObjectName('settingsButton')
        self.settings_btn.setText('\u2699')
        self.settings_btn.setToolTip(tr('main.settings_tooltip'))
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        top_layout.addWidget(self.settings_btn, 0, Qt.AlignVCenter)

        self.about_btn = QToolButton()
        self.about_btn.setObjectName('aboutButton')
        self.about_btn.setText('\u24D8')
        self.about_btn.setToolTip(tr('main.about_tooltip'))
        self.about_btn.clicked.connect(self._on_about_clicked)
        top_layout.addWidget(self.about_btn, 0, Qt.AlignVCenter)
        top_layout.addStretch()

        self._main_splitter = QSplitter(Qt.Horizontal)
        self.history_panel = HistoryPanel(self.history_store)
        self.request_tabs = RequestTabWidget(self.history_store, self.async_task)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_layout.addWidget(top_bar, 0)
        left_layout.addWidget(self.history_panel, 1)

        self._main_splitter.addWidget(left_container)
        self._main_splitter.addWidget(self.request_tabs)
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 3)
        self._main_splitter.setSizes([280, 920])

        main_layout.addWidget(self._main_splitter)
        self._setup_shortcuts()

    def _setup_shortcuts(self) -> None:
        close_key = 'Ctrl+F4' if sys.platform == 'win32' else 'Ctrl+W'
        close_shortcut = QShortcut(QKeySequence(close_key), self)
        close_shortcut.activated.connect(self.request_tabs.close_current_tab)

        new_shortcut = QShortcut(QKeySequence('Ctrl+N'), self)
        new_shortcut.activated.connect(self._on_new_request)

    def _connect_signals(self) -> None:
        self.history_panel.record_selected.connect(self._on_record_selected)
        self.history_panel.record_deleted.connect(self.request_tabs.close_record_tab)
        self.history_panel.records_bulk_deleted.connect(self.request_tabs.close_record_tabs)
        self.history_panel.record_renamed.connect(self._on_record_renamed)
        self.request_tabs.record_renamed.connect(self._on_record_renamed)
        self.request_tabs.record_saved.connect(self._on_record_saved)
        self.request_tabs.currentChanged.connect(self._on_current_tab_changed)
        self.request_tabs.tab_title_changed.connect(self._schedule_session_save)
        self.request_tabs.workspace_changed.connect(self._schedule_session_save)
        self.request_tabs.record_saved.connect(self._schedule_session_save)

    def _schedule_session_save(self, *_args) -> None:
        self._session_save_timer.start()

    def _on_current_tab_changed(self, index: int) -> None:
        self._schedule_session_save()
        widget = self.request_tabs.widget(index) if index >= 0 else None
        record_id = widget.get_record_id() if isinstance(widget, RequestTab) else None
        self.history_panel.select_record(record_id)

    def _on_record_renamed(self, record_id: str, new_name: str) -> None:
        self.history_panel.update_record_name(record_id, new_name)
        self.request_tabs.update_tab_title_for_record(record_id, new_name)

    def _appearance(self):
        return get_app_config().appearance

    def _restore_session(self) -> None:
        session = self.session_store.load()
        window = session.get('window', {})
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
        self._on_current_tab_changed(self.request_tabs.currentIndex())

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
            'window': window_state,
            'tabs': tab_state.get('tabs', []),
            'current_tab_index': tab_state.get('current_tab_index', 0),
        })

    def closeEvent(self, event: 'QCloseEvent') -> None:
        self._save_session()
        super().closeEvent(event)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr('main.window_title'))
        self.new_btn.setText(tr('main.new_request'))
        self.settings_btn.setToolTip(tr('main.settings_tooltip'))
        self.about_btn.setToolTip(tr('main.about_tooltip'))
        self.history_panel.retranslate_ui()
        self.request_tabs.retranslate_ui()

    def _on_new_request(self) -> None:
        self.request_tabs.new_request()

    def _current_theme(self) -> str:
        return normalize_theme_name(self._appearance().theme)

    def _apply_appearance(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        appearance = self._appearance()
        apply_app_theme(
            app,
            self._current_theme(),
            normalize_body_text_font_size(appearance.body_text_font_size_px),
            normalize_body_text_font_family(appearance.body_text_font_family),
        )

    def _save_settings(self, settings: AppSettings) -> None:
        save_app_preferences(
            theme=settings.theme,
            body_text_font_family=settings.family,
            body_text_font_size_px=settings.size,
            language=settings.language,
        )
        set_language(settings.language)
        # app = QApplication.instance()
        # if app is not None:
        #     sync_qt_translator(app, settings.language)  # Qt .qm; see i18n/qt_locale.py
        self._apply_appearance()

    def _on_settings_clicked(self) -> None:
        appearance = self._appearance()
        prompt_app_settings(
            self,
            self._current_theme(),
            appearance.body_text_font_size_px,
            appearance.body_text_font_family,
            get_app_config().language,
            on_save=self._save_settings,
        )

    def _on_about_clicked(self) -> None:
        show_about_dialog(self)

    def _on_record_selected(self, record_id: str) -> None:
        record = self.history_panel.get_record(record_id)
        if record:
            self.request_tabs.open_record(record)

    def _on_record_saved(self, record: HistoryRecord) -> None:
        self.history_panel.prepend_record(record)
