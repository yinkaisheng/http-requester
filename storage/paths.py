#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
HISTORY_FILE = APP_DIR / 'history.json'
SESSION_FILE = APP_DIR / 'session.json'
