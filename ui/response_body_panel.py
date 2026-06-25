#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QClipboard, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.http_models import is_text_body
from storage.app_config import get_app_config
from i18n import tr
from ui.dialog_i18n import get_save_file_name, message_warning
from ui.headers_editor import (
    _compact_action_button,
    add_section_header_widget,
    configure_section_header_layout,
)
from ui.notifications import show_system_tip

_VIEW_RAW = 0
_VIEW_JSON = 1
_VIEW_JSON_TREE = 2

_CONTENT_TYPE_EXTENSIONS = {
    'text/html': '.html',
    'text/plain': '.txt',
    'text/css': '.css',
    'text/javascript': '.js',
    'text/xml': '.xml',
    'text/csv': '.csv',
    'application/json': '.json',
    'application/xml': '.xml',
    'application/javascript': '.js',
    'application/pdf': '.pdf',
    'application/zip': '.zip',
    'application/gzip': '.gz',
    'application/x-gzip': '.gz',
    'application/x-bzip2': '.bz2',
    'application/x-tar': '.tar',
    'application/x-www-form-urlencoded': '.txt',
    'image/png': '.png',
    'image/jpeg': '.jpg',
    'image/gif': '.gif',
    'image/webp': '.webp',
    'image/svg+xml': '.svg',
    'image/x-icon': '.ico',
    'image/bmp': '.bmp',
    'audio/mpeg': '.mp3',
    'audio/wav': '.wav',
    'audio/ogg': '.ogg',
    'video/mp4': '.mp4',
    'video/webm': '.webm',
    'application/octet-stream': '.bin',
}


def _guess_file_extension(headers: Dict[str, str]) -> str:
    for name, value in headers.items():
        if name.lower() != 'content-type':
            continue
        media_type = value.split(';', 1)[0].strip().lower()
        return _CONTENT_TYPE_EXTENSIONS.get(media_type, '.bin')
    return '.bin'


def _is_image_content_type(headers: Dict[str, str]) -> bool:
    for name, value in headers.items():
        if name.lower() != 'content-type':
            continue
        media_type = value.split(';', 1)[0].strip().lower()
        if media_type.startswith('image/'):
            return True
    return False


def _ascii_repr(chunk: bytes) -> str:
    return ''.join(chr(byte) if 32 <= byte < 127 else '.' for byte in chunk)


def format_hex_preview(
    data: bytes,
    preview_bytes: Optional[int] = None,
    line_width: Optional[int] = None,
) -> str:
    cfg = get_app_config()
    if preview_bytes is None:
        preview_bytes = cfg.binary_hex_preview_bytes
    if line_width is None:
        line_width = cfg.binary_hex_line_width
    preview = data[:preview_bytes]
    hex_column_width = line_width * 3 - 1
    lines = []
    for offset in range(0, len(preview), line_width):
        chunk = preview[offset:offset + line_width]
        hex_part = ' '.join(f'{byte:02x}' for byte in chunk).ljust(hex_column_width)
        ascii_part = _ascii_repr(chunk).ljust(line_width)
        lines.append(f'{offset:08x}  {hex_part}  {ascii_part}')
    if len(data) > preview_bytes:
        remaining = len(data) - preview_bytes
        lines.append(tr('response.hex_more_bytes', count=remaining, total=len(data)))
    return '\n'.join(lines)


def _looks_like_json(body_text: str) -> bool:
    stripped = body_text.strip()
    if not stripped or stripped[0] not in ('{', '['):
        return False
    try:
        json.loads(body_text)
        return True
    except (json.JSONDecodeError, TypeError, ValueError):
        return False


def _pretty_print_json_body(body_text: str) -> str:
    if len(body_text.encode('utf-8')) > get_app_config().json_format_max_bytes:
        return body_text
    if not _looks_like_json(body_text):
        return body_text
    try:
        parsed = json.loads(body_text)
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        return body_text


