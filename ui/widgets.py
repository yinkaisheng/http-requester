#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from PyQt5.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPalette, QPen, QPolygon
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QListView,
    QSpinBox,
    QStyle,
    QStyleOptionButton,
    QStyleOptionComboBox,
    QStyleOptionSpinBox,
    QStyleOptionViewItem,
    QStyledItemDelegate,
)

from ui.theme import popup_list_font

ARROW_GLYPH_BASE_PX = 8
ARROW_GLYPH_HEIGHT_PX = 6
COMBO_DROPDOWN_WIDTH_PX = 26
CHECK_MARK_COLOR = QColor('#ffffff')


def _arrow_color(widget) -> QColor:
    return widget.palette().color(QPalette.WindowText)


def _paint_check_mark(painter: QPainter, rect: QRect) -> None:
    side = min(rect.width(), rect.height())
    margin = side * 0.2
    x0 = rect.x() + margin
    y0 = rect.y() + side * 0.54
    x1 = rect.x() + side * 0.4
    y1 = rect.y() + side * 0.74
    x2 = rect.x() + side - margin
    y2 = rect.y() + side * 0.3

    painter.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(CHECK_MARK_COLOR)
    pen.setWidthF(max(1.6, side * 0.12))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.drawLine(QPointF(x0, y0), QPointF(x1, y1))
    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def _paint_triangle(
    painter: QPainter,
    cx: float,
    cy: float,
    base_w: int,
    height: int,
    *,
    up: bool,
) -> None:
    if base_w < 4 or height < 4:
        return
    half_base = base_w / 2.0
    half_height = height / 2.0
    if up:
        y_top = cy - half_height
        y_bottom = cy + half_height
        points = [
            QPoint(int(round(cx)), int(round(y_top))),
            QPoint(int(round(cx - half_base)), int(round(y_bottom))),
            QPoint(int(round(cx + half_base)), int(round(y_bottom))),
        ]
    else:
        y_top = cy - half_height
        y_bottom = cy + half_height
        points = [
            QPoint(int(round(cx - half_base)), int(round(y_top))),
            QPoint(int(round(cx + half_base)), int(round(y_top))),
            QPoint(int(round(cx)), int(round(y_bottom))),
        ]
    painter.drawPolygon(QPolygon(points))


class _AppFontItemDelegate(QStyledItemDelegate):
    """Force combo popup rows to use the same pixel size as global QSS."""

    def initStyleOption(self, option: QStyleOptionViewItem, index) -> None:
        super().initStyleOption(option, index)
        option.font = popup_list_font()


class ArrowComboBox(QComboBox):
    """Paint a dropdown glyph after the style pass; Fusion+QSS often hides native arrows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_popup_view()

    def _setup_popup_view(self) -> None:
        view = QListView(self)
        view.setObjectName('comboPopupListView')
        view.setItemDelegate(_AppFontItemDelegate(view))
        self.setView(view)

    def _sync_popup_font(self) -> None:
        font = popup_list_font()
        view = self.view()
        if view is not None:
            view.setFont(font)

    def showPopup(self) -> None:
        self._sync_popup_font()
        super().showPopup()
        view = self.view()
        if view is not None:
            popup = view.window()
            if popup is not view:
                popup.setFont(popup_list_font())

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        style = self.style()
        arrow_rect = style.subControlRect(
            QStyle.CC_ComboBox, opt, QStyle.SC_ComboBoxArrow, self
        )
        if arrow_rect.isNull() or arrow_rect.width() < 2:
            arrow_rect = QRect(
                self.width() - COMBO_DROPDOWN_WIDTH_PX,
                0,
                COMBO_DROPDOWN_WIDTH_PX,
                self.height(),
            )
        if arrow_rect.isNull() or arrow_rect.width() < 2:
            return

        center = QRectF(arrow_rect).center()
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(Qt.NoPen)
            painter.setBrush(_arrow_color(self))
            _paint_triangle(
                painter,
                center.x(),
                center.y(),
                ARROW_GLYPH_BASE_PX,
                ARROW_GLYPH_HEIGHT_PX,
                up=False,
            )
        finally:
            painter.end()


class GlyphSpinBox(QSpinBox):
    """Paint up/down glyphs after the style pass; Fusion+QSS often hides native arrows."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        opt = QStyleOptionSpinBox()
        self.initStyleOption(opt)
        style = self.style()
        up_rect = style.subControlRect(QStyle.CC_SpinBox, opt, QStyle.SC_SpinBoxUp, self)
        down_rect = style.subControlRect(QStyle.CC_SpinBox, opt, QStyle.SC_SpinBoxDown, self)
        if up_rect.isNull() or down_rect.isNull():
            return

        up_center = QRectF(up_rect).center()
        down_center = QRectF(down_rect).center()
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(Qt.NoPen)
            painter.setBrush(_arrow_color(self))
            _paint_triangle(
                painter,
                up_center.x(),
                up_center.y(),
                ARROW_GLYPH_BASE_PX,
                ARROW_GLYPH_HEIGHT_PX,
                up=True,
            )
            _paint_triangle(
                painter,
                down_center.x(),
                down_center.y(),
                ARROW_GLYPH_BASE_PX,
                ARROW_GLYPH_HEIGHT_PX,
                up=False,
            )
        finally:
            painter.end()


class AccentCheckBox(QCheckBox):
    """Checkbox with accent indicator and a painted check mark when selected."""

    def __init__(self, text: str = '', parent=None):
        super().__init__(text, parent)
        self.setObjectName('sslVerifyCheck')
        self.setFocusPolicy(Qt.NoFocus)
        self.stateChanged.connect(lambda _state: self.update())

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self.isChecked():
            return

        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        indicator = self.style().subElementRect(
            QStyle.SE_CheckBoxIndicator, opt, self
        )
        if indicator.isNull() or indicator.width() < 2:
            return

        painter = QPainter(self)
        try:
            _paint_check_mark(painter, indicator)
        finally:
            painter.end()
