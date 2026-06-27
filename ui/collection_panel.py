#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collections sidebar panel — tree of project API groups."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.collection_models import Collection, CollectionItem
from models.http_models import HttpRequest
from storage.app_config import get_app_config
from storage.collection_store import CollectionStore
from services.postman_import import parse_postman_collection_file
from i18n import tr
from ui.dialog_i18n import ask_yes_no, message_warning, message_info
from ui.dialogs import prompt_text

ITEM_TYPE_COLLECTION = 'collection'
ITEM_TYPE_FOLDER = 'folder'
ITEM_TYPE_REQUEST = 'request'

ROLE_TYPE = Qt.UserRole
ROLE_COLLECTION_INDEX = Qt.UserRole + 1
ROLE_ITEM_PATH = Qt.UserRole + 2


class _CollectionTreeWidget(QTreeWidget):
    """QTreeWidget subclass that validates drag-drop and syncs with the data model."""

    def __init__(self, panel: CollectionPanel):
        super().__init__()
        self._panel = panel
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)

    def dropEvent(self, event):
        source_item = self.currentItem()
        if not source_item:
            event.ignore()
            return

        # Root collection items cannot be dragged
        if source_item.data(0, ROLE_TYPE) == ITEM_TYPE_COLLECTION:
            event.ignore()
            return

        target_item = self.itemAt(event.pos())
        if not target_item:
            event.ignore()
            return

        source_data = self._panel._item_data(source_item)
        target_data = self._panel._item_data(target_item)

        # Folder cannot be dropped onto its own descendants
        if source_data['type'] == ITEM_TYPE_FOLDER:
            if self._panel._is_descendant(source_data, target_data):
                event.ignore()
                return

        drop_pos = self.dropIndicatorPosition()

        # When dropping OnItem on a nested item (not a direct child of the
        # collection root), treat as BelowItem (insert as sibling) instead.
        # This avoids accidentally burying items under deeply nested folders
        # when the user drags over an expanded folder's child area.
        if drop_pos == QAbstractItemView.OnItem:
            parent = target_item.parent()
            if parent and parent.data(0, ROLE_TYPE) != ITEM_TYPE_COLLECTION:
                drop_pos = QAbstractItemView.BelowItem

        # Perform the move in the data model
        if self._panel._move_item(source_data, target_data, drop_pos):
            event.accept()
            self._panel._rebuild_tree()
            self._panel._expand_parent_for_move(target_data, drop_pos)
            self._panel._highlight_item(
                source_data['collection_index'],
                source_data['item_path'],
            )
            self._panel.collections_changed.emit()
        else:
            event.ignore()


