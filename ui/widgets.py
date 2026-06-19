#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from PyQt5.QtCore import QPoint, QRect, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPalette, QPolygon
from PyQt5.QtWidgets import (
    QComboBox,
    QSpinBox,
    QStyle,
    QStyleOptionComboBox,
    QStyleOptionSpinBox,
)

ARROW_GLYPH_BASE_PX = 8
ARROW_GLYPH_HEIGHT_PX = 6
COMBO_DROPDOWN_WIDTH_PX = 26


def _arrow_color(widget) -> QColor:
    return widget.palette().color(QPalette.WindowText)


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


class ArrowComboBox(QComboBox):
    """Paint a dropdown glyph after the style pass; Fusion+QSS often hides native arrows."""

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
