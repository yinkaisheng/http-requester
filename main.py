#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from pathlib import Path

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QStyleFactory

hpath = Path(__file__).resolve().parent / 'Lib' / 'http-requester'
sys.path.append(str(hpath)) # need for building portable release
# print(f"Added {hpath} to sys.path")

from log_util import config_logger, logger
from storage.session_store import SessionStore
from ui.main_window import MainWindow
from ui.theme import (
    apply_app_font,
    apply_app_theme,
    migrate_session_theme,
    normalize_theme_name,
)

APP_ICON_PATH = Path(__file__).resolve().parent / 'web.ico'


def _load_app_icon() -> QIcon:
    if APP_ICON_PATH.is_file():
        return QIcon(str(APP_ICON_PATH))
    return QIcon()


def main():
    config_logger(logger)
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))
    app.setApplicationName('HTTP Requester')
    icon = _load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    session = SessionStore().load()
    theme = normalize_theme_name(
        migrate_session_theme(session.get('theme'), session.get('theme_version'))
    )
    apply_app_font(app)
    apply_app_theme(app, theme)
    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
