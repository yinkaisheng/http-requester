#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(sys.argv[0]).resolve().parent
DATA_DIR = APP_DIR / 'data'
HISTORY_INDEX_FILE = DATA_DIR / 'history_index.json'
RECORDS_DIR = DATA_DIR / 'records'
SESSION_FILE = DATA_DIR / 'session.json'

STORAGE_VERSION = 1
