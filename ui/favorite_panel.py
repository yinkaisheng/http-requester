#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Favorites sidebar panel — tree of API request groups."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QDrag
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.favorite_models import FavoriteItem
from models.http_models import HttpRequest
from storage.app_config import get_app_config
from storage.favorite_store import FavoriteStore
from services.postman_import import parse_postman_collection_file
from i18n import tr
from ui.dialog_i18n import ask_yes_no, message_warning, message_info
from ui.dialogs import prompt_text
from ui.theme import active_theme_palette

# Item-type markers stored at Qt.UserRole
ITEM_TYPE_FOLDER = 'folder'
ITEM_TYPE_FAVORITE = 'favorite'

ROLE_TYPE = Qt.UserRole           # ITEM_TYPE_FOLDER or ITEM_TYPE_FAVORITE
ROLE_ITEM_ID = Qt.UserRole + 1    # FavoriteItem.id (UUID string)


# ======================================================================
#  _FavoriteTreeWidget — tree with two drag-drop modes
# ======================================================================

class _FavoriteTreeWidget(QTreeWidget):
    """QTreeWidget that:

    * emits ``itemMoved`` on successful drag-drop
    * preserves ALL descendant expanded states of moved items
    * prevents dropping onto a favorite leaf (only folders accept drops)
    * when dragging over the **left icon/indentation area**, inserts as
      sibling (instead of child) with a visual indicator line
    """

    itemMoved = pyqtSignal(QTreeWidgetItem)
    renameRequested = pyqtSignal(QTreeWidgetItem)
    deleteRequested = pyqtSignal(QTreeWidgetItem)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        # ---- unique tree id for cut/paste clipboard check ----
        self._tree_id = uuid.uuid4().hex

        # ---- drag-drop configuration ----
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)

        # ---- custom sibling-insert state (icon-area drag) ----
        self._sibling_dragging = False
        self._sibling_indicator_target: Optional[QTreeWidgetItem] = None
        self._sibling_above = True

        # ---- empty-state hint (drawn in paintEvent) ----

    # ------------------------------------------------------------------
    #  Drag appearance — semi-transparent drag item
    # ------------------------------------------------------------------

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item is None:
            return

        # Create MIME data so Qt's default drop handler can identify
        # this as an internal move (required for InternalMove mode).
        indexes = self.selectedIndexes()
        if not indexes:
            idx = self.currentIndex()
            if idx.isValid():
                indexes = [idx]
        mime_data = None
        if indexes:
            mime_data = self.model().mimeData(indexes)

        # Capture the visual area of the item being dragged
        rect = self.visualItemRect(item)

        # Expand the rect to include visible children
        if item.isExpanded():
            for i in range(item.childCount()):
                child_rect = self.visualItemRect(item.child(i))
                if child_rect.isValid():
                    rect = rect.united(child_rect)

        rect.adjust(-2, -2, 4, 4)

        # Grab the viewport content for this area
        pixmap = self.viewport().grab(rect)

        # Create a semi-transparent version
        transparent = QPixmap(pixmap.size())
        transparent.fill(Qt.transparent)
        painter = QPainter(transparent)
        painter.setOpacity(0.5)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        drag = QDrag(self)
        drag.setPixmap(transparent)
        if mime_data is not None:
            drag.setMimeData(mime_data)
        # Hot-spot at left edge so the pixmap's left aligns with the cursor
        drag.setHotSpot(QPoint(0, 8))

        # Execute the drag (blocking, enters modal loop);
        # our dropEvent handles the actual move.
        drag.exec_(supportedActions)

    # ------------------------------------------------------------------
    #  drag-enter — always accept; validation happens in dragMoveEvent
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event):
        event.accept()

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_folder(item: QTreeWidgetItem) -> bool:
        return item.data(0, ROLE_TYPE) == ITEM_TYPE_FOLDER

    @staticmethod
    def _is_descendant_of(item: QTreeWidgetItem, ancestor: QTreeWidgetItem) -> bool:
        p = item.parent()
        while p is not None:
            if p is ancestor:
                return True
            p = p.parent()
        return False

    # ------------------------------------------------------------------
    #  drag-move — icon area → sibling insert; right area → Qt default
    # ------------------------------------------------------------------

    def dragMoveEvent(self, event):
        target = self.itemAt(event.pos())

        # ---- Icon-area branch ----
        if target is not None:
            rect = self.visualItemRect(target)
            if event.pos().x() < rect.left():
                cur = self.currentItem()
                if cur is not None and (target is cur or self._is_descendant_of(target, cur)):
                    self._clear_sibling_state()
                    event.ignore()
                    return

                mid_y = rect.top() + rect.height() // 2
                self._sibling_above = event.pos().y() < mid_y
                self._sibling_indicator_target = target
                self._sibling_dragging = True
                event.accept()
                self.viewport().update()
                return

        # ---- Default branch — Qt native InternalMove ----
        self._clear_sibling_state()

        # Prevent dropping onto a favorite leaf (OnItem = as child)
        if target is not None and not self._is_folder(target):
            if self.dropIndicatorPosition() == QAbstractItemView.OnItem:
                event.ignore()
                return

        super().dragMoveEvent(event)

    # ------------------------------------------------------------------
    #  drop — icon area → deferred sibling insert; right area → Qt
    # ------------------------------------------------------------------

    def dropEvent(self, event):
        item = self.currentItem()
        if item is None:
            self._clear_sibling_state()
            super().dropEvent(event)
            return

        # ---- Icon-area branch: deferred sibling insert ----
        if self._sibling_dragging and self._sibling_indicator_target is not None:
            target = self._sibling_indicator_target
            if target is not item:
                expanded_states = self._collect_expanded(item)
                QTimer.singleShot(0, lambda it=item, tg=target,
                                  ab=self._sibling_above, es=expanded_states:
                                  self._execute_sibling_move(it, tg, ab, es))
            self._clear_sibling_state()
            return

        # ---- Default branch: Qt InternalMove ----
        target = self.itemAt(event.pos())
        # Reject dropping onto a favorite leaf
        if target is not None and not self._is_folder(target):
            if self.dropIndicatorPosition() == QAbstractItemView.OnItem:
                event.ignore()
                self._clear_sibling_state()
                return

        # Prevent dropping into own parent when already inside
        if target is not None and item.parent() is target:
            if self.dropIndicatorPosition() == QAbstractItemView.OnItem:
                event.ignore()
                self._clear_sibling_state()
                return

        expanded_states = self._collect_expanded(item)
        super().dropEvent(event)
        QTimer.singleShot(0, lambda it=item, es=expanded_states:
                          self._execute_internal_move_finish(it, es))

    # ------------------------------------------------------------------
    #  Paint — sibling-insert indicator line
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        super().paintEvent(event)

        if self.topLevelItemCount() == 0:
            painter = QPainter(self.viewport())
            painter.setPen(QColor(active_theme_palette().text_disabled))
            font = painter.font()
            font.setPointSize(font.pointSize() + 1)
            painter.setFont(font)
            painter.drawText(self.viewport().rect(), Qt.AlignCenter, tr('favorites.empty_hint'))
            painter.end()

        if self._sibling_dragging and self._sibling_indicator_target is not None:
            painter = QPainter(self.viewport())
            # Use the theme's highlight/accent colour (Send-button blue)
            accent = QColor(active_theme_palette().highlight)
            pen = QPen(accent, 3)
            painter.setPen(pen)

            rect = self.visualItemRect(self._sibling_indicator_target)
            y = rect.top() if self._sibling_above else rect.bottom()
            painter.drawLine(rect.left(), y, self.viewport().width(), y)
            painter.end()

    # ------------------------------------------------------------------
    #  drag-leave — clear indicator
    # ------------------------------------------------------------------

    def dragLeaveEvent(self, event):
        self._clear_sibling_state()
        super().dragLeaveEvent(event)

    # ------------------------------------------------------------------
    #  State management
    # ------------------------------------------------------------------

    def _clear_sibling_state(self):
        self._sibling_dragging = False
        self._sibling_indicator_target = None
        self.viewport().update()

    # ------------------------------------------------------------------
    #  Cut / paste helpers
    # ------------------------------------------------------------------

    @property
    def tree_id(self) -> str:
        return self._tree_id

    def get_item_path(self, item: QTreeWidgetItem) -> List[int]:
        """Return the index-path from root to *item*: ``[top_idx, …, child_idx]``."""
        path: List[int] = []
        node: Optional[QTreeWidgetItem] = item
        while node is not None:
            parent = node.parent()
            if parent:
                path.append(parent.indexOfChild(node))
            else:
                path.append(self.indexOfTopLevelItem(node))
            node = parent
        path.reverse()
        return path

    def get_item_by_path(self, path: List[int]) -> Optional[QTreeWidgetItem]:
        """Return the |QTreeWidgetItem| at *path*, or ``None`` if invalid."""
        node: Optional[QTreeWidgetItem] = None
        for idx in path:
            if node is None:
                if 0 <= idx < self.topLevelItemCount():
                    node = self.topLevelItem(idx)
                else:
                    return None
            else:
                if 0 <= idx < node.childCount():
                    node = node.child(idx)
                else:
                    return None
        return node

    # ------------------------------------------------------------------
    #  Keyboard shortcuts
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F2:
            item = self.currentItem()
            if item is not None:
                self.renameRequested.emit(item)
            event.accept()
            return
        if event.key() == Qt.Key_Delete:
            item = self.currentItem()
            if item is not None:
                self.deleteRequested.emit(item)
            event.accept()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    #  Expanded-state helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_expanded(item: QTreeWidgetItem) -> Dict[int, bool]:
        states = {id(item): item.isExpanded()}
        for i in range(item.childCount()):
            states.update(_FavoriteTreeWidget._collect_expanded(item.child(i)))
        return states

    @staticmethod
    def _restore_expanded_map(item: QTreeWidgetItem, states: Dict[int, bool]):
        if id(item) in states:
            item.setExpanded(states[id(item)])
        for i in range(item.childCount()):
            _FavoriteTreeWidget._restore_expanded_map(item.child(i), states)
        parent = item.parent()
        if parent is not None and _FavoriteTreeWidget._is_folder(parent):
            parent.setExpanded(True)

    # ------------------------------------------------------------------
    #  Manual sibling insert
    # ------------------------------------------------------------------

    def _insert_as_sibling(self, item: QTreeWidgetItem,
                           target: QTreeWidgetItem, above: bool) -> QTreeWidgetItem:
        """Remove *item* from its current position and insert it as a
        sibling of *target*, before (*above*=True) or after (False)."""
        # Record target index
        item_parent = item.parent()
        target_parent = target.parent()

        if target_parent:
            target_idx = target_parent.indexOfChild(target)
        else:
            target_idx = self.indexOfTopLevelItem(target)

        # Remove item from its current parent
        if item_parent:
            item_idx = item_parent.indexOfChild(item)
            moved = item_parent.takeChild(item_idx)
            if moved is None:
                moved = item
            if item_parent is target_parent and item_idx < target_idx:
                target_idx -= 1
        else:
            item_idx = self.indexOfTopLevelItem(item)
            moved = self.takeTopLevelItem(item_idx)
            if moved is None:
                moved = item
            if item_parent is target_parent or (target_parent is None and item_idx < target_idx):
                target_idx -= 1

        # Insert at computed position
        insert_idx = target_idx if above else target_idx + 1
        if target_parent:
            target_parent.insertChild(insert_idx, moved)
            target_parent.setExpanded(True)
        else:
            self.insertTopLevelItem(insert_idx, moved)

        return moved

    def _execute_sibling_move(self, item: QTreeWidgetItem,
                              target: QTreeWidgetItem, above: bool,
                              expanded_states: Dict[int, bool]):
        if target is item or self._is_descendant_of(target, item):
            self.setCurrentItem(item)
            return
        moved = self._insert_as_sibling(item, target, above)
        self._restore_expanded_map(moved, expanded_states)
        self.itemMoved.emit(moved)
        self.setCurrentItem(moved)

    def _execute_internal_move_finish(self, item: QTreeWidgetItem,
                                      expanded_states: Dict[int, bool]):
        self._restore_expanded_map(item, expanded_states)
        self.itemMoved.emit(item)
        self.setCurrentItem(item)


