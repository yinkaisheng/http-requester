#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QLineEdit,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app_info import APP_NAME, APP_VERSION, GITHUB_URL

from ui.widgets import ArrowFontComboBox, ArrowComboBox, GlyphSpinBox
from ui.theme import (
    BODY_TEXT_FONT_SIZE_MAX,
    BODY_TEXT_FONT_SIZE_MIN,
    THEME_LABELS,
    THEME_OPTIONS,
    ThemeName,
    default_body_text_font_family,
    normalize_body_text_font_family,
    normalize_theme_name,
)


@dataclass(frozen=True)
class AppSettings:
    theme: ThemeName
    size: int
    family: str


def _create_dialog(parent: QWidget, title: str, *, min_width: int = 400) -> QDialog:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(min_width)
    dialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    return dialog


def prompt_text(
    parent: QWidget,
    title: str,
    label: str,
    initial: str = '',
    *,
    min_width: int = 400,
    allow_empty: bool = False,
) -> Optional[str]:
    dialog = _create_dialog(parent, title, min_width=min_width)

    layout = QFormLayout(dialog)
    edit = QLineEdit(initial)
    edit.setMinimumWidth(min_width - 48)
    layout.addRow(label, edit)

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)

    edit.selectAll()
    edit.setFocus()

    if dialog.exec_() != QDialog.Accepted:
        return None
    text = edit.text().strip()
    if not text and not allow_empty:
        return None
    return text


def _select_monospace_family(combo: QFontComboBox, family: str) -> None:
    target = normalize_body_text_font_family(family)
    combo.setCurrentFont(QFont(target))
    if combo.currentFont().family() == target:
        return
    for index in range(combo.count()):
        if combo.itemText(index) == target:
            combo.setCurrentIndex(index)
            return
    combo.setCurrentFont(QFont(default_body_text_font_family()))


def prompt_app_settings(
    parent: QWidget,
    current_theme: str,
    current_size: int,
    current_family: str,
    *,
    on_save: Optional[Callable[[AppSettings], None]] = None,
    min_width: int = 400,
) -> Optional[AppSettings]:
    dialog = _create_dialog(parent, 'Settings', min_width=min_width)
    initial = AppSettings(
        theme=normalize_theme_name(current_theme),
        size=current_size,
        family=normalize_body_text_font_family(current_family),
    )
    last_saved = initial

    layout = QFormLayout(dialog)
    theme_combo = ArrowComboBox()
    theme_combo.setMinimumWidth(min_width - 48)
    for theme_name in THEME_OPTIONS:
        theme_combo.addItem(THEME_LABELS[theme_name], theme_name)
    theme_combo.setCurrentIndex(THEME_OPTIONS.index(initial.theme))
    layout.addRow('Theme', theme_combo)

    family_combo = ArrowFontComboBox()
    family_combo.setEditable(False)
    family_combo.setFontFilters(QFontComboBox.MonospacedFonts)
    family_combo.setMinimumWidth(min_width - 48)
    _select_monospace_family(family_combo, initial.family)
    layout.addRow('Editor Font Family', family_combo)

    spin = GlyphSpinBox()
    spin.setRange(BODY_TEXT_FONT_SIZE_MIN, BODY_TEXT_FONT_SIZE_MAX)
    spin.setValue(initial.size)
    spin.setMinimumWidth(120)
    layout.addRow('Editor Font Size (px)', spin)

    def current_settings() -> AppSettings:
        return AppSettings(
            theme=normalize_theme_name(theme_combo.currentData()),
            size=spin.value(),
            family=normalize_body_text_font_family(family_combo.currentFont().family()),
        )

    buttons = QDialogButtonBox(
        QDialogButtonBox.Apply | QDialogButtonBox.Save | QDialogButtonBox.Close,
        parent=dialog,
    )
    apply_btn = buttons.button(QDialogButtonBox.Apply)

    def update_apply_enabled() -> None:
        if apply_btn is not None:
            apply_btn.setEnabled(current_settings() != last_saved)

    def commit_settings(settings: AppSettings) -> None:
        nonlocal last_saved
        if settings == last_saved:
            return
        if on_save is not None:
            on_save(settings)
        last_saved = settings
        update_apply_enabled()

    def do_apply() -> None:
        commit_settings(current_settings())

    if apply_btn is not None:
        apply_btn.clicked.connect(do_apply)
        apply_btn.setEnabled(False)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)

    theme_combo.currentIndexChanged.connect(lambda _i: update_apply_enabled())
    family_combo.currentFontChanged.connect(lambda _f: update_apply_enabled())
    spin.valueChanged.connect(lambda _v: update_apply_enabled())

    theme_combo.setFocus()

    if dialog.exec_() != QDialog.Accepted:
        return None
    commit_settings(current_settings())
    return last_saved


def show_about_dialog(parent: QWidget) -> None:
    dialog = _create_dialog(parent, 'About', min_width=360)

    layout = QVBoxLayout(dialog)
    layout.setSpacing(8)

    title = QLabel(APP_NAME)
    title.setAlignment(Qt.AlignCenter)
    layout.addWidget(title)

    version = QLabel(f'Version {APP_VERSION}')
    version.setAlignment(Qt.AlignCenter)
    layout.addWidget(version)

    link = QLabel(f'<a href="{GITHUB_URL}">{GITHUB_URL}</a>')
    link.setAlignment(Qt.AlignCenter)
    link.setOpenExternalLinks(True)
    link.setTextInteractionFlags(Qt.TextBrowserInteraction)
    layout.addWidget(link)

    buttons = QDialogButtonBox(QDialogButtonBox.Ok, parent=dialog)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)

    dialog.exec_()
