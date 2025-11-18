import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtGui import QColor

from ao3_helper import constants as const
from ao3_helper.ui.ui_manager import UIManager


class MockMainWindow:
    """
    Un Mock robusto che simula la MainWindow aggiornata all'architettura MVC.
    """

    def __init__(self):

        self.library_service = MagicMock()
        self.worker_manager = MagicMock()
        self.filter_manager = MagicMock()
        self.analysis_engine = MagicMock()
        self.logger = MagicMock()

        self.fic_model = MagicMock()
        self.fic_model._data = []
        self.proxy_model = MagicMock()

        self._menu_bar_mock = MagicMock()
        self._status_bar_mock = MagicMock()

        self.add_button = MagicMock()
        self.dashboard_button = MagicMock()
        self.notifications_button = MagicMock()
        self.refresh_button = MagicMock()
        self.achievements_button = MagicMock()
        self.detail_close_button = MagicMock()
        self.add_tag_button = MagicMock()
        self.to_read_button = MagicMock()
        self.read_button = MagicMock()
        self.dropped_button = MagicMock()
        self.open_browser_button = MagicMock()
        self.kudosed_button = MagicMock()
        self.commented_button = MagicMock()
        self.sync_status_button = MagicMock()
        self.delete_button = MagicMock()
        self.save_filter_button = MagicMock()
        self.advanced_search_button = MagicMock()
        self.clear_search_button = MagicMock()
        self.add_to_library_button = MagicMock()
        self.library_button = MagicMock()
        self.history_button = MagicMock()
        self.inbox_button = MagicMock()
        self.all_button = MagicMock()

        self.rating_buttons = [MagicMock() for _ in range(5)]

        self.fics_table = MagicMock()

        self._selection_model_mock = MagicMock()
        self.fics_table.selectionModel.return_value = self._selection_model_mock

        self.fics_table.horizontalHeader().count.return_value = len(const.COLUMN_MAP)

        self.welcome_label = MagicMock()
        self.fic_count_label = MagicMock()
        self.word_count_label = MagicMock()
        self.level_label = MagicMock()
        self.fic_stats_label = MagicMock()
        self.kudos_stats_label = MagicMock()
        self.comment_stats_label = MagicMock()
        self.recommendation_title = MagicMock()
        self.recommendation_author = MagicMock()
        self.recommendation_score = MagicMock()

        self.detail_notes = MagicMock()
        self.detail_summary = MagicMock()
        self.detail_author = MagicMock()
        self.detail_info = MagicMock()
        self.detail_category = MagicMock()
        self.detail_relationships = MagicMock()
        self.detail_characters = MagicMock()
        self.detail_tags = MagicMock()
        self.detail_user_tags = MagicMock()

        self.recommendation_panel = MagicMock()
        self.xp_bar = MagicMock()

        self.url_input = MagicMock()
        self.search_input = MagicMock()
        self.search_combo = MagicMock()
        self.status_filter_combo = MagicMock()
        self.saved_filters_combo = MagicMock()
        self.tag_input = MagicMock()

        self.completer_model = MagicMock()
        self.completer = MagicMock()
        self.tag_completer_model = MagicMock()
        self.tag_completer = MagicMock()
        self.view_filter_group = MagicMock()

        self.column_map = const.COLUMN_MAP
        self.manual_override_enabled = False
        self.current_theme = "default"
        self.current_view_filter = "library"
        self.status_text_colors = {}
        self.fics_in_memory = {}
        self.selected_url = None
        self.current_recommendations = []
        self.current_recommendation_index = 0

        self._on_import_clicked = MagicMock()
        self._open_dashboard_window = MagicMock()
        self._open_notifications_window = MagicMock()
        self._open_achievements_window = MagicMock()
        self._on_fic_selection_changed = MagicMock()
        self._open_fics_table_context_menu = MagicMock()
        self._hide_details_panel = MagicMock()
        self._save_notes = MagicMock()
        self._add_tag_to_fic = MagicMock()
        self._open_user_tag_context_menu = MagicMock()
        self._change_fic_status = MagicMock()
        self._open_fic_in_browser = MagicMock()
        self._save_rating = MagicMock()
        self._on_delete_fics_clicked = MagicMock()
        self._add_to_library = MagicMock()
        self._open_login_dialog = MagicMock()
        self._perform_logout = MagicMock()
        self._backup_database = MagicMock()
        self._restore_database = MagicMock()
        self._delete_current_user_database = MagicMock()
        self._open_tag_management_window = MagicMock()
        self._change_theme = MagicMock()
        self._open_reading_queue_dialog = MagicMock()
        self._on_recommendation_select = MagicMock()
        self._on_recommendation_shuffle = MagicMock()
        self._open_recommendation_center = MagicMock()
        self._open_author_recs_dialog = MagicMock()
        self._on_analysis_ready = MagicMock()
        self._update_single_fic_row = MagicMock()
        self._update_fics_table = MagicMock()
        self._select_fic_from_url = MagicMock()
        self._find_row_by_url = MagicMock(return_value=0)
        self._refresh_rows_by_url = MagicMock()
        self._handle_add_to_queue_request = MagicMock()
        self._on_update_check_finished = MagicMock()
        self._on_mass_import_finished = MagicMock()
        self._on_bookmarks_import_finished = MagicMock()
        self._on_history_import_finished = MagicMock()
        self._on_status_sync_finished = MagicMock()
        self._on_status_sync_error = MagicMock()
        self._update_progress_bar = MagicMock()
        self._new_notification_from_worker = MagicMock()
        self._on_new_fic_from_worker = MagicMock()
        self._on_add_fic_finished = MagicMock()
        self._on_add_fic_error = MagicMock()
        self._handle_private_fic = MagicMock()
        self._on_total_sync_finished = MagicMock()
        self._on_discovery_finished = MagicMock()
        self._on_discovery_error = MagicMock()
        self._update_single_fic_row = MagicMock()

    def menuBar(self):
        return self._menu_bar_mock

    def statusBar(self):
        return self._status_bar_mock

    def setCentralWidget(self, widget):
        pass

    def styleSheet(self):
        return ""

    def setStyleSheet(self, style):
        pass


