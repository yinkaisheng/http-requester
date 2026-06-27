# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- **Run app**: `python main.py`
- **Install dependencies**: `pip install -r requirements.txt`
- **No test framework is set up** — there are no tests in the project. The `.pytest_cache/` directory from a prior run is gitignored but contains no actual tests.
- **Run with debug log**: Set `LOG_LEVEL=DEBUG` before running (also set via the `.vscode/launch.json` "dev" configuration)

## Project Architecture

HTTP Requester is a PyQt5 desktop app with a clean model/service/storage/ui separation. All modules use `__init__.py` with explicit `__all__` exports.

### Data flow

```
User input → RequestTab (ui/) → send_request() (services/) → requests library
                                          ↓
                                HistoryRecord → HistoryStore (storage/) → JSON on disk
```

### Layers

- **`models/http_models.py`** — Core dataclasses (`HttpRequest`, `HttpResponse`, `HistoryRecord`, `HeaderItem`, `FormField`, `BodyType` enum). Every model has `to_dict()` / `from_dict()` for JSON serialization. Key utility functions: `decode_bytes_to_text()`, `is_text_body()`, `encode_response_body_for_storage()`, `is_valid_header_name()` (RFC 9110).

- **`services/`** — Business logic. `http_service.py` executes `HttpRequest` via `requests.request()` in a blocking call (UI uses `AsyncTask` to keep responsive). `curl_*.py` / `powershell_*.py` handle import/export of command-line formats. `path_import.py` resolves cross-platform file paths (WSL `/mnt/c/...` → `C:\...`).

- **`storage/`** — File-based JSON persistence in `config/`:
  - `app_config.py` — Loads/saves `config.json` (themes, fonts, language). Frozen dataclasses: `AppConfig`, `AppearanceConfig`. Singleton access via `get_app_config()`.
  - `history_store.py` — `HistoryStore` class: CRUD over `history.json` (index) + `records/{uuid}.json` (full payloads).
  - `session_store.py` — `SessionStore` class: loads/saves `session.json` (window layout, open tabs).
  - `paths.py` — Well-known paths: `APP_DIR`, `DATA_DIR`, `CONFIG_FILE`, `HISTORY_FILE`, `RECORDS_DIR`, `SESSION_FILE`.

- **`ui/`** — PyQt5 widgets:
  - `main_window.py` — `MainWindow(QMainWindow)`: root window with splitter (history + tabs).
  - `request_tab.py` — `RequestTab(QWidget)`: single request lifecycle (method, URL, headers, body, send, response). Uses `AsyncTask` from `pyqt_async_task.py` for non-blocking HTTP.
  - `request_tab_widget.py` — `RequestTabWidget(QTabWidget)`: tab manager.
  - `headers_editor.py` — Editable headers table, sent-headers read-only view, context menus for copy/paste/import, Basic Auth / Bearer Token dialogs.
  - `body_editor.py` — Body type selector (Raw/JSON/Form Data/File Upload) with stacked widget.
  - `response_body_panel.py` — Raw, JSON (pretty-print), JSON Tree, image preview, binary hex dump views.
  - `history_panel.py` — History list with filter, rename, delete, bulk delete.
  - `params_dialog.py` — URL query parameter editor with type-inferred value editors.
  - `dialogs.py` — Settings, About, prompt dialogs.
  - `theme.py` / `theme_defaults.py` — Theme application (QSS stylesheet builder) and 3 themes (solarized, light, dark).
  - `widgets.py` — Custom painted widgets (`ArrowComboBox`, `AccentCheckBox`, etc.) and edit-menu i18n installation.

- **`i18n/`** — Custom plain-text translation engine (no Qt `.qm` files):
  - `translator.py` — Singleton `Translator` with `tr(key, **kwargs)` function. Fallback chain: strings.txt overlay → builtin English dict → raw key.
  - `builtin_strings.py` — 168 English fallback keys.
  - `register_retranslator(callback)` / `unregister_retranslator(callback)` — widgets register to update `setText()` on language change.
  - `set_language(locale)` changes locale and calls `notify_retranslate()`.
  - Strings live in `Languages/<locale>/strings.txt` (key=value, UTF-8, `#` comments).

- **`pyqt_async_task.py`** — `AsyncTask(QThread)` wrapper: runs a callable in a background thread, emits `finished(result)` / `error(exception)` signals. Used by `RequestTab` for HTTP calls.

- **`log_util.py`** — Logging via loguru with graceful fallback to stdlib `logging`. Falls back silently if loguru/colorama not installed.

### Key patterns

- **`from __future__ import annotations`** at the top of model files for deferred evaluation.
- **Imports**: full absolute imports (`from models.http_models import HttpRequest`), not relative.
- **Serialization**: every dataclass has explicit `to_dict()` / `from_dict()` — no `__dict__` or `asdict()` reliance.
- **i18n**: UI strings use `tr('key')` everywhere; keys follow module-scoped naming (e.g. `main.window_title`, `request_tab.send`).
- **Config**: `config.json` is the single source of truth for runtime settings; `get_app_config()` returns a frozen dataclass.
- **No type checker** — `.vscode/settings.json` sets `typeCheckingMode: "off"`. Type hints are used informally.

### Notable constraints

- Response bodies over 5 MB (`json_format_max_bytes`) skip JSON formatting and fall back to Raw.
- Binary response hex preview is limited to 10 KB (`binary_hex_preview_bytes`).
- Binary bodies are base64-encoded in storage (`encode_response_body_for_storage`).
