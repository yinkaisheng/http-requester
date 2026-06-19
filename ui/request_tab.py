#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QClipboard
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.http_models import DEFAULT_REQUEST_TIMEOUT_SECONDS, HTTP_METHODS, HistoryRecord, HttpRequest, HttpResponse
from pyqt_async_task import AsyncTask, MsgIDThreadExit
from services.curl_export import format_curl_linux_command
from services.http_service import send_request
from services.powershell_export import format_powershell_command
from storage.history_store import HistoryStore
from ui.body_editor import BodyEditor
from ui.headers_editor import (
    COPY_CURL_MENU_TEXT,
    COPY_POWERSHELL_MENU_TEXT,
    RequestHeadersPanel,
    _set_compact_table_header,
    attach_header_table_menu,
    fill_key_value_table,
)
from ui.widgets import AccentCheckBox, ArrowComboBox, GlyphSpinBox

MSG_HTTP_DONE = 1
DEFAULT_PANEL_RATIO = (1, 3)
STATUS_DISPLAY_MAX_LENGTH = 72


def _status_code_style_id(status_code: int) -> str:
    if 200 <= status_code < 300:
        return 'statusOk'
    if status_code < 500:
        return 'statusWarn'
    return 'statusError'


def _truncate_status_text(text: str, max_length: int = STATUS_DISPLAY_MAX_LENGTH) -> tuple[str, str]:
    full = text.strip()
    if len(full) <= max_length:
        return full, ''
    if max_length <= 1:
        return '…', full
    return full[: max_length - 1] + '…', full


def _ratio_sizes(total: int, ratio: tuple[int, int]) -> List[int]:
    if total <= 0:
        return []
    r1, r2 = ratio
    first = total * r1 // (r1 + r2)
    return [first, total - first]


def _valid_sizes(sizes) -> bool:
    return isinstance(sizes, list) and len(sizes) == 2 and all(
        isinstance(s, int) and s > 0 for s in sizes
    )


def _http_worker(signal, task_id, req: HttpRequest):
    resp = send_request(req)
    signal.emit((task_id, MSG_HTTP_DONE, resp))


def _format_response_body_text(resp: HttpResponse) -> str:
    body_text = resp.body_text()
    try:
        parsed = json.loads(body_text)
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        return body_text


def _response_snapshot(resp: HttpResponse) -> dict:
    return {
        'last_status': resp.status_code,
        'last_status_reason': resp.reason,
        'last_elapsed_ms': resp.elapsed_ms,
        'response_headers': dict(resp.headers),
        'response_body': _format_response_body_text(resp),
    }