class CollectionPanel(QWidget):
    """Tree view of collections, with context menus for management."""

    request_selected = pyqtSignal(HttpRequest, str)  # request, name
    collections_changed = pyqtSignal()

    def __init__(
        self,
        collection_store: CollectionStore,
        get_current_request: Optional[Callable[[], Optional[HttpRequest]]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.store = collection_store
        self._get_current_request = get_current_request
        self._collections: List[Collection] = []
        self._init_ui()
        self.reload()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Title row
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        self._title_label = QLabel(tr('collections.title'))
        self._title_label.setObjectName('panelTitle')
        title_layout.addWidget(self._title_label)
        title_layout.addStretch()

        self._add_btn = QPushButton('+')
        self._add_btn.setObjectName('collectionAddButton')
        self._add_btn.setFixedWidth(36)
        self._add_btn.setToolTip(tr('collections.add_collection'))
        self._add_btn.clicked.connect(self._add_collection)
        title_layout.addWidget(self._add_btn)
        layout.addLayout(title_layout)

        # Tree
        self.tree = _CollectionTreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.setAnimated(True)
        self.tree.setIndentation(16)
        # Apply global UI font
        appearance = get_app_config().appearance
        tree_font = QFont()
        tree_font.setPixelSize(appearance.ui_font_size_px)
        self.tree.setFont(tree_font)
        layout.addWidget(self.tree, 1)

    def reload(self) -> None:
        self._collections = self.store.load()
        self._rebuild_tree()

    def _rebuild_tree(self) -> None:
        # Save expanded state before clearing (keyed by parent_name → item_name)
        expanded: Dict[Optional[str], set] = {}
        for ci in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(ci)
            self._save_expanded(top, None, expanded)

        self.tree.clear()
        for ci, collection in enumerate(self._collections):
            item = QTreeWidgetItem()
            item.setText(0, collection.name)
            item.setData(0, ROLE_TYPE, ITEM_TYPE_COLLECTION)
            item.setData(0, ROLE_COLLECTION_INDEX, ci)
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
            self.tree.addTopLevelItem(item)
            self._populate_tree(item, collection.items, ci, (), expanded)
            # Restore expanded state; default to True when no prior state exists
            saved = expanded.get('')
            item.setExpanded(collection.name in saved if saved is not None else True)

    @staticmethod
    def _save_expanded(
        item: QTreeWidgetItem, parent_name: Optional[str], out: Dict[Optional[str], set]
    ) -> None:
        """Recursively collect expanded item names grouped by parent name."""
        key = parent_name or ''
        if item.isExpanded():
            out.setdefault(key, set()).add(item.text(0))
        for i in range(item.childCount()):
            CollectionPanel._save_expanded(item.child(i), item.text(0), out)

    def _populate_tree(
        self,
        parent_item: QTreeWidgetItem,
        items: List[CollectionItem],
        collection_index: int,
        base_path: Tuple[int, ...],
        expanded: Optional[Dict[Optional[str], set]] = None,
    ) -> None:
        expanded = expanded or {}
        for i, child in enumerate(items):
            item_path = base_path + (i,)
            child_item = QTreeWidgetItem()
            child_item.setText(0, child.name)
            child_item.setData(0, ROLE_COLLECTION_INDEX, collection_index)
            child_item.setData(0, ROLE_ITEM_PATH, item_path)
            if child.is_folder():
                child_item.setData(0, ROLE_TYPE, ITEM_TYPE_FOLDER)
                child_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                font = child_item.font(0)
                font.setBold(True)
                child_item.setFont(0, font)
                parent_item.addChild(child_item)
                self._populate_tree(child_item, child.children, collection_index, item_path, expanded)
                # Restore expanded state after item is part of the tree
                parent_item_name = parent_item.text(0) if parent_item else ''
                names = expanded.get(parent_item_name, set())
                child_item.setExpanded(child.name in names)
            else:
                child_item.setData(0, ROLE_TYPE, ITEM_TYPE_REQUEST)
                parent_item.addChild(child_item)

    # ------------------------------------------------------------------
    # Item lookup
    # ------------------------------------------------------------------

    def _collection_item(
        self, collection_index: int, item_path: Tuple[int, ...]
    ) -> Optional[CollectionItem]:
        if collection_index < 0 or collection_index >= len(self._collections):
            return None
        if not item_path:
            return None
        collection = self._collections[collection_index]
        items = collection.items
        # Navigate to the parent using all indices except the last
        for idx in item_path[:-1]:
            if idx < 0 or idx >= len(items):
                return None
            items = items[idx].children
        # Access the item at the last index
        last = item_path[-1]
        if last < 0 or last >= len(items):
            return None
        return items[last]

    def _item_data(self, item: QTreeWidgetItem) -> dict:
        return {
            'type': item.data(0, ROLE_TYPE),
            'collection_index': item.data(0, ROLE_COLLECTION_INDEX),
            'item_path': item.data(0, ROLE_ITEM_PATH) or (),
        }

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if not item:
            return

        data = self._item_data(item)
        menu = QMenu(self)
        item_type = data['type']

        if item_type == ITEM_TYPE_COLLECTION:
            expand_action = menu.addAction(tr('collections.expand_all'))
            collapse_action = menu.addAction(tr('collections.collapse_all'))
            expand_action.setEnabled(self._has_expandable_descendant(item))
            collapse_action.setEnabled(self._has_expanded_descendant(item))
            menu.addSeparator()
            rename_action = menu.addAction(tr('collections.rename'))
            delete_action = menu.addAction(tr('collections.delete'))
            menu.addSeparator()
            import_action = menu.addAction(tr('collections.import_postman'))
            menu.addSeparator()
            add_folder_action = menu.addAction(tr('collections.add_folder'))
            add_request_action = menu.addAction(tr('collections.add_request_from_current'))

            action = menu.exec_(self.tree.mapToGlobal(pos))
            if action == expand_action:
                self._expand_item_recursive(item)
            elif action == collapse_action:
                self._collapse_item_recursive(item)
            elif action == rename_action:
                self._rename_collection(data['collection_index'])
            elif action == delete_action:
                self._delete_collection(data['collection_index'])
            elif action == import_action:
                self._import_postman()
            elif action == add_folder_action:
                self._add_folder(data['collection_index'], ())
            elif action == add_request_action:
                self._add_request_from_current(data['collection_index'], ())

        elif item_type == ITEM_TYPE_FOLDER:
            expand_action = menu.addAction(tr('collections.expand_all'))
            collapse_action = menu.addAction(tr('collections.collapse_all'))
            expand_action.setEnabled(self._has_expandable_descendant(item))
            collapse_action.setEnabled(self._has_expanded_descendant(item))
            menu.addSeparator()
            rename_action = menu.addAction(tr('collections.rename'))
            delete_action = menu.addAction(tr('collections.delete'))
            menu.addSeparator()
            add_folder_action = menu.addAction(tr('collections.add_folder'))
            add_request_action = menu.addAction(tr('collections.add_request_from_current'))

            action = menu.exec_(self.tree.mapToGlobal(pos))
            if action == expand_action:
                self._expand_item_recursive(item)
            elif action == collapse_action:
                self._collapse_item_recursive(item)
            elif action == rename_action:
                self._rename_item(data['collection_index'], data['item_path'])
            elif action == delete_action:
                self._delete_item(data['collection_index'], data['item_path'])
            elif action == add_folder_action:
                self._add_folder(data['collection_index'], data['item_path'])
            elif action == add_request_action:
                self._add_request_from_current(data['collection_index'], data['item_path'])

        elif item_type == ITEM_TYPE_REQUEST:
            open_action = menu.addAction(tr('collections.open'))
            update_action = menu.addAction(tr('collections.update_from_current'))
            menu.addSeparator()
            rename_action = menu.addAction(tr('collections.rename'))
            delete_action = menu.addAction(tr('collections.delete'))

            action = menu.exec_(self.tree.mapToGlobal(pos))
            if action == open_action:
                self._open_request(data['collection_index'], data['item_path'])
            elif action == update_action:
                self._update_request_from_current(data['collection_index'], data['item_path'])
            elif action == rename_action:
                self._rename_item(data['collection_index'], data['item_path'])
            elif action == delete_action:
                self._delete_item(data['collection_index'], data['item_path'])

    # ------------------------------------------------------------------
    # Expand / Collapse
    # ------------------------------------------------------------------

    @staticmethod
    def _expand_item_recursive(item: QTreeWidgetItem) -> None:
        item.setExpanded(True)
        for i in range(item.childCount()):
            CollectionPanel._expand_item_recursive(item.child(i))

    @staticmethod
    def _collapse_item_recursive(item: QTreeWidgetItem) -> None:
        item.setExpanded(False)
        for i in range(item.childCount()):
            CollectionPanel._collapse_item_recursive(item.child(i))

    @staticmethod
    def _has_expandable_descendant(item: QTreeWidgetItem) -> bool:
        """True if item has at least one child (expand would show something)."""
        return item.childCount() > 0

    @staticmethod
    def _has_expanded_descendant(item: QTreeWidgetItem) -> bool:
        """True if any descendant is currently expanded."""
        for i in range(item.childCount()):
            child = item.child(i)
            if child.isExpanded():
                return True
            if CollectionPanel._has_expanded_descendant(child):
                return True
        return False

    # ------------------------------------------------------------------
    # Drag-drop helpers
    # ------------------------------------------------------------------

    def _is_descendant(self, ancestor_data: dict, target_data: dict) -> bool:
        """Check if target is a descendant of ancestor (same collection, target path starts with ancestor path)."""
        if ancestor_data['collection_index'] != target_data['collection_index']:
            return False
        a_path = ancestor_data['item_path']
        t_path = target_data['item_path']
        if not a_path or len(t_path) <= len(a_path):
            return False
        return t_path[:len(a_path)] == a_path

    def _highlight_item(
        self, collection_index: int, item_path: Tuple[int, ...]
    ) -> None:
        """Select and scroll to the tree item at the given path."""
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top.data(0, ROLE_COLLECTION_INDEX) == collection_index:
                target = self._find_tree_item(top, item_path) if item_path else top
                if target:
                    self.tree.setCurrentItem(target)
                    self.tree.scrollToItem(target)
                return

    @staticmethod
    def _find_tree_item(parent: QTreeWidgetItem, path: Tuple[int, ...]) -> Optional[QTreeWidgetItem]:
        """Find a tree widget item by walking the index path."""
        current = parent
        for idx in path:
            if 0 <= idx < current.childCount():
                current = current.child(idx)
            else:
                return None
        return current

    def _expand_parent_for_move(
        self, target_data: dict, drop_pos: QAbstractItemView.DropIndicatorPosition
    ) -> None:
        """Expand the right folder after a drag-drop so the moved item is visible."""
        ci = target_data['collection_index']
        path = target_data['item_path']
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top.data(0, ROLE_COLLECTION_INDEX) == ci:
                if drop_pos == QAbstractItemView.OnItem:
                    node = self._find_tree_item(top, path)
                else:
                    node = self._find_tree_item(top, path[:-1]) if path else top
                while node:
                    node.setExpanded(True)
                    node = node.parent()
                return

    def _scroll_to_last_child(self, collection_index: int, parent_path: Tuple[int, ...]) -> None:
        """Scroll to and select the last child of the given parent."""
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top.data(0, ROLE_COLLECTION_INDEX) == collection_index:
                parent = self._find_tree_item(top, parent_path) if parent_path else top
                if parent and parent.childCount() > 0:
                    last = parent.child(parent.childCount() - 1)
                    self.tree.setCurrentItem(last)
                    self.tree.scrollToItem(last)
                return

    def _move_item(
        self,
        source_data: dict,
        target_data: dict,
        drop_pos: QAbstractItemView.DropIndicatorPosition,
    ) -> bool:
        """Move a CollectionItem from source position to target position in the data model."""
        src_ci = source_data['collection_index']
        src_path = source_data['item_path']
        tgt_ci = target_data['collection_index']
        tgt_path = target_data['item_path']

        # Remove source from its parent
        src_parent_path = src_path[:-1]
        src_idx = src_path[-1]
        src_items = self._get_items_container(src_ci, src_parent_path)
        if src_idx < 0 or src_idx >= len(src_items):
            return False
        moved = src_items.pop(src_idx)

        # Calculate target insertion position
        if drop_pos == QAbstractItemView.OnItem:
            # Drop onto a collection or folder — add as last child
            if target_data['type'] == ITEM_TYPE_REQUEST:
                return False
            tgt_items = self._get_items_container(tgt_ci, tgt_path)
            tgt_items.append(moved)
        elif drop_pos == QAbstractItemView.AboveItem:
            tgt_items = self._get_items_container(tgt_ci, tgt_path[:-1])
            insert_at = tgt_path[-1]
            if src_ci == tgt_ci and src_parent_path == tgt_path[:-1] and src_idx < insert_at:
                insert_at -= 1
            tgt_items.insert(insert_at, moved)
        elif drop_pos == QAbstractItemView.BelowItem:
            tgt_items = self._get_items_container(tgt_ci, tgt_path[:-1])
            insert_at = tgt_path[-1] + 1
            if src_ci == tgt_ci and src_parent_path == tgt_path[:-1] and src_idx < insert_at:
                insert_at -= 1
            tgt_items.insert(insert_at, moved)
        else:
            return False

        self.store._write(self._collections)
        return True

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        data = self._item_data(item)
        if data['type'] == ITEM_TYPE_REQUEST:
            self._open_request(data['collection_index'], data['item_path'])

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def _add_collection(self) -> None:
        name = prompt_text(self, tr('collections.prompt_title'), tr('collections.prompt_name'))
        if not name:
            return
        collection = Collection(name=name)
        self.store.add(collection)
        self.reload()
        # Scroll to the newly added collection (last top-level item)
        if self.tree.topLevelItemCount() > 0:
            last = self.tree.topLevelItem(self.tree.topLevelItemCount() - 1)
            self.tree.setCurrentItem(last)
            self.tree.scrollToItem(last)
        self.collections_changed.emit()

    def _rename_collection(self, collection_index: int) -> None:
        collection = self._collections[collection_index]
        new_name = prompt_text(
            self, tr('collections.prompt_title'), tr('collections.prompt_name'),
            initial=collection.name,
        )
        if not new_name:
            return
        self.store.rename(collection.id, new_name)
        self.reload()
        self.collections_changed.emit()

    def _delete_collection(self, collection_index: int) -> None:
        collection = self._collections[collection_index]
        if not ask_yes_no(
            self,
            tr('collections.confirm_delete'),
            tr('collections.confirm_delete_body', name=collection.name),
        ):
            return
        self.store.delete(collection.id)
        self.reload()
        self.collections_changed.emit()

    def _get_items_container(self, collection_index: int, item_path: Tuple[int, ...]) -> List[CollectionItem]:
        """Return the list that contains the item at item_path (the parent's children)."""
        if not item_path:
            return self._collections[collection_index].items
        parent_path = item_path[:-1]
        if not parent_path:
            return self._collections[collection_index].items
        parent = self._collection_item(collection_index, parent_path)
        if parent is None:
            return []
        return parent.children

    def _add_folder(self, collection_index: int, parent_path: Tuple[int, ...]) -> None:
        name = prompt_text(
            self, tr('collections.folder_prompt_title'), tr('collections.prompt_name'),
        )
        if not name:
            return
        items = self._get_items_container(collection_index, parent_path)
        items.append(CollectionItem(name=name))
        self.store._write(self._collections)
        self.reload()
        self._scroll_to_last_child(collection_index, parent_path)
        self.collections_changed.emit()

    def _add_request_from_current(self, collection_index: int, parent_path: Tuple[int, ...]) -> None:
        """Create a new collection item from the active request tab."""
        current_req = self._get_current_request() if self._get_current_request else None
        if current_req is None:
            message_warning(self, '', tr('collections.no_active_tab'))
            return
        name = prompt_text(
            self, tr('collections.request_prompt_title'), tr('collections.prompt_name'),
            initial=current_req.method + ' ' + (current_req.url or ''),
        )
        if not name:
            return
        items = self._get_items_container(collection_index, parent_path)
        items.append(CollectionItem(name=name, request=current_req))
        self.store._write(self._collections)
        self.reload()
        self._scroll_to_last_child(collection_index, parent_path)
        self.collections_changed.emit()

    def _update_request_from_current(self, collection_index: int, item_path: Tuple[int, ...]) -> None:
        """Overwrite a collection item's request with the active tab's request."""
        current_req = self._get_current_request() if self._get_current_request else None
        if current_req is None:
            message_warning(self, '', tr('collections.no_active_tab'))
            return
        item = self._collection_item(collection_index, item_path)
        if item is None:
            return
        item.request = current_req
        self.store._write(self._collections)
        self.reload()
        self.collections_changed.emit()

    def _rename_item(self, collection_index: int, item_path: Tuple[int, ...]) -> None:
        item = self._collection_item(collection_index, item_path)
        if item is None:
            return
        new_name = prompt_text(
            self, tr('collections.prompt_title'), tr('collections.prompt_name'),
            initial=item.name,
        )
        if not new_name:
            return
        item.name = new_name
        self.store._write(self._collections)
        self.reload()
        self.collections_changed.emit()

    def _delete_item(self, collection_index: int, item_path: Tuple[int, ...]) -> None:
        item = self._collection_item(collection_index, item_path)
        if item is None:
            return
        if not ask_yes_no(
            self,
            tr('collections.confirm_delete'),
            tr('collections.confirm_delete_body', name=item.name),
        ):
            return
        parent_path = item_path[:-1]
        items = self._get_items_container(collection_index, parent_path)
        idx = item_path[-1]
        if 0 <= idx < len(items):
            items.pop(idx)
        self.store._write(self._collections)
        self.reload()
        self.collections_changed.emit()

    def _open_request(self, collection_index: int, item_path: Tuple[int, ...]) -> None:
        item = self._collection_item(collection_index, item_path)
        if item is None or item.request is None:
            return
        self.request_selected.emit(item.request, item.name)

    def _import_postman(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr('collections.import_postman'),
            '',
            tr('collections.postman_file_filter'),
        )
        if not file_path:
            return
        try:
            collection = parse_postman_collection_file(file_path)
        except Exception as exc:
            message_warning(
                self,
                tr('collections.import_error_title'),
                tr('collections.import_error', error=str(exc)),
            )
            return
        # Count requests (leaf nodes)
        def _count_req(items):
            count = 0
            for c in items:
                if c.request is not None:
                    count += 1
                count += _count_req(c.children)
            return count
        count = _count_req(collection.items)
        self.store.add(collection)
        self.reload()
        self.collections_changed.emit()
        message_info(
            self,
            tr('collections.import_success_title'),
            tr('collections.import_success', name=collection.name, count=count),
        )

    # ------------------------------------------------------------------
    # Retranslation
    # ------------------------------------------------------------------

    def retranslate_ui(self) -> None:
        self._title_label.setText(tr('collections.title'))
        self._add_btn.setToolTip(tr('collections.add_collection'))
