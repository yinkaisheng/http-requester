#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QStyleFactory

from log_util import config_logger, logger

exe_path = Path(sys.executable).resolve()
script_path = Path(__file__).resolve()
if 'python' not in exe_path.name.lower():
    os.chdir(exe_path.parent) # sys.executable is HttpRequester.exe(Windows) or httpreq(Linux)
    config_logger(logger, log_dir='logs', log_file='http-requester.log')
else:
    os.chdir(script_path.parent)
    config_logger(logger)

from storage.session_store import SessionStore
from ui.main_window import MainWindow
from ui.theme import (
    apply_app_font,
    apply_app_theme,
    migrate_session_theme,
    normalize_body_text_font_family,
    normalize_body_text_font_size,
    normalize_theme_name,
)


def _load_app_icon() -> QIcon:
    APP_ICON_PATH = Path(__file__).parent / 'web.ico'
    if APP_ICON_PATH.is_file():
        return QIcon(str(APP_ICON_PATH))
    return QIcon()


def main():
    logger.info(f'========================================\n\n')
    logger.info(f'executable={exe_path}, pid={os.getpid()}, working_directory={os.getcwd()}')
    logger.info(f'__file__={script_path}, argv={sys.argv}')
    logger.info(f'sys.path=\n[\n{"\n".join(sys.path)}\n]')
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
    body_text_font_size = normalize_body_text_font_size(session.get('body_text_font_size'))
    body_text_font_family = normalize_body_text_font_family(session.get('body_text_font_family'))
    apply_app_font(app)
    apply_app_theme(app, theme, body_text_font_size, body_text_font_family)
    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
