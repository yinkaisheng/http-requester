#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QWidget,
)

from ui.widgets import GlyphSpinBox
from ui.theme import (
    BODY_TEXT_FONT_SIZE_MAX,
    BODY_TEXT_FONT_SIZE_MIN,
)


def prompt_text(
    parent: QWidget,
    title: str,
    label: str,
    initial: str = '',
    *,
    min_width: int = 400,
) -> Optional[str]:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(min_width)

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


def prompt_body_text_font_size(
    parent: QWidget,
    current: int,
    *,
    min_width: int = 400,
) -> Optional[int]:
    dialog = QDialog(parent)
    dialog.setWindowTitle('Settings')
    dialog.setMinimumWidth(min_width)

    layout = QFormLayout(dialog)
    spin = GlyphSpinBox()
    spin.setRange(BODY_TEXT_FONT_SIZE_MIN, BODY_TEXT_FONT_SIZE_MAX)
    spin.setValue(current)
    spin.setMinimumWidth(120)
    layout.addRow('Editor font size (px)', spin)

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)

    spin.setFocus()

    if dialog.exec_() != QDialog.Accepted:
        return None
    return spin.value()
