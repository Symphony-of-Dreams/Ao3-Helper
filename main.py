import os
import re
import shutil
import sqlite3
import sys
import webbrowser
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import (
    QByteArray,
    QItemSelection,
    QItemSelectionModel,
    QPoint,
    QProcess,
    QStringListModel,
    Qt,
    QThread,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QAction, QActionGroup, QCloseEvent, QColor, QIcon, QTextCursor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QCompleter,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import constants as const
from achievements_window import AchievementsWindow
from ao3_manager import ao3_client
from bulk_edit_dialog import BulkEditDialog
from config_manager import config_manager
from database import (
    add_fic,
    add_notification,
    assign_tag_to_fic,
    bulk_add_tags,
    bulk_remove_tags,
    bulk_update_status,
    calculate_base_stats,
    count_read_uncommented_fics,
    count_verified_statuses,
    delete_fic,
    get_all_user_tags,
    get_data_for_charts,
    get_fic_by_url,
    get_fics_for_sync,
    get_filtered_fics,
    get_or_create_tag,
    get_tags_for_fic,
    get_unread_notifications,
    initialize_database,
    remove_tag_from_fic,
    run_database_migrations,
    update_fic_notes,
    update_fic_rating,
    update_fic_status,
)
from gamification import calculate_xp_level, check_for_achievements
from logger_setup import logger
from login_dialog import LoginDialog
from notifications_window import NotificationsWindow
from stats_window import StatsWindow
from tag_management_window import TagManagementWindow
from workers import (
    AddFicWorker,
    ImportBookmarksWorker,
    ImportCollectionWorker,
    ImportSeriesWorker,
    MassImportWorker,
    SyncStatusWorker,
    TotalSyncWorker,
    UpdateCheckWorker,
)

PALETTE_LIGHT = {
    "window_bg": "#f0f0f0",
    "widget_bg": "white",
    "text": "black",
    "text_accent": "#555555",
    "border": "#cccccc",
    "highlight": "#3399ff",
    "highlight_text": "white",
}
PALETTE_DARK = {
    "window_bg": "#2b2b2b",
    "widget_bg": "#3c3c3c",
    "text": "#dddddd",
    "text_accent": "#aaaaaa",
    "border": "#555555",
    "highlight": "#007acc",
    "highlight_text": "white",
}


def resource_path(relative_path: str) -> str:
    try:
        base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class NoteWidget(QTextEdit):
    editingFinished = pyqtSignal()

    def focusOutEvent(self, event: Any) -> None:
        super().focusOutEvent(event)
        self.editingFinished.emit()


class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:
        other_data = other.data(Qt.ItemDataRole.UserRole)
        self_data = self.data(Qt.ItemDataRole.UserRole)
        return (self_data or 0) < (other_data or 0)


class MainWindow(QMainWindow):
    update_thread: Optional[QThread]
    import_thread: Optional[QThread]
    bookmarks_import_thread: Optional[QThread]
    sync_thread: Optional[QThread]
    selected_url: Optional[str]
    fics_in_memory: Dict[str, sqlite3.Row]
    _ignore_selection_change: bool
    status_text_colors: Dict[str, QColor]
    manual_override_enabled: bool
    current_theme: str
    column_map: List[str]
    fics_table: QTableWidget
    word_count_label: QLabel
    fic_count_label: QLabel
    version_label: QLabel
    theme_action_group: QActionGroup
    default_theme_action: QAction
    light_theme_action: QAction
    dark_theme_action: QAction
    url_input: QLineEdit
    add_button: QPushButton
    stats_button: QPushButton
    notifications_button: QPushButton
    refresh_button: QPushButton
    import_author_button: QPushButton
    search_combo: QComboBox
    search_input: QLineEdit
    completer_model: QStringListModel
    completer: QCompleter
    status_filter_combo: QComboBox
    level_label: QLabel
    xp_bar: QProgressBar
    fic_stats_label: QLabel
    kudos_stats_label: QLabel
    comment_stats_label: QLabel
    achievements_button: QPushButton
    detail_title: QLabel
    detail_close_button: QPushButton
    detail_author: QLabel
    detail_info: QLabel
    detail_category: QLabel
    detail_relationships: QLabel
    detail_characters: QLabel
    detail_tags: QLabel
    detail_user_tags: QTextBrowser
    tag_input: QLineEdit
    add_tag_button: QPushButton
    detail_summary: QTextEdit
    detail_notes: NoteWidget
    to_read_button: QPushButton
    read_button: QPushButton
    kudosed_button: QPushButton
    commented_button: QPushButton
    dropped_button: QPushButton
    sync_status_button: QPushButton
    open_browser_button: QPushButton
    rating_buttons: List[QPushButton]
    delete_button: QPushButton
    add_fic_thread: Optional[QThread] = None
    worker: Optional[AddFicWorker]
    import_worker: Optional[MassImportWorker]
    bookmarks_import_worker: Optional[ImportBookmarksWorker]
    collection_import_thread: Optional[QThread] = None
    collection_import_worker: Optional[ImportCollectionWorker] = None
    total_sync_thread: Optional[QThread] = None
    total_sync_worker: Optional[TotalSyncWorker] = None
    bulk_edit_dialog: Optional[BulkEditDialog] = None

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AO3 Helper - Your Fanfiction Archive")
        self.setGeometry(200, 200, 1200, 700)
        self.setWindowIcon(QIcon(resource_path("assets/app_icon.ico")))

        self.add_fic_thread: Optional[QThread] = None
        self.worker: Optional[AddFicWorker] = None
        self.update_thread: Optional[QThread] = None
        self.import_thread: Optional[QThread] = None
        self.sync_thread: Optional[QThread] = None
        self.bookmarks_import_thread, self.bookmarks_import_worker = None, None
        self.selected_url: Optional[str] = None
        self.collection_import_worker: Optional[ImportCollectionWorker] = None
        self.series_import_thread: Optional[QThread] = None  # <-- NUOVO
        self.series_import_worker: Optional[ImportSeriesWorker] = None  # <-- NUOVO
        self.total_sync_thread: Optional[QThread] = None
        self.fics_in_memory: Dict[str, sqlite3.Row] = {}
        self._ignore_selection_change: bool = False
        self.status_text_colors: Dict[str, QColor] = {}
        self.manual_override_enabled: bool
        self.current_theme: str
        self.column_map: List[str]

        self.welcome_label: QLabel
        self.fics_table: QTableWidget
        self.word_count_label: QLabel
        self.fic_count_label: QLabel
        self.version_label = QLabel(f"|| Version {const.APP_VERSION}")
        self.theme_action_group: QActionGroup
        self.default_theme_action: QAction
        self.light_theme_action: QAction
        self.dark_theme_action: QAction
        self.url_input: QLineEdit
        self.add_button: QPushButton
        self.stats_button: QPushButton
        self.notifications_button: QPushButton
        self.refresh_button: QPushButton
        self.import_author_button: QPushButton
        self.search_combo: QComboBox
        self.search_input: QLineEdit
        self.completer_model: QStringListModel
        self.completer: QCompleter
        self.status_filter_combo: QComboBox
        self.level_label: QLabel
        self.xp_bar: QProgressBar
        self.fic_stats_label: QLabel
        self.kudos_stats_label: QLabel
        self.comment_stats_label: QLabel
        self.achievements_button: QPushButton
        self.detail_title: QLabel
        self.detail_close_button: QPushButton
        self.detail_author: QLabel
        self.detail_info: QLabel
        self.detail_category: QLabel
        self.detail_relationships: QLabel
        self.detail_characters: QLabel
        self.detail_tags: QLabel
        self.detail_user_tags: QTextBrowser
        self.tag_input: QLineEdit
        self.add_tag_button: QPushButton
        self.detail_summary: QTextEdit
        self.detail_notes: NoteWidget
        self.to_read_button: QPushButton
        self.read_button: QPushButton
        self.kudosed_button: QPushButton
        self.commented_button: QPushButton
        self.dropped_button: QPushButton
        self.sync_status_button: QPushButton
        self.open_browser_button: QPushButton
        self.rating_buttons: List[QPushButton]
        self.delete_button: QPushButton

        self.tag_completer: QCompleter
        self.tag_completer_model: QStringListModel

        self.selected_url, self.fics_in_memory, self._ignore_selection_change = (None, {}, False)
        self.manual_override_enabled = config_manager.getboolean(
            const.CONFIG_SECTION_SETTINGS, const.CONFIG_KEY_MANUAL_OVERRIDE, fallback=False
        )
        self.current_theme = config_manager.get(
            const.CONFIG_SECTION_SETTINGS, const.CONFIG_KEY_THEME, fallback=const.THEME_DEFAULT
        )

        self._create_main_widgets()
        self._setup_fics_table()
        self._create_menu()
        self._create_main_layout()
        self._connect_signals()

        if self.current_theme == const.THEME_DARK:
            self.dark_theme_action.setChecked(True)
            self._apply_theme(PALETTE_DARK)
        elif self.current_theme == const.THEME_LIGHT:
            self.light_theme_action.setChecked(True)
            self._apply_theme(PALETTE_LIGHT)
        else:
            self.default_theme_action.setChecked(True)
            self._apply_theme(None)

        self._update_fics_table()
        self._update_search_completer()
        self._update_tag_completer()  # Questa chiamata che hai già aggiunto è corretta
        self._load_settings()
        self._generate_startup_notification()
        self._update_welcome_message()
        self.start_update_check()
        self._update_menu_actions_visibility()

    def _create_main_widgets(self) -> None:
        self.column_map = const.COLUMN_MAP
        self.fics_table = QTableWidget()
        self.fics_table.setColumnCount(len(self.column_map))
        self.fics_table.setHorizontalHeaderLabels(self.column_map)
        self.version_label = QLabel(f"|| Version {const.APP_VERSION}")
        self.fic_count_label = QLabel("Total Fics: -")
        self.word_count_label = QLabel("Words Read: -")
        status_bar = self.statusBar()
        if status_bar:
            status_bar.addPermanentWidget(self.word_count_label)
            status_bar.addPermanentWidget(self.fic_count_label)
            status_bar.addPermanentWidget(self.version_label)

    def _create_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")

        settings_action = QAction("Settings / Login...", self)
        settings_action.triggered.connect(self._open_login_dialog)
        file_menu.addAction(settings_action)
        self.logout_action = QAction("Logout", self)
        self.logout_action.triggered.connect(self._perform_logout)
        file_menu.addAction(self.logout_action)
        file_menu.addSeparator()

        file_menu.addSeparator()
        backup_action = QAction("Backup Database...", self)
        backup_action.triggered.connect(self._backup_database)
        file_menu.addAction(backup_action)
        restore_action = QAction("Restore Database...", self)
        restore_action.triggered.connect(self._restore_database)
        file_menu.addAction(restore_action)
        file_menu.addSeparator()
        manage_tags_action = QAction("Manage Tags...", self)
        manage_tags_action.triggered.connect(self._open_tag_management_window)
        file_menu.addAction(manage_tags_action)

        view_menu = menu_bar.addMenu("&View")
        theme_menu = view_menu.addMenu("Theme")
        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.setExclusive(True)

        self.default_theme_action = QAction("Default (System)", self)
        self.default_theme_action.setCheckable(True)
        self.default_theme_action.triggered.connect(lambda: self._change_theme(const.THEME_DEFAULT))
        theme_menu.addAction(self.default_theme_action)
        self.theme_action_group.addAction(self.default_theme_action)

        self.light_theme_action = QAction("Light (Custom)", self)
        self.light_theme_action.setCheckable(True)
        self.light_theme_action.triggered.connect(lambda: self._change_theme(const.THEME_LIGHT))
        theme_menu.addAction(self.light_theme_action)
        self.theme_action_group.addAction(self.light_theme_action)

        self.dark_theme_action = QAction("Dark (Custom)", self)
        self.dark_theme_action.setCheckable(True)
        self.dark_theme_action.triggered.connect(lambda: self._change_theme(const.THEME_DARK))
        theme_menu.addAction(self.dark_theme_action)
        self.theme_action_group.addAction(self.dark_theme_action)
        view_menu.addSeparator()
        tools_menu = menu_bar.addMenu("&Tools")
        sync_action = QAction("Full Status Sync...", self)
        sync_action.triggered.connect(self._start_total_sync)
        tools_menu.addAction(sync_action)
        tools_menu.addSeparator()
        import_bookmarks_action = QAction("Import from AO3 Bookmarks...", self)
        import_bookmarks_action.triggered.connect(self._start_bookmarks_import)
        tools_menu.addAction(import_bookmarks_action)

        for idx, name in enumerate(self.column_map):
            if name in [const.COLUMN_TITLE, const.COLUMN_STATUS]:
                continue
            action = QAction(name, self)
            action.setCheckable(True)
            action.setChecked(not self.fics_table.isColumnHidden(idx))
            action.triggered.connect(lambda checked, i=idx: self.fics_table.setColumnHidden(i, not checked))
            view_menu.addAction(action)

    def _create_main_layout(self):
        container = QWidget()
        main_layout = QHBoxLayout(container)
        self.setCentralWidget(container)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        top_layout = self._create_top_layout()
        search_layout = self._create_search_layout()
        filter_layout = self._create_filter_layout()
        welcome_layout = QHBoxLayout()
        self.welcome_label = QLabel()
        self.welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.welcome_label.setStyleSheet("font-size: 14px; margin: 5px;")
        welcome_layout.addWidget(self.welcome_label)
        gamification_layout = self._create_gamification_layout()
        left_layout.addLayout(top_layout)
        left_layout.addLayout(search_layout)
        left_layout.addLayout(welcome_layout)
        left_layout.addLayout(filter_layout)
        left_layout.addLayout(gamification_layout)
        left_layout.addWidget(self.fics_table)
        right_widget = self._create_details_panel()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([700, 500])
        main_layout.addWidget(splitter)

    def _create_top_layout(self) -> QHBoxLayout:
        top_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste fic, author, or collection URL here...")
        self.add_button = QPushButton("📥 Import")
        self.stats_button = QPushButton("📊 Stats")
        self.notifications_button = QPushButton("🔔")
        self.refresh_button = QPushButton("🔄 Refresh")

        top_layout.addWidget(QLabel("URL:"))
        top_layout.addWidget(self.url_input, 1)
        top_layout.addWidget(self.add_button)
        top_layout.addWidget(self.stats_button)
        top_layout.addWidget(self.notifications_button)
        top_layout.addWidget(self.refresh_button)

        return top_layout

    def _create_search_layout(self) -> QHBoxLayout:
        search_layout = QHBoxLayout()
        self.search_combo = QComboBox()
        self.search_combo.addItems(
            [
                "Search In: All",
                "Title",
                "Author",
                "Fandom",
                "Rating",
                "Tags",
                "Category",
                "Relationships",
                "Characters",
                "Your Tags",
                "Series",
            ]
        )  # noqa: E501
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search your fics...")
        self.completer_model = QStringListModel(self)
        self.completer = QCompleter(self.completer_model, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.search_input.setCompleter(self.completer)
        search_layout.addWidget(self.search_combo)
        search_layout.addWidget(self.search_input, 1)
        return search_layout

    def _create_filter_layout(self) -> QHBoxLayout:
        filter_layout = QHBoxLayout()
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(
            [
                "Show: All",
                f"Show: {const.STATUS_TO_READ}",
                f"Show: {const.STATUS_READ}",
                f"Show: {const.STATUS_KUDOSED}",
                f"Show: {const.STATUS_COMMENTED}",
                f"Show: {const.STATUS_DROPPED}",
            ]
        )  # noqa: E501
        filter_layout.addStretch()
        filter_layout.addWidget(QLabel("Filter by status:"))
        filter_layout.addWidget(self.status_filter_combo)
        return filter_layout

    def _create_gamification_layout(self) -> QHBoxLayout:
        gamification_layout = QHBoxLayout()
        self.level_label = QLabel("LVL: 1")
        self.xp_bar = QProgressBar()
        self.fic_stats_label = QLabel("Fics Read: 0")
        self.kudos_stats_label = QLabel("Kudos: 0")
        self.comment_stats_label = QLabel("Comments: 0")
        self.achievements_button = QPushButton("🏆 Achievements")
        gamification_layout.addWidget(self.level_label)
        gamification_layout.addWidget(self.xp_bar, 1)
        gamification_layout.addStretch()
        gamification_layout.addWidget(self.fic_stats_label)
        gamification_layout.addWidget(self.kudos_stats_label)
        gamification_layout.addWidget(self.comment_stats_label)
        gamification_layout.addWidget(self.achievements_button)
        return gamification_layout

    def _update_welcome_message(self) -> None:
        """Aggiorna il messaggio di benvenuto in base allo stato del login."""
        username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME, fallback="")
        if username and username != const.CONFIG_DEFAULT_USER:
            self.welcome_label.setText(f"Welcome back, <b>{username}</b>!")
        else:
            self.welcome_label.setText("Welcome, <b>Guest</b>!")

    def _setup_fics_table(self):
        self.fics_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.fics_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.fics_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.fics_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.fics_table.setSortingEnabled(True)
        self.fics_table.horizontalHeader().setSectionsMovable(True)
        self.fics_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        columns_to_hide_by_default = [
            const.COLUMN_SERIES,
            const.COLUMN_HITS,
            const.COLUMN_KUDOS,
            const.COLUMN_CATEGORY,
            const.COLUMN_RELATIONSHIPS,
            const.COLUMN_CHARACTERS,
            const.COLUMN_USER_TAGS,
        ]

        for column_name in columns_to_hide_by_default:
            try:
                column_index = self.column_map.index(column_name)
                self.fics_table.setColumnHidden(column_index, True)
            except ValueError:
                logger.warning(f"Column '{column_name}' not found in COLUMN_MAP. Cannot hide.")

    def _create_details_panel(self) -> QWidget:
        right_widget = QWidget()
        right_widget.setObjectName("right_widget")
        right_layout = QVBoxLayout(right_widget)
        title_layout = QHBoxLayout()
        self.detail_title = QLabel("Select a fic")
        self.detail_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.detail_close_button = QPushButton("X")
        self.detail_close_button.setStyleSheet("font-weight: bold; border-radius: 12px;")
        self.detail_close_button.setFixedSize(24, 24)
        title_layout.addWidget(self.detail_title, 1)
        title_layout.addWidget(self.detail_close_button)
        self.detail_author = QLabel()
        self.detail_author.setStyleSheet("font-style: italic;")
        self.detail_author.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.detail_info = QLabel()
        self.detail_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.detail_category = QLabel()
        self.detail_category.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.detail_relationships = QLabel()
        self.detail_relationships.setWordWrap(True)
        self.detail_relationships.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.detail_characters = QLabel()
        self.detail_characters.setWordWrap(True)
        self.detail_characters.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.detail_tags = QLabel()
        self.detail_tags.setWordWrap(True)
        self.detail_tags.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.detail_user_tags = QTextBrowser()
        self.detail_user_tags.setReadOnly(True)
        self.detail_user_tags.setOpenLinks(False)  # FONDAMENTALE: per gestire i click sui link noi stessi
        self.detail_user_tags.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detail_user_tags.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detail_user_tags.setStyleSheet("QTextBrowser { border: none; background-color: transparent; }")
        self.detail_user_tags.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.detail_summary = QTextEdit()
        self.detail_summary.setReadOnly(True)
        self.detail_notes = NoteWidget()
        self.detail_notes.setPlaceholderText("Your personal notes...")
        status_layout = self._create_details_status_buttons()
        rating_layout = self._create_details_rating_buttons()
        self.delete_button = QPushButton("DELETE FIC")
        self.delete_button.setStyleSheet("background-color: #a13333; color: white;")
        right_layout.addLayout(title_layout)
        right_layout.addWidget(self.detail_author)
        right_layout.addWidget(self.detail_info)
        right_layout.addWidget(self.detail_category)
        right_layout.addWidget(self.detail_relationships)
        right_layout.addWidget(self.detail_characters)
        right_layout.addWidget(QLabel("<b>Tags:</b>"))
        right_layout.addWidget(self.detail_tags)
        right_layout.addWidget(QLabel("<b>Your Tags:</b>"))
        right_layout.addWidget(self.detail_user_tags)
        tag_input_layout = QHBoxLayout()
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Add a tag...")
        self.tag_completer_model = QStringListModel(self)
        self.tag_completer = QCompleter(self.tag_completer_model, self)
        self.tag_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.tag_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.tag_input.setCompleter(self.tag_completer)
        self.add_tag_button = QPushButton("Add Tag")
        tag_input_layout.addWidget(self.tag_input)
        tag_input_layout.addWidget(self.add_tag_button)
        right_layout.addLayout(tag_input_layout)
        right_layout.addWidget(QLabel("<b>Summary:</b>"))
        right_layout.addWidget(self.detail_summary, 1)
        right_layout.addWidget(QLabel("<b>Personal Notes:</b>"))
        right_layout.addWidget(self.detail_notes, 1)
        right_layout.addLayout(status_layout)
        right_layout.addLayout(rating_layout)
        right_layout.addWidget(self.delete_button)
        right_widget.setVisible(False)
        return right_widget

    def _create_details_status_buttons(self) -> QHBoxLayout:
        status_layout = QHBoxLayout()
        self.to_read_button = QPushButton(const.STATUS_TO_READ)
        self.read_button = QPushButton(const.STATUS_READ)
        self.kudosed_button = QPushButton(const.STATUS_KUDOSED)
        self.commented_button = QPushButton(const.STATUS_COMMENTED)
        self.dropped_button = QPushButton(const.STATUS_DROPPED)
        self.sync_status_button = QPushButton("🔄 Sync Status")
        self.open_browser_button = QPushButton("🌐 Open in Browser")
        status_layout.addWidget(self.to_read_button)
        status_layout.addWidget(self.read_button)
        if self.manual_override_enabled:
            status_layout.addWidget(self.kudosed_button)
            status_layout.addWidget(self.commented_button)
        else:
            status_layout.addWidget(self.sync_status_button)
        status_layout.addWidget(self.dropped_button)
        status_layout.addStretch()
        status_layout.addWidget(self.open_browser_button)
        return status_layout

    def _create_details_rating_buttons(self) -> QHBoxLayout:
        rating_layout = QHBoxLayout()
        rating_layout.addWidget(QLabel("<b>Your Rating:</b>"))
        self.rating_buttons = []
        for _ in range(5):
            btn = QPushButton("☆")
            btn.setStyleSheet("font-size: 18px; border: none;")
            rating_layout.addWidget(btn)
            self.rating_buttons.append(btn)
        rating_layout.addStretch()
        return rating_layout

    def _connect_signals(self) -> None:
        self.add_button.clicked.connect(self._on_import_clicked)
        self.stats_button.clicked.connect(self._open_stats_window)
        self.notifications_button.clicked.connect(self._open_notifications_window)
        self.refresh_button.clicked.connect(self.start_update_check)
        self.achievements_button.clicked.connect(self._open_achievements_window)
        self.fics_table.itemSelectionChanged.connect(self._on_fic_selection_changed)
        self.fics_table.customContextMenuRequested.connect(self._open_fics_table_context_menu)
        self.detail_close_button.clicked.connect(self._hide_details_panel)
        self.detail_notes.editingFinished.connect(self._save_notes)
        self.detail_author.linkActivated.connect(self._execute_search_from_link)
        self.detail_info.linkActivated.connect(self._execute_search_from_link)
        self.detail_category.linkActivated.connect(self._execute_search_from_link)
        self.detail_relationships.linkActivated.connect(self._execute_search_from_link)
        self.detail_characters.linkActivated.connect(self._execute_search_from_link)
        self.detail_tags.linkActivated.connect(self._execute_search_from_link)
        self.add_tag_button.clicked.connect(self._add_tag_to_fic)
        self.detail_user_tags.anchorClicked.connect(self._on_user_tag_clicked)  # Da linkActivated a anchorClicked
        self.detail_user_tags.customContextMenuRequested.connect(
            self._open_user_tag_context_menu
        )  # Puntiamo alla nuova funzione
        self.to_read_button.clicked.connect(lambda: self._change_fic_status(const.STATUS_TO_READ))
        self.read_button.clicked.connect(lambda: self._change_fic_status(const.STATUS_READ))
        self.dropped_button.clicked.connect(lambda: self._change_fic_status(const.STATUS_DROPPED))
        self.open_browser_button.clicked.connect(self._open_fic_in_browser)
        if self.manual_override_enabled:
            self.kudosed_button.clicked.connect(lambda: self._change_fic_status(const.STATUS_KUDOSED, 0))
            self.commented_button.clicked.connect(lambda: self._change_fic_status(const.STATUS_COMMENTED, 0))
        else:
            self.sync_status_button.clicked.connect(self.start_status_sync)
        for i, btn in enumerate(self.rating_buttons):
            btn.clicked.connect(lambda checked, num=i + 1: self._save_rating(num))
        self.delete_button.clicked.connect(
            lambda: self._on_delete_fics_clicked([self.selected_url] if self.selected_url else [])
        )  # noqa: E501
        self.search_input.textChanged.connect(self._on_search_triggered)
        self.search_combo.currentIndexChanged.connect(self._on_search_triggered)
        self.status_filter_combo.currentIndexChanged.connect(self._on_quick_filter_triggered)

    def _open_fics_table_context_menu(self, position: QPoint) -> None:
        selected_items = self.fics_table.selectedItems()
        if not selected_items:
            return

        selected_urls_set: set[str] = set()
        for item in selected_items:
            url_item = self.fics_table.item(item.row(), 0)
            if url_item:
                url = url_item.data(Qt.ItemDataRole.UserRole)
                if isinstance(url, str):
                    selected_urls_set.add(url)

        selected_urls = sorted(list(selected_urls_set))
        if not selected_urls:
            return

        menu = QMenu()
        fic_count = len(selected_urls)

        if fic_count == 1:
            single_fic_url = selected_urls[0]
            open_action = menu.addAction("🌐 Open in Browser")
            if open_action:
                open_action.triggered.connect(lambda: webbrowser.open(single_fic_url))
            menu.addSeparator()
        else:
            bulk_edit_action = menu.addAction(f"✍️ Bulk Edit {fic_count} Fics...")
            if bulk_edit_action:
                bulk_edit_action.triggered.connect(self._open_bulk_edit_dialog)
            menu.addSeparator()

        delete_action_text = f"DELETE {fic_count} Fic" + ("s" if fic_count > 1 else "")
        delete_action = menu.addAction(f"🗑️ {delete_action_text}")
        if delete_action:
            delete_action.triggered.connect(lambda: self._on_delete_fics_clicked(selected_urls))

        viewport = self.fics_table.viewport()
        if viewport:
            menu.exec(viewport.mapToGlobal(position))

    def _apply_bulk_changes(self, urls: List[str], changes: Dict[str, List[str] | str | None]) -> None:
        """Applica le modifiche in blocco al database."""
        logger.info(f"Applying bulk changes to {len(urls)} fics: {changes}")

        new_status = changes["status"]
        if new_status and isinstance(new_status, str):  # <-- Controllo del tipo
            bulk_update_status(urls, new_status)

        if changes["add_tags"]:
            tags_to_add = changes["add_tags"]
            if isinstance(tags_to_add, list):
                bulk_add_tags(urls, tags_to_add)

        if changes["remove_tags"]:
            tags_to_remove = changes["remove_tags"]
            if isinstance(tags_to_remove, list):
                bulk_remove_tags(urls, tags_to_remove)

        self._update_tag_completer()

    def _open_bulk_edit_dialog(self) -> None:
        """Apre e gestisce la finestra di dialogo non modale per la modifica in blocco."""
        if self.bulk_edit_dialog and self.bulk_edit_dialog.isVisible():
            self.bulk_edit_dialog.activateWindow()
            return

        selected_urls = self._get_selected_urls_from_table()
        if not selected_urls:
            return

        self.bulk_edit_dialog = BulkEditDialog(len(selected_urls), self)
        self.bulk_edit_dialog.changes_requested.connect(self._on_bulk_changes_requested)

        self.refresh_bulk_edit_dialog_tags()

        self.bulk_edit_dialog.show()

    def _on_bulk_changes_requested(self, changes: dict) -> None:
        """
        Slot che riceve le modifiche dalla BulkEditDialog, le applica,
        e aggiorna la UI in modo mirato senza perdere la selezione.
        """
        urls_to_modify = self._get_selected_urls_from_table()
        if not urls_to_modify:
            return

        original_row_indices = {self._find_row_by_url(url) for url in urls_to_modify}

        self._apply_bulk_changes(urls_to_modify, changes)

        selection_model = self.fics_table.selectionModel()
        if selection_model:  # <-- Controllo di sicurezza
            selection_model.blockSignals(True)

        for url in urls_to_modify:
            fresh_fic_data = get_fic_by_url(url)
            if fresh_fic_data:
                row_index = self._find_row_by_url(url)
                if row_index is not None:
                    self.fics_in_memory[url] = fresh_fic_data
                    self._populate_table_row(row_index, fresh_fic_data)

        selection = QItemSelection()

        model = self.fics_table.model()
        header = self.fics_table.horizontalHeader()

        if model and header:
            for row_idx in original_row_indices:
                if row_idx is not None:
                    top_left = model.index(row_idx, 0)
                    bottom_right = model.index(row_idx, header.count() - 1)
                    selection.select(top_left, bottom_right)

        selection_model = self.fics_table.selectionModel()
        if selection_model:
            selection_model.select(
                selection, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
            )

            selection_model.blockSignals(False)

        if self.bulk_edit_dialog and self.bulk_edit_dialog.isVisible():
            self.refresh_bulk_edit_dialog_tags()

    def refresh_bulk_edit_dialog_tags(self) -> None:
        """Ricalcola e aggiorna la lista dei tag comuni nella BulkEditDialog."""
        if not self.bulk_edit_dialog:
            return

        urls = self._get_selected_urls_from_table()
        if not urls:
            self.bulk_edit_dialog.populate_remove_tags_list([])
            return

        all_tags_sets = [{tag_name for _, tag_name in get_tags_for_fic(url)} for url in urls]
        common_tags = list(set.intersection(*all_tags_sets)) if all_tags_sets else []
        self.bulk_edit_dialog.populate_remove_tags_list(common_tags)

    def _get_selected_urls_from_table(self) -> List[str]:
        """Funzione helper per ottenere gli URL correntemente selezionati."""
        selected_urls_set: set[str] = set()

        for item in self.fics_table.selectedItems():
            url_item = self.fics_table.item(item.row(), 0)

            if url_item:
                url = url_item.data(Qt.ItemDataRole.UserRole)
                if isinstance(url, str):
                    selected_urls_set.add(url)

        return sorted(list(selected_urls_set))

    def _find_row_by_url(self, url: str) -> Optional[int]:
        for row in range(self.fics_table.rowCount()):
            item = self.fics_table.item(row, 0)
            if item is not None:
                assert item is not None
                if item.data(Qt.ItemDataRole.UserRole) == url:
                    return row
        return None

    def _populate_table_row(self, row_num: int, fic: sqlite3.Row):
        rating = fic["user_rating"] or 0
        wc = fic["word_count"] or 0
        complete_icon = "✅" if fic["is_complete"] else "📖"
        verified_icon = "🔹" if fic["status_verified"] else "🔸"
        hits = fic["hits"] or 0
        kudos = fic["kudos"] or 0
        series_text = f"{fic['series_name']} (Part {fic['series_part']})" if fic["series_name"] else ""
        items: Dict[str, QTableWidgetItem] = {
            const.COLUMN_TITLE: QTableWidgetItem(f"{complete_icon} {fic['title']}"),
            const.COLUMN_AUTHOR: QTableWidgetItem(fic["author"]),
            const.COLUMN_FANDOM: QTableWidgetItem(fic["fandoms"]),
            const.COLUMN_CHAPTERS: QTableWidgetItem(fic["chapters"]),
            const.COLUMN_DATE_UPDATED: QTableWidgetItem(fic["date_updated"]),
            const.COLUMN_SERIES: QTableWidgetItem(series_text),
            const.COLUMN_RATING: QTableWidgetItem(fic["rating"]),
            const.COLUMN_STATUS: QTableWidgetItem(f"{verified_icon} {fic['status']}"),
            const.COLUMN_CATEGORY: QTableWidgetItem(fic["category"]),
            const.COLUMN_RELATIONSHIPS: QTableWidgetItem(fic["relationships"]),
            const.COLUMN_CHARACTERS: QTableWidgetItem(fic["characters"]),
            const.COLUMN_USER_TAGS: QTableWidgetItem(fic["user_tags"] or ""),
        }
        items[const.COLUMN_WORDS] = NumericTableWidgetItem(f"{wc:,}")
        items[const.COLUMN_WORDS].setData(Qt.ItemDataRole.UserRole, wc)

        items[const.COLUMN_HITS] = NumericTableWidgetItem(f"{hits:,}")
        items[const.COLUMN_HITS].setData(Qt.ItemDataRole.UserRole, hits)
        items[const.COLUMN_KUDOS] = NumericTableWidgetItem(f"{kudos:,}")
        items[const.COLUMN_KUDOS].setData(Qt.ItemDataRole.UserRole, kudos)

        items[const.COLUMN_USER_RATING] = NumericTableWidgetItem("★" * rating + "☆" * (5 - rating))
        items[const.COLUMN_USER_RATING].setData(Qt.ItemDataRole.UserRole, rating)
        text_color = self.status_text_colors.get(fic["status"], QColor("black"))
        items[const.COLUMN_TITLE].setData(Qt.ItemDataRole.UserRole, fic["url"])
        self.fics_table.setSortingEnabled(False)
        for col_idx, key in enumerate(self.column_map):
            if key in items:
                item = items[key]
                item.setForeground(text_color)
                self.fics_table.setItem(row_num, col_idx, item)
        self.fics_table.setSortingEnabled(True)

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        logger.info("Close event triggered. Shutting down active threads.")
        active_threads = [t for t in [self.update_thread, self.import_thread, self.sync_thread] if t and t.isRunning()]
        if active_threads:
            for thread in active_threads:
                thread.quit()
                thread.wait()
        self._save_settings()
        logger.info("Application closing.")
        super().closeEvent(event)

    def _save_settings(self) -> None:
        config_manager.set(
            const.CONFIG_SECTION_UI, const.CONFIG_KEY_GEOMETRY, self.saveGeometry().toBase64().data().decode("utf-8")
        )
        header = self.fics_table.horizontalHeader()
        if header:
            hidden_cols = [str(i) for i in range(header.count()) if self.fics_table.isColumnHidden(i)]
        config_manager.set(const.CONFIG_SECTION_UI, "hidden_columns", ",".join(hidden_cols))

    config_manager.save_config()

    def _load_settings(self) -> None:
        if geom := config_manager.get(const.CONFIG_SECTION_UI, const.CONFIG_KEY_GEOMETRY, fallback=None):
            self.restoreGeometry(QByteArray.fromBase64(geom.encode("utf-8")))
        if order_str := config_manager.get(const.CONFIG_SECTION_UI, const.CONFIG_KEY_COL_ORDER, fallback=None):
            order = [int(i) for i in order_str.split(",")]
            header = self.fics_table.horizontalHeader()
            if header and len(order) == header.count():
                for v_idx, l_idx in enumerate(order):
                    header.moveSection(header.visualIndex(l_idx), v_idx)
            if hidden_str := config_manager.get(const.CONFIG_SECTION_UI, "hidden_columns", fallback=None):
                hidden_cols_indices = [int(i) for i in hidden_str.split(",") if i]
                for i in range(self.fics_table.columnCount()):
                    self.fics_table.setColumnHidden(i, i in hidden_cols_indices)

    def _backup_database(self) -> None:
        backup_filename = f"ao3_helper_backup_{datetime.now().strftime('%Y-%m-%d')}.db"
        file_path, _ = QFileDialog.getSaveFileName(self, "Backup Database", backup_filename, "Database Files (*.db)")
        if file_path:
            try:
                shutil.copyfile("ao3_helper.db", file_path)
                logger.info(f"Database successfully backed up to {file_path}")
                QMessageBox.information(self, "Backup Successful", f"Database backed up to:\n{file_path}")
            except Exception as e:
                logger.exception("Database backup failed.")
                QMessageBox.critical(self, "Backup Failed", f"Error: {e}")

    def _restore_database(self) -> None:
        response = QMessageBox.warning(
            self,
            "Confirm Restore",
            "This will OVERWRITE your current data.\nThis action cannot be undone. Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response == QMessageBox.StandardButton.No:
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "Restore Database", "", "Database Files (*.db)")
        if file_path:
            try:
                shutil.copyfile(file_path, "ao3_helper.db")
                logger.warning(f"Database successfully restored from {file_path}. Application will restart.")
                QMessageBox.information(
                    self, "Restore Successful", "Database restored. The application will now restart."
                )
                QApplication.quit()
                QProcess.startDetached(sys.executable, sys.argv or [])
            except Exception as e:
                logger.exception("Database restore failed.")
                QMessageBox.critical(self, "Restore Failed", f"Error: {e}")

    def update_notification_indicator(self) -> None:
        count = len(get_unread_notifications())
        self.notifications_button.setText(f"🔔 ({count})" if count > 0 else "🔔")
        self.notifications_button.setStyleSheet("background-color: #48cae4; color: white;" if count > 0 else "")

    def _generate_startup_notification(self) -> None:
        if count := count_read_uncommented_fics():
            add_notification(f"You have {count} read fics that you haven't commented on yet.")
            self.update_notification_indicator()

    def start_update_check(self) -> None:
        if self.update_thread and self.update_thread.isRunning():
            logger.warning("Update check requested, but one is already running.")
            return
        self.refresh_button.setEnabled(False)
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("Checking for updates...")
        self.update_thread = QThread()
        self.update_worker = UpdateCheckWorker()
        self.update_worker.moveToThread(self.update_thread)
        self.update_thread.started.connect(self.update_worker.run)
        self.update_worker.progress.connect(self._update_progress_bar)
        self.update_worker.new_notification.connect(self._new_notification_from_worker)
        self.update_worker.finished.connect(self._on_update_check_finished)
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_worker.finished.connect(self.update_worker.deleteLater)
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_thread.finished.connect(lambda: setattr(self, "update_thread", None))
        self.update_thread.start()

    def _on_update_check_finished(self) -> None:
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("Update check finished.", 3000)
        self.refresh_button.setEnabled(True)
        self._update_fics_table()

    def start_mass_import(self, url_or_name: str) -> None:
        status_bar = self.statusBar()

        if (self.import_thread and self.import_thread.isRunning()) or (
            self.bookmarks_import_thread and self.bookmarks_import_thread.isRunning()
        ):
            logger.warning("Mass import requested, but another import is already running.")
            if status_bar:
                status_bar.showMessage("An import process is already running.", 3000)
            return

        logger.info(f"Starting mass import for author: {url_or_name}")
        self.add_button.setEnabled(False)  # Assumendo tu abbia questo pulsante
        if status_bar:
            status_bar.showMessage("Starting import...")

        self.import_thread = QThread()
        self.import_worker = MassImportWorker(url_or_name)
        self.import_worker.moveToThread(self.import_thread)
        self.import_thread.started.connect(self.import_worker.run)
        self.import_worker.progress.connect(self._update_progress_bar)
        self.import_worker.new_fic_added.connect(self._update_fics_table)

        self.import_worker.error.connect(self._on_import_error)  # <-- MODIFICATO: da .new_notification a .error

        self.import_worker.finished.connect(self._on_mass_import_finished)
        self.import_worker.finished.connect(self.import_thread.quit)
        self.import_worker.finished.connect(self.import_worker.deleteLater)
        self.import_thread.finished.connect(self.import_thread.deleteLater)
        self.import_thread.finished.connect(lambda: setattr(self, "import_thread", None))
        self.import_thread.start()

    def _on_mass_import_finished(self) -> None:
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("Mass import finished.", 3000)
        self.add_button.setEnabled(True)
        self._update_search_completer()

    def _start_bookmarks_import(self) -> None:
        """
        Avvia il processo di importazione dei bookmark in un thread separato.
        """
        status_bar = self.statusBar()

        if (self.import_thread and self.import_thread.isRunning()) or (
            self.bookmarks_import_thread and self.bookmarks_import_thread.isRunning()
        ):
            logger.warning("Bookmark import requested, but another import is already running.")
            if status_bar:
                status_bar.showMessage("An import process is already running.", 3000)
            return

        if not ao3_client.session:
            QMessageBox.critical(
                self,
                "Login Required",
                "You must be logged in to import bookmarks.\nPlease configure your credentials in File > Settings / Login and restart the application.",  # noqa: E501
            )
            return

        logger.info("Starting bookmarks import process.")
        if status_bar:
            status_bar.showMessage("Starting bookmarks import...")

        self.add_button.setEnabled(False)  # Assumendo tu abbia un pulsante per questo

        self.bookmarks_import_thread = QThread()
        self.bookmarks_import_worker = ImportBookmarksWorker()
        self.bookmarks_import_worker.moveToThread(self.bookmarks_import_thread)

        self.bookmarks_import_thread.started.connect(self.bookmarks_import_worker.run)
        self.bookmarks_import_worker.progress.connect(self._update_progress_bar)
        self.bookmarks_import_worker.new_fic_added.connect(self._update_fics_table)
        self.bookmarks_import_worker.error.connect(self._on_import_error)  # Nuovo slot per errori
        self.bookmarks_import_worker.finished.connect(self._on_bookmarks_import_finished)

        self.bookmarks_import_worker.finished.connect(self.bookmarks_import_thread.quit)
        self.bookmarks_import_worker.finished.connect(self.bookmarks_import_worker.deleteLater)
        self.bookmarks_import_thread.finished.connect(self.bookmarks_import_thread.deleteLater)
        self.bookmarks_import_thread.finished.connect(lambda: setattr(self, "bookmarks_import_thread", None))

        self.bookmarks_import_thread.start()

    def start_status_sync(self) -> None:
        status_bar = self.statusBar()
        if self.sync_thread and self.sync_thread.isRunning():
            logger.warning("Status sync requested, but one is already running.")
            if status_bar:
                status_bar.showMessage("Sync already in progress...", 2000)
            return
        if not self.selected_url:
            QMessageBox.warning(self, "No Fic Selected", "Please select a fic to sync.")
            return
        username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME, fallback=None)
        if not username or not username.strip() or username == const.CONFIG_DEFAULT_USER:
            QMessageBox.critical(self, "Username Not Set", "Please set your AO3 username in File > Settings / Login.")
            return
        logger.info(f"Starting status sync for user '{username}' on fic {self.selected_url}")
        if status_bar:
            status_bar.showMessage("Syncing status with AO3...")
        self.sync_status_button.setEnabled(False)
        self.sync_status_button.setText("Syncing...")
        work_id = int(self.selected_url.split("/")[-1])
        self.sync_thread = QThread()
        self.sync_worker = SyncStatusWorker(work_id, self.selected_url, username)
        self.sync_worker.moveToThread(self.sync_thread)
        self.sync_thread.started.connect(self.sync_worker.run)
        self.sync_worker.finished.connect(self._on_status_sync_finished)
        self.sync_worker.error.connect(self._on_status_sync_error)
        self.sync_worker.finished.connect(self.sync_thread.quit)
        self.sync_worker.finished.connect(self.sync_worker.deleteLater)
        self.sync_thread.finished.connect(self.sync_thread.deleteLater)
        self.sync_thread.finished.connect(lambda: setattr(self, "sync_thread", None))
        self.sync_thread.start()

    def _on_status_sync_finished(self, new_status: str, url: str) -> None:
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage(f"Sync complete. New status: {new_status}", 3000)
        if not self.manual_override_enabled:
            self.sync_status_button.setEnabled(True)
            self.sync_status_button.setText("🔄 Sync Status")
        fresh_fic_data = get_fic_by_url(url)
        if fresh_fic_data:
            update_fic_status(url, new_status, 1)
            self.fics_in_memory[url] = fresh_fic_data
            row_to_update = self._find_row_by_url(url)
            if row_to_update is not None:
                self._populate_table_row(row_to_update, fresh_fic_data)
            stats, chart_data = calculate_base_stats(), get_data_for_charts("lette")
            if check_for_achievements(stats, chart_data, newly_modified_fic=dict(fresh_fic_data)):
                self.update_notification_indicator()

    def _on_status_sync_error(self, error_message: str) -> None:
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage(f"Sync failed: {error_message}", 5000)
        if not self.manual_override_enabled:
            self.sync_status_button.setEnabled(True)
            self.sync_status_button.setText("🔄 Sync Status")

    def _update_progress_bar(self, current: int, total: int) -> None:
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage(f"Processing... ({current}/{total})")

    def _new_notification_from_worker(self, msg: str, url: Any) -> None:
        add_notification(msg, url)
        self.update_notification_indicator()

    def _open_login_dialog(self) -> None:
        dialog = LoginDialog(self)
        dialog.exec()
        self._update_welcome_message()

    def _open_stats_window(self) -> None:
        dialog = StatsWindow(self)
        dialog.exec()

    def _open_notifications_window(self) -> None:
        dialog = NotificationsWindow(self)
        dialog.exec()

    def _open_achievements_window(self) -> None:
        dialog = AchievementsWindow(self)
        dialog.exec()

    def _open_import_author_dialog(self) -> None:
        text, ok = QInputDialog.getText(self, "Import by Author", "Enter the author's profile URL or username:")
        if ok and text.strip():
            self.start_mass_import(text.strip())

    def _update_search_completer(self) -> None:
        suggestions: set[str] = {fic["title"] for fic in self.fics_in_memory.values()}
        for fic in self.fics_in_memory.values():
            if fic["author"]:
                suggestions.add(fic["author"])
            for field in ["fandoms", "tags", "category", "relationships", "characters"]:
                if fic[field]:
                    for item in fic[field].split(","):
                        if item.strip():
                            suggestions.add(item.strip())
        self.completer_model.setStringList(sorted(list(suggestions)))

    def _update_fics_table(self, fics_to_display: Optional[List[sqlite3.Row]] = None) -> None:
        self._ignore_selection_change = True
        previously_selected_url = self.selected_url
        self.fics_table.setSortingEnabled(False)
        self.fics_table.clearContents()
        all_fics = get_filtered_fics()
        self.fics_in_memory = {fic["url"]: fic for fic in all_fics}
        fics_to_render = fics_to_display if fics_to_display is not None else all_fics
        self.fics_table.setRowCount(len(fics_to_render))
        selected_row = -1
        for row_num, fic in enumerate(fics_to_render):
            self._populate_table_row(row_num, fic)
            if previously_selected_url == fic["url"]:
                selected_row = row_num
        self.fics_table.setSortingEnabled(True)
        if selected_row != -1:
            self.fics_table.selectRow(selected_row)
        self._ignore_selection_change = False
        self._update_status_bar()
        self._update_gamification_panel()

    def _update_gamification_panel(self) -> None:
        stats, verified_stats = calculate_base_stats(), count_verified_statuses()
        words_read = stats.get("total_words_read", 0)
        level_info = calculate_xp_level(words_read)
        self.level_label.setText(f"<b>LVL: {level_info['level']}</b>")
        self.xp_bar.setValue(level_info["xp_current"])
        self.xp_bar.setMaximum(level_info["xp_needed"])
        self.xp_bar.setFormat(f"{level_info['xp_current']:,} / {level_info['xp_needed']:,} XP")
        fics_read_count = stats.get("fics_read", 0) + stats.get("fics_commented", 0)
        self.fic_stats_label.setText(f"Fics Read: {fics_read_count}")
        self.kudos_stats_label.setText(f"Kudos Given: {verified_stats.get('kudos', 0)}")
        self.comment_stats_label.setText(f"Comments Left: {verified_stats.get('comments', 0)}")

    def _update_status_bar(self) -> None:
        stats = calculate_base_stats()
        self.fic_count_label.setText(f"Total Fics: {stats.get('total_fics', 0)}")
        self.word_count_label.setText(f"Words Read: {stats.get('total_words_read', 0):,}")

    def _on_search_triggered(self) -> None:
        self.status_filter_combo.setCurrentIndex(0)
        text, idx = self.search_input.text(), self.search_combo.currentIndex()
        field_map = {
            0: const.SEARCH_ALL,
            1: const.SEARCH_TITLE,
            2: const.SEARCH_AUTHOR,
            3: const.SEARCH_FANDOMS,
            4: const.SEARCH_RATING,
            5: const.SEARCH_TAGS,
            6: const.SEARCH_CATEGORY,
            7: const.SEARCH_RELATIONSHIPS,
            8: const.SEARCH_CHARACTERS,
            9: const.SEARCH_USER_TAGS,
            10: const.SEARCH_SERIES,
        }
        self._update_fics_table(get_filtered_fics(text, field_map.get(idx, const.SEARCH_ALL)))

    def _on_quick_filter_triggered(self) -> None:
        self.search_input.clear()
        idx = self.status_filter_combo.currentIndex()
        if idx == 0:
            self._update_fics_table()
            return
        status_map = {
            1: const.STATUS_TO_READ,
            2: const.STATUS_READ,
            3: const.STATUS_KUDOSED,
            4: const.STATUS_COMMENTED,
            5: const.STATUS_DROPPED,
        }
        self._update_fics_table([fic for fic in get_filtered_fics() if fic["status"] == status_map.get(idx)])

    def _execute_search_from_link(self, link: str) -> None:
        try:
            field, value = link.split(":", 1)
        except ValueError:
            return
        combo_map = {
            "author": 2,
            "fandoms": 3,
            "rating": 4,
            "tags": 5,
            "category": 6,
            "relationships": 7,
            "characters": 8,
            const.SEARCH_USER_TAGS: 9,
            const.SEARCH_SERIES: 10,  # <-- AGGIUNTA
        }
        if idx := combo_map.get(field):
            self.search_combo.setCurrentIndex(idx)
            self.search_input.setText(value)

    def _on_fic_selection_changed(self) -> None:
        if self._ignore_selection_change:
            return
        selected_items = self.fics_table.selectedItems()
        if not selected_items:
            self._hide_details_panel()
            return
        central_widget = self.centralWidget()
        if not central_widget:
            return
        right_widget = central_widget.findChild(QWidget, "right_widget")
        if right_widget:
            right_widget.setVisible(True)
        url_item = self.fics_table.item(selected_items[0].row(), 0)
        if not url_item:
            return
        self.selected_url = url_item.data(Qt.ItemDataRole.UserRole)
        if data := self.fics_in_memory.get(self.selected_url or ""):
            kudos = data["kudos"] or 0
            bookmarks = data["bookmarks"] or 0
            comments = data["comments"] or 0
            hits = data["hits"] or 0
            word_count = data["word_count"] or 0
            self.detail_title.setText(data["title"])

            def format_link(text: Optional[str], link_type: str) -> str:
                return (
                    ", ".join(
                        [f'<a href="{link_type}:{i.strip()}">{i.strip()}</a>' for i in text.split(",") if i.strip()]
                    )
                    if text
                    else ""
                )

            self.detail_author.setText(f"by {format_link(data['author'], 'author')}")
            series_html = ""
            if data["series_name"]:
                series_link = f'<a href="series_name:{data["series_name"]}">{data["series_name"]}</a>'
                series_html = f"Part {data['series_part']} of the series {series_link}<br>"
            self.detail_info.setText(
                f"{series_html}"
                f"<b>Fandom:</b> {format_link(data['fandoms'], 'fandoms')}<br>"
                f"<b>Published:</b> {data['date_published']} | <b>Updated:</b> {data['date_updated']}<br>"
                f"<b>Rating:</b> {data['rating']} | <b>Language:</b> {data['language']}<br>"
                f"<b>Words:</b> {word_count:,} | <b>Chapters:</b> {data['chapters']}<br>"
                f"<b>Stats:</b> Kudos: {kudos:,} | Bookmarks: {bookmarks:,} | Comments: {comments:,} | Hits: {hits:,}"
            )
            self.detail_category.setText(f"<b>Category:</b> {format_link(data['category'], 'category')}")
            self.detail_relationships.setText(
                f"<b>Relationships:</b> {format_link(data['relationships'], 'relationships')}"
            )
            self.detail_characters.setText(f"<b>Characters:</b> {format_link(data['characters'], 'characters')}")
            self.detail_tags.setText(f"<b>Tags:</b> {format_link(data['tags'], 'tags')}")
            self.detail_summary.setText(data["summary"])
            self.detail_notes.setText(data["user_notes"])
            self._refresh_tags_display_and_table()
            rating = data["user_rating"] or 0
            for i, btn in enumerate(self.rating_buttons):
                btn.setText("★" if i < rating else "☆")

    def _add_tag_to_fic(self) -> None:
        if not self.selected_url:
            return
        tag_name = self.tag_input.text().strip()
        if not tag_name:
            return
        tag_id = get_or_create_tag(tag_name)
        if tag_id:
            assign_tag_to_fic(self.selected_url, tag_id)
            self.tag_input.clear()
            self._refresh_tags_display_and_table()
            self._update_tag_completer()

    def _on_user_tag_clicked(self, link: str) -> None:
        self._execute_search_from_link(link)

    def _refresh_tags_display_and_table(self) -> None:
        if not self.selected_url:
            return

        user_tags_data = get_tags_for_fic(self.selected_url)

        if user_tags_data:
            tags_html_parts = []
            for _, tag_name in user_tags_data:
                search_link = f'<a href="{const.SEARCH_USER_TAGS}:{tag_name}">{tag_name}</a>'
                tags_html_parts.append(search_link)
            self.detail_user_tags.setHtml(", ".join(tags_html_parts))
        else:
            self.detail_user_tags.setHtml("<i>No tags assigned.</i>")

        doc = self.detail_user_tags.document()
        if doc:
            doc_height = doc.size().toSize().height()
            self.detail_user_tags.setFixedHeight(doc_height)

        fresh_fic_data = get_fic_by_url(self.selected_url)
        if fresh_fic_data:
            self.fics_in_memory[self.selected_url] = fresh_fic_data
            row_to_update = self._find_row_by_url(self.selected_url)
            if row_to_update is not None:
                self._populate_table_row(row_to_update, fresh_fic_data)

    def _save_notes(self) -> None:
        if not self.selected_url:
            return
        current_notes_in_memory = self.fics_in_memory[self.selected_url]["user_notes"]
        new_notes = self.detail_notes.toPlainText()
        if new_notes != current_notes_in_memory:
            update_fic_notes(self.selected_url, new_notes)
            fresh_fic_data = get_fic_by_url(self.selected_url)
            if fresh_fic_data:
                self.fics_in_memory[self.selected_url] = fresh_fic_data
            status_bar = self.statusBar()
            if status_bar:
                status_bar.showMessage("Notes saved.", 2000)

    def _save_rating(self, rating: int) -> None:
        if not self.selected_url:
            return
        current_rating = self.fics_in_memory[self.selected_url]["user_rating"] or 0
        new_rating = rating if rating != current_rating else 0
        update_fic_rating(self.selected_url, new_rating)
        fresh_fic_data = get_fic_by_url(self.selected_url)
        if fresh_fic_data:
            self.fics_in_memory[self.selected_url] = fresh_fic_data
            row_to_update = self._find_row_by_url(self.selected_url)
            if row_to_update is not None:
                self._populate_table_row(row_to_update, fresh_fic_data)
            for i, btn in enumerate(self.rating_buttons):
                btn.setText("★" if i < new_rating else "☆")
            if check_for_achievements(
                calculate_base_stats(), get_data_for_charts("lette"), newly_modified_fic=dict(fresh_fic_data)
            ):
                self.update_notification_indicator()

    def _hide_details_panel(self) -> None:
        central_widget = self.centralWidget()
        if not central_widget:
            return
        right_widget = central_widget.findChild(QWidget, "right_widget")
        if right_widget:
            right_widget.setVisible(False)
        self.selected_url = None
        self.fics_table.clearSelection()

    def _change_fic_status(self, new_status: str, verified: int = 0) -> None:
        if not self.selected_url:
            return
        current_fic_dict = dict(self.fics_in_memory[self.selected_url])
        update_fic_status(self.selected_url, new_status, verified)
        fresh_fic_data = get_fic_by_url(self.selected_url)
        if fresh_fic_data:
            self.fics_in_memory[self.selected_url] = fresh_fic_data
            row_to_update = self._find_row_by_url(self.selected_url)
            if row_to_update is not None:
                self._populate_table_row(row_to_update, fresh_fic_data)
            if check_for_achievements(
                calculate_base_stats(), get_data_for_charts("lette"), newly_modified_fic=current_fic_dict
            ):
                self.update_notification_indicator()
            if new_status == const.STATUS_READ:
                QMessageBox.information(
                    self, "Well Done!", "Now that you've read it, consider leaving a comment for the author!"
                )

    def _open_fic_in_browser(self) -> None:
        if self.selected_url:
            webbrowser.open(self.selected_url)
        else:
            QMessageBox.warning(self, "No Fic Selected", "Please select a fic first.")

    def _on_import_clicked(self) -> None:
        """
        Gestore unificato per il pulsante 'Import'. Analizza l'URL
        e avvia l'azione appropriata.
        """
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.critical(self, "Error", "Please enter a URL.")
            return

        url_type, identifier = self._parse_ao3_url(url)

        match url_type:
            case "work":
                self._start_single_fic_add(url)

            case "author":
                assert identifier is not None
                reply = QMessageBox.question(
                    self,
                    "Confirm Author Import",
                    f"This appears to be an author's page for '<b>{identifier}</b>'.<br><br>"
                    f"Do you want to import all works by this author?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.start_mass_import(identifier)

            case "collection":
                assert identifier is not None
                reply = QMessageBox.question(
                    self,
                    "Confirm Collection Import",
                    f"This appears to be a collection named '<b>{identifier}</b>'.<br><br>"
                    f"Do you want to import all public works from this collection?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.start_collection_import(identifier)

            case "series":
                assert identifier is not None
                reply = QMessageBox.question(
                    self,
                    "Confirm Series Import",
                    "This appears to be a series. Do you want to import all public works from this series?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.start_series_import(identifier)
            case "unknown":
                QMessageBox.critical(
                    self, "Invalid URL", "The provided URL is not a recognized AO3 work, author, or collection page."
                )

    def _on_add_fic_finished(self, data: Optional[Dict[str, Any]]):
        status_bar = self.statusBar()
        if data:
            if add_fic(data):
                logger.info(f"Successfully added '{data['title']}' to the database via worker.")
                QMessageBox.information(self, "Success", f"'{data['title']}' has been added!")
                self.url_input.clear()
                self.search_input.clear()
                self.status_filter_combo.setCurrentIndex(0)
                self._update_fics_table()
                self._update_search_completer()
            else:
                logger.warning(f"Worker tried to add a fic that is already in the database: {data['url']}")
                QMessageBox.warning(self, "Attention", "This fic is already in your archive.")
        else:
            logger.error("Worker failed to retrieve data from URL.")
            QMessageBox.critical(self, "Error", "Could not retrieve data from the URL.")
        if status_bar:
            status_bar.clearMessage()
        self.add_button.setEnabled(True)

    def _on_add_fic_error(self, error_message: str):
        logger.error(f"An error occurred in the AddFicWorker: {error_message}")
        QMessageBox.critical(self, "Error", f"An unexpected error occurred: {error_message}")
        status_bar = self.statusBar()
        if status_bar:
            status_bar.clearMessage()
        self.add_button.setEnabled(True)

    def _on_delete_fics_clicked(self, urls_to_delete: List[str]) -> None:
        if not urls_to_delete:
            return

        fic_count = len(urls_to_delete)

        if fic_count == 1:
            fic_title = "this fic"  # Un default sicuro
            fic_data = self.fics_in_memory.get(urls_to_delete[0])
            if fic_data:
                fic_title = fic_data["title"]
            question = f"Permanently delete '{fic_title}'?"
        else:
            question = f"Permanently delete {fic_count} selected fics?"

        response = QMessageBox.question(
            self,
            "Confirm Deletion",
            question,  # 'question' ora ha sempre un valore valido
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response == QMessageBox.StandardButton.Yes:
            logger.info(f"User confirmed deletion of {fic_count} fic(s).")
            for url in urls_to_delete:
                delete_fic(url)
            self.search_input.clear()
            self.status_filter_combo.setCurrentIndex(0)
            self._hide_details_panel()
            self._update_fics_table()
            self._update_search_completer()

    def start_series_import(self, series_id: str) -> None:
        status_bar = self.statusBar()
        if self.series_import_thread and self.series_import_thread.isRunning():
            logger.warning("Series import requested, but one is already running.")
            return

        logger.info(f"Starting series import for ID: {series_id}")
        self.add_button.setEnabled(False)
        if status_bar:
            status_bar.showMessage(f"Starting import from series '{series_id}'...")

        self.series_import_thread = QThread()
        self.series_import_worker = ImportSeriesWorker(series_id)
        self.series_import_worker.moveToThread(self.series_import_thread)
        self.series_import_thread.started.connect(self.series_import_worker.run)
        self.series_import_worker.progress.connect(self._update_progress_bar)
        self.series_import_worker.new_fic_added.connect(self._update_fics_table)
        self.series_import_worker.error.connect(self._on_import_error)
        self.series_import_worker.finished.connect(self._on_mass_import_finished)
        self.series_import_worker.finished.connect(self.series_import_thread.quit)
        self.series_import_worker.finished.connect(self.series_import_worker.deleteLater)
        self.series_import_thread.finished.connect(self.series_import_thread.deleteLater)
        self.series_import_thread.finished.connect(lambda: setattr(self, "series_import_thread", None))
        self.series_import_thread.start()

    def _apply_theme(self, palette: Optional[Dict[str, str]]) -> None:
        if palette is None:
            self.setStyleSheet("")
            self.status_text_colors.update(
                {
                    const.STATUS_TO_READ: QColor("#AAAAAA"),
                    const.STATUS_DROPPED: QColor("#606060"),
                    const.STATUS_READ: QColor("#E53935"),
                    const.STATUS_KUDOSED: QColor("#FB8C00"),
                    const.STATUS_COMMENTED: QColor("#43A047"),
                }
            )
        else:
            ss = f"""
                QMainWindow, QDialog {{ background-color: {palette["window_bg"]}; }}
                QLabel, QCheckBox {{ color: {palette["text"]}; }}
                QLineEdit, QTextEdit, QSpinBox, QComboBox {{ background-color: {palette["widget_bg"]}; color: {palette["text"]}; border: 1px solid {palette["border"]}; border-radius: 4px; padding: 4px;}}
                QHeaderView::section {{ background-color: {palette["widget_bg"]}; color: {palette["text"]}; border: 1px solid {palette["border"]}; padding: 4px; }}
                QTableWidget {{ background-color: {palette["widget_bg"]}; gridline-color: {palette["border"]}; }}
                QTableWidget::item:selected {{ background-color: {palette["highlight"]}; color: {palette["highlight_text"]}; }}
                QPushButton {{ background-color: {palette["widget_bg"]}; color: {palette["text"]}; border: 1px solid {palette["border"]}; border-radius: 4px; padding: 5px;}}
                QPushButton:hover {{ border: 1px solid {palette["highlight"]}; }}
                QPushButton:pressed {{ background-color: {palette["highlight"]}; color: {palette["highlight_text"]}; }}
                QMenuBar, QMenu {{ background-color: {palette["widget_bg"]}; color: {palette["text"]}; }}
                QMenu::item:selected {{ background-color: {palette["highlight"]}; }}
            """  # noqa: E501
            self.setStyleSheet(ss)
            self.status_text_colors.update(
                {
                    const.STATUS_TO_READ: QColor(palette["text_accent"]),
                    const.STATUS_DROPPED: QColor(palette["text_accent"]),
                    const.STATUS_READ: QColor("#e63946"),
                    const.STATUS_KUDOSED: QColor("#fca311"),
                    const.STATUS_COMMENTED: QColor("#2a9d8f"),
                }
            )
        if hasattr(self, "fics_table"):
            self._update_fics_table()

    def _change_theme(self, theme_name: str) -> None:
        self.current_theme = theme_name
        if theme_name == const.THEME_DARK:
            self._apply_theme(PALETTE_DARK)
        elif theme_name == const.THEME_LIGHT:
            self._apply_theme(PALETTE_LIGHT)
        else:
            self._apply_theme(None)
        config_manager.set(const.CONFIG_SECTION_SETTINGS, const.CONFIG_KEY_THEME, self.current_theme)
        config_manager.save_config()

    def _open_user_tag_context_menu(self, position: QPoint) -> None:
        """
        Apre un menu contestuale intelligente che agisce specificamente sul tag
        sotto il cursore del mouse.
        """
        if not self.selected_url:
            return

        cursor = self.detail_user_tags.cursorForPosition(position)
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        clicked_tag_name = cursor.selectedText().strip(" ,.")  # Pulisce da spazi o punteggiatura

        if not clicked_tag_name:
            return  # L'utente ha cliccato su uno spazio vuoto

        all_fic_tags = get_tags_for_fic(self.selected_url)
        target_tag = None
        for tag_id, tag_name in all_fic_tags:
            if tag_name == clicked_tag_name:
                target_tag = (tag_id, tag_name)
                break

        if target_tag is None:
            return  # La parola cliccata non corrisponde a un tag valido

        menu = QMenu()
        tag_id_to_remove, tag_name_to_remove = target_tag

        remove_action = menu.addAction(f"Remove Tag '{tag_name_to_remove}'")
        if remove_action:
            remove_action.triggered.connect(lambda: self._remove_tag_by_id(tag_id_to_remove))

        menu.exec(self.detail_user_tags.mapToGlobal(position))

    def _remove_tag_by_id(self, tag_id: int) -> None:
        if self.selected_url:
            remove_tag_from_fic(self.selected_url, tag_id)
            self._refresh_tags_display_and_table()

    def _open_tag_management_window(self) -> None:
        """Apre la finestra di dialogo per la gestione globale dei tag."""
        dialog = TagManagementWindow(self)
        dialog.exec()
        self._update_fics_table()

    def _update_tag_completer(self) -> None:
        """
        Recupera tutti i tag utente dal database e aggiorna il modello
        del QCompleter per i suggerimenti di tag.
        """
        all_tags = get_all_user_tags()
        tag_names = [tag_name for tag_id, tag_name in all_tags]
        self.tag_completer_model.setStringList(tag_names)

    def _on_bookmarks_import_finished(self) -> None:
        """
        Slot eseguito al termine dell'importazione dei bookmark.
        """
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("Bookmarks import finished.", 3000)

        self.add_button.setEnabled(True)  # Assumendo tu abbia un pulsante per questo
        self._update_search_completer()
        self._update_tag_completer()
        logger.info("Bookmarks import process has finished.")

    def _on_import_error(self, error_message: str) -> None:
        """
        Slot eseguito quando un worker di importazione emette un errore.
        """
        logger.error(f"An error occurred during import: {error_message}")
        QMessageBox.critical(self, "Import Error", error_message)

        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("Import failed.", 3000)
        self.add_button.setEnabled(True)

    def _parse_ao3_url(self, url: str) -> tuple[str, str | None]:
        """
        Analizza un URL di AO3 e ne determina il tipo e l'ID/nome.

        Returns:
            Una tupla contenente (url_type, identifier).
            url_type può essere 'work', 'author', 'collection', 'series', o 'unknown'.
            identifier è l'ID o il nome estratto, o None.
        """
        work_match = re.search(r"/works/(\d+)", url)
        if work_match:
            return ("work", work_match.group(1))

        author_works_match = re.search(r"/users/([^/]+)/works", url)
        if author_works_match:
            return ("author", author_works_match.group(1))

        author_profile_match = re.search(r"/users/([^/]+)", url)
        if author_profile_match:
            return ("author", author_profile_match.group(1))

        collection_match = re.search(r"/collections/([^/]+)", url)
        if collection_match:
            return ("collection", collection_match.group(1).split("/")[0])
        series_match = re.search(r"/series/(\d+)", url)
        if series_match:
            return ("series", series_match.group(1))
        return ("unknown", None)

    def _perform_logout(self) -> None:
        """
        Logs the user out by clearing credentials and resetting the AO3 session.
        """
        reply = QMessageBox.question(
            self,
            "Confirm Logout",
            "Are you sure you want to log out? Your saved credentials will be removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        logger.info("User initiated logout. Clearing credentials.")

        import security_manager  # Import locale

        username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME)

        security_manager.delete_password(username)

        config_manager.set(
            const.CONFIG_SECTION_CREDS,
            const.CONFIG_KEY_USERNAME,
            const.CONFIG_DEFAULT_USER,
        )
        config_manager.save_config()

        ao3_client.reload_session()  # Questo imposterà self.session a None

        QMessageBox.information(self, "Logged Out", "You have been successfully logged out.")

        self._update_ui_for_logout()
        self._update_welcome_message()

    def _update_ui_for_logout(self) -> None:
        """Updates UI elements to reflect the logged-out state."""
        if self.selected_url:
            self._on_fic_selection_changed()  # Ricarica il pannello con i controlli corretti

        self._update_menu_actions_visibility()

    def _update_menu_actions_visibility(self) -> None:
        """Shows or hides menu actions based on the user's login status."""
        username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME, fallback="")
        is_logged_in = username and username != const.CONFIG_DEFAULT_USER

        if hasattr(self, "logout_action"):
            self.logout_action.setVisible(is_logged_in)

    def start_collection_import(self, collection_name: str) -> None:
        status_bar = self.statusBar()
        if self.collection_import_thread and self.collection_import_thread.isRunning():
            logger.warning("Collection import requested, but one is already running.")
            return

        logger.info(f"Starting collection import for: {collection_name}")
        self.add_button.setEnabled(False)
        if status_bar:
            status_bar.showMessage(f"Starting import from collection '{collection_name}'...")

        self.collection_import_thread = QThread()
        self.collection_import_worker = ImportCollectionWorker(collection_name)
        self.collection_import_worker.moveToThread(self.collection_import_thread)
        self.collection_import_thread.started.connect(self.collection_import_worker.run)
        self.collection_import_worker.progress.connect(self._update_progress_bar)
        self.collection_import_worker.new_fic_added.connect(self._update_fics_table)  # noqa: E501
        self.collection_import_worker.error.connect(self._on_import_error)
        self.collection_import_worker.finished.connect(
            self._on_mass_import_finished
        )  # Possiamo riutilizzare lo stesso slot di fine
        self.collection_import_worker.finished.connect(self.collection_import_thread.quit)
        self.collection_import_worker.finished.connect(self.collection_import_worker.deleteLater)
        self.collection_import_thread.finished.connect(self.collection_import_thread.deleteLater)
        self.collection_import_thread.finished.connect(lambda: setattr(self, "collection_import_thread", None))
        self.collection_import_thread.start()

    @pyqtSlot(sqlite3.Row)
    def _update_single_fic_row(self, fic_data: sqlite3.Row) -> None:
        """Aggiorna una singola riga nella tabella senza ricaricare tutto."""
        url = fic_data["url"]

        row = self._find_row_by_url(url)
        if row is not None:
            self.fics_in_memory[url] = fic_data
            self._populate_table_row(row, fic_data)

    def _start_total_sync(self) -> None:
        from sync_status_window import SyncStatusWindow

        if self.total_sync_thread and self.total_sync_thread.isRunning():
            QMessageBox.warning(self, "In Progress", "A sync process is already running.")
            return

        username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME)
        if not username or username == const.CONFIG_DEFAULT_USER:
            QMessageBox.critical(self, "Login Required", "You must be logged in to perform a full sync.")
            return

        fics_to_sync = get_fics_for_sync()
        if not fics_to_sync:
            QMessageBox.information(self, "All Good!", "No fics require status synchronization.")
            return
        estimated_minutes = len(fics_to_sync) * 8 // 60
        reply = QMessageBox.question(
            self,
            "Confirm Full Sync",
            f"This will check the status of <b>{len(fics_to_sync)}</b> fics on AO3. "
            f"The process could take approximately <b>{estimated_minutes} minutes or more</b>, "
            "depending on the number of comments.<br><br>"
            "You can continue using the application during the sync. Do you want to proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.No:
            return

        self.total_sync_thread = QThread()
        self.total_sync_worker = TotalSyncWorker(fics_to_sync)
        self.total_sync_worker.moveToThread(self.total_sync_thread)

        self.sync_dialog = SyncStatusWindow(self.total_sync_worker, len(fics_to_sync), self)

        self.total_sync_worker.progress.connect(self.sync_dialog.update_progress)
        self.total_sync_worker.status_update.connect(self.sync_dialog.update_status_text)
        self.total_sync_worker.eta_update.connect(self.sync_dialog.update_eta)
        self.total_sync_worker.finished.connect(self.sync_dialog.on_sync_finished)
        self.total_sync_worker.fic_updated.connect(self._update_single_fic_row)
        self.total_sync_worker.error.connect(lambda msg: QMessageBox.critical(self.sync_dialog, "Error", msg))

        self.total_sync_worker.finished.connect(self.total_sync_thread.quit)
        self.total_sync_worker.finished.connect(self.total_sync_worker.deleteLater)
        self.total_sync_thread.finished.connect(self.total_sync_thread.deleteLater)
        self.total_sync_thread.finished.connect(self._on_total_sync_finished)

        self.total_sync_thread.started.connect(self.total_sync_worker.run)
        self.total_sync_thread.start()
        self.sync_dialog.show()

    def _start_single_fic_add(self, url: str) -> None:
        """Avvia il worker per aggiungere una singola fic."""
        if self.add_fic_thread and self.add_fic_thread.isRunning():
            QMessageBox.warning(self, "In Progress", "A fic is already being added. Please wait.")
            return

        logger.info(f"Starting worker to add fic from URL: {url}")
        self.add_button.setEnabled(False)  # Il pulsante ora si chiama "Import"
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("Retrieving data from AO3...")

        self.add_fic_thread = QThread()
        self.worker = AddFicWorker(url)
        self.worker.moveToThread(self.add_fic_thread)
        self.add_fic_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_add_fic_finished)
        self.worker.error.connect(self._on_add_fic_error)
        self.worker.finished.connect(self.add_fic_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.add_fic_thread.finished.connect(lambda: setattr(self, "add_fic_thread", None))
        self.add_fic_thread.start()

    def _on_total_sync_finished(self) -> None:
        logger.info("Total sync process has concluded.")
        self.total_sync_thread = None
        self._update_fics_table()  # Ricarica la tabella con i nuovi stati


if __name__ == "__main__":
    logger.info("========================================")
    logger.info("Application starting...")
    initialize_database()
    try:
        run_database_migrations()
    except Exception:
        logger.critical("Database migration failed. The application cannot start safely. Please check the logs.")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME, fallback="")
    is_logged_in = username and username != const.CONFIG_DEFAULT_USER

    if not is_logged_in:
        logger.info("User is not logged in. Displaying WelcomeDialog.")
        from welcome_dialog import WelcomeDialog

        welcome_dialog = WelcomeDialog()
        welcome_dialog.exec()

    window = MainWindow()
    window.show()
    logger.info("Application startup complete. Main window is now visible.")
    sys.exit(app.exec())
