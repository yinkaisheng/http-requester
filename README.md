# HTTP Requester

A lightweight desktop HTTP client built with **Python** and **PyQt5**.

## Why this project?

I wanted a simple tool to send and inspect HTTP requests without installing the Electron-based Postman client. After installation, Postman easily takes up **~500 MB** on disk — far more than I need for everyday API testing. HTTP Requester keeps the workflow familiar while staying small, fast to launch, and easy to hack on.

## Screenshot

![HTTP Requester screenshot](images/screenshot.png)

## Features

### Request & response

- **HTTP methods** — GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
- **Request headers** — editable key/value table with per-row enable/disable; separate views for user headers and headers actually sent
- **Request body** — Raw, JSON, Form Data, and File Upload
- **Options** — configurable timeout and SSL certificate verification
- **Response view** — status line, response headers, and body (JSON is pretty-printed when `Content-Type` indicates JSON)
- **Non-blocking UI** — requests run in background threads
- **HTTP logging** — each request logs URL, headers, response, and errors to the console / log file

### History & tabs

- **Send history** — every **Send** creates a new history entry (newest on top); click to open in a tab
- **History management** — rename, delete, and bulk delete (others / same method & URL / all)
- **Linked names** — renaming a tab or a history entry updates both; custom names persist in history index
- **Multi-tab workspace** — open several requests at once; tabs are closable, draggable, and renameable (right-click tab bar)
- **Tab ↔ history** — opening history creates a tab if needed; deleting history closes its tab
- **Session restore** — window layout, theme, splitter sizes, and open tabs persist across restarts

### Import & export

- **Copy as curl / PowerShell** — toolbar buttons or headers context menu; Linux curl line endings with WSL path conversion on Windows
- **Paste headers** — paste `Key: Value` lines into the request headers table
- **Paste curl / PowerShell command** — parse clipboard command and fill URL, method, headers, and body; cross-platform file paths are resolved when the target file exists (e.g. WSL `/mnt/c/...` → `C:\...` on Windows)

### UI

- **Themes** — Solarized Light, Light, and Dark (selector in the top bar)
- **Clean UI** — Fusion style with consistent tables, tabs, and context menus

## Requirements

- Python 3.8+
- PyQt5
- requests

## Installation

```bash
pip install -r requirements.txt
```

## Portable release (Windows)

Each release includes a portable **~18 MB** 7z archive for **Windows 7** and later. The package bundles a self-contained **Python 3.11** runtime and all required libraries, so you can extract it and run `HttpRequester.exe` without installing Python or running `pip` on your system.

## Usage

```bash
python main.py
```

1. Click **+ New Request** to open a tab.
2. Enter the URL, method, headers, and body as needed.
3. Click **Send** to execute the request; each send adds a history entry on the left.
4. Click a history item to open it in a tab (or focus the tab if already open).
5. Right-click a history item for rename / delete / bulk delete; right-click a tab bar for **Rename tab**.
6. Right-click the request headers table to copy, paste headers, or paste a curl / PowerShell command.
7. Use **curl** / **pwsh** toolbar buttons to copy the current request as a command.

## Data files

Local data is stored under `data/` next to the executable (or project root when running from source):

| Path | Purpose |
|------|---------|
| `data/history_index.json` | History list metadata (id, name, method, URL, status, time) |
| `data/records/{id}.json` | Full request/response payload per history entry |
| `data/session.json` | Theme, window size, splitter layout, and open tabs |

These paths are listed in `.gitignore` and are not committed to version control.

## Project layout

```
http-requester/
├── main.py                 # Application entry point
├── log_util.py             # Console / file logging
├── models/                 # Data models (requests, history records)
├── services/               # HTTP client, curl/PowerShell import & export
├── storage/                # History index, record files, session persistence
├── ui/                     # PyQt5 widgets, themes, dialogs
├── pyqt_async_task.py      # Background task helper
└── requirements.txt
```

## License

MIT.
