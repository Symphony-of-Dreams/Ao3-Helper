from functools import partial
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QStringListModel, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QActionGroup, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QCompleter,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ao3_helper import constants as const
from ao3_helper.core.database import (
    add_fics_to_queue,
    calculate_base_stats,
    count_verified_statuses,
    get_all_user_tags,
    get_filtered_fics,
)
from ao3_helper.ui.dialogs.recommendation_center_dialog import RecommendationCenterDialog
from ao3_helper.workers.gamification import calculate_xp_level


class NoteWidget(QTextEdit):
    editingFinished = pyqtSignal()

    def focusOutEvent(self, event: Any) -> None:
        super().focusOutEvent(event)
        self.editingFinished.emit()


class UIManager:
    def __init__(self, main_window: QMainWindow):
        self.main_window = main_window

    def connect_signals(self) -> None:
        self.main_window.add_button.clicked.connect(self.main_window._on_import_clicked)
        self.main_window.dashboard_button.clicked.connect(self.main_window._open_dashboard_window)

        self.main_window.notifications_button.clicked.connect(self.main_window._open_notifications_window)
        self.main_window.refresh_button.clicked.connect(self.main_window.worker_manager.start_update_check)
        self.main_window.achievements_button.clicked.connect(self.main_window._open_achievements_window)
        self.main_window.fics_table.itemSelectionChanged.connect(self.main_window._on_fic_selection_changed)
        self.main_window.fics_table.customContextMenuRequested.connect(self.main_window._open_fics_table_context_menu)
        self.main_window.detail_close_button.clicked.connect(self.main_window._hide_details_panel)
        self.main_window.detail_notes.editingFinished.connect(self.main_window._save_notes)
        self.main_window.detail_author.linkActivated.connect(self.main_window.filter_manager.execute_search_from_link)
        self.main_window.detail_info.linkActivated.connect(self.main_window.filter_manager.execute_search_from_link)
        self.main_window.detail_category.linkActivated.connect(self.main_window.filter_manager.execute_search_from_link)
        self.main_window.detail_relationships.linkActivated.connect(
            self.main_window.filter_manager.execute_search_from_link
        )
        self.main_window.detail_characters.linkActivated.connect(
            self.main_window.filter_manager.execute_search_from_link
        )
        self.main_window.detail_tags.linkActivated.connect(self.main_window.filter_manager.execute_search_from_link)
        self.main_window.add_tag_button.clicked.connect(self.main_window._add_tag_to_fic)
        self.main_window.detail_user_tags.linkActivated.connect(
            self.main_window.filter_manager.execute_search_from_link
        )
        self.main_window.detail_user_tags.customContextMenuRequested.connect(
            self.main_window._open_user_tag_context_menu
        )
        self.main_window.to_read_button.clicked.connect(
            partial(self.main_window._change_fic_status, const.STATUS_TO_READ)
        )
        self.main_window.read_button.clicked.connect(partial(self.main_window._change_fic_status, const.STATUS_READ))
        self.main_window.dropped_button.clicked.connect(
            partial(self.main_window._change_fic_status, const.STATUS_DROPPED)
        )
        self.main_window.open_browser_button.clicked.connect(self.main_window._open_fic_in_browser)
        if self.main_window.manual_override_enabled:
            self.main_window.kudosed_button.clicked.connect(
                partial(self.main_window._change_fic_status, const.STATUS_KUDOSED, verified=0)
            )
            self.main_window.commented_button.clicked.connect(
                partial(self.main_window._change_fic_status, const.STATUS_COMMENTED, verified=0)
            )
        else:
            self.main_window.sync_status_button.clicked.connect(
                lambda: (
                    self.main_window.worker_manager.start_status_sync(self.main_window.selected_url)
                    if self.main_window.selected_url
                    else None
                )
            )
        for i, btn in enumerate(self.main_window.rating_buttons):

            btn.clicked.connect(lambda checked, num=i + 1: self.main_window._save_rating(num))
        self.main_window.delete_button.clicked.connect(
            lambda: self.main_window._on_delete_fics_clicked(
                [self.main_window.selected_url] if self.main_window.selected_url else []
            )
        )  # noqa: E501
        self.main_window.search_input.textChanged.connect(lambda: self.main_window.filter_manager.trigger_search())
        self.main_window.search_combo.currentIndexChanged.connect(
            lambda: self.main_window.filter_manager.trigger_search()
        )
        self.main_window.status_filter_combo.currentIndexChanged.connect(
            lambda: self.main_window.filter_manager.trigger_search()
        )
        self.main_window.view_filter_group.buttonClicked.connect(
            lambda: self.main_window.filter_manager.on_view_filter_changed()
        )
        self.main_window.save_filter_button.clicked.connect(
            lambda: self.main_window.filter_manager.save_current_filter()
        )
        self.main_window.saved_filters_combo.activated.connect(self.main_window.filter_manager.apply_saved_filter)
        self.main_window.advanced_search_button.clicked.connect(
            lambda: self.main_window.filter_manager.open_filter_builder()
        )
        self.main_window.clear_search_button.clicked.connect(lambda: self.main_window.filter_manager.clear_search())
        self.main_window.add_to_library_button.clicked.connect(self.main_window._add_to_library)

        # Worker Manager Signals
        self.main_window.worker_manager.analysis_ready.connect(self.main_window._on_analysis_ready)
        self.main_window.worker_manager.update_check_finished.connect(self.main_window._on_update_check_finished)
        self.main_window.worker_manager.mass_import_finished.connect(self.main_window._on_mass_import_finished)
        self.main_window.worker_manager.bookmarks_import_finished.connect(
            self.main_window._on_bookmarks_import_finished
        )
        self.main_window.worker_manager.history_import_finished.connect(self.main_window._on_history_import_finished)
        self.main_window.worker_manager.status_sync_finished.connect(self.main_window._on_status_sync_finished)
        self.main_window.worker_manager.status_sync_error.connect(self.main_window._on_status_sync_error)
        self.main_window.worker_manager.progress_updated.connect(self.main_window._update_progress_bar)
        self.main_window.worker_manager.new_notification.connect(self.main_window._new_notification_from_worker)
        self.main_window.worker_manager.new_fic_from_worker.connect(self.main_window._on_new_fic_from_worker)
        self.main_window.worker_manager.add_fic_finished.connect(self.main_window._on_add_fic_finished)
        self.main_window.worker_manager.add_fic_error.connect(self.main_window._on_add_fic_error)
        self.main_window.worker_manager.private_fic_detected.connect(self.main_window._handle_private_fic)
        self.main_window.worker_manager.total_sync_finished.connect(self.main_window._on_total_sync_finished)
        self.main_window.worker_manager.discovery_finished.connect(self.main_window._on_discovery_finished)
        self.main_window.worker_manager.discovery_error.connect(self.main_window._on_discovery_error)
        self.main_window.worker_manager.single_fic_row_updated.connect(self.main_window._update_single_fic_row)

    def create_main_widgets(self) -> None:
        self.main_window.column_map = const.COLUMN_MAP
        self.main_window.fics_table = QTableWidget()
        self.main_window.fics_table.setColumnCount(len(self.main_window.column_map))
        self.main_window.fics_table.setHorizontalHeaderLabels(self.main_window.column_map)
        self.main_window.version_label = QLabel(f"|| Version {const.APP_VERSION}")
        self.main_window.fic_count_label = QLabel("Total Fics: -")
        self.main_window.word_count_label = QLabel("Words Read: -")
        status_bar = self.main_window.statusBar()
        if status_bar:
            status_bar.addPermanentWidget(self.main_window.word_count_label)
            status_bar.addPermanentWidget(self.main_window.fic_count_label)
            status_bar.addPermanentWidget(self.main_window.version_label)

    def create_menu(self) -> None:
        menu_bar = self.main_window.menuBar()
        file_menu = menu_bar.addMenu("&File")

        settings_action = QAction("Settings / Login...", self.main_window)
        settings_action.triggered.connect(self.main_window._open_login_dialog)
        file_menu.addAction(settings_action)
        self.main_window.logout_action = QAction("Logout", self.main_window)
        self.main_window.logout_action.triggered.connect(self.main_window._perform_logout)
        file_menu.addAction(self.main_window.logout_action)
        file_menu.addSeparator()

        file_menu.addSeparator()
        backup_action = QAction("Backup Database...", self.main_window)
        backup_action.triggered.connect(self.main_window._backup_database)
        file_menu.addAction(backup_action)
        restore_action = QAction("Restore Database...", self.main_window)
        restore_action.triggered.connect(self.main_window._restore_database)
        file_menu.addAction(restore_action)
        file_menu.addSeparator()
        delete_db_action = QAction("Delete Current User's Data...", self.main_window)
        delete_db_action.triggered.connect(self.main_window._delete_current_user_database)
        file_menu.addAction(delete_db_action)
        file_menu.addSeparator()
        manage_tags_action = QAction("Manage Tags...", self.main_window)
        manage_tags_action.triggered.connect(self.main_window._open_tag_management_window)
        file_menu.addAction(manage_tags_action)

        view_menu = menu_bar.addMenu("&View")
        theme_menu = view_menu.addMenu("Theme")
        self.main_window.theme_action_group = QActionGroup(self.main_window)
        self.main_window.theme_action_group.setExclusive(True)

        self.main_window.default_theme_action = QAction("Default (System)", self.main_window)
        self.main_window.default_theme_action.setCheckable(True)
        self.main_window.default_theme_action.triggered.connect(
            lambda: self.main_window._change_theme(const.THEME_DEFAULT)
        )
        theme_menu.addAction(self.main_window.default_theme_action)
        self.main_window.theme_action_group.addAction(self.main_window.default_theme_action)

        self.main_window.light_theme_action = QAction("Light (Custom)", self.main_window)
        self.main_window.light_theme_action.setCheckable(True)
        self.main_window.light_theme_action.triggered.connect(lambda: self.main_window._change_theme(const.THEME_LIGHT))
        theme_menu.addAction(self.main_window.light_theme_action)
        self.main_window.theme_action_group.addAction(self.main_window.light_theme_action)

        self.main_window.dark_theme_action = QAction("Dark (Custom)", self.main_window)
        self.main_window.dark_theme_action.setCheckable(True)
        self.main_window.dark_theme_action.triggered.connect(lambda: self.main_window._change_theme(const.THEME_DARK))
        theme_menu.addAction(self.main_window.dark_theme_action)
        self.main_window.theme_action_group.addAction(self.main_window.dark_theme_action)
        view_menu.addSeparator()
        tools_menu = menu_bar.addMenu("&Tools")
        reading_queue_action = QAction("🔖 Reading Queue...", self.main_window)
        reading_queue_action.triggered.connect(self.main_window._open_reading_queue_dialog)
        tools_menu.addAction(reading_queue_action)
        tools_menu.addSeparator()
        sync_action = QAction("Full Status Sync...", self.main_window)
        sync_action.triggered.connect(self.main_window.worker_manager.start_total_sync)
        tools_menu.addAction(sync_action)
        tools_menu.addSeparator()
        import_bookmarks_action = QAction("Import from AO3 Bookmarks...", self.main_window)
        import_bookmarks_action.triggered.connect(self.main_window.worker_manager.start_bookmarks_import)
        tools_menu.addAction(import_bookmarks_action)
        import_history_action = QAction("Import from AO3 History...", self.main_window)
        import_history_action.triggered.connect(self.main_window.worker_manager.start_history_import)
        tools_menu.addAction(import_history_action)

        for idx, name in enumerate(self.main_window.column_map):
            if name in [const.COLUMN_TITLE, const.COLUMN_STATUS]:
                continue
            action = QAction(name, self.main_window)
            action.setCheckable(True)
            action.setChecked(not self.main_window.fics_table.isColumnHidden(idx))
            action.triggered.connect(lambda checked, i=idx: self.main_window.fics_table.setColumnHidden(i, not checked))
            view_menu.addAction(action)

    def create_main_layout(self) -> None:
        container = QWidget()
        main_layout = QHBoxLayout(container)
        self.main_window.setCentralWidget(container)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        top_layout = self.create_top_layout()
        search_layout = self.create_search_layout()
        view_filter_layout = self.create_view_filter_layout()
        self.main_window.recommendation_panel = self.create_recommendation_panel()
        self.main_window.recommendation_panel.setVisible(False)

        welcome_layout = QHBoxLayout()
        self.main_window.welcome_label = QLabel()
        self.main_window.welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_window.welcome_label.setStyleSheet("font-size: 14px; margin: 5px;")
        welcome_layout.addWidget(self.main_window.welcome_label)
        gamification_layout = self.create_gamification_layout()
        left_layout.addLayout(top_layout)
        left_layout.addLayout(search_layout)
        left_layout.addLayout(view_filter_layout)
        left_layout.addWidget(self.main_window.recommendation_panel)
        left_layout.addLayout(welcome_layout)

        left_layout.addLayout(gamification_layout)
        left_layout.addWidget(self.main_window.fics_table)
        right_widget = self.create_details_panel()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([700, 500])
        main_layout.addWidget(splitter)

    def create_top_layout(self) -> QHBoxLayout:
        top_layout = QHBoxLayout()
        self.main_window.url_input = QLineEdit()
        self.main_window.url_input.setPlaceholderText("Paste fic, author, or collection URL here...")
        self.main_window.add_button = QPushButton("📥 Import")
        self.main_window.dashboard_button = QPushButton("🚀 Dashboard")
        self.main_window.dashboard_button.setEnabled(False)
        self.main_window.dashboard_button.setToolTip("Please wait while the initial analysis is performed...")

        self.main_window.notifications_button = QPushButton("🔔")
        self.main_window.refresh_button = QPushButton("🔄 Refresh")

        top_layout.addWidget(QLabel("URL:"))
        top_layout.addWidget(self.main_window.url_input, 1)
        top_layout.addWidget(self.main_window.add_button)
        top_layout.addWidget(self.main_window.dashboard_button)

        top_layout.addWidget(self.main_window.notifications_button)
        top_layout.addWidget(self.main_window.refresh_button)

        return top_layout

    def create_search_layout(self) -> QHBoxLayout:
        search_layout = QHBoxLayout()
        self.main_window.saved_filters_combo = QComboBox()
        self.main_window.saved_filters_combo.addItem("Saved Filters...")

        self.main_window.save_filter_button = QPushButton("💾 Save")
        self.main_window.save_filter_button.setToolTip("Save the current search criteria as a new filter")

        self.main_window.advanced_search_button = QPushButton("Advanced...")
        self.main_window.advanced_search_button.setToolTip("Open the Filter Builder for complex searches")

        search_layout.addWidget(self.main_window.saved_filters_combo)
        search_layout.addWidget(self.main_window.save_filter_button)
        search_layout.addWidget(self.main_window.advanced_search_button)
        search_layout.addStretch()
        self.main_window.search_combo = QComboBox()
        self.main_window.search_combo.addItems(
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
        )
        self.main_window.search_input = QLineEdit()
        self.main_window.search_input.setPlaceholderText("Search your fics...")
        self.main_window.completer_model = QStringListModel(self.main_window)
        self.main_window.completer = QCompleter(self.main_window.completer_model, self.main_window)
        self.main_window.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.main_window.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.main_window.search_input.setCompleter(self.main_window.completer)
        search_layout.addWidget(self.main_window.search_combo)
        search_layout.addWidget(self.main_window.search_input, 1)
        self.main_window.status_filter_combo = QComboBox()
        self.main_window.status_filter_combo.addItems(
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
        search_layout.addWidget(self.main_window.status_filter_combo)
        self.main_window.clear_search_button = QPushButton("Clear")
        self.main_window.clear_search_button.setToolTip("Reset all search filters")
        search_layout.addWidget(self.main_window.clear_search_button)

        return search_layout

    def create_gamification_layout(self) -> QHBoxLayout:
        gamification_layout = QHBoxLayout()
        self.main_window.level_label = QLabel("LVL: 1")
        self.main_window.xp_bar = QProgressBar()
        self.main_window.fic_stats_label = QLabel("Fics Read: 0")
        self.main_window.kudos_stats_label = QLabel("Kudos: 0")
        self.main_window.comment_stats_label = QLabel("Comments: 0")
        self.main_window.achievements_button = QPushButton("🏆 Achievements")
        gamification_layout.addWidget(self.main_window.level_label)
        gamification_layout.addWidget(self.main_window.xp_bar, 1)
        gamification_layout.addStretch()
        gamification_layout.addWidget(self.main_window.fic_stats_label)
        gamification_layout.addWidget(self.main_window.kudos_stats_label)
        gamification_layout.addWidget(self.main_window.comment_stats_label)
        gamification_layout.addWidget(self.main_window.achievements_button)
        return gamification_layout

    def create_recommendation_panel(self) -> QGroupBox:
        panel = QGroupBox("✨ For You: Next Recommendation")
        panel_layout = QHBoxLayout(panel)

        info_layout = QVBoxLayout()
        self.main_window.recommendation_title = QLabel("<b>Title will appear here</b>")
        self.main_window.recommendation_title.setStyleSheet("font-size: 14px;")
        self.main_window.recommendation_author = QLabel("by Author")
        self.main_window.recommendation_score = QLabel("<i>Match Score: -</i>")
        self.main_window.recommendation_score.setToolTip(
            "This score represents how well this fic matches your established tastes.\n" "Higher is a better match!"
        )

        info_layout.addWidget(self.main_window.recommendation_title)
        info_layout.addWidget(self.main_window.recommendation_author)
        info_layout.addWidget(self.main_window.recommendation_score)

        panel_layout.addLayout(info_layout, 1)

        actions_layout = QHBoxLayout()
        actions_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        select_button = QPushButton("➡️ Select Fic")
        select_button.clicked.connect(self.main_window._on_recommendation_select)

        shuffle_button = QPushButton("🔀 Suggest Another")
        shuffle_button.clicked.connect(self.main_window._on_recommendation_shuffle)

        details_button = QPushButton("📊 View All Suggestions...")
        details_button.clicked.connect(self.main_window._open_recommendation_center)

        author_recs_button = QPushButton("🌟 Author-Curated...")
        author_recs_button.clicked.connect(self.main_window._open_author_recs_dialog)

        actions_layout.addWidget(select_button)
        actions_layout.addWidget(shuffle_button)
        actions_layout.addWidget(details_button)

        actions_layout.addWidget(author_recs_button)

        panel_layout.addLayout(actions_layout)

        return panel

    def setup_fics_table(self) -> None:
        self.main_window.fics_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.main_window.fics_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.main_window.fics_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.main_window.fics_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.main_window.fics_table.setSortingEnabled(True)
        self.main_window.fics_table.horizontalHeader().setSectionsMovable(True)
        self.main_window.fics_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

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
                column_index = self.main_window.column_map.index(column_name)
                self.main_window.fics_table.setColumnHidden(column_index, True)
            except ValueError:
                self.main_window.logger.warning(f"Column '{column_name}' not found in COLUMN_MAP. Cannot hide.")

    def create_details_panel(self) -> QWidget:
        right_widget = QWidget()
        right_widget.setObjectName("right_widget")
        right_layout = QVBoxLayout(right_widget)
        title_layout = QHBoxLayout()
        self.main_window.detail_title = QLabel("Select a fic")
        self.main_window.detail_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.main_window.detail_close_button = QPushButton("X")
        self.main_window.detail_close_button.setStyleSheet("font-weight: bold; border-radius: 12px;")
        self.main_window.detail_close_button.setFixedSize(24, 24)
        title_layout.addWidget(self.main_window.detail_title, 1)
        title_layout.addWidget(self.main_window.detail_close_button)
        self.main_window.detail_author = QLabel()
        self.main_window.detail_author.setStyleSheet("font-style: italic;")
        self.main_window.detail_author.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.main_window.detail_info = QLabel()
        self.main_window.detail_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.main_window.detail_category = QLabel()
        self.main_window.detail_category.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.main_window.detail_relationships = QLabel()
        self.main_window.detail_relationships.setWordWrap(True)
        self.main_window.detail_relationships.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.main_window.detail_characters = QLabel()
        self.main_window.detail_characters.setWordWrap(True)
        self.main_window.detail_characters.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.main_window.detail_tags = QLabel()
        self.main_window.detail_tags.setWordWrap(True)
        self.main_window.detail_tags.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)

        self.main_window.detail_user_tags = QLabel()
        self.main_window.detail_user_tags.setWordWrap(True)
        self.main_window.detail_user_tags.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.main_window.detail_user_tags.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.main_window.detail_summary = QTextEdit()
        self.main_window.detail_summary.setReadOnly(True)
        self.main_window.detail_notes = NoteWidget()
        self.main_window.detail_notes.setPlaceholderText("Your personal notes...")
        status_layout = self.create_details_status_buttons()
        rating_layout = self.create_details_rating_buttons()
        self.main_window.delete_button = QPushButton("🗑️ DELETE FIC")
        self.main_window.delete_button.setObjectName("deleteButton")

        self.main_window.add_to_library_button = QPushButton("📚 Add to Library")
        self.main_window.add_to_library_button.setStyleSheet(
            "background-color: #2a9d8f; color: white; font-weight: bold; border-radius: 4px; padding: 5px;"
        )
        self.main_window.add_to_library_button.setVisible(False)

        actions_layout = QHBoxLayout()
        actions_layout.addWidget(self.main_window.add_to_library_button)
        actions_layout.addStretch()
        actions_layout.addWidget(self.main_window.delete_button)

        right_layout.addLayout(title_layout)
        right_layout.addWidget(self.main_window.detail_author)
        right_layout.addWidget(self.main_window.detail_info)
        right_layout.addWidget(self.main_window.detail_category)
        right_layout.addWidget(self.main_window.detail_relationships)
        right_layout.addWidget(self.main_window.detail_characters)
        right_layout.addWidget(self.main_window.detail_tags)
        right_layout.addWidget(QLabel("<b>Your Tags:</b>"))
        right_layout.addWidget(self.main_window.detail_user_tags)
        tag_input_layout = QHBoxLayout()
        self.main_window.tag_input = QLineEdit()
        self.main_window.tag_input.setPlaceholderText("Add a tag...")
        self.main_window.tag_completer_model = QStringListModel(self.main_window)
        self.main_window.tag_completer = QCompleter(self.main_window.tag_completer_model, self.main_window)
        self.main_window.tag_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.main_window.tag_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.main_window.tag_input.setCompleter(self.main_window.tag_completer)
        self.main_window.add_tag_button = QPushButton("Add Tag")
        tag_input_layout.addWidget(self.main_window.tag_input)
        tag_input_layout.addWidget(self.main_window.add_tag_button)
        right_layout.addLayout(tag_input_layout)
        right_layout.addWidget(QLabel("<b>Summary:</b>"))
        right_layout.addWidget(self.main_window.detail_summary, 1)
        right_layout.addWidget(QLabel("<b>Personal Notes:</b>"))
        right_layout.addWidget(self.main_window.detail_notes, 1)
        right_layout.addLayout(status_layout)
        right_layout.addLayout(rating_layout)
        right_layout.addLayout(actions_layout)
        right_layout.addWidget(self.main_window.delete_button)
        right_widget.setVisible(False)
        return right_widget

    def create_details_status_buttons(self) -> QHBoxLayout:
        status_layout = QHBoxLayout()
        self.main_window.to_read_button = QPushButton(const.STATUS_TO_READ)
        self.main_window.read_button = QPushButton(const.STATUS_READ)
        self.main_window.kudosed_button = QPushButton(const.STATUS_KUDOSED)
        self.main_window.commented_button = QPushButton(const.STATUS_COMMENTED)
        self.main_window.dropped_button = QPushButton(const.STATUS_DROPPED)
        self.main_window.sync_status_button = QPushButton("🔄 Sync Status")
        self.main_window.open_browser_button = QPushButton("🌐 Open in Browser")
        status_layout.addWidget(self.main_window.to_read_button)
        status_layout.addWidget(self.main_window.read_button)
        if self.main_window.manual_override_enabled:
            status_layout.addWidget(self.main_window.kudosed_button)
            status_layout.addWidget(self.main_window.commented_button)
        else:
            status_layout.addWidget(self.main_window.sync_status_button)
        status_layout.addWidget(self.main_window.dropped_button)
        status_layout.addStretch()
        status_layout.addWidget(self.main_window.open_browser_button)
        return status_layout

    def create_details_rating_buttons(self) -> QHBoxLayout:
        rating_layout = QHBoxLayout()
        rating_layout.addWidget(QLabel("<b>Your Rating:</b>"))
        self.main_window.rating_buttons = []
        for _ in range(5):
            btn = QPushButton("☆")
            btn.setStyleSheet("font-size: 18px; border: none;")
            rating_layout.addWidget(btn)
            self.main_window.rating_buttons.append(btn)
        rating_layout.addStretch()
        return rating_layout

    def create_view_filter_layout(self) -> QHBoxLayout:
        """Crea il layout con i pulsanti per filtrare la vista principale."""
        view_filter_layout = QHBoxLayout()

        filter_container = QWidget()
        filter_container_layout = QHBoxLayout(filter_container)
        filter_container_layout.setContentsMargins(0, 0, 0, 0)
        filter_container_layout.setSpacing(6)

        style_sheet = """            QPushButton {
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

        self.main_window.view_filter_group = QButtonGroup(self.main_window)
        self.main_window.view_filter_group.setExclusive(True)

        self.main_window.library_button = QPushButton("📚 My Library")
        self.main_window.library_button.setCheckable(True)
        self.main_window.library_button.setChecked(True)

        self.main_window.history_button = QPushButton("🕓 History")
        self.main_window.history_button.setCheckable(True)

        self.main_window.inbox_button = QPushButton("📥 Inbox")
        self.main_window.inbox_button.setCheckable(True)

        self.main_window.all_button = QPushButton("🌐 All Entries")
        self.main_window.all_button.setCheckable(True)

        self.main_window.view_filter_group.addButton(self.main_window.library_button)
        self.main_window.view_filter_group.addButton(self.main_window.history_button)
        self.main_window.view_filter_group.addButton(self.main_window.inbox_button)
        self.main_window.view_filter_group.addButton(self.main_window.all_button)

        filter_container_layout.addWidget(self.main_window.library_button)
        filter_container_layout.addWidget(self.main_window.history_button)
        filter_container_layout.addWidget(self.main_window.inbox_button)
        filter_container_layout.addWidget(self.main_window.all_button)

        view_filter_layout.addWidget(filter_container)
        view_filter_layout.addStretch()

        return view_filter_layout

    def update_status_bar(self) -> None:
        stats = calculate_base_stats()
        self.main_window.fic_count_label.setText(f"Total Fics: {stats.get('total_fics', 0)}")
        self.main_window.word_count_label.setText(f"Words Read: {stats.get('total_words_read', 0):,}")

    def update_gamification_panel(self) -> None:
        stats, verified_stats = calculate_base_stats(), count_verified_statuses()
        words_read = stats.get("total_words_read", 0)
        level_info = calculate_xp_level(words_read)
        self.main_window.level_label.setText(f"<b>LVL: {level_info['level']}</b>")
        self.main_window.xp_bar.setValue(level_info["xp_current"])
        self.main_window.xp_bar.setMaximum(level_info["xp_needed"])
        self.main_window.xp_bar.setFormat(f"{level_info['xp_current']:,} / {level_info['xp_needed']:,} XP")
        fics_read_count = stats.get("fics_read", 0) + stats.get("fics_commented", 0)
        self.main_window.fic_stats_label.setText(f"Fics Read: {fics_read_count}")
        self.main_window.kudos_stats_label.setText(f"Kudos Given: {verified_stats.get('kudos', 0)}")
        self.main_window.comment_stats_label.setText(f"Comments Left: {verified_stats.get('comments', 0)}")

    def update_search_completer(self) -> None:
        suggestions: set[str] = {fic["title"] for fic in self.main_window.fics_in_memory.values()}
        for fic in self.main_window.fics_in_memory.values():
            if fic["author"]:
                suggestions.add(fic["author"])

            fields_to_scan = ["fandoms", "tags", "category", "relationships", "characters", const.SEARCH_USER_TAGS]

            for field in fields_to_scan:

                key = "user_tags" if field == const.SEARCH_USER_TAGS else field
                if fic[key]:
                    for item in fic[key].split(","):
                        if item.strip():
                            suggestions.add(item.strip())
        self.main_window.completer_model.setStringList(sorted(list(suggestions)))

    def apply_theme(self, palette: Optional[Dict[str, str]]) -> None:
        base_stylesheet = self.main_window.styleSheet()

        if "/* THEME_SPECIFIC_STYLES_START */" in base_stylesheet:
            base_stylesheet = base_stylesheet.split("/* THEME_SPECIFIC_STYLES_START */")[0]

        if palette is None:
            self.main_window.setStyleSheet(base_stylesheet)
            self.main_window.status_text_colors.update(
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
            self.main_window.setStyleSheet(base_stylesheet + theme_stylesheet)
            self.main_window.status_text_colors.update(
                {
                    const.STATUS_TO_READ: QColor(palette["text_accent"]),
                    const.STATUS_DROPPED: QColor(palette["text_accent"]),
                    const.STATUS_READ: QColor(const.CLR_STATUS_READ_THEMED),
                    const.STATUS_KUDOSED: QColor(const.CLR_STATUS_KUDOSED_THEMED),
                    const.STATUS_COMMENTED: QColor(const.CLR_STATUS_COMMENTED_THEMED),
                }
            )

        if hasattr(self.main_window, "fics_table"):
            self.main_window._update_fics_table(get_filtered_fics(view_filter=self.main_window.current_view_filter))

    def update_tag_completer(self) -> None:
        """
        Recupera tutti i tag utente dal database e aggiorna il modello
        del QCompleter per i suggerimenti di tag.
        """
        all_tags = get_all_user_tags()
        tag_names = [tag_name for tag_id, tag_name in all_tags]
        self.main_window.tag_completer_model.setStringList(tag_names)

    def update_recommendations_panel(self) -> None:
        """
        Fetches and displays the top recommendation in the 'For You' panel.
        Hides the panel if no suitable recommendations are found.
        """

        fics_to_consider = [
            fic for fic in self.main_window.fics_in_memory.values() if fic["status"] == const.STATUS_TO_READ
        ]

        if not fics_to_consider:
            self.main_window.recommendation_panel.setVisible(False)
            return

        self.main_window.current_recommendations = self.main_window.analysis_engine.generate_recommendations(
            fics_to_consider
        )

        self.main_window.current_recommendations = [
            rec for rec in self.main_window.current_recommendations if rec["recommendation_score"] > 0
        ]

        if not self.main_window.current_recommendations:
            self.main_window.recommendation_panel.setVisible(False)
            return

        self.main_window.current_recommendation_index = 0
        self.display_current_recommendation()
        self.main_window.recommendation_panel.setVisible(True)

    def open_recommendation_center(self) -> None:
        """Opens the recommendation center dialog with all current recommendations."""
        if not self.main_window.current_recommendations:
            QMessageBox.information(
                self.main_window, "No Recommendations", "There are currently no recommendations to display."
            )  # noqa: E501
            return

        dialog = RecommendationCenterDialog(self.main_window.current_recommendations, self.main_window)

        dialog.fic_selected.connect(self.main_window._select_fic_from_url)
        dialog.discover_fics_requested.connect(self.main_window.worker_manager.start_discovery_worker)
        dialog.import_fic_requested.connect(self.main_window.worker_manager.start_single_fic_add)

        # MODIFICA: Connettiamo il segnale al metodo corretto sulla MainWindow.
        # Nota che il metodo in MainWindow si chiama _handle_add_to_queue_request
        dialog.add_to_queue_requested.connect(self.main_window._handle_add_to_queue_request)

        dialog.exec()

    @pyqtSlot(str)
    def select_fic_from_url(self, url: str) -> None:
        """Selects a fic in the main table based on a URL received from a child dialog."""
        row_index = self.main_window._find_row_by_url(url)
        if row_index is not None:
            self.main_window.fics_table.selectRow(row_index)
            item = self.main_window.fics_table.item(row_index, 0)
            if item:
                self.main_window.fics_table.scrollToItem(item)

    @pyqtSlot()
    def on_recommendation_select(self) -> None:
        """Handles the 'Select Fic' button click."""
        url_to_select = self.main_window.recommendation_panel.property("fic_url")
        if url_to_select:
            self.select_fic_from_url(url_to_select)

    @pyqtSlot()
    def on_recommendation_shuffle(self) -> None:
        """Handles the 'Suggest Another' button click by showing the next recommendation."""
        if not self.main_window.current_recommendations:
            return

        self.main_window.current_recommendation_index = (self.main_window.current_recommendation_index + 1) % len(
            self.main_window.current_recommendations
        )

        self.display_current_recommendation()

    @pyqtSlot(list)
    def handle_add_to_queue_request(self, urls: List[str]) -> None:
        """Aggiunge una lista di URL alla coda e aggiorna la UI."""
        add_fics_to_queue(urls)
        self.main_window._refresh_rows_by_url(urls)

    def display_current_recommendation(self) -> None:
        """
        Updates the UI labels of the recommendation panel with the current recommendation.
        """
        if not self.main_window.current_recommendations:
            self.main_window.recommendation_panel.setVisible(False)
            return

        if not (0 <= self.main_window.current_recommendation_index < len(self.main_window.current_recommendations)):
            self.main_window.current_recommendation_index = 0

        fic = self.main_window.current_recommendations[self.main_window.current_recommendation_index]

        self.main_window.recommendation_title.setText(f"<b>{fic['title']}</b>")
        self.main_window.recommendation_author.setText(f"by {fic['author']}")
        self.main_window.recommendation_score.setText(f"<i>Match Score: {fic['recommendation_score']}</i>")

        self.main_window.recommendation_panel.setProperty("fic_url", fic["url"])
