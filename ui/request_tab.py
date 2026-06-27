#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QClipboard, QShowEvent
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from models.http_models import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    HTTP_METHODS,
    BodyType,
    HistoryRecord,
    HttpRequest,
    HttpResponse,
    decode_stored_response_body,
    encode_response_body_for_storage,
    url_without_query,
    validate_json_body_text,
)
from pyqt_async_task import AsyncTask, MsgIDThreadExit
from services.curl_export import format_curl_linux_command
from services.http_service import send_request
from services.powershell_export import format_powershell_command
from storage.history_store import HistoryStore
from ui.body_editor import BodyEditor
from ui.response_body_panel import ResponseBodyPanel
from ui.headers_editor import (
    RequestHeadersPanel,
    _set_compact_table_header,
    add_section_header_widget,
    apply_section_header_row_height,
    attach_header_table_menu,
    configure_section_header_layout,
    fill_key_value_table,
    header_table_labels,
)
from i18n import tr
from ui.dialog_i18n import ask_yes_no_cancel, message_warning
from ui.params_dialog import prompt_url_params
from ui.widgets import AccentCheckBox, ArrowComboBox, GlyphSpinBox

MSG_HTTP_DONE = 1
DEFAULT_CONTENT_RATIO = 0.5
DEFAULT_PANEL_RATIO = 0.25
STATUS_DISPLAY_MAX_LENGTH = 72


def _status_code_style_id(status_code: int) -> str:
    if 200 <= status_code < 300:
        return 'statusOk'
    if status_code < 500:
        return 'statusWarn'
    return 'statusError'


def _truncate_status_text(text: str, max_length: int = STATUS_DISPLAY_MAX_LENGTH) -> Tuple[str, str]:
    full = text.strip()
    if len(full) <= max_length:
        return full, ''
    if max_length <= 1:
        return '…', full
    return full[: max_length - 1] + '…', full


def splitter_sizes_to_ratio(sizes: List[int]) -> float:
    total = sum(sizes)
    if total <= 0:
        return DEFAULT_CONTENT_RATIO
    return round(sizes[0] / total, 3)


def splitter_ratio_to_sizes(total: int, ratio: float) -> List[int]:
    if total <= 0:
        return []
    ratio = max(0.0, min(1.0, float(ratio)))
    first = int(total * ratio)
    return [first, total - first]


def _valid_ratio(ratio) -> bool:
    return isinstance(ratio, (int, float)) and 0.0 <= ratio <= 1.0


def _http_worker(signal: pyqtSignal, task_id: int, req: HttpRequest) -> None:
    resp = send_request(req)
    signal.emit((task_id, MSG_HTTP_DONE, resp))


def _response_snapshot(resp: HttpResponse) -> dict:
    body_text = resp.body_text()
    stored_body, is_binary = encode_response_body_for_storage(body_text, resp.body)
    return {
        'status_code': resp.status_code,
        'status_reason': resp.reason,
        'elapsed_ms': resp.elapsed_ms,
        'response_headers': dict(resp.headers),
        'response_body': stored_body,
        'response_body_is_binary': is_binary,
    }


