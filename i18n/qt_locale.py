#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Load PyQt5 shipped .qm files for Qt built-in UI strings.

Common Qt / PyQt approach (NOT used in this project)
----------------------------------------------------
Most Qt applications call ``QApplication.installTranslator()`` with ``.qm``
files from PyQt5's ``Qt5/translations/`` directory (e.g. ``qt_zh_CN.qm``).
That translates Qt-owned strings in one shot: QMessageBox Yes/No, QFileDialog
buttons, QDialogButtonBox defaults, edit context menus, etc.

Pros: broad coverage, maintained by Qt, standard for C++/Qt apps.
Cons: must ship ``translations/`` with the package (or rely on PyQt5 install path).

This project's approach
-----------------------
We do NOT install Qt ``.qm`` translators. Instead:

- App UI: ``Languages/<locale>/strings.txt`` + ``tr()``
- Dialog / message-box / file-dialog buttons: ``ui/dialog_i18n.py``
- Edit context menus: ``ui/widgets.py`` (``edit.*`` keys)

This keeps all user-visible strings in plain text under ``Languages/`` and
avoids bundling PyQt5's ``translations/`` folder in release builds.

The implementation below is kept (commented out) as a reference if you ever
want to switch to or combine with the standard Qt ``.qm`` approach.
"""
from __future__ import annotations

# from pathlib import Path
# from typing import Optional
#
# from PyQt5.QtCore import QLibraryInfo, QTranslator
# from PyQt5.QtWidgets import QApplication
#
# from i18n.translator import DEFAULT_LOCALE
# from log_util import logger
#
# # Map app locale folder names to PyQt5 translation base names (without .qm).
# _QT_TRANSLATION_BASE: dict[str, str] = {
#     'zh-CN': 'qt_zh_CN',
#     'zh-TW': 'qt_zh_TW',
# }
#
# _qt_translator: Optional[QTranslator] = None
#
#
# def _translation_search_paths() -> list[str]:
#     paths: list[str] = []
#     qt_path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
#     if qt_path:
#         paths.append(qt_path)
#     try:
#         import PyQt5
#
#         pkg_path = Path(PyQt5.__file__).resolve().parent / 'Qt5' / 'translations'
#         if pkg_path.is_dir():
#             paths.append(str(pkg_path))
#     except ImportError:
#         pass
#     unique: list[str] = []
#     for path in paths:
#         if path and path not in unique:
#             unique.append(path)
#     return unique
#
#
# def sync_qt_translator(app: QApplication, locale: str) -> None:
#     """Install or remove Qt's translator for standard widgets (dialogs, edit menus, etc.)."""
#     global _qt_translator
#     if _qt_translator is not None:
#         app.removeTranslator(_qt_translator)
#         _qt_translator = None
#
#     if locale == DEFAULT_LOCALE:
#         return
#
#     base = _QT_TRANSLATION_BASE.get(locale)
#     if base is None:
#         return
#
#     translator = QTranslator(app)
#     loaded = False
#     for path in _translation_search_paths():
#         if translator.load(base, path):
#             loaded = True
#             logger.info('Loaded Qt translation {} from {}', base, path)
#             break
#     if not loaded:
#         logger.warning(
#             'Qt translation not found: {} (searched {})',
#             base,
#             ', '.join(_translation_search_paths()),
#         )
#         return
#     app.installTranslator(translator)
#     _qt_translator = translator