class TestUIManager(unittest.TestCase):

    def setUp(self):
        self.mock_window = MockMainWindow()
        self.ui_manager = UIManager(self.mock_window)

    @patch("ao3_helper.ui.ui_manager.QTableView")
    @patch("ao3_helper.ui.ui_manager.FicTableModel")
    @patch("ao3_helper.ui.ui_manager.QSortFilterProxyModel")
    @patch("ao3_helper.ui.ui_manager.QLabel")
    @patch("ao3_helper.ui.ui_manager.QPushButton")
    @patch("ao3_helper.ui.ui_manager.QLineEdit")
    @patch("ao3_helper.ui.ui_manager.QComboBox")
    @patch("ao3_helper.ui.ui_manager.QProgressBar")
    @patch("ao3_helper.ui.ui_manager.QTextEdit")
    @patch("ao3_helper.ui.ui_manager.QGroupBox")
    @patch("ao3_helper.ui.ui_manager.QCompleter")
    @patch("ao3_helper.ui.ui_manager.QStringListModel")
    @patch("ao3_helper.ui.ui_manager.QButtonGroup")
    @patch("ao3_helper.ui.ui_manager.QSplitter")
    @patch("ao3_helper.ui.ui_manager.QWidget")
    @patch("ao3_helper.ui.ui_manager.QVBoxLayout")
    @patch("ao3_helper.ui.ui_manager.QHBoxLayout")
    def test_create_main_widgets(self, *args):
        """
        Verifica la creazione dei widget e, soprattutto, l'inizializzazione
        dei Modelli (View/Proxy) invece dei vecchi Widget.
        """

        MockProxy = args[-3]
        MockModel = args[-2]
        MockTableView = args[-1]

        self.ui_manager.create_main_widgets()

        MockTableView.assert_called_once()

        MockModel.assert_called_once()
        MockProxy.assert_called_once()

        self.mock_window.fics_table.setModel.assert_called_with(self.mock_window.proxy_model)

        self.assertTrue(hasattr(self.mock_window, "column_map"))
        self.mock_window.statusBar().addPermanentWidget.assert_called()

    @patch("ao3_helper.ui.ui_manager.QAction")
    @patch("ao3_helper.ui.ui_manager.QActionGroup")
    def test_create_menu(self, MockActionGroup, MockAction):
        """Verifica che i menu File, View e Tools siano creati."""
        self.ui_manager.create_menu()
        menu_bar = self.mock_window.menuBar()
        self.assertEqual(menu_bar.addMenu.call_count, 3)

    def test_connect_signals_manual_override_disabled(self):
        """Verifica le connessioni quando l'override manuale è spento."""
        self.mock_window.manual_override_enabled = False
        self.ui_manager.connect_signals()
        self.mock_window.sync_status_button.clicked.connect.assert_called()
        self.mock_window.kudosed_button.clicked.connect.assert_not_called()

        self.mock_window.fics_table.selectionModel.assert_called()
        self.mock_window._selection_model_mock.selectionChanged.connect.assert_called()

    def test_connect_signals_manual_override_enabled(self):
        """Verifica le connessioni quando l'override manuale è attivo."""
        self.mock_window.manual_override_enabled = True
        self.ui_manager.connect_signals()
        self.mock_window.kudosed_button.clicked.connect.assert_called()
        self.mock_window.commented_button.clicked.connect.assert_called()
        self.mock_window.sync_status_button.clicked.connect.assert_not_called()

    def test_update_status_bar(self):
        """Verifica l'aggiornamento delle statistiche tramite LibraryService."""

        self.mock_window.library_service.calculate_stats.return_value = {"total_fics": 42, "total_words_read": 1000}

        self.ui_manager.update_status_bar()

        self.mock_window.library_service.calculate_stats.assert_called_once()
        self.mock_window.fic_count_label.setText.assert_called_with("Total Fics: 42")
        self.mock_window.word_count_label.setText.assert_called_with("Words Read: 1,000")

    @patch("ao3_helper.workers.gamification.calculate_xp_level")
    def test_update_gamification_panel(self, mock_xp):
        """Verifica l'aggiornamento del pannello gamification tramite LibraryService."""

        self.mock_window.library_service.calculate_stats.return_value = {
            "total_words_read": 5000,
            "fics_read": 10,
            "fics_commented": 2,
        }
        self.mock_window.library_service.count_verified_stats.return_value = {"kudos": 5, "comments": 2}
        mock_xp.return_value = {"level": 1, "xp_current": 5000, "xp_needed": 10000}

        self.ui_manager.update_gamification_panel()

        self.mock_window.library_service.calculate_stats.assert_called()
        self.mock_window.library_service.count_verified_stats.assert_called()

        self.mock_window.level_label.setText.assert_called_with("<b>LVL: 1</b>")
        self.mock_window.fic_stats_label.setText.assert_called_with("Fics Read: 12")

    def test_update_tag_completer(self):
        """Verifica l'aggiornamento del completamento tag usando LibraryService."""
        self.mock_window.library_service.get_all_user_tags.return_value = [(1, "Tag A"), (2, "Tag B")]

        self.ui_manager.update_tag_completer()

        self.mock_window.library_service.get_all_user_tags.assert_called_once()
        self.mock_window.tag_completer_model.setStringList.assert_called_with(["Tag A", "Tag B"])

    def test_update_search_completer(self):
        """Verifica l'aggiornamento del completamento ricerca."""

        self.mock_window.fics_in_memory = {
            "url1": {
                "title": "Fic One",
                "author": "Author A",
                "fandoms": "",
                "tags": "",
                "category": "",
                "relationships": "",
                "characters": "",
                "user_tags": "",
            },
        }
        self.ui_manager.update_search_completer()
        args = self.mock_window.completer_model.setStringList.call_args[0][0]
        self.assertIn("Fic One", args)

    def test_apply_theme_default(self):
        """Verifica l'applicazione del tema di default."""

        self.mock_window.library_service.get_all_fics.return_value = []

        self.ui_manager.apply_theme(None)

        self.assertIn(const.STATUS_TO_READ, self.mock_window.status_text_colors)

        self.mock_window._update_fics_table.assert_called()

    def test_apply_theme_custom(self):
        """Verifica l'applicazione di un tema custom."""
        self.mock_window.library_service.get_all_fics.return_value = []
        palette = const.PALETTE_DARK

        self.ui_manager.apply_theme(palette)

        self.assertEqual(self.mock_window.status_text_colors[const.STATUS_READ], QColor(const.CLR_STATUS_READ_THEMED))

    def test_update_recommendations_panel_with_recommendations(self):
        """Verifica che il pannello raccomandazioni si mostri se ci sono dati."""
        self.mock_window.fics_in_memory = {"url1": {"status": const.STATUS_TO_READ, "url": "url1"}}
        self.mock_window.analysis_engine.generate_recommendations.return_value = [
            {"url": "url1", "title": "Best Fic", "author": "Best Author", "recommendation_score": 50.0}
        ]

        self.ui_manager.update_recommendations_panel()

        self.mock_window.recommendation_panel.setVisible.assert_called_with(True)
        self.mock_window.recommendation_title.setText.assert_called_with("<b>Best Fic</b>")

    def test_handle_add_to_queue_request(self):
        """Verifica l'aggiunta alla coda di lettura usando LibraryService."""
        urls = ["url1", "url2"]
        self.ui_manager.handle_add_to_queue_request(urls)

        self.mock_window.library_service.add_to_queue.assert_called_with(urls)
        self.mock_window._refresh_rows_by_url.assert_called_with(urls)
