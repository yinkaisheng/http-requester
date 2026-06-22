#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QToolTip, QWidget

_tray_icon: Optional[QSystemTrayIcon] = None


def show_system_tip(
    title: str,
    message: str,
    *,
    msecs: int = 5000,
    widget: Optional[QWidget] = None,
) -> None:
    """Non-modal system notification; falls back to a tooltip near *widget*."""
    global _tray_icon
    if QSystemTrayIcon.isSystemTrayAvailable():
        if _tray_icon is None:
            _tray_icon = QSystemTrayIcon()
            icon = QApplication.windowIcon()
            if not icon.isNull():
                _tray_icon.setIcon(icon)
        if not _tray_icon.icon().isNull():
            _tray_icon.showMessage(title, message, QSystemTrayIcon.Information, msecs)
            return

    anchor = widget or QApplication.activeWindow()
    if anchor is not None:
        pos = anchor.mapToGlobal(anchor.rect().center())
        QToolTip.showText(pos, f'{title}\n{message}', anchor, anchor.rect(), msecs)