class RequestTab(QWidget):
    record_saved = pyqtSignal(object)

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
        self.record_id: Optional[str] = record.id if record else None
        self._record = record
        self._draft_name = ''
        self._cached_response: Optional[dict] = None
        self._splitter_ratios: Optional[Dict[str, float]] = None
        self._closed = False
        self._active_task_id: Optional[int] = None
        self._init_ui()
        if record:
            self.load_record(record)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        toolbar = QHBoxLayout()
        toolbar.setAlignment(Qt.AlignVCenter)
        self.method_combo = ArrowComboBox()
        self.method_combo.addItems(HTTP_METHODS)
        self.ssl_verify_check = AccentCheckBox(tr('request.ssl_verify'))
        self.ssl_verify_check.setChecked(True)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(tr('request.url_placeholder'))
        timeout_row = QWidget()
        timeout_layout = QHBoxLayout(timeout_row)
        timeout_layout.setContentsMargins(0, 0, 0, 0)
        timeout_layout.setSpacing(4)
        timeout_label = QLabel(tr('request.timeout'))
        timeout_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self._timeout_label = timeout_label
        self.timeout_spin = GlyphSpinBox()
        self.timeout_spin.setRange(1, 3600)
        self.timeout_spin.setValue(DEFAULT_REQUEST_TIMEOUT_SECONDS)
        self.timeout_spin.setSuffix(tr('request.timeout_suffix'))
        self.timeout_spin.setFixedWidth(72)
        timeout_layout.addWidget(timeout_label)
        timeout_layout.addWidget(self.timeout_spin)
        self.send_btn = QPushButton(tr('request.send'))
        self.send_btn.setObjectName('primaryButton')
        self.send_btn.setFixedWidth(80)
        self.send_btn.clicked.connect(self._on_send_clicked)
        self.curl_btn = QPushButton(tr('request.curl_btn'))
        self.curl_btn.setToolTip(tr('menu.copy_curl'))
        self.curl_btn.clicked.connect(self._copy_request_as_curl)
        self.pwsh_btn = QPushButton(tr('request.powershell_btn'))
        self.pwsh_btn.setToolTip(tr('menu.copy_powershell'))
        self.pwsh_btn.clicked.connect(self._copy_request_as_powershell)
        toolbar.addWidget(self.method_combo, 0, Qt.AlignVCenter)
        toolbar.addWidget(self.ssl_verify_check, 0, Qt.AlignVCenter)
        toolbar.addWidget(self.url_edit, 1, Qt.AlignVCenter)

        self.params_btn = QPushButton('P')
        self.params_btn.setObjectName('paramsButton')
        self.params_btn.setFixedWidth(32)
        self.params_btn.setFlat(True)
        self.params_btn.setToolTip(tr('url_params.btn_tooltip'))
        self.params_btn.clicked.connect(self._on_params_clicked)
        toolbar.addWidget(self.params_btn, 0, Qt.AlignVCenter)

        toolbar.addWidget(timeout_row, 0, Qt.AlignVCenter)
        toolbar.addWidget(self.send_btn, 0, Qt.AlignVCenter)
        toolbar.addWidget(self.curl_btn, 0, Qt.AlignVCenter)
        toolbar.addWidget(self.pwsh_btn, 0, Qt.AlignVCenter)
        layout.addLayout(toolbar)

        self.content_splitter = QSplitter(Qt.Horizontal)
        self.content_splitter.setObjectName('contentSplitter')
        self.content_splitter.setHandleWidth(4)

        self.left_splitter = QSplitter(Qt.Vertical)
        self.headers_panel = RequestHeadersPanel(
            curl_copy_callback=self._copy_request_as_curl,
            powershell_copy_callback=self._copy_request_as_powershell,
            paste_request_callback=self._apply_imported_request,
        )
        self.body_editor = BodyEditor()
        self.left_splitter.addWidget(self.headers_panel)
        self.left_splitter.addWidget(self.body_editor)
        self.left_splitter.setStretchFactor(0, 1)
        self.left_splitter.setStretchFactor(1, 3)

        self.right_splitter = QSplitter(Qt.Vertical)
        self.response_headers_table = QTableWidget(0, 2)
        self.response_headers_table.setObjectName('headerTable')
        self.response_headers_table.setHorizontalHeaderLabels(header_table_labels())
        self.response_headers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.response_headers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.response_headers_table.verticalHeader().setVisible(False)
        self.response_headers_table.setEditTriggers(QTableWidget.NoEditTriggers)
        _set_compact_table_header(self.response_headers_table, header_table=True)
        attach_header_table_menu(self.response_headers_table, key_col=0, value_col=1)

        self.response_body_panel = ResponseBodyPanel()

        response_headers_block = QWidget()
        rh_layout = QVBoxLayout(response_headers_block)
        rh_layout.setContentsMargins(0, 0, 0, 0)
        rh_layout.setSpacing(0)
        rh_header_row = QWidget()
        rh_header = QHBoxLayout(rh_header_row)
        configure_section_header_layout(rh_header)
        self._rh_title = QLabel(tr('request.response_headers'))
        self._rh_title.setObjectName('sectionTitle')
        self._rh_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.status_label = QLabel()
        self.status_label.setObjectName('statusPending')
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._set_status_text(tr('request.waiting'))
        add_section_header_widget(rh_header, self._rh_title)
        rh_header.addStretch()
        add_section_header_widget(rh_header, self.status_label)
        apply_section_header_row_height(rh_header_row)
        rh_layout.addWidget(rh_header_row)
        rh_layout.addWidget(self.response_headers_table, 1)

        self.right_splitter.addWidget(response_headers_block)
        self.right_splitter.addWidget(self.response_body_panel)
        self.right_splitter.setStretchFactor(0, 1)
        self.right_splitter.setStretchFactor(1, 3)

        self.content_splitter.addWidget(self.left_splitter)
        self.content_splitter.addWidget(self.right_splitter)
        self.content_splitter.setStretchFactor(0, 1)
        self.content_splitter.setStretchFactor(1, 1)
        for splitter in (self.content_splitter, self.left_splitter, self.right_splitter):
            splitter.splitterMoved.connect(self._on_splitter_moved)
        layout.addWidget(self.content_splitter, 1)

    def retranslate_ui(self) -> None:
        self.ssl_verify_check.setText(tr('request.ssl_verify'))
        self._timeout_label.setText(tr('request.timeout'))
        self.send_btn.setText(tr('request.send'))
        self.curl_btn.setToolTip(tr('menu.copy_curl'))
        self.pwsh_btn.setToolTip(tr('menu.copy_powershell'))
        self.params_btn.setToolTip(tr('url_params.btn_tooltip'))
        self._rh_title.setText(tr('request.response_headers'))
        self.response_headers_table.setHorizontalHeaderLabels(header_table_labels())
        self.headers_panel.retranslate_ui()
        self.body_editor.retranslate_ui()
        self.response_body_panel.retranslate_ui()
        if self.status_label.objectName() == 'statusPending' and self._active_task_id is None:
            self._set_status_text(tr('request.waiting'))

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._splitter_ratios:
            self._apply_splitter_sizes_now(self._splitter_ratios)
        else:
            self.apply_default_splitter_sizes()

    def _on_splitter_moved(self, _pos: int, _index: int) -> None:
        if not self.isVisible():
            return
        if self.content_splitter.width() <= 0:
            return
        self._splitter_ratios = {
            'content': splitter_sizes_to_ratio(self.content_splitter.sizes()),
            'left': splitter_sizes_to_ratio(self.left_splitter.sizes()),
            'right': splitter_sizes_to_ratio(self.right_splitter.sizes()),
        }

    def _ratios_from_widgets(self) -> dict:
        return {
            'content': splitter_sizes_to_ratio(self.content_splitter.sizes()),
            'left': splitter_sizes_to_ratio(self.left_splitter.sizes()),
            'right': splitter_sizes_to_ratio(self.right_splitter.sizes()),
        }

    def get_splitter_state(self) -> dict:
        if self._splitter_ratios:
            return dict(self._splitter_ratios)
        return self._ratios_from_widgets()

    def set_splitter_state(self, state: Optional[dict]) -> None:
        if not state:
            return
        self.apply_splitter_sizes(
            content=state.get('content'),
            left=state.get('left'),
            right=state.get('right'),
        )

    def _apply_splitter_sizes_now(self, ratios: Dict[str, float]) -> None:
        def _apply() -> None:
            if not self.isVisible():
                return
            lh = self.left_splitter.height()
            rh = self.right_splitter.height()
            cw = self.content_splitter.width()
            if lh <= 0 or rh <= 0 or cw <= 0:
                QTimer.singleShot(50, _apply)
                return
            self.content_splitter.setSizes(splitter_ratio_to_sizes(cw, ratios['content']))
            self.left_splitter.setSizes(splitter_ratio_to_sizes(lh, ratios['left']))
            self.right_splitter.setSizes(splitter_ratio_to_sizes(rh, ratios['right']))

        QTimer.singleShot(0, _apply)

    def apply_splitter_sizes(
        self,
        content: Optional[float] = None,
        left: Optional[float] = None,
        right: Optional[float] = None,
    ) -> None:
        """Store splitter ratios and apply them when the tab is visible and laid out."""
        ratios = {
            'content': content if _valid_ratio(content) else DEFAULT_CONTENT_RATIO,
            'left': left if _valid_ratio(left) else DEFAULT_PANEL_RATIO,
            'right': right if _valid_ratio(right) else DEFAULT_PANEL_RATIO,
        }
        self._splitter_ratios = ratios
        self._apply_splitter_sizes_now(ratios)

    def apply_default_splitter_sizes(self) -> None:
        self.apply_splitter_sizes()

    def tab_title(self) -> str:
        if self._record and self._record.name.strip():
            return self._record.name.strip()
        if self._draft_name.strip():
            return self._draft_name.strip()
        url = url_without_query(self.url_edit.text().strip())
        if url:
            return url
        return tr('request.new_request')

    def apply_record_name(self, name: str) -> None:
        if self._record is not None:
            self._record.name = name.strip()

    def set_draft_name(self, name: str) -> None:
        self._draft_name = name.strip()

    def get_draft_name(self) -> str:
        return self._draft_name

    def load_record(self, record: HistoryRecord) -> None:
        self._record = record
        self.record_id = record.id
        self._draft_name = ''
        self.load_request(record.request, record.sent_headers)
        self._apply_saved_response(
            record.status_code,
            record.status_reason,
            record.elapsed_ms,
            record.response_headers,
            record.response_body,
            record.response_body_is_binary,
        )
        self._cached_response = {
            'status_code': record.status_code,
            'status_reason': record.status_reason,
            'elapsed_ms': record.elapsed_ms,
            'response_headers': dict(record.response_headers),
            'response_body': record.response_body,
            'response_body_is_binary': record.response_body_is_binary,
        }

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
        response = dict(self._cached_response) if self._cached_response else {}
        return {
            'record_id': record_id,
            'draft_name': self._draft_name if not record_id else '',
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
        self._draft_name = state.get('draft_name', '') or state.get('tab_name', '') or ''
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
                record.status_code,
                record.status_reason,
                record.elapsed_ms,
                record.response_headers,
                record.response_body,
                record.response_body_is_binary,
            )
            self._cached_response = {
                'status_code': record.status_code,
                'status_reason': record.status_reason,
                'elapsed_ms': record.elapsed_ms,
                'response_headers': dict(record.response_headers),
                'response_body': record.response_body,
                'response_body_is_binary': record.response_body_is_binary,
            }
        elif response_state:
            self._apply_saved_response(
                response_state.get('status_code'),
                response_state.get('status_reason', ''),
                response_state.get('elapsed_ms'),
                response_state.get('response_headers', {}),
                response_state.get('response_body', ''),
                response_state.get('response_body_is_binary', False),
            )
            self._cached_response = dict(response_state)
        else:
            self._clear_response_display()
        splitters = state.get('splitters')
        if splitters:
            self.set_splitter_state(splitters)
        else:
            self._splitter_ratios = None

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

    def _on_params_clicked(self) -> None:
        prompt_url_params(self, self.url_edit.text(), self.url_edit.setText)

    def _apply_imported_request(self, req: HttpRequest) -> None:
        self.load_request(req)
        self.headers_panel.show_raw_mode()
        self._clear_response_display()

    def prepare_close(self) -> None:
        """Mark tab closed so in-flight HTTP callbacks are ignored."""
        self._closed = True

    def _on_send_clicked(self) -> None:
        req = self.collect_request()
        if req.body_type == BodyType.JSON and req.body_text.strip():
            json_error = validate_json_body_text(req.body_text)
            if json_error:
                message_warning(
                    self,
                    tr('request.invalid_json_title'),
                    tr('request.invalid_json_body', error=json_error),
                )
                return
        if req.method.upper() == 'GET' and req.has_body():
            reply = ask_yes_no_cancel(
                self,
                tr('request.confirm_get_title'),
                tr('request.confirm_get_body'),
            )
            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.No:
                post_index = self.method_combo.findText('POST')
                if post_index >= 0:
                    self.method_combo.setCurrentIndex(post_index)
                req = self.collect_request()
        self._execute_send(req)

    def _execute_send(self, req: HttpRequest) -> None:
        self.send_btn.setEnabled(False)
        self._set_status_text(tr('request.sending'))
        self._set_status_style('statusPending')
        try:
            self._active_task_id = self.async_task.runTaskInThread(
                _http_worker, req, self._on_http_result
            )
        except Exception:
            self._active_task_id = None
            self.send_btn.setEnabled(True)
            self._set_status_text(tr('request.error_start'))
            self._set_status_style('statusError')

    def _on_http_result(self, task_id: int, msg_id: int, data: Any) -> None:
        if self._closed:
            return
        if msg_id == MsgIDThreadExit:
            if task_id == self._active_task_id:
                self._active_task_id = None
                self.send_btn.setEnabled(True)
            return
        if msg_id != MSG_HTTP_DONE or task_id != self._active_task_id:
            return

        resp: HttpResponse = data
        if resp.request_headers:
            self.headers_panel.set_sent_headers(resp.request_headers)
            if not resp.error:
                self.headers_panel.show_sent_mode()
        self._show_response(resp)
        self._save_to_history(resp)

    def _show_response(self, resp: HttpResponse) -> None:
        if resp.error and not resp.status_code:
            self._set_status_text(tr('request.error_prefix', message=resp.error))
            self._set_status_style('statusError')
            self.response_headers_table.setRowCount(0)
            self.response_body_panel.clear()
            self._cached_response = None
            return

        if resp.error:
            self._set_status_text(
                tr(
                    'request.status_error',
                    error=resp.error,
                    status_code=resp.status_code,
                    reason=resp.reason,
                    elapsed_ms=f'{resp.elapsed_ms:.0f}',
                )
            )
        else:
            self._set_status_text(
                f'{resp.status_code} {resp.reason} · {resp.elapsed_ms:.0f} {tr("request.ms_unit")}'
            )
        self._set_status_style(_status_code_style_id(resp.status_code))

        self.response_headers_table.setRowCount(0)
        fill_key_value_table(self.response_headers_table, resp.headers)

        self.response_body_panel.set_body(
            resp.body_text(),
            resp.headers,
            raw_bytes=resp.body,
        )
        if not resp.error or resp.status_code:
            self._cached_response = _response_snapshot(resp)

    def _clear_response_display(self) -> None:
        self._set_status_text(tr('request.waiting'))
        self._set_status_style('statusPending')
        self.response_headers_table.setRowCount(0)
        self.response_body_panel.clear()
        self._cached_response = None

    def _apply_saved_response(
        self,
        status_code: Optional[int],
        reason: str,
        elapsed_ms: Optional[float],
        headers: Optional[Dict[str, str]],
        body: str,
        body_is_binary: bool = False,
    ) -> None:
        headers = headers or {}
        if status_code is None and not headers and not body and not reason:
            self._clear_response_display()
            return

        if status_code is not None:
            style_id = _status_code_style_id(status_code)
            if elapsed_ms is not None:
                status_text = f'{status_code} {reason} · {elapsed_ms:.0f} {tr("request.ms_unit")}'.strip()
            else:
                status_text = f'{status_code} {reason}'.strip()
            self._set_status_text(status_text)
            self._set_status_style(style_id)
        else:
            if reason:
                self._set_status_text(reason)
                self._set_status_style('statusError')
            else:
                self._set_status_text(tr('request.saved_response'))
                self._set_status_style('statusPending')

        fill_key_value_table(self.response_headers_table, headers)
        body_text = decode_stored_response_body(body or '', body_is_binary)
        raw_bytes = b''
        if body_is_binary and body:
            try:
                raw_bytes = base64.b64decode(body)
            except Exception:
                raw_bytes = b''
        elif body_text:
            raw_bytes = body_text.encode('utf-8')
        self.response_body_panel.set_body(body_text, headers, raw_bytes=raw_bytes)

    def _save_to_history(self, resp: HttpResponse) -> None:
        req = self.collect_request()
        now = datetime.now(timezone.utc).isoformat()
        record = HistoryRecord(
            id=str(uuid.uuid4()),
            request=req,
            sent_headers=self.headers_panel.get_sent_headers(),
            created_at=now,
            updated_at=now,
        )
        if self._draft_name.strip():
            record.name = self._draft_name.strip()
        if resp.error and not resp.status_code:
            record.error = resp.error
            record.status_reason = resp.error
        elif not resp.error or resp.status_code:
            snapshot = _response_snapshot(resp)
            record.status_code = snapshot['status_code']
            record.status_reason = snapshot['status_reason']
            record.elapsed_ms = snapshot['elapsed_ms']
            record.response_headers = snapshot['response_headers']
            record.response_body = snapshot['response_body']
            record.response_body_is_binary = snapshot['response_body_is_binary']
            if resp.error:
                record.error = resp.error

        self._record = record
        self.record_id = record.id
        self.history_store.add(record)
        self.record_saved.emit(record)

    def get_record_id(self) -> Optional[str]:
        return self.record_id
