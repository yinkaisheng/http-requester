#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
import traceback

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QStyleFactory

from log_util import config_logger, logger

exe_path = Path(sys.executable).resolve()
script_path = Path(__file__).resolve()
if 'python' not in exe_path.name.lower():
    os.chdir(exe_path.parent) # sys.executable is HttpRequester.exe(Windows) or httpreq(Linux)
else:
    os.chdir(script_path.parent) # main.py dir

# UI translations: Languages/<locale>/ (see i18n/translator.py for common locale folder names)
from storage.app_config import get_app_config, init_app_config
from i18n import init_i18n
# Qt .qm translator (standard Qt approach; not used — see i18n/qt_locale.py):
# from i18n.qt_locale import sync_qt_translator
from ui.dialog_i18n import install_dialog_translations
from ui.widgets import install_edit_context_menu_translations
from ui.main_window import MainWindow
from ui.theme import (
    apply_app_font,
    apply_app_theme,
    normalize_body_text_font_family,
    normalize_body_text_font_size,
    normalize_theme_name,
)


def _load_app_icon() -> QIcon:
    APP_ICON_PATH = Path(__file__).parent / 'web.ico'
    if APP_ICON_PATH.is_file():
        return QIcon(str(APP_ICON_PATH))
    return QIcon()


def run_qt_app():
    init_app_config()
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))
    install_edit_context_menu_translations(app)
    install_dialog_translations(app)
    init_i18n(get_app_config().language)
    # sync_qt_translator(app, get_app_config().language)  # Qt .qm; see i18n/qt_locale.py
    from i18n import tr
    app.setApplicationName(tr('main.window_title'))
    icon = _load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    appearance = get_app_config().appearance
    theme = normalize_theme_name(appearance.theme)
    body_text_font_size = normalize_body_text_font_size(appearance.body_text_font_size_px)
    body_text_font_family = normalize_body_text_font_family(appearance.body_text_font_family)
    apply_app_font(app)
    apply_app_theme(app, theme, body_text_font_size, body_text_font_family)
    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec_())


def main():
    if sys.stdout is None:
        config_logger(logger, log_dir='logs', log_file='http-requester.log')
    else:
        config_logger(logger)

    logger.info(f'========================================\n\n')
    logger.info(f'executable={exe_path}, pid={os.getpid()}, working_directory={os.getcwd()}')
    logger.info(f'__file__={script_path}, argv={sys.argv}')
    logger.info('sys.path=\n[\n{}\n]'.format('\n'.join(sys.path)))

    try:
        run_qt_app()
    except Exception as ex:
        logger.error(f'An unexpected error occurred:\n'
                     f'{"".join(traceback.format_exception(type(ex), ex, ex.__traceback__))}')
        sys.exit(1)


if __name__ == '__main__':
    main()
