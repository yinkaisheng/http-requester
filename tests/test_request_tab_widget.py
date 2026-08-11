#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication

from models.http_models import HistoryRecord, HttpRequest
from pyqt_async_task import AsyncTask
from storage.history_store import HistoryStore
from ui.request_tab_widget import RequestTabWidget


class RequestTabWidgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.history_store = HistoryStore(
            index_path=root / 'history.json',
            records_dir=root / 'records',
        )
        self.tabs = RequestTabWidget(self.history_store, AsyncTask())

    def tearDown(self) -> None:
        self.tabs._remove_all_tabs()
        self.tabs.deleteLater()
        self.temp_dir.cleanup()

    def test_bulk_close_keeps_tab_with_running_request(self) -> None:
        running_record = HistoryRecord(
            name='running',
            request=HttpRequest(url='https://example.com/running'),
        )
        idle_record = HistoryRecord(
            name='idle',
            request=HttpRequest(url='https://example.com/idle'),
        )
        running_tab = self.tabs._create_tab(record=running_record)
        idle_tab = self.tabs._create_tab(record=idle_record)
        self.tabs.addTab(running_tab, running_tab.tab_title())
        self.tabs.addTab(idle_tab, idle_tab.tab_title())
        running_tab._active_task_id = 1

        self.tabs.close_record_tabs([running_record.id, idle_record.id])

        self.assertGreaterEqual(self.tabs.indexOf(running_tab), 0)
        self.assertEqual(self.tabs.indexOf(idle_tab), -1)

    def test_single_close_keeps_tab_with_running_request(self) -> None:
        running_record = HistoryRecord(
            name='running',
            request=HttpRequest(url='https://example.com/running'),
        )
        running_tab = self.tabs._create_tab(record=running_record)
        self.tabs.addTab(running_tab, running_tab.tab_title())
        self.tabs._record_tab_map[running_record.id] = 0
        running_tab._active_task_id = 1

        self.tabs.close_record_tab(running_record.id)

        self.assertGreaterEqual(self.tabs.indexOf(running_tab), 0)


if __name__ == '__main__':
    unittest.main()
