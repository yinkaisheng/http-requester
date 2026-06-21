# HTTP Requester

A lightweight desktop HTTP client built with **Python** and **PyQt5**.

## Why this project?

I wanted a simple tool to send and inspect HTTP requests without installing the Electron-based Postman client. After installation, Postman easily takes up **~500 MB** on disk. HTTP Requester keeps the workflow familiar while staying small, fast to launch.

## Screenshot

![HTTP Requester screenshot](images/screenshot.png)

## Requirements

- Python 3.8+
- PyQt5
- requests

## Installation

```bash
pip install -r requirements.txt
python main.py
```

## Portable release (Windows)

Each release includes a portable **~18 MB** 7z archive for **Windows 7** and later. The package bundles a self-contained **Python 3.11** runtime and all required libraries, so you can extract it and run `HttpRequester.exe` without installing Python or running `pip` on your system. The executable is a native launcher ([PythonCaller](https://github.com/yinkaisheng/PythonCaller)) that loads the embedded runtime and starts the Python entry point.

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
- **Linked names** — renaming a tab or a history entry updates both; custom names persist in history
- **Multi-tab workspace** — open several requests at once; tabs are closable, draggable, and renameable (right-click tab bar)
- **Tab ↔ history** — opening history creates a tab if needed; deleting history closes its tab
- **Session restore** — window layout, theme, splitter sizes, and open tabs persist across restarts

### Import & export

- **Copy as curl / PowerShell** — toolbar buttons or headers context menu; Linux curl line endings with WSL path conversion on Windows
- **Paste headers** — paste `Key: Value` lines into the request headers table
- **Paste curl / PowerShell command** — right-click the **Request Headers User** table → **Paste from Curl Command** or **Paste from PowerShell Command**; fills URL, method, headers, and body. File paths in form/upload commands are resolved when the file exists (e.g. WSL `/mnt/c/...` → `C:\...` on Windows)

#### Paste examples

**curl** — a single line or a command joined with `\` line continuations:

```bash
curl 'https://api.example.com/users' \
  -H 'Authorization: Bearer token' \
  -H 'Content-Type: application/json' \
  -d '{"name":"alice"}'
```

```bash
curl -X PUT 'https://api.example.com/users/1' -H 'Accept: application/json' -d 'status=active'
```

```bash
curl 'https://api.example.com/upload' -F 'file=@/path/to/file.bin' -k --max-time 60
```

Supported curl flags include `-X` / `--request`, `-H` / `--header`, `-d` / `--data` / `--data-raw`, `-F` / `--form`, `--max-time`, and `-k` / `--insecure`. If `-X` is omitted, `-d` or `-F` implies **POST** (same as curl).

**PowerShell** — `Invoke-WebRequest` or `Invoke-RestMethod`, including multi-line commands with `` ` `` continuations. Commands copied from this app (with trailing `$response` output) also paste correctly; lines after the invoke call are ignored.

```powershell
Invoke-WebRequest `
  -Uri 'https://api.example.com/users' `
  -Method POST `
  -Headers @{ Authorization = 'Bearer token' } `
  -ContentType 'application/json' `
  -Body '{"name":"alice"}'
```

```powershell
Invoke-RestMethod -Uri 'https://api.example.com/upload' -Form @{
  file = (Get-Item -LiteralPath 'C:\path\to\file.bin')
} -SkipCertificateCheck -TimeoutSec 60
```

#### Does argument order matter?

**Mostly no.** Both parsers match flags and values anywhere in the command, so `-H` before or after `-d` is fine.

Exceptions worth knowing:

| Case | curl | PowerShell |
|------|------|------------|
| Flag order | Not important for supported flags | Not important for supported parameters |
| URL | The first `http://` or `https://` token is used | Taken from `-Uri '...'` or `-Uri "..."` |
| Repeated body | Multiple `-d` / `--data` — **last one wins** | Single `-Body` is read |
| Repeated form fields | Multiple `-F` / `--form` — **all are kept** | All entries in `-Form @{ ... }` are kept |
| Method | `-X` overrides; otherwise `-d` / `-F` sets POST | `-Method`; otherwise `-Body` / `-Form` sets POST |

Not every curl or pwsh option is supported (e.g. cookies, proxies, redirects). Paste what you copied from this app or from typical API examples; if parsing fails, a message is shown in the UI.

### UI

- **Settings** — click **⚙** next to **+ New Request** for theme, editor font family/size; **Apply** saves without closing the dialog
- **Themes** — Solarized Light, Light, and Dark
- **Clean UI** — Fusion style with consistent tables, tabs, and context menus

## Usage

1. Click **+ New Request** to open a tab.
2. Enter the URL, method, headers, and body as needed.
3. Click **Send** to execute the request; each send adds a history entry on the left.
4. Click a history item to open it in a tab (or focus the tab if already open).
5. Right-click a history item for rename / delete / bulk delete (no confirmation for bulk delete); right-click a tab bar for **Rename tab**.
6. Right-click the request headers table to copy, paste headers, or paste a curl / PowerShell command.
7. Use **curl** / **pwsh** toolbar buttons to copy the current request as a command.
8. Click **⚙ Settings** to change theme and editor font; **Apply** or **Save** persists changes, **Close** closes the dialog (already-applied settings stay in effect).

## Data files

Local data is stored under `config/` next to the executable (or project root when running from source):

| Path | Purpose |
|------|---------|
| `config/history.json` | History list metadata (id, name, method, URL, status, time) |
| `config/records/{id}.json` | Full request/response payload per history entry |
| `config/session.json` | Theme, font settings, window size, splitter layout, and open tabs |

These paths are listed in `.gitignore` and are not committed to version control.

## Project layout

```
http-requester/
├── main.py                 # Application entry point
├── log_util.py             # Console / file logging
├── models/                 # Data models (requests, history records)
├── services/               # HTTP client, curl/PowerShell import & export
├── storage/                # History, record files, session persistence
├── ui/                     # PyQt5 widgets, themes, dialogs
├── pyqt_async_task.py      # Background task helper
└── requirements.txt
```

## License

MIT.
