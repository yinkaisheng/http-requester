#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QLineEdit,
    QWidget,
)

from ui.widgets import ArrowFontComboBox, GlyphSpinBox
from ui.theme import (
    BODY_TEXT_FONT_SIZE_MAX,
    BODY_TEXT_FONT_SIZE_MIN,
    default_body_text_font_family,
    normalize_body_text_font_family,
)


@dataclass(frozen=True)
class EditorFontSettings:
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
    return text or None


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


def prompt_editor_settings(
    parent: QWidget,
    current_size: int,
    current_family: str,
    *,
    min_width: int = 400,
) -> Optional[EditorFontSettings]:
    dialog = _create_dialog(parent, 'Settings', min_width=min_width)

    layout = QFormLayout(dialog)
    family_combo = ArrowFontComboBox()
    family_combo.setFontFilters(QFontComboBox.MonospacedFonts)
    family_combo.setMinimumWidth(min_width - 48)
    _select_monospace_family(family_combo, current_family)
    layout.addRow('Editor Font Family', family_combo)

    spin = GlyphSpinBox()
    spin.setRange(BODY_TEXT_FONT_SIZE_MIN, BODY_TEXT_FONT_SIZE_MAX)
    spin.setValue(current_size)
    spin.setMinimumWidth(120)
    layout.addRow('Editor Font Size (px)', spin)

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)

    family_combo.setFocus()

    if dialog.exec_() != QDialog.Accepted:
        return None
    return EditorFontSettings(
        size=spin.value(),
        family=normalize_body_text_font_family(family_combo.currentFont().family()),
    )