class RequestTab(QWidget):
    record_saved = pyqtSignal(object)
    record_bound = pyqtSignal(str)

    def __init__(
        self,
        history_store: HistoryStore,
        async_task: AsyncTask,
        record: Optional[HistoryRecord] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.history_store = history_store
        self.async_task = async_task
        self.async_task.setMsgIDName(MSG_HTTP_DONE, 'MSG_HTTP_DONE')
        self.record_id: Optional[str] = record.id if record else None
        self._record = record
        self._init_ui()
        if record:
            self.load_record(record)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        toolbar = QHBoxLayout()
        self.method_combo = ArrowComboBox()
        self.method_combo.addItems(HTTP_METHODS)
        self.ssl_verify_check = AccentCheckBox('SSL Verify')
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText('https://api.example.com/path')
        timeout_row = QWidget()
        timeout_layout = QHBoxLayout(timeout_row)
        timeout_layout.setContentsMargins(0, 0, 0, 0)
        timeout_layout.setSpacing(4)
        timeout_label = QLabel('Timeout')
        timeout_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.timeout_spin = GlyphSpinBox()
        self.timeout_spin.setRange(1, 3600)
        self.timeout_spin.setValue(DEFAULT_REQUEST_TIMEOUT_SECONDS)
        self.timeout_spin.setSuffix('s')
        self.timeout_spin.setFixedWidth(72)
        timeout_layout.addWidget(timeout_label)
        timeout_layout.addWidget(self.timeout_spin)
        self.send_btn = QPushButton('Send')
        self.send_btn.setObjectName('primaryButton')
        self.send_btn.setFixedWidth(80)
        self.send_btn.clicked.connect(self._on_send_clicked)
        self.curl_btn = QPushButton('curl')
        self.curl_btn.setToolTip(COPY_CURL_MENU_TEXT)
        self.curl_btn.clicked.connect(self._copy_request_as_curl)
        self.pwsh_btn = QPushButton('pwsh')
        self.pwsh_btn.setToolTip(COPY_POWERSHELL_MENU_TEXT)
        self.pwsh_btn.clicked.connect(self._copy_request_as_powershell)
        self.send_btn.ensurePolished()
        toolbar_btn_height = self.send_btn.sizeHint().height()
        self.curl_btn.setFixedHeight(toolbar_btn_height)
        self.pwsh_btn.setFixedHeight(toolbar_btn_height)
        toolbar.addWidget(self.method_combo)
        toolbar.addWidget(self.ssl_verify_check)
        toolbar.addWidget(self.url_edit, 1)
        toolbar.addWidget(timeout_row)
        toolbar.addWidget(self.send_btn)
        toolbar.addWidget(self.curl_btn)
        toolbar.addWidget(self.pwsh_btn)
        layout.addLayout(toolbar)

        self.content_splitter = QSplitter(Qt.Horizontal)

        self.left_splitter = QSplitter(Qt.Vertical)
        self.headers_panel = RequestHeadersPanel(
            curl_copy_callback=self._copy_request_as_curl,
            powershell_copy_callback=self._copy_request_as_powershell,
        )
        self.body_editor = BodyEditor()
        self.left_splitter.addWidget(self.headers_panel)
        self.left_splitter.addWidget(self.body_editor)
        self.left_splitter.setStretchFactor(0, 1)
        self.left_splitter.setStretchFactor(1, 3)

        self.right_splitter = QSplitter(Qt.Vertical)
        self.response_headers_table = QTableWidget(0, 2)
        self.response_headers_table.setObjectName('headerTable')
        self.response_headers_table.setHorizontalHeaderLabels(['Header', 'Value'])
        self.response_headers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.response_headers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.response_headers_table.verticalHeader().setVisible(False)
        self.response_headers_table.setEditTriggers(QTableWidget.NoEditTriggers)
        _set_compact_table_header(self.response_headers_table, header_table=True)
        attach_header_table_menu(self.response_headers_table, key_col=0, value_col=1)

        self.response_body_edit = QPlainTextEdit()
        self.response_body_edit.setObjectName('bodyTextEdit')
        self.response_body_edit.setReadOnly(True)
        self.response_body_edit.setPlaceholderText('Response will appear here')

        response_body_block = QWidget()
        rb_layout = QVBoxLayout(response_body_block)
        rb_layout.setContentsMargins(0, 0, 0, 0)
        rb_layout.setSpacing(4)
        rb_header_row = QWidget()
        rb_header_row.setFixedHeight(BodyEditor.section_header_height())
        rb_header = QHBoxLayout(rb_header_row)
        rb_header.setContentsMargins(0, 0, 0, 0)
        rb_title = QLabel('Response Body')
        rb_title.setObjectName('sectionTitle')
        rb_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        rb_header.addWidget(rb_title)
        rb_header.addStretch()
        rb_layout.addWidget(rb_header_row)
        rb_layout.addWidget(self.response_body_edit, 1)

        response_headers_block = QWidget()
        rh_layout = QVBoxLayout(response_headers_block)
        rh_layout.setContentsMargins(0, 0, 0, 0)
        rh_layout.setSpacing(4)
        rh_header_row = QWidget()
        rh_header_row.setFixedHeight(BodyEditor.section_header_height())
        rh_header = QHBoxLayout(rh_header_row)
        rh_header.setContentsMargins(0, 0, 0, 0)
        rh_header.setSpacing(8)
        rh_title = QLabel('Response Headers')
        rh_title.setObjectName('sectionTitle')
        rh_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.status_label = QLabel()
        self.status_label.setObjectName('statusPending')
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._set_status_text('Waiting to send request')
        rh_header.addWidget(rh_title)
        rh_header.addStretch()
        rh_header.addWidget(self.status_label)
        rh_layout.addWidget(rh_header_row)
        rh_layout.addWidget(self.response_headers_table, 1)

        self.right_splitter.addWidget(response_headers_block)
        self.right_splitter.addWidget(response_body_block)
        self.right_splitter.setStretchFactor(0, 1)
        self.right_splitter.setStretchFactor(1, 3)

        self.content_splitter.addWidget(self.left_splitter)
        self.content_splitter.addWidget(self.right_splitter)
        self.content_splitter.setStretchFactor(0, 1)
        self.content_splitter.setStretchFactor(1, 1)
        self.content_splitter.setSizes([500, 500])
        layout.addWidget(self.content_splitter, 1)

    def get_splitter_state(self) -> dict:
        return {
            'content': self.content_splitter.sizes(),
            'left': self.left_splitter.sizes(),
            'right': self.right_splitter.sizes(),
        }

    def set_splitter_state(self, state: Optional[dict]) -> None:
        if not state:
            return
        content = state.get('content')
        left = state.get('left')
        right = state.get('right')
        if _valid_sizes(content):
            self.content_splitter.setSizes(content)
        if _valid_sizes(left):
            self.left_splitter.setSizes(left)
        if _valid_sizes(right):
            self.right_splitter.setSizes(right)

    def apply_default_splitter_sizes(self) -> None:
        def _apply() -> None:
            lh = self.left_splitter.height()
            rh = self.right_splitter.height()
            cw = self.content_splitter.width()
            if lh <= 0 or rh <= 0 or cw <= 0:
                QTimer.singleShot(50, _apply)
                return
            self.left_splitter.setSizes(_ratio_sizes(lh, DEFAULT_PANEL_RATIO))
            self.right_splitter.setSizes(_ratio_sizes(rh, DEFAULT_PANEL_RATIO))
            self.content_splitter.setSizes([cw // 2, cw - cw // 2])

        QTimer.singleShot(0, _apply)

    def set_content_splitter_sizes(self, sizes: List[int]) -> None:
        if _valid_sizes(sizes):
            self.content_splitter.setSizes(sizes)

    def get_content_splitter_sizes(self) -> List[int]:
        return self.content_splitter.sizes()

    def tab_title(self) -> str:
        url = self.url_edit.text().strip()
        if self._record and self._record.name:
            return self._record.name
        if url:
            return url
        return 'New Request'

    def load_record(self, record: HistoryRecord) -> None:
        self._record = record
        self.record_id = record.id
        self.load_request(record.request, record.sent_headers)
        self._apply_saved_response(
            record.last_status,
            record.last_status_reason,
            record.last_elapsed_ms,
            record.response_headers,
            record.response_body,
        )

    def load_request(
        self,
        req: HttpRequest,
        sent_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        idx = self.method_combo.findText(req.method.upper())
        if idx >= 0:
            self.method_combo.setCurrentIndex(idx)
        self.url_edit.setText(req.url)
        self.ssl_verify_check.setChecked(req.ssl_verify)
        self.timeout_spin.setValue(req.timeout_seconds)
        self.headers_panel.set_raw_headers(req.headers)
        self.headers_panel.set_sent_headers(sent_headers or {})
        self.headers_panel.show_raw_mode()
        self.body_editor.set_body(
            req.body_type,
            req.body_text,
            req.form_fields,
            req.file_path,
        )

    def collect_request(self) -> HttpRequest:
        return HttpRequest(
            method=self.method_combo.currentText(),
            url=self.url_edit.text().strip(),
            headers=self.headers_panel.get_headers(),
            body_type=self.body_editor.get_body_type(),
            body_text=self.body_editor.get_body_text(),
            form_fields=self.body_editor.get_form_fields(),
            file_path=self.body_editor.get_file_path(),
            ssl_verify=self.ssl_verify_check.isChecked(),
            timeout_seconds=self.timeout_spin.value(),
        )

    def get_session_state(self) -> dict:
        record_id = self.record_id
        if record_id and not self.history_store.get(record_id):
            record_id = None
        response = {}
        source = self._record
        if source:
            response = {
                'last_status': source.last_status,
                'last_status_reason': source.last_status_reason,
                'last_elapsed_ms': source.last_elapsed_ms,
                'response_headers': dict(source.response_headers),
                'response_body': source.response_body,
            }
        return {
            'record_id': record_id,
            'request': self.collect_request().to_dict(),
            'sent_headers': self.headers_panel.get_sent_headers(),
            'response': response,
            'splitters': self.get_splitter_state(),
        }

    def restore_session_state(self, state: dict) -> None:
        record_id = state.get('record_id')
        request = HttpRequest.from_dict(state.get('request', {}))
        sent_headers = state.get('sent_headers', {})
        response_state = state.get('response', {})
        self._record = None
        self.record_id = None
        record = None
        if record_id:
            record = self.history_store.get(record_id)
            if record:
                self._record = record
                self.record_id = record_id
                if not sent_headers:
                    sent_headers = record.sent_headers
        self.load_request(request, sent_headers)
        if record:
            self._apply_saved_response(
                record.last_status,
                record.last_status_reason,
                record.last_elapsed_ms,
                record.response_headers,
                record.response_body,
            )
        elif response_state:
            self._apply_saved_response(
                response_state.get('last_status'),
                response_state.get('last_status_reason', ''),
                response_state.get('last_elapsed_ms'),
                response_state.get('response_headers', {}),
                response_state.get('response_body', ''),
            )
        else:
            self._clear_response_display()
        splitters = state.get('splitters')
        if splitters:
            QTimer.singleShot(0, lambda s=splitters: self.set_splitter_state(s))
        else:
            legacy = state.get('content_splitter')
            if _valid_sizes(legacy):
                QTimer.singleShot(0, lambda sz=legacy: self.set_content_splitter_sizes(sz))
            QTimer.singleShot(0, self.apply_default_splitter_sizes)

    def _set_status_style(self, style_id: str) -> None:
        self.status_label.setObjectName(style_id)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _set_status_text(self, text: str) -> None:
        display, tooltip = _truncate_status_text(text)
        self.status_label.setText(display)
        self.status_label.setToolTip(tooltip)

    def _copy_request_as_curl(self) -> None:
        command = format_curl_linux_command(self.collect_request())
        if command:
            QApplication.clipboard().setText(command, QClipboard.Clipboard)

    def _copy_request_as_powershell(self) -> None:
        command = format_powershell_command(self.collect_request())
        if command:
            QApplication.clipboard().setText(command, QClipboard.Clipboard)

    def _on_send_clicked(self) -> None:
        self.send_btn.setEnabled(False)
        self._set_status_text('Sending...')
        self._set_status_style('statusPending')
        req = self.collect_request()
        self.async_task.runTaskInThread(_http_worker, req, self._on_http_result)

    def _on_http_result(self, task_id: int, msg_id: int, data) -> None:
        if msg_id == MsgIDThreadExit:
            self.send_btn.setEnabled(True)
            return
        if msg_id != MSG_HTTP_DONE:
            return

        resp: HttpResponse = data
        if not resp.error and resp.request_headers:
            self.headers_panel.set_sent_headers(resp.request_headers)
            self.headers_panel.show_sent_mode()
        self._show_response(resp)
        self._save_to_history(resp)

    def _show_response(self, resp: HttpResponse) -> None:
        if resp.error:
            self._set_status_text(f'Error: {resp.error}')
            self._set_status_style('statusError')
            self.response_headers_table.setRowCount(0)
            self.response_body_edit.setPlainText('')
            return

        style_id = _status_code_style_id(resp.status_code)
        self._set_status_text(
            f'{resp.status_code} {resp.reason} · {resp.elapsed_ms:.0f} ms'
        )
        self._set_status_style(style_id)

        self.response_headers_table.setRowCount(0)
        fill_key_value_table(self.response_headers_table, resp.headers)

        body_text = _format_response_body_text(resp)
        self.response_body_edit.setPlainText(body_text)

    def _clear_response_display(self) -> None:
        self._set_status_text('Waiting to send request')
        self._set_status_style('statusPending')
        self.response_headers_table.setRowCount(0)
        self.response_body_edit.setPlainText('')

    def _apply_saved_response(
        self,
        status_code: Optional[int],
        reason: str,
        elapsed_ms: Optional[float],
        headers: Optional[Dict[str, str]],
        body: str,
    ) -> None:
        headers = headers or {}
        if status_code is None and not headers and not body:
            self._clear_response_display()
            return

        if status_code is not None:
            style_id = _status_code_style_id(status_code)
            if elapsed_ms is not None:
                status_text = f'{status_code} {reason} · {elapsed_ms:.0f} ms'.strip()
            else:
                status_text = f'{status_code} {reason}'.strip()
            self._set_status_text(status_text)
            self._set_status_style(style_id)
        else:
            self._set_status_text('Saved response')
            self._set_status_style('statusPending')

        fill_key_value_table(self.response_headers_table, headers)
        self.response_body_edit.setPlainText(body or '')

    def _save_to_history(self, resp: HttpResponse) -> None:
        req = self.collect_request()
        now = datetime.now(timezone.utc).isoformat()

        if self._record is None:
            self._record = HistoryRecord(
                id=str(uuid.uuid4()),
                request=req,
                created_at=now,
            )
            self.record_id = self._record.id
            self.record_bound.emit(self.record_id)

        self._record.request = req
        self._record.sent_headers = self.headers_panel.get_sent_headers()
        self._record.updated_at = now
        if not resp.error:
            snapshot = _response_snapshot(resp)
            self._record.last_status = snapshot['last_status']
            self._record.last_status_reason = snapshot['last_status_reason']
            self._record.last_elapsed_ms = snapshot['last_elapsed_ms']
            self._record.response_headers = snapshot['response_headers']
            self._record.response_body = snapshot['response_body']

        self.history_store.upsert(self._record)
        self.record_saved.emit(self._record)

    def get_record_id(self) -> Optional[str]:
        return self.record_id
