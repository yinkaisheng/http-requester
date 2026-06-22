#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


APP_DIR = Path.cwd()
DATA_DIR = APP_DIR / 'config'
CONFIG_FILE = DATA_DIR / 'config.json'
HISTORY_FILE = DATA_DIR / 'history.json'
RECORDS_DIR = DATA_DIR / 'records'
SESSION_FILE = DATA_DIR / 'session.json'

STORAGE_VERSION = 1