def _json_type_label(value: Any) -> str:
    if isinstance(value, dict):
        return '{...}'
    if isinstance(value, list):
        return f'[{len(value)}]'
    if isinstance(value, str):
        preview = value.replace('\n', '\\n')
        if len(preview) > 80:
            preview = preview[:77] + '...'
        return f'"{preview}"'
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def _append_json_children(parent: QTreeWidgetItem, value: Any) -> None:
    if isinstance(value, dict):
        parent.setData(0, Qt.UserRole, 'object')
        for child_key, child_value in value.items():
            child = QTreeWidgetItem(parent, [str(child_key), _json_type_label(child_value)])
            _append_json_children(child, child_value)
    elif isinstance(value, list):
        parent.setData(0, Qt.UserRole, 'array')
        for index, child_value in enumerate(value):
            child = QTreeWidgetItem(parent, [str(index), _json_type_label(child_value)])
            _append_json_children(child, child_value)
    elif isinstance(value, str):
        parent.setData(0, Qt.UserRole, 'string')
        parent.setData(1, Qt.UserRole, value)
    elif isinstance(value, bool):
        parent.setData(0, Qt.UserRole, 'bool')
    elif value is None:
        parent.setData(0, Qt.UserRole, 'null')
    else:
        parent.setData(0, Qt.UserRole, 'number')


def _populate_json_tree(tree: QTreeWidget, parsed: Any) -> None:
    tree.clear()
    if isinstance(parsed, dict):
        for key, value in parsed.items():
            item = QTreeWidgetItem(tree, [str(key), _json_type_label(value)])
            _append_json_children(item, value)
    elif isinstance(parsed, list):
        for index, value in enumerate(parsed):
            item = QTreeWidgetItem(tree, [str(index), _json_type_label(value)])
            _append_json_children(item, value)
    else:
        item = QTreeWidgetItem(tree, ['(root)', _json_type_label(parsed)])
        _append_json_children(item, parsed)


