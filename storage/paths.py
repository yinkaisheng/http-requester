#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(sys.argv[0]).resolve().parent
HISTORY_FILE = APP_DIR / 'history.json'
SESSION_FILE = APP_DIR / 'session.json'