# ======================================================================
#  FavoritePanel
# ======================================================================

class FavoritePanel(QWidget):
    """Tree view of favorites, with context menus for management.

    Stores a flat list of root |FavoriteItem| nodes.  Every modification
    to the tree (drag-drop, rename, delete, add) syncs the in-memory
    ``self._items`` list from the widget tree and persists via the store.
    """

    request_selected = pyqtSignal(HttpRequest, str)  # request, name
    favorites_changed = pyqtSignal()

    def __init__(
        self,
        favorite_store: FavoriteStore,
        get_current_request: Optional[Callable[[], Optional[HttpRequest]]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.store = favorite_store
        self._get_current_request = get_current_request
        self._items: List[FavoriteItem] = []
        self._init_ui()
        self.reload()

    # ------------------------------------------------------------------
    #  UI setup
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Filter row: [QLineEdit] [× clear]
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(4)
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText(tr('favorites.filter_placeholder'))
        self._filter_edit.setClearButtonEnabled(False)
        self._filter_edit.textChanged.connect(self._on_filter_text_changed)
        filter_layout.addWidget(self._filter_edit, 0, Qt.AlignVCenter)

        self._clear_btn = QPushButton('×')
        self._clear_btn.setObjectName('favoriteClearButton')
        self._clear_btn.setMaximumWidth(36)
        self._clear_btn.setToolTip(tr('favorites.clear_filter'))
        self._clear_btn.clicked.connect(self._clear_filter)
        filter_layout.addWidget(self._clear_btn, 0, Qt.AlignVCenter)
        filter_layout.addStretch()  # push filter group to the left
        layout.addLayout(filter_layout)

        # Tree
        self.tree = _FavoriteTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.itemMoved.connect(self._on_tree_item_moved)
        self.tree.renameRequested.connect(self._rename_item)
        self.tree.deleteRequested.connect(lambda item: self._delete_item(item, confirm=True))
        self.tree.setAnimated(True)
        self.tree.setIndentation(16)
        # Apply global UI font
        appearance = get_app_config().appearance
        tree_font = QFont()
        tree_font.setPixelSize(appearance.ui_font_size_px)
        self.tree.setFont(tree_font)
        layout.addWidget(self.tree, 1)

    # ------------------------------------------------------------------
    #  Load / rebuild
    # ------------------------------------------------------------------

    def reload(self) -> None:
        self._items = self.store.load()
        self._rebuild_tree()

    def _rebuild_tree(self) -> None:
        self.tree.clear()
        for item in self._items:
            self.tree.addTopLevelItem(self._fav_to_tree(item))
        self.tree.expandAll()
        self.tree.viewport().update()

    def _fav_to_tree(self, fav: FavoriteItem) -> QTreeWidgetItem:
        """Convert a |FavoriteItem| into a |QTreeWidgetItem|."""
        tree_item = QTreeWidgetItem([fav.name])
        tree_item.setData(0, ROLE_ITEM_ID, fav.id)
        if fav.is_folder():
            tree_item.setData(0, ROLE_TYPE, ITEM_TYPE_FOLDER)
            tree_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
            font = tree_item.font(0)
            font.setBold(True)
            tree_item.setFont(0, font)
            for child in fav.children:
                tree_item.addChild(self._fav_to_tree(child))
        else:
            tree_item.setData(0, ROLE_TYPE, ITEM_TYPE_FAVORITE)
        return tree_item

    # ------------------------------------------------------------------
    #  Sync data model ← widget tree
    # ------------------------------------------------------------------

    def _sync_data_model(self) -> None:
        """Rebuild ``self._items`` from the current widget tree.

        Existing |FavoriteItem| objects are matched by their stored *id*
        so that attached |HttpRequest| data is preserved.
        """
        # Build lookup by id from the current data model
        lookup: Dict[str, FavoriteItem] = {}
        self._collect_by_id(self._items, lookup)

        new_items: List[FavoriteItem] = []
        for i in range(self.tree.topLevelItemCount()):
            new_items.append(self._tree_to_fav(self.tree.topLevelItem(i), lookup))
        self._items = new_items
        self.store.save_items(self._items)
        self.tree.viewport().update()

    @staticmethod
    def _collect_by_id(items: List[FavoriteItem], out: Dict[str, FavoriteItem]) -> None:
        for item in items:
            out[item.id] = item
            FavoritePanel._collect_by_id(item.children, out)

    def _tree_to_fav(self, tree_item: QTreeWidgetItem,
                     lookup: Dict[str, FavoriteItem]) -> FavoriteItem:
        item_id = tree_item.data(0, ROLE_ITEM_ID)
        name = tree_item.text(0)
        item_type = tree_item.data(0, ROLE_TYPE)
        existing: Optional[FavoriteItem] = lookup.get(item_id)

        if item_type == ITEM_TYPE_FOLDER:
            children: List[FavoriteItem] = []
            for i in range(tree_item.childCount()):
                children.append(self._tree_to_fav(tree_item.child(i), lookup))
            if existing is not None and existing.is_folder():
                existing.name = name
                existing.children = children
                return existing
            return FavoriteItem(id=item_id, name=name, children=children)

        # ITEM_TYPE_FAVORITE
        if existing is not None and existing.request is not None:
            existing.name = name
            return existing
        return FavoriteItem(id=item_id, name=name)

    # ------------------------------------------------------------------
    #  Find FavoriteItem by tree widget item
    # ------------------------------------------------------------------

    def _find_fav_by_tree(self, tree_item: QTreeWidgetItem) -> Optional[FavoriteItem]:
        """Navigate ``self._items`` following the tree path of *tree_item*."""
        # Build path from tree_item → root: [top_idx, ..., child_idx]
        path: List[int] = []
        node: Optional[QTreeWidgetItem] = tree_item
        while node is not None:
            parent = node.parent()
            if parent:
                path.append(parent.indexOfChild(node))
            else:
                path.append(self.tree.indexOfTopLevelItem(node))
            node = parent
        path.reverse()

        if not path:
            return None

        items: List[FavoriteItem] = self._items
        for idx in path[:-1]:
            if 0 <= idx < len(items) and items[idx].is_folder():
                items = items[idx].children
            else:
                return None
        last = path[-1]
        if 0 <= last < len(items):
            return items[last]
        return None

    # ------------------------------------------------------------------
    #  Signal handlers
    # ------------------------------------------------------------------

    def _on_tree_item_moved(self, _item: QTreeWidgetItem) -> None:
        # Drag-drop invalidates any stored cut-path, so clear the
        # cut-state clipboard to prevent pasting to a wrong location.
        clip_text = QApplication.clipboard().text()
        if clip_text.startswith(f'internal_move_tree_item_{self.tree.tree_id}='):
            QApplication.clipboard().clear()
        self._sync_data_model()
        self.favorites_changed.emit()

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        if item.data(0, ROLE_TYPE) != ITEM_TYPE_FAVORITE:
            return
        fav = self._find_fav_by_tree(item)
        if fav is not None and fav.request is not None:
            self.request_selected.emit(fav.request, fav.name)

    # ------------------------------------------------------------------
    #  Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        menu = QMenu(self)

        if item is None:
            # Right-click on empty space → root-level actions
            add_folder = menu.addAction(tr('favorites.add_favorite_dir'))
            add_fav = menu.addAction(tr('favorites.add_favorite_from_current'))
            menu.addSeparator()
            import_action = menu.addAction(tr('favorites.import_postman'))

            has_items = self.tree.topLevelItemCount() > 0
            if has_items:
                menu.addSeparator()
                expand_all_action = menu.addAction(tr('favorites.expand_all'))
                collapse_all_action = menu.addAction(tr('favorites.collapse_all'))

            action = menu.exec_(self.tree.viewport().mapToGlobal(pos))
            if action == add_folder:
                self._add_top_level_folder()
            elif action == add_fav:
                self._add_favorite_to_parent(None)
            elif action == import_action:
                self._import_postman()
            elif has_items:
                if action == expand_all_action:
                    self._expand_all()
                elif action == collapse_all_action:
                    self._collapse_all()
            return

        # Right-click on an existing item
        is_folder = self._is_folder(item)

        if is_folder:
            menu.addAction(tr('favorites.add_favorite_dir'))
            menu.addAction(tr('favorites.add_favorite_from_current'))
            menu.addSeparator()
            menu.addAction(tr('favorites.expand_all'))
            menu.addAction(tr('favorites.collapse_all'))
            menu.addSeparator()
        else:
            menu.addAction(tr('favorites.open'))
            menu.addAction(tr('favorites.update_from_current'))
            menu.addSeparator()
        menu.addAction(tr('favorites.rename'))
        menu.addAction(tr('favorites.delete'))
        menu.addSeparator()

        # Cut — available for every item
        cut_action = menu.addAction(tr('favorites.cut'))

        # Paste — only shown on folder nodes when clipboard has a valid cut item
        paste_action = None
        clip_text = QApplication.clipboard().text()
        prefix = f'internal_move_tree_item_{self.tree.tree_id}='
        if clip_text.startswith(prefix) and is_folder:
            try:
                source_path = json.loads(clip_text[len(prefix):])
                source_item = self.tree.get_item_by_path(source_path)
                paste_action = menu.addAction(tr('favorites.paste'))
                # Disable when target is source itself, or a descendant of source
                if source_item is None or source_item is item or self.tree._is_descendant_of(item, source_item):
                    paste_action.setEnabled(False)
            except (json.JSONDecodeError, TypeError):
                pass

        action = menu.exec_(self.tree.viewport().mapToGlobal(pos))
        if action is None:
            return

        # Check cut/paste actions by reference first
        if action == cut_action:
            self._cut_item(item)
            return
        if paste_action is not None and action == paste_action:
            self._paste_item(item)
            return

        action_text = action.text()

        if is_folder:
            if action_text == tr('favorites.add_favorite_dir'):
                self._add_folder_under(item)
            elif action_text == tr('favorites.add_favorite_from_current'):
                self._add_favorite_to_parent(item)
            elif action_text == tr('favorites.expand_all'):
                self._expand_recursive(item)
            elif action_text == tr('favorites.collapse_all'):
                self._collapse_recursive(item)
            elif action_text == tr('favorites.rename'):
                self._rename_item(item)
            elif action_text == tr('favorites.delete'):
                self._delete_item(item, confirm=False)
        else:
            if action_text == tr('favorites.open'):
                self._on_item_double_clicked(item, 0)
            elif action_text == tr('favorites.update_from_current'):
                self._update_request(item)
            elif action_text == tr('favorites.rename'):
                self._rename_item(item)
            elif action_text == tr('favorites.delete'):
                self._delete_item(item, confirm=False)

    @staticmethod
    def _is_folder(item: QTreeWidgetItem) -> bool:
        return item.data(0, ROLE_TYPE) == ITEM_TYPE_FOLDER

    # ------------------------------------------------------------------
    #  Expand / collapse
    # ------------------------------------------------------------------

    def _expand_recursive(self, item: QTreeWidgetItem) -> None:
        item.setExpanded(True)
        for i in range(item.childCount()):
            child = item.child(i)
            if self._is_folder(child):
                self._expand_recursive(child)

    def _collapse_recursive(self, item: QTreeWidgetItem) -> None:
        item.setExpanded(False)
        for i in range(item.childCount()):
            child = item.child(i)
            if self._is_folder(child):
                self._collapse_recursive(child)

    def _expand_all(self) -> None:
        for i in range(self.tree.topLevelItemCount()):
            self._expand_recursive(self.tree.topLevelItem(i))

    def _collapse_all(self) -> None:
        for i in range(self.tree.topLevelItemCount()):
            self._collapse_recursive(self.tree.topLevelItem(i))

    # ------------------------------------------------------------------
    #  Tree operations
    # ------------------------------------------------------------------

    def _add_top_level_folder(self) -> None:
        name = prompt_text(self, tr('favorites.folder_prompt_title'), tr('favorites.prompt_name'))
        if not name:
            return
        fav = FavoriteItem(name=name)
        tree_item = self._fav_to_tree(fav)
        self.tree.addTopLevelItem(tree_item)
        self._items.append(fav)
        self.store.save_items(self._items)
        self.favorites_changed.emit()
        self.tree.setCurrentItem(tree_item)
        self.tree.scrollToItem(tree_item)

    def _add_folder_under(self, parent_item: QTreeWidgetItem) -> None:
        name = prompt_text(self, tr('favorites.folder_prompt_title'), tr('favorites.prompt_name'))
        if not name:
            return
        fav = FavoriteItem(name=name)
        tree_item = self._fav_to_tree(fav)
        parent_item.addChild(tree_item)
        parent_item.setExpanded(True)
        parent_fav = self._find_fav_by_tree(parent_item)
        if parent_fav is not None:
            parent_fav.children.append(fav)
        self.store.save_items(self._items)
        self.favorites_changed.emit()
        self.tree.setCurrentItem(tree_item)
        self.tree.scrollToItem(tree_item)

    def _add_favorite_to_parent(self, parent_item: Optional[QTreeWidgetItem]) -> None:
        current_req = self._get_current_request() if self._get_current_request else None
        if current_req is None:
            message_warning(self, '', tr('favorites.no_active_tab'))
            return
        name = prompt_text(
            self, tr('favorites.favorite_prompt_title'), tr('favorites.prompt_name'),
            initial=current_req.method + ' ' + (current_req.url or ''),
        )
        if not name:
            return
        fav = FavoriteItem(name=name, request=current_req)
        tree_item = self._fav_to_tree(fav)
        if parent_item is not None:
            parent_item.addChild(tree_item)
            parent_item.setExpanded(True)
            parent_fav = self._find_fav_by_tree(parent_item)
            if parent_fav is not None:
                parent_fav.children.append(fav)
        else:
            self.tree.addTopLevelItem(tree_item)
            self._items.append(fav)
        self.store.save_items(self._items)
        self.favorites_changed.emit()
        self.tree.setCurrentItem(tree_item)
        self.tree.scrollToItem(tree_item)

    def _update_request(self, item: QTreeWidgetItem) -> None:
        current_req = self._get_current_request() if self._get_current_request else None
        if current_req is None:
            message_warning(self, '', tr('favorites.no_active_tab'))
            return
        fav = self._find_fav_by_tree(item)
        if fav is None:
            return
        fav.request = current_req
        self.store.save_items(self._items)
        self.favorites_changed.emit()

    def _rename_item(self, item: QTreeWidgetItem) -> None:
        fav = self._find_fav_by_tree(item)
        if fav is None:
            return
        title_key = 'favorites.folder_prompt_title' if fav.is_folder() else 'favorites.favorite_prompt_title'
        new_name = prompt_text(
            self, tr(title_key), tr('favorites.prompt_name'),
            initial=item.text(0),
        )
        if not new_name or new_name == item.text(0):
            return
        item.setText(0, new_name)
        self._sync_data_model()
        self.favorites_changed.emit()

    def _delete_item(self, item: QTreeWidgetItem, confirm: bool = False) -> None:
        """Delete *item* from the tree.

        *confirm* controls whether a confirmation dialog is shown:
        - ``True``  → always confirm (used by Delete-key shortcut)
        - ``False`` → only confirm for non-empty folders (used by context menu)
        """
        fav = self._find_fav_by_tree(item)
        if fav is None:
            return
        if confirm:
            # Delete key — always ask
            if not ask_yes_no(
                self,
                tr('favorites.confirm_delete'),
                tr('favorites.confirm_delete_body', name=item.text(0)),
            ):
                return
        else:
            # Context menu — only confirm for non-empty folders
            if fav.is_folder() and fav.children:
                if not ask_yes_no(
                    self,
                    tr('favorites.confirm_delete'),
                    tr('favorites.confirm_delete_body', name=item.text(0)),
                ):
                    return
        parent = item.parent()
        if parent:
            parent.removeChild(item)
        else:
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))
        self._sync_data_model()
        self.favorites_changed.emit()

    # ------------------------------------------------------------------
    #  Cut / paste — move any node via clipboard (handy beyond viewport)
    # ------------------------------------------------------------------

    def _cut_item(self, item: QTreeWidgetItem) -> None:
        """Copy the index-path of *item* to the system clipboard for later paste."""
        path = self.tree.get_item_path(item)
        clip_text = f'internal_move_tree_item_{self.tree.tree_id}={json.dumps(path)}'
        QApplication.clipboard().setText(clip_text)

    def _paste_item(self, target_folder: QTreeWidgetItem) -> None:
        """Move the previously cut node into *target_folder*."""
        clip_text = QApplication.clipboard().text()
        prefix = f'internal_move_tree_item_{self.tree.tree_id}='
        if not clip_text.startswith(prefix):
            return
        try:
            source_path = json.loads(clip_text[len(prefix):])
        except (json.JSONDecodeError, TypeError):
            return

        source_item = self.tree.get_item_by_path(source_path)
        if source_item is None or target_folder is None:
            return
        # Disallowed: target is source itself, or target is a descendant of source
        if source_item is target_folder or self.tree._is_descendant_of(target_folder, source_item):
            return

        # Preserve expanded states before removing
        expanded_states = self.tree._collect_expanded(source_item)

        # Remove source from current position
        parent = source_item.parent()
        if parent:
            idx = parent.indexOfChild(source_item)
            moved = parent.takeChild(idx)
        else:
            idx = self.tree.indexOfTopLevelItem(source_item)
            moved = self.tree.takeTopLevelItem(idx)
        if moved is None:
            moved = source_item

        # Insert as child of target folder (at end)
        target_folder.addChild(moved)
        target_folder.setExpanded(True)

        # Restore expanded states
        self.tree._restore_expanded_map(moved, expanded_states)

        self._sync_data_model()
        self.favorites_changed.emit()
        self.tree.setCurrentItem(moved)

    # ------------------------------------------------------------------
    #  Real-time filter
    # ------------------------------------------------------------------

    def _on_filter_text_changed(self, text: str) -> None:
        keyword = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            self._filter_tree_item(item, keyword)

    @staticmethod
    def _filter_tree_item(item: QTreeWidgetItem, keyword: str) -> bool:
        child_visible = False
        for i in range(item.childCount()):
            child = item.child(i)
            if FavoritePanel._filter_tree_item(child, keyword):
                child_visible = True
        self_match = (not keyword) or (keyword in item.text(0).lower())
        visible = self_match or child_visible
        item.setHidden(not visible)
        return visible

    def _clear_filter(self) -> None:
        self._filter_edit.clear()

    # ------------------------------------------------------------------
    #  Import Postman
    # ------------------------------------------------------------------

    def _import_postman(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr('favorites.import_postman'),
            '',
            tr('favorites.postman_file_filter'),
        )
        if not file_path:
            return
        try:
            items = parse_postman_collection_file(file_path)
        except Exception as exc:
            message_warning(
                self,
                tr('favorites.import_error_title'),
                tr('favorites.import_error', error=str(exc)),
            )
            return
        if not items:
            return

        count = self._count_requests(items)
        self._items.extend(items)
        self.store.save_items(self._items)
        self.reload()
        self.favorites_changed.emit()
        message_info(
            self,
            tr('favorites.import_success_title'),
            tr('favorites.import_success', name=items[0].name, count=count),
        )

    @staticmethod
    def _count_requests(items: List[FavoriteItem]) -> int:
        count = 0
        for c in items:
            if c.request is not None:
                count += 1
            count += FavoritePanel._count_requests(c.children)
        return count

    # ------------------------------------------------------------------
    #  Retranslation
    # ------------------------------------------------------------------

    def retranslate_ui(self) -> None:
        self._filter_edit.setPlaceholderText(tr('favorites.filter_placeholder'))
        self._clear_btn.setToolTip(tr('favorites.clear_filter'))