class _ImagePreviewWidget(QWidget):
    """Paint pixmap scaled-to-fit — no sizeHint impact on parent layout."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None

    def set_pixmap(self, pixmap: Optional[QPixmap]) -> None:
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._pixmap is None:
            return
        pm = self._pixmap
        if pm.width() <= self.width() and pm.height() <= self.height():
            pix = pm
        else:
            pix = pm.scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        x = (self.width() - pix.width()) // 2
        y = (self.height() - pix.height()) // 2
        painter = QPainter(self)
        painter.drawPixmap(x, y, pix)
        painter.end()


class ResponseBodyPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._raw_body = ''
        self._headers: Dict[str, str] = {}
        self._raw_bytes: bytes = b''
        self._is_image = False
        self._is_binary_non_image = False
        self._original_pixmap: Optional[QPixmap] = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.view_group = QButtonGroup(self)
        self.radio_raw = QRadioButton(tr('response.raw'))
        self.radio_json = QRadioButton(tr('response.json'))
        self.radio_tree = QRadioButton(tr('response.json_tree'))
        self.radio_raw.setChecked(True)
        for view_id, radio in enumerate([self.radio_raw, self.radio_json, self.radio_tree]):
            self.view_group.addButton(radio, view_id)

        self.save_raw_btn = _compact_action_button(tr('response.save_raw'))
        self.save_raw_btn.setVisible(False)
        self.save_raw_btn.clicked.connect(self._save_raw)

        layout.addWidget(self._build_header_row())

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setObjectName('bodyTextEdit')
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlaceholderText(tr('response.placeholder'))
        self.stack.addWidget(self.text_edit)

        self._tree_page = QWidget()
        tree_layout = QVBoxLayout(self._tree_page)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(0)

        self._tree_splitter = QSplitter(Qt.Vertical)
        tree_layout.addWidget(self._tree_splitter, 1)

        self.json_tree = QTreeWidget()
        self.json_tree.setObjectName('jsonTree')
        self.json_tree.setHeaderLabels([tr('response.key'), tr('response.value')])
        self.json_tree.setColumnWidth(0, 200)
        self.json_tree.setAlternatingRowColors(True)
        self.json_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.json_tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self.json_tree.itemClicked.connect(self._on_tree_item_clicked)
        self._tree_splitter.addWidget(self.json_tree)

        self.string_detail = QPlainTextEdit()
        self.string_detail.setObjectName('bodyTextEdit')
        self.string_detail.setReadOnly(True)
        self.string_detail.setVisible(False)
        self._tree_splitter.addWidget(self.string_detail)

        self.stack.addWidget(self._tree_page)

        self._image_page = _ImagePreviewWidget()
        self._image_page.setMinimumSize(0, 0)
        self.stack.addWidget(self._image_page)

        self.view_group.buttonClicked.connect(self._on_view_changed)

    def _build_header_row(self) -> QWidget:
        row = QWidget()
        header_layout = QHBoxLayout(row)
        configure_section_header_layout(header_layout)
        self._title_label = QLabel(tr('response.response_body'))
        self._title_label.setObjectName('sectionTitle')
        self._title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        add_section_header_widget(header_layout, self._title_label)
        for radio in (self.radio_raw, self.radio_json, self.radio_tree):
            add_section_header_widget(header_layout, radio)
        add_section_header_widget(header_layout, self.save_raw_btn)
        header_layout.addStretch()
        return row

    def retranslate_ui(self) -> None:
        self._title_label.setText(tr('response.response_body'))
        self.radio_raw.setText(tr('response.raw'))
        self.radio_json.setText(tr('response.json'))
        self.radio_tree.setText(tr('response.json_tree'))
        self.save_raw_btn.setText(tr('response.save_raw'))
        self.text_edit.setPlaceholderText(tr('response.placeholder'))
        self.json_tree.setHeaderLabels([tr('response.key'), tr('response.value')])

    def _has_body(self) -> bool:
        """Whether there is response content to save."""
        return bool(self._raw_body) or bool(self._raw_bytes)

    def _body_byte_size(self) -> int:
        if self._raw_bytes:
            return len(self._raw_bytes)
        return len(self._raw_body.encode('utf-8'))

    def _exceeds_json_format_limit(self) -> bool:
        return self._body_byte_size() > get_app_config().json_format_max_bytes

    def _json_format_limit_tip(self) -> str:
        limit_bytes = get_app_config().json_format_max_bytes
        if limit_bytes % (1024 * 1024) == 0:
            limit_label = f'{limit_bytes // (1024 * 1024)} {tr("response.mb_unit")}'
        elif limit_bytes % 1024 == 0:
            limit_label = f'{limit_bytes // 1024} {tr("response.kb_unit")}'
        else:
            limit_label = f'{limit_bytes} {tr("response.bytes_unit")}'
        return tr('response.json_limit_tip', limit=limit_label)

    def _is_body_json(self) -> bool:
        return _looks_like_json(self._raw_body)

    def _notify_json_format_limit(self) -> None:
        show_system_tip(tr('main.window_title'), self._json_format_limit_tip(), widget=self)

    def _revert_to_raw_view(self) -> None:
        self.view_group.blockSignals(True)
        self.radio_raw.setChecked(True)
        self.view_group.blockSignals(False)

    def _raw_display_text(self) -> str:
        if self._is_binary_non_image:
            header = self._raw_body.strip() or tr('response.binary_data', count=len(self._raw_bytes))
            return f'{header}\n\n{format_hex_preview(self._raw_bytes)}'
        return self._raw_body

    def _set_view_enabled(self) -> None:
        if self._is_image or self._is_binary_non_image:
            self.radio_json.setEnabled(False)
            self.radio_tree.setEnabled(False)
            return
        is_json = self._is_body_json()
        self.radio_json.setEnabled(is_json)
        self.radio_tree.setEnabled(is_json)
        if not is_json and self.view_group.checkedId() != _VIEW_RAW:
            self._revert_to_raw_view()

    def set_body(
        self,
        body_text: str,
        headers: Optional[Dict[str, str]] = None,
        raw_bytes: bytes = b'',
    ) -> None:
        self._raw_body = body_text
        self._headers = dict(headers or {})
        self._raw_bytes = raw_bytes
        self._is_image = bool(raw_bytes) and _is_image_content_type(self._headers)
        self._is_binary_non_image = (
            bool(raw_bytes) and not self._is_image and not is_text_body(raw_bytes)
        )
        self._original_pixmap = None
        self._image_page.set_pixmap(None)
        self._image_page.setToolTip('')
        self._hide_string_detail()
        self.save_raw_btn.setVisible(self._has_body())
        self._set_view_enabled()
        # Auto-switch to JSON view if body is JSON and within format limit
        if self.radio_json.isEnabled() and not self._exceeds_json_format_limit():
            self.radio_json.setChecked(True)
        else:
            self.radio_raw.setChecked(True)
        if self._is_image:
            self._load_image()
        self._apply_current_view()

    def clear(self) -> None:
        self._raw_body = ''
        self._headers = {}
        self._raw_bytes = b''
        self._is_image = False
        self._is_binary_non_image = False
        self._original_pixmap = None
        self._image_page.set_pixmap(None)
        self._image_page.setToolTip('')
        self.radio_raw.setChecked(True)
        self.radio_json.setEnabled(True)
        self.radio_tree.setEnabled(True)
        self.text_edit.clear()
        self.json_tree.clear()
        self._hide_string_detail()
        self.save_raw_btn.setVisible(False)
        self.stack.setCurrentIndex(0)

    def _on_view_changed(self) -> None:
        self._hide_string_detail()
        view_id = self.view_group.checkedId()
        if view_id in (_VIEW_JSON, _VIEW_JSON_TREE) and self._exceeds_json_format_limit():
            self._notify_json_format_limit()
            self._revert_to_raw_view()
        self._apply_current_view()

    def _apply_current_view(self) -> None:
        if self._is_image:
            self.stack.setCurrentIndex(2)
            self._update_image_display()
            return
        view_id = self.view_group.checkedId()
        if view_id == _VIEW_RAW:
            self.stack.setCurrentIndex(0)
            self.text_edit.setPlainText(self._raw_display_text())
            return
        if view_id == _VIEW_JSON:
            self.stack.setCurrentIndex(0)
            if self._exceeds_json_format_limit():
                self.text_edit.setPlainText(self._raw_body)
            else:
                self.text_edit.setPlainText(_pretty_print_json_body(self._raw_body))
            return
        self.stack.setCurrentIndex(1)
        self._refresh_json_tree()

    def _refresh_json_tree(self) -> None:
        self.json_tree.clear()
        self._hide_string_detail()
        if not self._raw_body.strip():
            return
        if self._exceeds_json_format_limit():
            return
        try:
            parsed = json.loads(self._raw_body)
        except (json.JSONDecodeError, TypeError):
            error_item = QTreeWidgetItem(self.json_tree, [tr('response.tree_invalid_json'), tr('response.tree_invalid_json_value')])
            error_item.setData(0, Qt.UserRole, 'error')
            return
        _populate_json_tree(self.json_tree, parsed)
        self.json_tree.expandToDepth(1)

    def _load_image(self) -> None:
        pixmap = QPixmap()
        if pixmap.loadFromData(self._raw_bytes):
            self._original_pixmap = pixmap
            self._image_page.set_pixmap(pixmap)
            self._image_page.setToolTip(f'{pixmap.width()} × {pixmap.height()}')

    def _update_image_display(self) -> None:
        """Called when switching to the image page — triggers a repaint."""
        if self._original_pixmap is not None:
            self._image_page.update()

    def _tree_item_at_pos(self, pos) -> Optional[QTreeWidgetItem]:
        item = self.json_tree.itemAt(pos)
        return item

    def _on_tree_context_menu(self, pos) -> None:
        item = self._tree_item_at_pos(pos)
        if item is None:
            return
        menu = QMenu(self)
        expand_action = menu.addAction(tr('response.tree_expand'))
        expand_all_action = menu.addAction(tr('response.tree_expand_all'))
        collapse_action = menu.addAction(tr('response.tree_collapse'))
        collapse_all_action = menu.addAction(tr('response.tree_collapse_all'))
        menu.addSeparator()
        copy_key_action = menu.addAction(tr('response.tree_copy_key'))
        copy_val_action = menu.addAction(tr('response.tree_copy_value'))
        copy_kv_action = menu.addAction(tr('response.tree_copy_kv'))
        copy_json_action = menu.addAction(tr('response.tree_copy_json'))
        action = menu.exec_(self.json_tree.viewport().mapToGlobal(pos))
        if action == expand_action:
            item.setExpanded(True)
        elif action == expand_all_action:
            self._expand_item_recursive(item)
        elif action == collapse_action:
            item.setExpanded(False)
        elif action == collapse_all_action:
            self._collapse_item_recursive(item)
        elif action == copy_key_action:
            self._copy_text(item.text(0))
        elif action == copy_val_action:
            self._copy_text(self._item_value_for_copy(item))
        elif action == copy_kv_action:
            key = item.text(0)
            val = self._item_value_for_copy(item)
            self._copy_text(f'{key}: {val}')
        elif action == copy_json_action:
            self._copy_text(self._item_json_pair(item))

    @staticmethod
    def _expand_item_recursive(item: QTreeWidgetItem) -> None:
        item.setExpanded(True)
        for index in range(item.childCount()):
            ResponseBodyPanel._expand_item_recursive(item.child(index))

    @staticmethod
    def _collapse_item_recursive(item: QTreeWidgetItem) -> None:
        item.setExpanded(False)
        for index in range(item.childCount()):
            ResponseBodyPanel._collapse_item_recursive(item.child(index))

    @staticmethod
    def _copy_text(text: str) -> None:
        if text:
            QApplication.clipboard().setText(text)

    @staticmethod
    def _item_raw_value(item: QTreeWidgetItem) -> str:
        if item.data(0, Qt.UserRole) == 'string':
            raw = item.data(1, Qt.UserRole)
            if isinstance(raw, str):
                return raw
        return item.text(1)

    @staticmethod
    def _item_value_for_copy(item: QTreeWidgetItem) -> str:
        """Human-readable value; formatted JSON for container nodes, raw text for leaves."""
        kind = item.data(0, Qt.UserRole)
        if kind in ('object', 'array'):
            return json.dumps(
                ResponseBodyPanel._json_value(item), ensure_ascii=False, indent=2
            )
        return ResponseBodyPanel._item_raw_value(item)

    @staticmethod
    def _json_value(item: QTreeWidgetItem) -> Any:
        """Recursively reconstruct the actual JSON value from the tree item."""
        kind = item.data(0, Qt.UserRole)
        if kind == 'string':
            val = item.data(1, Qt.UserRole)
            return val if isinstance(val, str) else item.text(1)
        if kind == 'null':
            return None
        if kind == 'bool':
            return item.text(1) == 'true'
        if kind == 'number':
            display = item.text(1)
            try:
                return int(display)
            except ValueError:
                try:
                    return float(display)
                except ValueError:
                    return display
        if kind == 'object':
            obj = {}
            for i in range(item.childCount()):
                child = item.child(i)
                obj[child.text(0)] = ResponseBodyPanel._json_value(child)
            return obj
        if kind == 'array':
            arr = []
            for i in range(item.childCount()):
                child = item.child(i)
                arr.append(ResponseBodyPanel._json_value(child))
            return arr
        return item.text(1)

    @staticmethod
    def _item_json_pair(item: QTreeWidgetItem) -> str:
        key = item.text(0)
        return json.dumps({key: ResponseBodyPanel._json_value(item)}, ensure_ascii=False, indent=2)

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        if item.data(0, Qt.UserRole) != 'string':
            self._hide_string_detail()
            return
        text = item.data(1, Qt.UserRole)
        if not isinstance(text, str):
            self._hide_string_detail()
            return
        self.string_detail.setPlainText(text)
        if not self.string_detail.isVisible():
            self.string_detail.setVisible(True)
            # Default to ~4 lines
            line_h = self.string_detail.fontMetrics().lineSpacing()
            margins = self.string_detail.contentsMargins()
            frame = self.string_detail.frameWidth() * 2
            doc_margin = self.string_detail.document().documentMargin()
            edit_h = int(line_h * 4 + doc_margin * 2 + margins.top() + margins.bottom() + frame + 2)
            total = self._tree_splitter.height()
            if total > edit_h:
                self._tree_splitter.setSizes([total - edit_h, edit_h])
            else:
                self._tree_splitter.setSizes([total // 2, total // 2])

    def _hide_string_detail(self) -> None:
        self.string_detail.clear()
        self.string_detail.setVisible(False)

    def _save_raw(self) -> None:
        if self._raw_bytes:
            data = self._raw_bytes
        elif self._raw_body:
            data = self._raw_body.encode('utf-8')
        else:
            return
        default_name = f'response{_guess_file_extension(self._headers)}'
        path, _ = get_save_file_name(self, tr('response.save_title'), default_name)
        if not path:
            return
        try:
            with open(path, 'wb') as f:
                f.write(data)
        except OSError as e:
            message_warning(self, tr('response.save_error_title'), tr('response.save_error_body', error=str(e)))
