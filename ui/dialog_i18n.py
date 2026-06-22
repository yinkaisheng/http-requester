#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Translate Qt standard dialog buttons via strings.txt (no Qt .qm files)."""
from __future__ import annotations

from typing import Optional, Tuple

from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMessageBox,
    QPushButton,
    QWidget,
)

from i18n import register_retranslator, tr

_DIALOG_BUTTON_BOX_KEYS = {
    QDialogButtonBox.Ok: 'dialog.ok',
    QDialogButtonBox.Cancel: 'dialog.cancel',
    QDialogButtonBox.Apply: 'dialog.apply',
    QDialogButtonBox.Save: 'dialog.save',
    QDialogButtonBox.Close: 'dialog.close',
}

_FILE_DIALOG_BUTTON_KEYS = {
    'Open': 'dialog.open',
    '&Open': 'dialog.open',
    'Save': 'dialog.save',
    '&Save': 'dialog.save',
    'Cancel': 'dialog.cancel',
    '&Cancel': 'dialog.cancel',
}

_INSTALLED = False


def translate_button_box(button_box: QDialogButtonBox) -> None:
    for btn_flag, key in _DIALOG_BUTTON_BOX_KEYS.items():
        btn = button_box.button(btn_flag)
        if btn is not None:
            btn.setText(tr(key))


def _translate_file_dialog_buttons(dialog: QWidget) -> None:
    for button_box in dialog.findChildren(QDialogButtonBox):
        translate_button_box(button_box)
    for btn in dialog.findChildren(QPushButton):
        raw = btn.text()
        clean = raw.replace('&', '').split('(', 1)[0].strip()
        key = _FILE_DIALOG_BUTTON_KEYS.get(clean) or _FILE_DIALOG_BUTTON_KEYS.get(raw.replace('&', ''))
        if key is not None:
            btn.setText(tr(key))


def _retranslate_open_dialogs() -> None:
    app = QApplication.instance()
    if app is None:
        return
    for button_box in app.findChildren(QDialogButtonBox):
        translate_button_box(button_box)
    for dialog in app.findChildren(QFileDialog):
        _translate_file_dialog_buttons(dialog)


def _wrap_show_event(original):
    def show_event(self, event):
        if isinstance(self, QDialogButtonBox):
            translate_button_box(self)
        elif isinstance(self, QFileDialog):
            _translate_file_dialog_buttons(self)
        original(self, event)

    return show_event


def install_dialog_translations(app=None) -> None:
    del app  # kept for call-site compatibility
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    QDialogButtonBox.showEvent = _wrap_show_event(QDialogButtonBox.showEvent)
    QFileDialog.showEvent = _wrap_show_event(QFileDialog.showEvent)
    register_retranslator(_retranslate_open_dialogs)


def message_warning(parent: QWidget, title: str, text: str) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(title)
    box.setText(text)
    ok_btn = box.addButton(tr('dialog.ok'), QMessageBox.AcceptRole)
    box.setDefaultButton(ok_btn)
    box.exec_()


def message_info(parent: QWidget, title: str, text: str) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Information)
    box.setWindowTitle(title)
    box.setText(text)
    ok_btn = box.addButton(tr('dialog.ok'), QMessageBox.AcceptRole)
    box.setDefaultButton(ok_btn)
    box.exec_()


def ask_yes_no(
    parent: QWidget,
    title: str,
    text: str,
    *,
    default: int = QMessageBox.No,
) -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(text)
    yes_btn = box.addButton(tr('dialog.yes'), QMessageBox.YesRole)
    no_btn = box.addButton(tr('dialog.no'), QMessageBox.NoRole)
    box.setDefaultButton(yes_btn if default == QMessageBox.Yes else no_btn)
    box.exec_()
    return box.clickedButton() == yes_btn


def ask_yes_no_cancel(
    parent: QWidget,
    title: str,
    text: str,
    *,
    default: int = QMessageBox.Cancel,
) -> int:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(text)
    yes_btn = box.addButton(tr('dialog.yes'), QMessageBox.YesRole)
    no_btn = box.addButton(tr('dialog.no'), QMessageBox.NoRole)
    cancel_btn = box.addButton(tr('dialog.cancel'), QMessageBox.RejectRole)
    if default == QMessageBox.Yes:
        box.setDefaultButton(yes_btn)
    elif default == QMessageBox.No:
        box.setDefaultButton(no_btn)
    else:
        box.setDefaultButton(cancel_btn)
    box.exec_()
    clicked = box.clickedButton()
    if clicked == yes_btn:
        return QMessageBox.Yes
    if clicked == no_btn:
        return QMessageBox.No
    return QMessageBox.Cancel


def get_open_file_name(
    parent: QWidget,
    title: str,
    directory: str = '',
    file_filter: str = '',
) -> Tuple[str, str]:
    dialog = QFileDialog(parent, title, directory, file_filter)
    dialog.setFileMode(QFileDialog.ExistingFile)
    if dialog.exec_() == QDialog.Accepted:
        files = dialog.selectedFiles()
        if files:
            return files[0], file_filter
    return '', file_filter


def get_save_file_name(
    parent: QWidget,
    title: str,
    default_name: str = '',
    file_filter: str = '',
) -> Tuple[str, str]:
    dialog = QFileDialog(parent, title, '', file_filter)
    dialog.setAcceptMode(QFileDialog.AcceptSave)
    if default_name:
        dialog.selectFile(default_name)
    if dialog.exec_() == QDialog.Accepted:
        files = dialog.selectedFiles()
        if files:
            return files[0], file_filter
    return '', file_filter
