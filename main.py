import json
import os
import shutil
import sqlite3
import sys
import webbrowser
from datetime import datetime
from functools import partial
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
from PyQt6.QtGui import QAction, QActionGroup, QCloseEvent, QColor, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QComboBox,
    QCompleter,
    QFileDialog,
    QGroupBox,
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import constants as const
from achievements_window import AchievementsWindow
from analysis_engine import AnalysisEngine
from ao3_manager import ao3_client, parse_ao3_url
from author_recs_dialog import AuthorRecsDialog
from bulk_edit_dialog import BulkEditDialog
from config_manager import config_manager
from dashboard_window import DashboardWindow
from database import (
    add_fic,
    add_fics_to_queue,
    add_notification,
    assign_tag_to_fic,
    bulk_add_tags,
    bulk_remove_tags,
    bulk_update_status,
    calculate_base_stats,
    count_read_uncommented_fics,
    count_verified_statuses,
    delete_fic,
    get_all_filters,
    get_all_user_tags,
    get_data_for_charts,
    get_fic_by_url,
    get_fics_for_sync,
    get_filtered_fics,
    get_or_create_tag,
    get_tags_for_fic,
    get_unread_notifications,
    remove_fics_from_queue,
    remove_tag_from_fic,
    run_database_migrations,
    save_filter,
    update_fic_notes,
    update_fic_rating,
    update_fic_status,
)
from filter_builder_dialog import FilterBuilderDialog
from gamification import calculate_xp_level, check_for_achievements
from logger_setup import logger
from login_dialog import LoginDialog
from notifications_window import NotificationsWindow
from reading_queue_dialog import ReadingQueueDialog
from recommendation_center_dialog import RecommendationCenterDialog
from tag_management_window import TagManagementWindow
from ui_components import NumericTableWidgetItem
from workers import (
    AddFicWorker,
    AnalysisWorker,
    AuthorRecsWorker,
    DiscoverFicsWorker,
    ImportBookmarksWorker,
    ImportCollectionWorker,
    ImportHistoryWorker,
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


class MainWindow(QMainWindow):
    update_thread: Optional[QThread]
    import_thread: Optional[QThread]
    bookmarks_import_thread: Optional[QThread]
    sync_thread: Optional[QThread]
    selected_url: Optional[str]
    fics_in_memory: Dict[str, Dict[str, Any]]
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
    detail_user_tags: QLabel
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
    update_worker: Optional[UpdateCheckWorker]
    sync_worker: Optional[SyncStatusWorker]

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AO3 Helper - Your Fanfiction Archive")
        self.setGeometry(200, 200, 1200, 700)
        self.setWindowIcon(QIcon(resource_path("assets/app_icon.ico")))

        self.add_fic_thread: Optional[QThread] = None
        self.worker: Optional[AddFicWorker] = None
        self.update_thread: Optional[QThread] = None
        self.update_worker = None
        self.import_thread: Optional[QThread] = None
        self.import_worker = None
        self.sync_thread: Optional[QThread] = None
        self.sync_worker = None
        self.bookmarks_import_thread = None
        self.bookmarks_import_worker: Optional[ImportBookmarksWorker] = None
        self.history_import_thread: Optional[QThread] = None
        self.history_import_worker: Optional[ImportHistoryWorker] = None
        self.selected_url: Optional[str] = None
        self.collection_import_thread: Optional[QThread] = None
        self.collection_import_worker: Optional[ImportCollectionWorker] = None
        self.author_recs_thread: Optional[QThread] = None
        self.author_recs_worker: Optional[AuthorRecsWorker] = None
        self.series_import_thread: Optional[QThread] = None
        self.series_import_worker: Optional[ImportSeriesWorker] = None
        self.total_sync_thread: Optional[QThread] = None
        self.total_sync_worker: Optional[TotalSyncWorker] = None
        self.discovery_thread: Optional[QThread] = None
        self.discovery_worker: Optional[DiscoverFicsWorker] = None
        self.bulk_edit_dialog: Optional[BulkEditDialog] = None
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
        self.saved_filters_combo: QComboBox
        self.save_filter_button: QPushButton
        self.advanced_search_button: QPushButton
        self.clear_search_button: QPushButton
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
        self.detail_user_tags: QLabel
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
        self.add_to_library_button: QPushButton
        self.delete_button: QPushButton

        self.view_filter_group: "QButtonGroup"
        self.library_button: QPushButton
        self.history_button: QPushButton
        self.inbox_button: QPushButton
        self.all_button: QPushButton
        self.current_view_filter: str = "library"

        self.tag_completer: QCompleter
        self.tag_completer_model: QStringListModel
        self.recommendation_panel: QGroupBox
        self.recommendation_title: QLabel
        self.recommendation_author: QLabel
        self.recommendation_score: QLabel
        self.current_recommendations: List[Dict[str, Any]] = []
        self.current_recommendation_index: int = 0

        self.analysis_engine = AnalysisEngine()
        self._setup_analysis_engine()
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
        base_stylesheet = """
            QPushButton#deleteButton {
                background-color: #a13333;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton#deleteButton:hover {
                background-color: #c94040;
            }
        """
        self.setStyleSheet(base_stylesheet)

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
        self._update_tag_completer()
        self._load_settings()
        self._generate_startup_notification()
        self._update_welcome_message()
        self.start_update_check()
        self._load_saved_filters()
        self._update_menu_actions_visibility()

    def _setup_analysis_engine(self):
        """
        Performs the initial full calculation of analysis data in a background thread
        using a dedicated, robust worker.
        """
        self.statusBar().showMessage("Initializing analysis engine...")

        self.analysis_thread = QThread(self)
        self.analysis_worker = AnalysisWorker(self.analysis_engine)
        self.analysis_worker.moveToThread(self.analysis_thread)

        self.analysis_thread.started.connect(self.analysis_worker.run)

        self.analysis_worker.finished.connect(self._on_analysis_ready)

        self.analysis_worker.finished.connect(self.analysis_thread.quit)
        self.analysis_worker.finished.connect(self.analysis_worker.deleteLater)
        self.analysis_thread.finished.connect(self.analysis_thread.deleteLater)

        self.analysis_thread.start()

    @pyqtSlot()
    def _on_analysis_ready(self) -> None:
        """
        Slot called when the background analysis calculation is complete.
        Enables the dashboard button and updates its tooltip.
        """
        self.dashboard_button.setEnabled(True)
        self.dashboard_button.setToolTip("Open the Reader Dashboard & Analysis Center")
        logger.info("Analysis engine is ready. Dashboard is now available.")
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("Analysis engine ready.", 3000)

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
        reading_queue_action = QAction("🔖 Reading Queue...", self)
        reading_queue_action.triggered.connect(self._open_reading_queue_dialog)
        tools_menu.addAction(reading_queue_action)
        tools_menu.addSeparator()
        sync_action = QAction("Full Status Sync...", self)
        sync_action.triggered.connect(self._start_total_sync)
        tools_menu.addAction(sync_action)
        tools_menu.addSeparator()
        import_bookmarks_action = QAction("Import from AO3 Bookmarks...", self)
        import_bookmarks_action.triggered.connect(self._start_bookmarks_import)
        tools_menu.addAction(import_bookmarks_action)
        import_history_action = QAction("Import from AO3 History...", self)
        import_history_action.triggered.connect(self._start_history_import)
        tools_menu.addAction(import_history_action)

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
        view_filter_layout = self._create_view_filter_layout()
        self.recommendation_panel = self._create_recommendation_panel()
        self.recommendation_panel.setVisible(False)

        welcome_layout = QHBoxLayout()
        self.welcome_label = QLabel()
        self.welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.welcome_label.setStyleSheet("font-size: 14px; margin: 5px;")
        welcome_layout.addWidget(self.welcome_label)
        gamification_layout = self._create_gamification_layout()
        left_layout.addLayout(top_layout)
        left_layout.addLayout(search_layout)
        left_layout.addLayout(view_filter_layout)
        left_layout.addWidget(self.recommendation_panel)
        left_layout.addLayout(welcome_layout)

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
        self.dashboard_button = QPushButton("🚀 Dashboard")
        self.dashboard_button.setEnabled(False)
        self.dashboard_button.setToolTip("Please wait while the initial analysis is performed...")

        self.notifications_button = QPushButton("🔔")
        self.refresh_button = QPushButton("🔄 Refresh")

        top_layout.addWidget(QLabel("URL:"))
        top_layout.addWidget(self.url_input, 1)
        top_layout.addWidget(self.add_button)
        top_layout.addWidget(self.dashboard_button)

        top_layout.addWidget(self.notifications_button)
        top_layout.addWidget(self.refresh_button)

        return top_layout

    def _create_search_layout(self) -> QHBoxLayout:
        search_layout = QHBoxLayout()
        self.saved_filters_combo = QComboBox()
        self.saved_filters_combo.addItem("Saved Filters...")

        self.save_filter_button = QPushButton("💾 Save")
        self.save_filter_button.setToolTip("Save the current search criteria as a new filter")

        self.advanced_search_button = QPushButton("Advanced...")
        self.advanced_search_button.setToolTip("Open the Filter Builder for complex searches")

        search_layout.addWidget(self.saved_filters_combo)
        search_layout.addWidget(self.save_filter_button)
        search_layout.addWidget(self.advanced_search_button)
        search_layout.addStretch()
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
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(
            [
                "Status: All",
                const.STATUS_TO_READ,
                const.STATUS_READ,
                const.STATUS_KUDOSED,
                const.STATUS_COMMENTED,
                const.STATUS_DROPPED,
            ]
        )
        search_layout.addWidget(QLabel("and"))
        search_layout.addWidget(self.status_filter_combo)
        self.clear_search_button = QPushButton("Clear")
        self.clear_search_button.setToolTip("Reset all search filters")
        search_layout.addWidget(self.clear_search_button)

        return search_layout

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

    def _create_recommendation_panel(self) -> QGroupBox:
        """Creates the 'For You' recommendation panel widget."""
        panel = QGroupBox("✨ For You: Next Recommendation")
        panel_layout = QHBoxLayout(panel)

        info_layout = QVBoxLayout()
        self.recommendation_title = QLabel("<b>Title will appear here</b>")
        self.recommendation_title.setStyleSheet("font-size: 14px;")
        self.recommendation_author = QLabel("by Author")
        self.recommendation_score = QLabel("<i>Match Score: -</i>")
        self.recommendation_score.setToolTip(
            "This score represents how well this fic matches your established tastes.\n" "Higher is a better match!"
        )

        info_layout.addWidget(self.recommendation_title)
        info_layout.addWidget(self.recommendation_author)
        info_layout.addWidget(self.recommendation_score)

        panel_layout.addLayout(info_layout, 1)

        actions_layout = QHBoxLayout()
        actions_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        select_button = QPushButton("➡️ Select Fic")
        select_button.clicked.connect(self._on_recommendation_select)

        shuffle_button = QPushButton("🔀 Suggest Another")
        shuffle_button.clicked.connect(self._on_recommendation_shuffle)

        details_button = QPushButton("📊 View All Suggestions...")
        details_button.clicked.connect(self._open_recommendation_center)

        author_recs_button = QPushButton("🌟 Author-Curated...")
        author_recs_button.clicked.connect(self._open_author_recs_dialog)

        actions_layout.addWidget(select_button)
        actions_layout.addWidget(shuffle_button)
        actions_layout.addWidget(details_button)

        actions_layout.addWidget(author_recs_button)

        panel_layout.addLayout(actions_layout)

        return panel

    def _open_recommendation_center(self) -> None:
        """Opens the recommendation center dialog with all current recommendations."""
        if not self.current_recommendations:
            QMessageBox.information(self, "No Recommendations", "There are currently no recommendations to display.")
            return

        dialog = RecommendationCenterDialog(self.current_recommendations, self)

        dialog.fic_selected.connect(self._select_fic_from_url)
        dialog.discover_fics_requested.connect(self._start_discovery_worker)
        dialog.import_fic_requested.connect(self._start_single_fic_add)
        dialog.add_to_queue_requested.connect(self._handle_add_to_queue_request)
        dialog.exec()

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
            const.COLUMN_MATCH_SCORE,
            const.COLUMN_CATEGORY,
            const.COLUMN_RELATIONSHIPS,
            const.COLUMN_CHARACTERS,
            const.COLUMN_USER_TAGS,
            const.COLUMN_LAST_VISIT,
            const.COLUMN_VISIT_COUNT,
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

        self.detail_user_tags = QLabel()
        self.detail_user_tags.setWordWrap(True)
        self.detail_user_tags.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.detail_user_tags.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.detail_summary = QTextEdit()
        self.detail_summary.setReadOnly(True)
        self.detail_notes = NoteWidget()
        self.detail_notes.setPlaceholderText("Your personal notes...")
        status_layout = self._create_details_status_buttons()
        rating_layout = self._create_details_rating_buttons()
        self.delete_button = QPushButton("🗑️ DELETE FIC")
        self.delete_button.setObjectName("deleteButton")

        self.add_to_library_button = QPushButton("📚 Add to Library")
        self.add_to_library_button.setStyleSheet(
            "background-color: #2a9d8f; color: white; font-weight: bold; border-radius: 4px; padding: 5px;"
        )
        self.add_to_library_button.setVisible(False)

        actions_layout = QHBoxLayout()
        actions_layout.addWidget(self.add_to_library_button)
        actions_layout.addStretch()
        actions_layout.addWidget(self.delete_button)

        right_layout.addLayout(title_layout)
        right_layout.addWidget(self.detail_author)
        right_layout.addWidget(self.detail_info)
        right_layout.addWidget(self.detail_category)
        right_layout.addWidget(self.detail_relationships)
        right_layout.addWidget(self.detail_characters)
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
        right_layout.addLayout(actions_layout)
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
        self.dashboard_button.clicked.connect(self._open_dashboard_window)

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
        self.detail_user_tags.linkActivated.connect(self._execute_search_from_link)
        self.detail_user_tags.customContextMenuRequested.connect(self._open_user_tag_context_menu)
        self.to_read_button.clicked.connect(partial(self._change_fic_status, const.STATUS_TO_READ))
        self.read_button.clicked.connect(partial(self._change_fic_status, const.STATUS_READ))
        self.dropped_button.clicked.connect(partial(self._change_fic_status, const.STATUS_DROPPED))
        self.open_browser_button.clicked.connect(self._open_fic_in_browser)
        if self.manual_override_enabled:
            self.kudosed_button.clicked.connect(partial(self._change_fic_status, const.STATUS_KUDOSED, verified=0))
            self.commented_button.clicked.connect(partial(self._change_fic_status, const.STATUS_COMMENTED, verified=0))
        else:
            self.sync_status_button.clicked.connect(self.start_status_sync)
        for i, btn in enumerate(self.rating_buttons):

            btn.clicked.connect(lambda checked, num=i + 1: self._save_rating(num))
        self.delete_button.clicked.connect(
            lambda: self._on_delete_fics_clicked([self.selected_url] if self.selected_url else [])
        )  # noqa: E501
        self.search_input.textChanged.connect(self._on_search_triggered)
        self.search_combo.currentIndexChanged.connect(self._on_search_triggered)
        self.status_filter_combo.currentIndexChanged.connect(self._on_search_triggered)
        self.view_filter_group.buttonClicked.connect(self._on_view_filter_changed)
        self.save_filter_button.clicked.connect(self._on_save_filter_clicked)
        self.saved_filters_combo.activated.connect(self._on_saved_filter_selected)
        self.advanced_search_button.clicked.connect(self._open_filter_builder)
        self.clear_search_button.clicked.connect(self._on_clear_search_clicked)
        self.add_to_library_button.clicked.connect(self._add_to_library)

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
        fics_in_queue = [url for url in selected_urls if self.fics_in_memory.get(url, {}).get("is_in_reading_queue")]

        if len(fics_in_queue) < fic_count:
            add_to_queue_action = menu.addAction(f"🔖 Add {fic_count} Fic(s) to Reading Queue")

            if add_to_queue_action:
                add_to_queue_action.triggered.connect(self._add_selected_to_queue)

        if len(fics_in_queue) > 0:
            remove_from_queue_action = menu.addAction(f"✖️ Remove {len(fics_in_queue)} Fic(s) from Reading Queue")

            if remove_from_queue_action:
                remove_from_queue_action.triggered.connect(self._remove_selected_from_queue)

        menu.addSeparator()

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
        if new_status and isinstance(new_status, str):
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

    def _update_recommendations_panel(self) -> None:
        """
        Fetches and displays the top recommendation in the 'For You' panel.
        Hides the panel if no suitable recommendations are found.
        """

        fics_to_consider = [fic for fic in self.fics_in_memory.values() if fic["status"] == const.STATUS_TO_READ]

        if not fics_to_consider:
            self.recommendation_panel.setVisible(False)
            return

        self.current_recommendations = self.analysis_engine.generate_recommendations(fics_to_consider)

        self.current_recommendations = [rec for rec in self.current_recommendations if rec["recommendation_score"] > 0]

        if not self.current_recommendations:
            self.recommendation_panel.setVisible(False)
            return

        self.current_recommendation_index = 0
        self._display_current_recommendation()
        self.recommendation_panel.setVisible(True)

    @pyqtSlot(str)
    def _select_fic_from_url(self, url: str) -> None:
        """Selects a fic in the main table based on a URL received from a child dialog."""
        row_index = self._find_row_by_url(url)
        if row_index is not None:
            self.fics_table.selectRow(row_index)
            item = self.fics_table.item(row_index, 0)
            if item:
                self.fics_table.scrollToItem(item)

    @pyqtSlot()
    def _on_recommendation_select(self) -> None:
        """Handles the 'Select Fic' button click."""
        url_to_select = self.recommendation_panel.property("fic_url")
        if url_to_select:
            self._select_fic_from_url(url_to_select)

    @pyqtSlot()
    def _on_recommendation_shuffle(self) -> None:
        """Handles the 'Suggest Another' button click by showing the next recommendation."""
        if not self.current_recommendations:
            return

        self.current_recommendation_index = (self.current_recommendation_index + 1) % len(self.current_recommendations)

        self._display_current_recommendation()

    @pyqtSlot(list)
    def _handle_add_to_queue_request(self, urls: List[str]) -> None:
        """Aggiunge una lista di URL alla coda e aggiorna la UI."""
        add_fics_to_queue(urls)
        self._refresh_rows_by_url(urls)

    def _display_current_recommendation(self) -> None:
        """Updates the UI labels of the recommendation panel with the current recommendation."""
        if not self.current_recommendations:
            self.recommendation_panel.setVisible(False)
            return

        if not (0 <= self.current_recommendation_index < len(self.current_recommendations)):
            self.current_recommendation_index = 0

        fic = self.current_recommendations[self.current_recommendation_index]

        self.recommendation_title.setText(f"<b>{fic['title']}</b>")
        self.recommendation_author.setText(f"by {fic['author']}")
        self.recommendation_score.setText(f"<i>Match Score: {fic['recommendation_score']}</i>")

        self.recommendation_panel.setProperty("fic_url", fic["url"])

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
        if selection_model:
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

    def _create_view_filter_layout(self) -> QHBoxLayout:
        """Crea il layout con i pulsanti per filtrare la vista principale."""
        view_filter_layout = QHBoxLayout()

        filter_container = QWidget()
        filter_container_layout = QHBoxLayout(filter_container)
        filter_container_layout.setContentsMargins(0, 0, 0, 0)
        filter_container_layout.setSpacing(6)

        style_sheet = """
            QPushButton {
                padding: 5px 10px; /* Aggiunge un po' di respiro al testo */
            }
            QPushButton:checked {
                background-color: #007acc;
                color: white;
                font-weight: bold;
                border: 1px solid #005a9e;
            }
        """
        filter_container.setStyleSheet(style_sheet)

        filter_container_layout.addWidget(QLabel("<b>View:</b>"))

        self.view_filter_group = QButtonGroup(self)
        self.view_filter_group.setExclusive(True)

        self.library_button = QPushButton("📚 My Library")
        self.library_button.setCheckable(True)
        self.library_button.setChecked(True)

        self.history_button = QPushButton("🕓 History")
        self.history_button.setCheckable(True)

        self.inbox_button = QPushButton("📥 Inbox")
        self.inbox_button.setCheckable(True)

        self.all_button = QPushButton("🌐 All Entries")
        self.all_button.setCheckable(True)

        self.view_filter_group.addButton(self.library_button)
        self.view_filter_group.addButton(self.history_button)
        self.view_filter_group.addButton(self.inbox_button)
        self.view_filter_group.addButton(self.all_button)

        filter_container_layout.addWidget(self.library_button)
        filter_container_layout.addWidget(self.history_button)
        filter_container_layout.addWidget(self.inbox_button)
        filter_container_layout.addWidget(self.all_button)

        view_filter_layout.addWidget(filter_container)
        view_filter_layout.addStretch()

        return view_filter_layout

    def _add_to_library(self) -> None:
        """
        Aggiunge l'opera attualmente selezionata alla libreria e aggiorna la UI.
        """
        if not self.selected_url:
            return

        from database import set_fic_in_library

        set_fic_in_library(self.selected_url)

        self.add_to_library_button.setVisible(False)

        self.fics_in_memory[self.selected_url]["is_in_library"] = True

        row_to_update = self._find_row_by_url(self.selected_url)
        if row_to_update is not None:
            fic_data = self.fics_in_memory[self.selected_url]
            self._populate_table_row(row_to_update, fic_data)

        QMessageBox.information(self, "Success", "Work has been added to your library!")

    def refresh_bulk_edit_dialog_tags(self) -> None:

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

    def _populate_table_row(self, row_num: int, fic: Dict[str, Any]):
        rating = fic["user_rating"] or 0
        wc = fic["word_count"] or 0
        icons = []
        if fic.get("is_in_reading_queue"):
            icons.append("🔖")
        if fic.get("is_in_library"):
            icons.append("📚")

        if fic["is_complete"]:
            icons.append("✅")
        else:
            icons.append("📖")

        icon_str = " ".join(icons)
        verified_icon = "🔹" if fic["status_verified"] else "🔸"
        hits = fic["hits"] or 0
        kudos = fic["kudos"] or 0
        visits = fic["visit_count"] or 0
        series_text = f"{fic['series_name']} (Part {fic['series_part']})" if fic["series_name"] else ""
        match_score = fic.get("recommendation_score", 0.0)

        items: Dict[str, QTableWidgetItem] = {
            const.COLUMN_TITLE: QTableWidgetItem(f"{icon_str} {fic['title']}"),
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
            const.COLUMN_LAST_VISIT: QTableWidgetItem(fic["last_visit_date"] or ""),
        }
        items[const.COLUMN_MATCH_SCORE] = NumericTableWidgetItem(f"{match_score:.2f}")
        items[const.COLUMN_MATCH_SCORE].setData(Qt.ItemDataRole.UserRole, match_score)
        items[const.COLUMN_VISIT_COUNT] = NumericTableWidgetItem(f"{visits:,}")
        items[const.COLUMN_VISIT_COUNT].setData(Qt.ItemDataRole.UserRole, visits)
        items[const.COLUMN_WORDS] = NumericTableWidgetItem(f"{wc:,}")
        items[const.COLUMN_WORDS].setData(Qt.ItemDataRole.UserRole, wc)

        items[const.COLUMN_HITS] = NumericTableWidgetItem(f"{hits:,}")
        items[const.COLUMN_HITS].setData(Qt.ItemDataRole.UserRole, hits)

        items[const.COLUMN_KUDOS] = NumericTableWidgetItem(f"{kudos:,}")
        items[const.COLUMN_KUDOS].setData(Qt.ItemDataRole.UserRole, kudos)

        rating_item_for_sorting = NumericTableWidgetItem()
        rating_item_for_sorting.setData(Qt.ItemDataRole.UserRole, rating)

        text_color = self.status_text_colors.get(fic["status"], QColor("black"))

        items[const.COLUMN_TITLE].setData(Qt.ItemDataRole.UserRole, fic["url"])

        self.fics_table.setSortingEnabled(False)

        for col_idx, key in enumerate(self.column_map):
            if key == const.COLUMN_USER_RATING:

                star_color = "#FFC107"
                filled_stars_html = f'<font color="{star_color}">{"★" * rating}</font>'
                empty_stars_text = "☆" * (5 - rating)

                stars_html = filled_stars_html + empty_stars_text

                rating_label = QLabel(stars_html)
                rating_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

                self.fics_table.setCellWidget(row_num, col_idx, rating_label)
                self.fics_table.setItem(row_num, col_idx, rating_item_for_sorting)

            elif key in items:
                item = items[key]
                item.setForeground(text_color)
                if key == const.COLUMN_MATCH_SCORE:
                    item.setToolTip("How well this fic matches your tastes based on your reading history.")
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

            column_order = [str(header.logicalIndex(i)) for i in range(header.count())]
            config_manager.set(const.CONFIG_SECTION_UI, const.CONFIG_KEY_COL_ORDER, ",".join(column_order))

            hidden_columns = [str(i) for i in range(header.count()) if self.fics_table.isColumnHidden(i)]
            config_manager.set(const.CONFIG_SECTION_UI, "hidden_columns", ",".join(hidden_columns))

        config_manager.save_config()

    def _load_settings(self) -> None:

        if geom := config_manager.get(const.CONFIG_SECTION_UI, const.CONFIG_KEY_GEOMETRY, fallback=None):
            self.restoreGeometry(QByteArray.fromBase64(geom.encode("utf-8")))

        header = self.fics_table.horizontalHeader()
        if header:

            order_str = config_manager.get(const.CONFIG_SECTION_UI, const.CONFIG_KEY_COL_ORDER, fallback=None)
            if order_str:
                try:

                    column_order = [int(i) for i in order_str.split(",")]
                    if len(column_order) == header.count():
                        for visual_index, logical_index in enumerate(column_order):
                            header.moveSection(header.visualIndex(logical_index), visual_index)
                except (ValueError, IndexError):
                    logger.warning("Could not parse or apply saved column order. Using default.")

            hidden_str = config_manager.get(const.CONFIG_SECTION_UI, "hidden_columns", fallback=None)
            if hidden_str:
                try:
                    hidden_columns = [int(i) for i in hidden_str.split(",") if i.strip()]
                    for i in range(header.count()):
                        self.fics_table.setColumnHidden(i, i in hidden_columns)
                except ValueError:
                    logger.warning("Could not parse saved hidden columns. Using default.")
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
                shutil.copyfile(const.DB_PATH, file_path)
                logger.info(f"Database successfully backed up to {file_path}")
                QMessageBox.information(self, "Backup Successful", f"Database backed up to:\n{file_path}")
            except Exception as e:
                logger.exception("Database backup failed.")
                QMessageBox.critical(self, "Backup Failed", f"Error: {e}")

    def _prepare_completer_data(self) -> Dict[str, List[str]]:
        """
        Scans all fics in memory to generate unique lists for completer suggestions.
        """
        all_fandoms: set[str] = set()
        all_authors: set[str] = set()
        all_tags: set[str] = set()

        all_fics_in_db = get_filtered_fics(view_filter="all")

        for fic in all_fics_in_db:
            if fic.get("fandoms"):
                all_fandoms.update(t.strip() for t in fic["fandoms"].split(","))
            if fic.get("author"):
                all_authors.update(t.strip() for t in fic["author"].split(","))
            if fic.get("tags"):
                all_tags.update(t.strip() for t in fic["tags"].split(","))

        return {
            "fandoms": sorted(list(all_fandoms)),
            "authors": sorted(list(all_authors)),
            "tags": sorted(list(all_tags)),
        }

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
                shutil.copyfile(file_path, const.DB_PATH)
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

        if status_bar:
            status_bar.showMessage("Starting import...")

        self.import_thread = QThread()
        self.import_worker = MassImportWorker(url_or_name)
        self.import_worker.moveToThread(self.import_thread)
        self.import_thread.started.connect(self.import_worker.run)
        self.import_worker.progress.connect(self._update_progress_bar)
        self.import_worker.new_fic_added.connect(self._on_new_fic_from_worker)

        self.import_worker.error.connect(self._on_import_error)

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

        self._update_search_completer()

    def _start_bookmarks_import(self) -> None:

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

        self.bookmarks_import_thread = QThread()
        self.bookmarks_import_worker = ImportBookmarksWorker()
        self.bookmarks_import_worker.moveToThread(self.bookmarks_import_thread)

        self.bookmarks_import_thread.started.connect(self.bookmarks_import_worker.run)
        self.bookmarks_import_worker.progress.connect(self._update_progress_bar)
        self.bookmarks_import_worker.new_fic_added.connect(self._on_new_fic_from_worker)
        self.bookmarks_import_worker.error.connect(self._on_import_error)
        self.bookmarks_import_worker.finished.connect(self._on_bookmarks_import_finished)

        self.bookmarks_import_worker.finished.connect(self.bookmarks_import_thread.quit)
        self.bookmarks_import_worker.finished.connect(self.bookmarks_import_worker.deleteLater)
        self.bookmarks_import_thread.finished.connect(self.bookmarks_import_thread.deleteLater)
        self.bookmarks_import_thread.finished.connect(lambda: setattr(self, "bookmarks_import_thread", None))

        self.bookmarks_import_thread.start()

    def _start_history_import(self) -> None:

        status_bar = self.statusBar()

        active_imports = [
            self.import_thread,
            self.bookmarks_import_thread,
            self.history_import_thread,
        ]
        if any(thread and thread.isRunning() for thread in active_imports):
            logger.warning("History import requested, but another import is already running.")
            if status_bar:
                status_bar.showMessage("An import process is already running.", 3000)
            return

        if not ao3_client.session:
            QMessageBox.critical(
                self,
                "Login Required",
                "You must be logged in to import your history.\nPlease use File > Settings / Login.",
            )
            return

        logger.info("Starting history import process.")
        if status_bar:
            status_bar.showMessage("Starting history import...")

        self.history_import_thread = QThread()
        self.history_import_worker = ImportHistoryWorker()
        self.history_import_worker.moveToThread(self.history_import_thread)

        self.history_import_thread.started.connect(self.history_import_worker.run)
        self.history_import_worker.progress.connect(self._update_progress_bar)
        self.history_import_worker.new_fic_added.connect(self._on_new_fic_from_worker)
        self.history_import_worker.error.connect(self._on_import_error)
        self.history_import_worker.finished.connect(self._on_history_import_finished)

        self.history_import_worker.finished.connect(self.history_import_thread.quit)
        self.history_import_worker.finished.connect(self.history_import_worker.deleteLater)
        self.history_import_thread.finished.connect(self.history_import_thread.deleteLater)
        self.history_import_thread.finished.connect(lambda: setattr(self, "history_import_thread", None))

        self.history_import_thread.start()

    def _on_history_import_finished(self) -> None:

        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("History import finished.", 3000)

        self._update_search_completer()
        self._update_tag_completer()
        logger.info("History import process has finished.")

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

    def _on_status_sync_finished(self, sync_results: Dict[str, bool], url: str) -> None:
        """
        Gestisce il completamento di una sincronizzazione e aggiorna l'interfaccia
        applicando la logica di business corretta basata sui fatti ricevuti.
        """
        fic_data = self.fics_in_memory.get(url)
        if not fic_data:
            logger.warning(f"Sync finished for a fic not in memory: {url}")
            return

        current_status = fic_data["status"]
        new_status = current_status

        if sync_results.get("commented"):
            new_status = const.STATUS_COMMENTED
        elif sync_results.get("kudosed"):
            new_status = const.STATUS_KUDOSED
        elif fic_data.get("is_in_history"):

            if current_status != const.STATUS_COMMENTED and current_status != const.STATUS_KUDOSED:
                new_status = const.STATUS_READ

        status_bar = self.statusBar()
        if status_bar:
            message = f"Sync complete for '{fic_data.get('title', 'fic')}'. "
            if new_status != current_status:
                message += f"New status: {new_status}"
            else:
                message += "Status is up to date."
            status_bar.showMessage(message, 4000)

        if hasattr(self, "sync_status_button") and not self.manual_override_enabled:
            self.sync_status_button.setEnabled(True)
            self.sync_status_button.setText("🔄 Sync Status")

        if new_status != current_status:
            update_fic_status(url, new_status, 1)
            old_fic_data = dict(fic_data)

            self.fics_in_memory[url]["status"] = new_status
            self.fics_in_memory[url]["status_verified"] = True
            self.analysis_engine.update_fic(old_fic_data, self.fics_in_memory[url])

            row_to_update = self._find_row_by_url(url)
            if row_to_update is not None:
                self._populate_table_row(row_to_update, self.fics_in_memory[url])

            if check_for_achievements(
                calculate_base_stats(),
                get_data_for_charts("lette"),
                count_verified_statuses(),
                newly_modified_fic=self.fics_in_memory[url],
            ):
                self.update_notification_indicator()
        else:

            self.fics_in_memory[url]["status_verified"] = True
            row_to_update = self._find_row_by_url(url)
            if row_to_update is not None:
                self._populate_table_row(row_to_update, self.fics_in_memory[url])

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

            fields_to_scan = ["fandoms", "tags", "category", "relationships", "characters", const.SEARCH_USER_TAGS]

            for field in fields_to_scan:

                key = "user_tags" if field == const.SEARCH_USER_TAGS else field
                if fic[key]:
                    for item in fic[key].split(","):
                        if item.strip():
                            suggestions.add(item.strip())
        self.completer_model.setStringList(sorted(list(suggestions)))

    def _update_fics_table(self, fics_to_display: Optional[List[Dict[str, Any]]] = None) -> None:
        self._ignore_selection_change = True
        previously_selected_url = self.selected_url
        self.fics_table.setSortingEnabled(False)
        self.fics_table.clearContents()

        all_fics_raw = get_filtered_fics(view_filter=self.current_view_filter)

        all_fics_scored = self.analysis_engine.generate_recommendations(all_fics_raw)
        self.fics_in_memory = {fic["url"]: fic for fic in all_fics_scored}

        fics_to_render = fics_to_display if fics_to_display is not None else list(self.fics_in_memory.values())

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
        self._update_recommendations_panel()

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

    @pyqtSlot()
    def _on_search_triggered(self) -> None:
        """
        Costruisce un "Filter Object" basato sullo stato attuale della UI
        di ricerca e aggiorna la tabella.
        """

        filters: Dict[str, Any] = {"conditions": {}, "tags": {}, "user_tags": {}}

        search_text = self.search_input.text().strip()
        field_idx = self.search_combo.currentIndex()
        status_idx = self.status_filter_combo.currentIndex()

        if status_idx > 0:
            filters["conditions"]["status"] = self.status_filter_combo.currentText()

        field_map = {
            0: "all",
            1: "title",
            2: "author",
            3: "fandoms",
            4: "rating",
            5: "tags",
            6: "category",
            7: "relationships",
            8: "characters",
            9: "user_tags",
            10: "series_name",
        }
        field_key = field_map.get(field_idx, "all")

        if search_text:
            if field_key == "tags":
                filters["tags"]["and"] = [t.strip() for t in search_text.split(",")]
            elif field_key == "user_tags":
                filters["user_tags"]["and"] = [t.strip() for t in search_text.split(",")]
            else:
                filters["conditions"][field_key] = search_text

        fics_found = get_filtered_fics(view_filter=self.current_view_filter, filters=filters)
        self._update_fics_table(fics_found)

    @pyqtSlot()
    def _on_clear_search_clicked(self) -> None:
        """Resets all search and filter controls to their default state."""

        self.search_input.blockSignals(True)
        self.search_combo.blockSignals(True)
        self.status_filter_combo.blockSignals(True)
        self.saved_filters_combo.blockSignals(True)

        self.search_input.clear()
        self.search_combo.setCurrentIndex(0)
        self.status_filter_combo.setCurrentIndex(0)
        self.saved_filters_combo.setCurrentIndex(0)

        self.search_input.blockSignals(False)
        self.search_combo.blockSignals(False)
        self.status_filter_combo.blockSignals(False)
        self.saved_filters_combo.blockSignals(False)

        self._on_search_triggered()

    @pyqtSlot()
    def _on_view_filter_changed(self) -> None:
        """
        Gestisce il cambio di vista tra Libreria, Cronologia e Tutto.
        Aggiorna lo stato interno e ricarica la tabella delle opere.
        """
        if self.library_button.isChecked():
            self.current_view_filter = "library"
        elif self.history_button.isChecked():
            self.current_view_filter = "history"
        elif self.inbox_button.isChecked():
            self.current_view_filter = "inbox"
        else:
            self.current_view_filter = "all"

        logger.info(f"View filter changed to: '{self.current_view_filter}'")

        self.search_input.clear()
        self.status_filter_combo.setCurrentIndex(0)

        self._update_fics_table()

    def _execute_search_from_link(self, link: str) -> None:
        """
        Handler for clicking a search link in the details panel.
        """
        logger.debug(f"DEBUG: _execute_search_from_link received: '{link}'")
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
            "series_name": 10,
        }

        if (idx := combo_map.get(field)) is not None:
            self.search_combo.setCurrentIndex(idx)
            self.search_input.setText(value)

    def format_link(self, text: Optional[str], link_type: str) -> str:
        """Helper method to format a comma-separated string into clickable HTML links."""
        if not text:
            return ""
        return ", ".join([f'<a href="{link_type}:{i.strip()}">{i.strip()}</a>' for i in text.split(",") if i.strip()])

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
            last_visit = data.get("last_visit_date")
            visit_count = data.get("visit_count")
            self.detail_title.setText(data["title"])

            self.detail_author.setText(f"by {self.format_link(data['author'], 'author')}")
            series_html = ""
            history_html = ""
            if last_visit:
                history_html = f"<b>Your History:</b> Last visit on {last_visit} ({visit_count} total visits)<br>"
            self.detail_info.setText(
                f"{series_html}"
                f"<b>Fandom:</b> {self.format_link(data['fandoms'], 'fandoms')}<br>"
                f"<b>Published:</b> {data['date_published']} | <b>Updated:</b> {data['date_updated']}<br>"
                f"<b>Rating:</b> {data['rating']} | <b>Language:</b> {data['language']}<br>"
                f"<b>Words:</b> {word_count:,} | <b>Chapters:</b> {data['chapters']}<br>"
                f"<b>AO3 Stats:</b> Kudos: {kudos:,} | Bookmarks: {bookmarks:,} | Comments: {comments:,} | Hits: {hits:,}<br>"  # noqa: E501
                f"{history_html}"
            )
            if data["series_name"]:
                series_link = f'<a href="series_name:{data["series_name"]}">{data["series_name"]}</a>'
                series_html = f"Part {data['series_part']} of the series {series_link}<br>"
            self.detail_info.setText(
                f"{series_html}"
                f"<b>Fandom:</b> {self.format_link(data['fandoms'], 'fandoms')}<br>"
                f"<b>Published:</b> {data['date_published']} | <b>Updated:</b> {data['date_updated']}<br>"
                f"<b>Rating:</b> {data['rating']} | <b>Language:</b> {data['language']}<br>"
                f"<b>Words:</b> {word_count:,} | <b>Chapters:</b> {data['chapters']}<br>"
                f"<b>Stats:</b> Kudos: {kudos:,} | Bookmarks: {bookmarks:,} | Comments: {comments:,} | Hits: {hits:,}"
            )
            self.detail_category.setText(f"<b>Category:</b> {self.format_link(data['category'], 'category')}")
            self.detail_relationships.setText(
                f"<b>Relationships:</b> {self.format_link(data['relationships'], 'relationships')}"
            )
            self.detail_characters.setText(f"<b>Characters:</b> {self.format_link(data['characters'], 'characters')}")
            self.detail_tags.setText(f"<b>Tags:</b> {self.format_link(data['tags'], 'tags')}")

            user_tags_html = self.format_link(data.get("user_tags"), const.SEARCH_USER_TAGS)
            self.detail_user_tags.setText(user_tags_html if user_tags_html else "<i>No tags assigned.</i>")

            self.detail_summary.setText(data["summary"])
            self.detail_notes.setText(data["user_notes"])
            is_in_library = data.get("is_in_library", False)
            self.add_to_library_button.setVisible(not is_in_library)

            rating = data["user_rating"] or 0
            for i, btn in enumerate(self.rating_buttons):
                if i < rating:
                    btn.setText("★")
                    btn.setStyleSheet("font-size: 18px; border: none; color: #FFC107;")
                else:
                    btn.setText("☆")
                    btn.setStyleSheet("font-size: 18px; border: none;")

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

            self._update_current_selection_details()

            self._update_tag_completer()
            self._update_search_completer()

    def _save_notes(self) -> None:
        if not self.selected_url:
            return
        current_notes_in_memory = self.fics_in_memory[self.selected_url]["user_notes"]
        new_notes = self.detail_notes.toPlainText()
        if new_notes != current_notes_in_memory:
            update_fic_notes(self.selected_url, new_notes)
            self._update_current_selection_details()
            status_bar = self.statusBar()
            if status_bar:
                status_bar.showMessage("Notes saved.", 2000)

    def _save_rating(self, rating: int) -> None:
        if not self.selected_url:
            return

        old_fic_data = dict(self.fics_in_memory[self.selected_url])

        current_rating = old_fic_data.get("user_rating") or 0
        new_rating = rating if rating != current_rating else 0
        update_fic_rating(self.selected_url, new_rating)

        new_fic_data = get_fic_by_url(self.selected_url)
        if new_fic_data:
            self.analysis_engine.update_fic(old_fic_data, new_fic_data)

        self._update_current_selection_details()

        fresh_fic_data = get_fic_by_url(self.selected_url)
        if fresh_fic_data:
            if check_for_achievements(
                calculate_base_stats(),
                get_data_for_charts("lette"),
                count_verified_statuses(),
                newly_modified_fic=dict(fresh_fic_data),  # noqa: E501
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

    def _start_auto_sync_for_fic(self, fic_data: Dict[str, Any]):
        """
        NOVITÀ: Avvia automaticamente una sincronizzazione dello stato in background
        per una nuova opera, se l'utente è loggato.
        """
        username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME)
        if not username or username == const.CONFIG_DEFAULT_USER:
            logger.info("Utente non loggato, auto-sync saltato.")
            return

        logger.info(f"Avvio auto-sync per la nuova opera: {fic_data['title']}")
        work_id = int(fic_data["url"].split("/")[-1])

        if not hasattr(self, "active_sync_threads_and_workers"):
            self.active_sync_threads_and_workers = []

        thread = QThread()
        worker = SyncStatusWorker(work_id, fic_data["url"], username)
        worker.moveToThread(thread)

        worker.finished.connect(self._on_status_sync_finished)
        worker.error.connect(thread.quit)

        def on_sync_done():
            for t, w in self.active_sync_threads_and_workers:
                if t is thread:
                    self.active_sync_threads_and_workers.remove((t, w))
                    break
            thread.quit()

        worker.finished.connect(on_sync_done)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self.active_sync_threads_and_workers.append((thread, worker))

        thread.started.connect(worker.run)
        thread.start()

    @pyqtSlot(dict)
    def _update_single_fic_row(self, fic_data: Dict[str, Any]) -> None:

        url = fic_data["url"]
        logger.debug(f"Aggiornamento in tempo reale per la riga con URL: {url}")

        row = self._find_row_by_url(url)
        if row is not None:

            self.fics_in_memory[url] = fic_data
            self._populate_table_row(row, fic_data)

    def _on_auto_sync_finished(self, url: str):
        """
        When an auto-sync finishes, get the final fic state and update the engine one last time.
        """
        final_fic_data = get_fic_by_url(url)

        old_fic_data = self.fics_in_memory.get(url)
        if final_fic_data and old_fic_data:
            self.analysis_engine.update_fic(dict(old_fic_data), final_fic_data)

    def _change_fic_status(self, new_status: str, verified: int = 0) -> None:
        if not self.selected_url:
            return

        old_fic_data = dict(self.fics_in_memory[self.selected_url])

        update_fic_status(self.selected_url, new_status, verified)

        new_fic_data = get_fic_by_url(self.selected_url)
        if new_fic_data:
            self.analysis_engine.update_fic(old_fic_data, new_fic_data)

        fresh_fic_data = get_fic_by_url(self.selected_url)
        if fresh_fic_data:
            self.analysis_engine.update_fic(old_fic_data, fresh_fic_data)

            self.fics_in_memory[self.selected_url] = fresh_fic_data
            row_to_update = self._find_row_by_url(self.selected_url)
            if row_to_update is not None:
                self._populate_table_row(row_to_update, fresh_fic_data)

            if check_for_achievements(
                calculate_base_stats(),
                get_data_for_charts("lette"),
                count_verified_statuses(),
                newly_modified_fic=old_fic_data,  # noqa: E501
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
        Gestore unificato per il pulsante 'Import'. Analizza l'URL,
        gestisce la concorrenza e avvia l'azione appropriata.
        """
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.critical(self, "Error", "Please enter a URL.")
            return

        if self.add_fic_thread and self.add_fic_thread.isRunning():
            QMessageBox.warning(self, "In Progress", "A fic is already being added. Please wait.")
            return

        url_type, identifier = parse_ao3_url(url)
        is_long_request = url_type in ["author", "collection", "series"]

        if self._is_long_worker_running():

            if is_long_request:
                QMessageBox.warning(
                    self,
                    "Import in Progress",
                    "Another import process is already running in the background.\n"
                    "Please wait for it to finish before starting a new one.",
                )
                return

            elif url_type == "work":
                self._pause_all_long_workers()
                self._start_single_fic_add(url)
                return

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
        if data is None:
            logger.debug("AddFicWorker finished without data, likely handled by private_fic_detected.")
            self._resume_all_long_workers()
            return

        status_bar = self.statusBar()

        if add_fic(data):
            logger.info(f"Successfully added '{data['title']}' to the database via worker.")
            QMessageBox.information(self, "Success", f"'{data['title']}' has been added!")
            self.url_input.clear()
            self.search_input.clear()
            self.status_filter_combo.setCurrentIndex(0)

            new_fic_data = get_fic_by_url(data["url"])
            if new_fic_data:
                self.analysis_engine.add_fic(new_fic_data)
                self._start_auto_sync_for_fic(new_fic_data)

            self._update_fics_table()
            self._update_search_completer()
        else:
            logger.warning(f"Worker tried to add a fic that is already in the database: {data['url']}")
            QMessageBox.warning(self, "Attention", "This fic is already in your archive.")

        if status_bar:
            status_bar.clearMessage()
        self._resume_all_long_workers()

        if self.history_import_thread and self.history_import_thread.isRunning():
            if self.history_import_worker:
                self.history_import_worker.resume()

    @pyqtSlot(dict)
    def _on_new_fic_from_worker(self, fic_data: Dict[str, Any]) -> None:
        """
        Gestore unificato per ogni nuova opera aggiunta da un worker di importazione di massa.
        Aggiorna la UI, il motore di analisi e avvia l'auto-sync.
        """
        self._update_fics_table()

        self.analysis_engine.add_fic(fic_data)
        self._start_auto_sync_for_fic(fic_data)

    def _on_add_fic_error(self, error_message: str):
        logger.error(f"An error occurred in the AddFicWorker: {error_message}")
        QMessageBox.critical(self, "Error", f"An unexpected error occurred: {error_message}")
        status_bar = self.statusBar()
        if status_bar:
            status_bar.clearMessage()
        self._resume_all_long_workers()

        if self.history_import_thread and self.history_import_thread.isRunning():
            if self.history_import_worker:
                self.history_import_worker.resume()

    def _on_delete_fics_clicked(self, urls_to_delete: List[str]) -> None:
        if not urls_to_delete:
            return

        fic_count = len(urls_to_delete)

        if fic_count == 1:
            fic_title = "this fic"
            fic_data = self.fics_in_memory.get(urls_to_delete[0])
            if fic_data:
                fic_title = fic_data["title"]
            question = f"Permanently delete '{fic_title}'?"
        else:
            question = f"Permanently delete {fic_count} selected fics?"

        response = QMessageBox.question(
            self,
            "Confirm Deletion",
            question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response == QMessageBox.StandardButton.Yes:
            logger.info(f"User confirmed deletion of {fic_count} fic(s).")
            for url in urls_to_delete:
                fic_to_delete_data = self.fics_in_memory.get(url)
                if fic_to_delete_data:
                    self.analysis_engine.remove_fic(dict(fic_to_delete_data))
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

        if status_bar:
            status_bar.showMessage(f"Starting import from series '{series_id}'...")

        self.series_import_thread = QThread()
        self.series_import_worker = ImportSeriesWorker(series_id)
        self.series_import_worker.moveToThread(self.series_import_thread)
        self.series_import_thread.started.connect(self.series_import_worker.run)
        self.series_import_worker.progress.connect(self._update_progress_bar)
        self.series_import_worker.new_fic_added.connect(self._on_new_fic_from_worker)
        self.series_import_worker.error.connect(self._on_import_error)
        self.series_import_worker.finished.connect(self._on_mass_import_finished)
        self.series_import_worker.finished.connect(self.series_import_thread.quit)
        self.series_import_worker.finished.connect(self.series_import_worker.deleteLater)
        self.series_import_thread.finished.connect(self.series_import_thread.deleteLater)
        self.series_import_thread.finished.connect(lambda: setattr(self, "series_import_thread", None))
        self.series_import_thread.start()

    def _apply_theme(self, palette: Optional[Dict[str, str]]) -> None:

        base_stylesheet = self.styleSheet()

        if "/* THEME_SPECIFIC_STYLES_START */" in base_stylesheet:
            base_stylesheet = base_stylesheet.split("/* THEME_SPECIFIC_STYLES_START */")[0]

        if palette is None:

            self.setStyleSheet(base_stylesheet)
            self.status_text_colors.update(
                {
                    const.STATUS_TO_READ: QColor(const.CLR_STATUS_NEUTRAL_DEFAULT),
                    const.STATUS_DROPPED: QColor(const.CLR_STATUS_DROPPED_DEFAULT),
                    const.STATUS_READ: QColor(const.CLR_STATUS_READ_DEFAULT),
                    const.STATUS_KUDOSED: QColor(const.CLR_STATUS_KUDOSED_DEFAULT),
                    const.STATUS_COMMENTED: QColor(const.CLR_STATUS_COMMENTED_DEFAULT),
                }
            )
        else:

            theme_stylesheet = f"""
                /* THEME_SPECIFIC_STYLES_START */
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
            self.setStyleSheet(base_stylesheet + theme_stylesheet)
            self.status_text_colors.update(
                {
                    const.STATUS_TO_READ: QColor(palette["text_accent"]),
                    const.STATUS_DROPPED: QColor(palette["text_accent"]),
                    const.STATUS_READ: QColor(const.CLR_STATUS_READ_THEMED),
                    const.STATUS_KUDOSED: QColor(const.CLR_STATUS_KUDOSED_THEMED),
                    const.STATUS_COMMENTED: QColor(const.CLR_STATUS_COMMENTED_THEMED),
                }
            )

        if hasattr(self, "fics_table"):
            self._update_fics_table(get_filtered_fics(view_filter=self.current_view_filter))

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
        Apre un menu contestuale che permette di rimuovere qualsiasi tag
        attualmente assegnato alla fic selezionata.
        """
        if not self.selected_url:
            return

        all_fic_tags = get_tags_for_fic(self.selected_url)
        if not all_fic_tags:
            return

        menu = QMenu()
        for tag_id, tag_name in all_fic_tags:
            action = QAction(f"Remove Tag '{tag_name}'", self)
            action.triggered.connect(lambda checked=False, t_id=tag_id: self._remove_tag_by_id(t_id))
            menu.addAction(action)

        menu.exec(self.detail_user_tags.mapToGlobal(position))

    def _remove_tag_by_id(self, tag_id: int) -> None:
        if self.selected_url:
            remove_tag_from_fic(self.selected_url, tag_id)

            self._update_current_selection_details()

    def _update_current_selection_details(self) -> None:
        """
        Helper method to fully refresh the data and UI for the currently selected fic.
        This is the single source of truth for updating the details panel and table row.
        """
        if not self.selected_url:
            self._hide_details_panel()
            return

        fresh_fic_data = get_fic_by_url(self.selected_url)
        if not fresh_fic_data:

            self._hide_details_panel()
            self._update_fics_table(get_filtered_fics())
            return

        self.fics_in_memory[self.selected_url] = fresh_fic_data

        row_to_update = self._find_row_by_url(self.selected_url)
        if row_to_update is not None:
            self._populate_table_row(row_to_update, fresh_fic_data)

        self._on_fic_selection_changed()

    def _open_tag_management_window(self) -> None:
        """Apre la finestra di dialogo per la gestione globale dei tag."""
        dialog = TagManagementWindow(self)
        dialog.exec()

        self._update_fics_table()
        self._update_tag_completer()
        self._update_search_completer()

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

        import security_manager

        username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME)

        security_manager.delete_password(username)

        config_manager.set(
            const.CONFIG_SECTION_CREDS,
            const.CONFIG_KEY_USERNAME,
            const.CONFIG_DEFAULT_USER,
        )
        config_manager.save_config()

        ao3_client.reload_session()

        QMessageBox.information(self, "Logged Out", "You have been successfully logged out.")

        self._update_ui_for_logout()
        self._update_welcome_message()

    def _open_dashboard_window(self) -> None:

        dialog = DashboardWindow(self.analysis_engine, self)

        dialog.populate_data_and_show()

    def _update_ui_for_logout(self) -> None:
        """Updates UI elements to reflect the logged-out state."""
        if self.selected_url:
            self._on_fic_selection_changed()

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

        if status_bar:
            status_bar.showMessage(f"Starting import from collection '{collection_name}'...")

        self.collection_import_thread = QThread()
        self.collection_import_worker = ImportCollectionWorker(collection_name)
        self.collection_import_worker.moveToThread(self.collection_import_thread)
        self.collection_import_thread.started.connect(self.collection_import_worker.run)
        self.collection_import_worker.progress.connect(self._update_progress_bar)
        self.collection_import_worker.new_fic_added.connect(self._on_new_fic_from_worker)  # noqa: E501
        self.collection_import_worker.error.connect(self._on_import_error)
        self.collection_import_worker.finished.connect(self._on_mass_import_finished)
        self.collection_import_worker.finished.connect(self.collection_import_thread.quit)
        self.collection_import_worker.finished.connect(self.collection_import_worker.deleteLater)
        self.collection_import_thread.finished.connect(self.collection_import_thread.deleteLater)
        self.collection_import_thread.finished.connect(lambda: setattr(self, "collection_import_thread", None))
        self.collection_import_thread.start()

    @pyqtSlot(dict, bool)
    def _apply_advanced_filter(self, filters: Dict[str, Any], should_save: bool) -> None:
        """
        Applica un filtro complesso ricevuto dal FilterBuilder, opzionalmente
        lo salva e aggiorna la UI di ricerca principale.
        """
        if should_save:
            filter_name, ok = QInputDialog.getText(self, "Save Filter", "Enter a name for this filter:")
            if ok and filter_name:
                try:
                    save_filter(filter_name, json.dumps(filters))
                    self._load_saved_filters()
                except Exception:
                    QMessageBox.warning(self, "Error", f"A filter named '{filter_name}' already exists.")
                    return
            elif not ok:
                return

        self._on_clear_search_clicked()

        fics_found = get_filtered_fics(view_filter=self.current_view_filter, filters=filters)
        self._update_fics_table(fics_found)

        self.search_input.blockSignals(True)
        self.search_input.setText("[Advanced Filter Active]")
        self.search_input.blockSignals(False)

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

    def _start_single_fic_add(self, url: str, use_auth: bool = False) -> None:
        """Avvia il worker per aggiungere una singola fic."""
        if self.add_fic_thread and self.add_fic_thread.isRunning():
            QMessageBox.warning(self, "In Progress", "A fic is already being added. Please wait.")
            return

        if self.history_import_thread and self.history_import_thread.isRunning():
            if self.history_import_worker:
                self.history_import_worker.pause()

        logger.info(f"Starting worker to add fic from URL: {url} (Authenticated Fallback: {use_auth})")

        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("Retrieving data from AO3...")

        self.add_fic_thread = QThread()

        self.worker = AddFicWorker(url, use_auth_fallback=use_auth)
        self.worker.moveToThread(self.add_fic_thread)
        self.add_fic_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_add_fic_finished)
        self.worker.error.connect(self._on_add_fic_error)

        self.worker.private_fic_detected.connect(self._handle_private_fic)

        self.worker.finished.connect(self.add_fic_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.add_fic_thread.finished.connect(lambda: setattr(self, "add_fic_thread", None))
        self.add_fic_thread.start()

    @pyqtSlot(str)
    def _handle_private_fic(self, url: str) -> None:
        """
        Slot che gestisce il caso in cui un'opera sia privata.
        Chiede all'utente il permesso di riprovare con l'account loggato.
        Il worker precedente si è già auto-terminato.
        """
        self.statusBar().clearMessage()

        reply = QMessageBox.question(
            self,
            "Private Work Detected",
            "This work could not be accessed as a guest. It might be private or require an AO3 account to view.\n\n"
            "Do you want to try again using your logged-in account?\n\n"
            "<b>Note:</b> This will register as a 'visit' in your AO3 History.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            logger.info(f"User approved authenticated fetch for {url}. Restarting worker.")

            self._start_single_fic_add(url, use_auth=True)
        else:
            logger.info(f"User declined authenticated fetch for {url}.")
            self._resume_all_long_workers()

    def _on_total_sync_finished(self) -> None:
        logger.info("Total sync process has concluded.")
        self.total_sync_thread = None

    def _is_long_worker_running(self) -> bool:
        """Controlla se uno qualsiasi dei worker a lunga esecuzione è attivo."""
        threads = [
            self.import_thread,
            self.bookmarks_import_thread,
            self.history_import_thread,
            self.collection_import_thread,
            self.series_import_thread,
            self.total_sync_thread,
        ]
        return any(thread and thread.isRunning() for thread in threads)

    def _pause_all_long_workers(self) -> None:
        """Mette in pausa tutti i worker a lunga esecuzione attualmente attivi."""
        logger.info("Requesting pause for all active long-running workers.")
        workers_map = {
            self.import_thread: self.import_worker,
            self.bookmarks_import_thread: self.bookmarks_import_worker,
            self.history_import_thread: self.history_import_worker,
            self.collection_import_thread: self.collection_import_worker,
            self.series_import_thread: self.series_import_worker,
        }
        for thread, worker in workers_map.items():
            if thread and thread.isRunning() and worker and hasattr(worker, "pause"):
                worker.pause()  # type: ignore

    def _resume_all_long_workers(self) -> None:
        """Riprende l'esecuzione di tutti i worker a lunga esecuzione."""
        logger.info("Requesting resume for all active long-running workers.")
        workers_map = {
            self.import_thread: self.import_worker,
            self.bookmarks_import_thread: self.bookmarks_import_worker,
            self.history_import_thread: self.history_import_worker,
            self.collection_import_thread: self.collection_import_worker,
            self.series_import_thread: self.series_import_worker,
        }
        for thread, worker in workers_map.items():
            if thread and thread.isRunning() and worker and hasattr(worker, "resume"):
                worker.resume()  # type: ignore

    def _add_selected_to_queue(self) -> None:
        """Adds all currently selected fics to the reading queue."""
        urls = self._get_selected_urls_from_table()
        if not urls:
            return

        add_fics_to_queue(urls)
        self._refresh_rows_by_url(urls)

    def _remove_selected_from_queue(self) -> None:
        """Removes all currently selected fics from the reading queue."""
        urls = self._get_selected_urls_from_table()
        if not urls:
            return

        remove_fics_from_queue(urls)
        self._refresh_rows_by_url(urls)

    def _refresh_rows_by_url(self, urls: List[str]) -> None:
        """
        Refreshes the data and visuals for specific rows in the table without
        doing a full reload, preserving user selection and scroll position.
        """
        for url in urls:

            fresh_fic_data = get_fic_by_url(url)
            if not fresh_fic_data:
                continue

            self.fics_in_memory[url] = fresh_fic_data

            row_index = self._find_row_by_url(url)
            if row_index is not None:
                self._populate_table_row(row_index, fresh_fic_data)

    def _open_reading_queue_dialog(self) -> None:
        """Opens the dedicated dialog for managing the reading queue."""
        dialog = ReadingQueueDialog(self)
        dialog.fic_selected.connect(self._select_fic_from_url)
        dialog.queue_changed.connect(self._refresh_rows_by_url)
        dialog.exec()

    def _load_saved_filters(self) -> None:
        """Carica i filtri salvati dal DB e popola il ComboBox."""
        self.saved_filters_combo.blockSignals(True)
        self.saved_filters_combo.clear()
        self.saved_filters_combo.addItem("Saved Filters...")

        filters = get_all_filters()
        for f in filters:

            self.saved_filters_combo.addItem(f["name"], userData=f)

        self.saved_filters_combo.blockSignals(False)

    def _on_save_filter_clicked(self) -> None:
        """Salva lo stato corrente dei filtri come un nuovo filtro."""

        filters: Dict[str, Any] = {"conditions": {}, "tags": {}, "user_tags": {}}

        search_text = self.search_input.text().strip()
        field_idx = self.search_combo.currentIndex()
        status_idx = self.status_filter_combo.currentIndex()
        if status_idx > 0:
            filters["conditions"]["status"] = self.status_filter_combo.currentText()
        field_map = {
            0: "all",
            1: "title",
            2: "author",
            3: "fandoms",
            4: "rating",
            5: "tags",
            6: "category",
            7: "relationships",
            8: "characters",
            9: "user_tags",
            10: "series_name",
        }
        field_key = field_map.get(field_idx, "all")
        if search_text:
            if field_key == "tags":
                filters["tags"]["and"] = [t.strip() for t in search_text.split(",")]
            elif field_key == "user_tags":
                filters["user_tags"]["and"] = [t.strip() for t in search_text.split(",")]
            else:
                filters["conditions"][field_key] = search_text

        filter_name, ok = QInputDialog.getText(self, "Save Filter", "Enter a name for this filter:")
        if ok and filter_name:
            try:

                save_filter(filter_name, json.dumps(filters))
                QMessageBox.information(self, "Success", f"Filter '{filter_name}' saved.")
                self._load_saved_filters()
            except Exception:
                QMessageBox.warning(self, "Error", f"A filter named '{filter_name}' already exists.")

    def _on_saved_filter_selected(self, index: int) -> None:
        """
        Applica un filtro salvato selezionato dal ComboBox, aggiornando
        visibilmente tutti i controlli della UI per riflettere il filtro attivo.
        """
        if index == 0:
            return

        filter_data = self.saved_filters_combo.itemData(index)
        if not filter_data or "filter_data" not in filter_data:
            return

        try:
            filters = json.loads(filter_data["filter_data"])
        except json.JSONDecodeError:
            logger.error(f"Failed to parse saved filter data: {filter_data['filter_data']}")
            return

        self.search_input.blockSignals(True)
        self.search_combo.blockSignals(True)
        self.status_filter_combo.blockSignals(True)

        self.search_input.clear()
        self.search_combo.setCurrentIndex(0)
        self.status_filter_combo.setCurrentIndex(0)

        conditions = filters.get("conditions", {})
        tags_filter = filters.get("tags", {})
        user_tags_filter = filters.get("user_tags", {})

        if "status" in conditions:

            status_index = self.status_filter_combo.findText(conditions["status"])
            if status_index != -1:
                self.status_filter_combo.setCurrentIndex(status_index)
            conditions.pop("status")

        field_map_inv = {
            "all": 0,
            "title": 1,
            "author": 2,
            "fandoms": 3,
            "rating": 4,
            "category": 6,
            "relationships": 7,
            "characters": 8,
            "series_name": 10,
        }

        found_main_search = False
        for field, value in conditions.items():
            if field in field_map_inv:
                self.search_combo.setCurrentIndex(field_map_inv[field])
                self.search_input.setText(value)
                found_main_search = True
                break

        if not found_main_search:
            if tags_filter.get("and"):
                self.search_combo.setCurrentIndex(5)
                self.search_input.setText(", ".join(tags_filter["and"]))
            elif user_tags_filter.get("and"):
                self.search_combo.setCurrentIndex(9)
                self.search_input.setText(", ".join(user_tags_filter["and"]))

        self.search_input.blockSignals(False)
        self.search_combo.blockSignals(False)
        self.status_filter_combo.blockSignals(False)

        self._on_search_triggered()

        self.saved_filters_combo.setCurrentIndex(0)

    def _open_author_recs_dialog(self):
        dialog = AuthorRecsDialog(self)
        dialog.reroll_requested.connect(lambda: self._start_author_recs_worker(dialog))
        dialog.import_fic_requested.connect(self._start_single_fic_add)
        dialog.add_to_queue_requested.connect(self._handle_add_to_queue_request)

        dialog.finished.connect(self._stop_author_recs_worker)

        self._start_author_recs_worker(dialog)
        dialog.exec()

    def _start_author_recs_worker(self, dialog: AuthorRecsDialog):
        if self.author_recs_thread and self.author_recs_thread.isRunning():
            return

        dialog.on_loading()

        self.author_recs_thread = QThread()
        self.author_recs_worker = AuthorRecsWorker(self.analysis_engine)
        self.author_recs_worker.moveToThread(self.author_recs_thread)

        self.author_recs_worker.finished.connect(dialog.on_results_ready)
        self.author_recs_worker.error.connect(dialog.on_error)

        self.author_recs_worker.finished.connect(self.author_recs_thread.quit)

        self.author_recs_thread.finished.connect(lambda: setattr(self, "author_recs_thread", None))

        self.author_recs_thread.started.connect(self.author_recs_worker.run)
        self.author_recs_thread.start()

    def _stop_author_recs_worker(self):
        if self.author_recs_worker:
            self.author_recs_worker.stop()

    def _open_filter_builder(self) -> None:
        """Apre il Costruttore di Filtri, passando i dati per i suggerimenti."""

        completer_data = self._prepare_completer_data()
        dialog = FilterBuilderDialog(completer_data, self)

        dialog.filter_generated.connect(self._apply_advanced_filter)
        dialog.exec()

    def _start_discovery_worker(self, search_params: Dict[str, Any]) -> None:
        """Avvia il worker per la scoperta di nuove opere su AO3."""
        if self.discovery_thread and self.discovery_thread.isRunning():
            QMessageBox.warning(self, "In Progress", "A discovery process is already running. Please wait.")
            return

        self.discovery_thread = QThread()
        self.discovery_worker = DiscoverFicsWorker(self.analysis_engine, search_params)
        self.discovery_worker.moveToThread(self.discovery_thread)

        self.discovery_worker.finished.connect(self._on_discovery_finished)
        self.discovery_worker.error.connect(self._on_discovery_error)

        self.discovery_worker.finished.connect(self.discovery_thread.quit)
        self.discovery_worker.finished.connect(self.discovery_worker.deleteLater)
        self.discovery_thread.finished.connect(self.discovery_thread.deleteLater)
        self.discovery_thread.finished.connect(lambda: setattr(self, "discovery_thread", None))

        self.discovery_thread.started.connect(self.discovery_worker.run)
        self.discovery_thread.start()

    @pyqtSlot(list)
    def _on_discovery_finished(self, results: List[Dict[str, Any]]) -> None:
        """Riceve i risultati dal worker e li passa alla finestra di dialogo."""

        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, RecommendationCenterDialog):
                widget.on_discovery_finished(results)
                break

    @pyqtSlot(str)
    def _on_discovery_error(self, message: str) -> None:
        """Riceve un errore dal worker e lo passa alla finestra di dialogo."""
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, RecommendationCenterDialog):
                widget.on_discovery_error(message)
                break


if __name__ == "__main__":
    logger.info("========================================")
    logger.info("Application starting...")

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
