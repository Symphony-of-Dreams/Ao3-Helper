import os
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
    QThread,
    pyqtSlot,
)
from PyQt6.QtGui import QAction, QActionGroup, QCloseEvent, QColor, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QCompleter,
    QFileDialog,
    QGroupBox,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTextEdit,
    QWidget,
)

from ao3_helper import constants as const
from ao3_helper.core.analysis_engine import AnalysisEngine
from ao3_helper.core.ao3_manager import parse_ao3_url
from ao3_helper.core.config_manager import config_manager
from ao3_helper.core.database import (
    add_notification,
    calculate_base_stats,
    count_read_uncommented_fics,
    count_verified_statuses,
    get_data_for_charts,
    get_db_path_for_user,
    get_unread_notifications,
    remove_tag_from_fic,
)
from ao3_helper.core.models import db
from ao3_helper.logger_setup import logger
from ao3_helper.services.library_service import LibraryService
from ao3_helper.ui.dialogs.achievements_window import AchievementsWindow
from ao3_helper.ui.dialogs.author_recs_dialog import AuthorRecsDialog
from ao3_helper.ui.dialogs.bulk_edit_dialog import BulkEditDialog
from ao3_helper.ui.dialogs.dashboard_window import DashboardWindow
from ao3_helper.ui.dialogs.filter_builder_dialog import FilterBuilderDialog
from ao3_helper.ui.dialogs.login_dialog import LoginDialog
from ao3_helper.ui.dialogs.notifications_window import NotificationsWindow
from ao3_helper.ui.dialogs.reading_queue_dialog import ReadingQueueDialog
from ao3_helper.ui.dialogs.recommendation_center_dialog import RecommendationCenterDialog
from ao3_helper.ui.dialogs.tag_management_window import TagManagementWindow
from ao3_helper.ui.filter_manager import FilterManager
from ao3_helper.ui.ui_manager import NoteWidget, UIManager
from ao3_helper.workers.gamification import check_for_achievements
from ao3_helper.workers.worker_manager import WorkerManager
from ao3_helper.workers.workers import SyncStatusWorker


def resource_path(relative_path: str) -> str:
    try:
        base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class MainWindow(QMainWindow):
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
    bulk_edit_dialog: Optional[BulkEditDialog] = None

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AO3 Helper - Your Fanfiction Archive")
        self.setGeometry(200, 200, 1200, 700)
        self.setWindowIcon(QIcon(resource_path("assets/app_icon.ico")))

        self.bulk_edit_dialog: Optional[BulkEditDialog] = None
        self.fics_in_memory: Dict[str, sqlite3.Row] = {}
        self._ignore_selection_change: bool = False
        self.status_text_colors: Dict[str, QColor] = {}
        self.manual_override_enabled: bool
        self.current_theme: str
        self.column_map: List[str]
        self.library_service = LibraryService()
        self.filter_manager = FilterManager(self)

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
        self.recommendation_panel: QGroupBox
        self.recommendation_title: QLabel
        self.recommendation_author: QLabel
        self.recommendation_score: QLabel
        self.current_recommendations: List[Dict[str, Any]] = []
        self.current_recommendation_index: int = 0

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

        self.filter_manager = FilterManager(self)

        self.analysis_engine = AnalysisEngine()
        self.worker_manager = WorkerManager(self, self.analysis_engine)
        self.worker_manager.setup_analysis_engine()
        self.selected_url, self.fics_in_memory, self._ignore_selection_change = (
            None,
            {},
            False,
        )
        self.manual_override_enabled = config_manager.getboolean(
            const.CONFIG_SECTION_SETTINGS,
            const.CONFIG_KEY_MANUAL_OVERRIDE,
            fallback=False,
        )
        self.current_theme = config_manager.get(
            const.CONFIG_SECTION_SETTINGS,
            const.CONFIG_KEY_THEME,
            fallback=const.THEME_DEFAULT,
        )

        self.ui_manager = UIManager(self)
        self.ui_manager.create_main_widgets()
        self.ui_manager.setup_fics_table()
        self.ui_manager.create_menu()
        self.ui_manager.create_main_layout()
        self.ui_manager.connect_signals()
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
            self.ui_manager.apply_theme(const.PALETTE_DARK)
        elif self.current_theme == const.THEME_LIGHT:
            self.light_theme_action.setChecked(True)
            self.ui_manager.apply_theme(const.PALETTE_LIGHT)
        else:
            self.default_theme_action.setChecked(True)
            self.ui_manager.apply_theme(None)

        self._update_fics_table()
        self.ui_manager.update_tag_completer()
        self._generate_startup_notification()
        self._update_welcome_message()
        self.worker_manager.start_update_check()
        self.filter_manager.load()
        self._update_menu_actions_visibility()

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

    def _open_fics_table_context_menu(self, position: QPoint) -> None:

        selected_proxy_indexes = self.fics_table.selectionModel().selectedRows()

        if not selected_proxy_indexes:
            return

        selected_urls = []
        for proxy_idx in selected_proxy_indexes:

            source_idx = self.proxy_model.mapToSource(proxy_idx)

            fic_data = self.fic_model.get_fic_at(source_idx.row())

            if fic_data and "url" in fic_data:
                selected_urls.append(fic_data["url"])

        selected_urls = sorted(list(set(selected_urls)))

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
        logger.info(f"Applying bulk changes to {len(urls)} fics via Service.")

        new_status = changes["status"]
        if new_status and isinstance(new_status, str):
            self.library_service.bulk_update_status(urls, new_status)

        if changes["add_tags"]:
            self.library_service.bulk_add_tags(urls, changes["add_tags"])

        if changes["remove_tags"]:
            self.library_service.bulk_remove_tags(urls, changes["remove_tags"])

        self.ui_manager.update_tag_completer()

    def _delete_current_user_database(self) -> None:
        """
        Elimina in modo permanente il database per l'utente attualmente loggato e riavvia.
        """
        username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME)
        profile_name = username if username else "guest"

        reply = QMessageBox.question(
            self,
            f"Confirm PERMANENT Deletion for user '{profile_name}'",
            "This will permanently delete all data for the current user, including all fics, tags, and settings.\n\n"
            "<b>THIS ACTION CANNOT BE UNDONE.</b>\n\n"
            "Are you absolutely sure you want to proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                db_path = get_db_path_for_user(username)

                logger.warning(f"User '{profile_name}' confirmed data deletion. Deleting database file: {db_path}")

                if not db.is_closed():
                    db.close()

                if os.path.exists(db_path):
                    os.remove(db_path)
                    logger.info("Database file deleted successfully.")

                QMessageBox.information(
                    self,
                    "Data Deleted",
                    "All data for the current user has been deleted. The application will now restart.",  # noqa: E501
                )

                self.close()
                QProcess.startDetached(sys.executable, sys.argv or [])

            except Exception as e:
                logger.exception("Failed to delete user database.")
                QMessageBox.critical(
                    self, "Error", f"Could not delete the database file. Please check the logs.\nError: {e}"
                )  # noqa: E501

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
        if selection_model:
            selection_model.blockSignals(True)

        for url in urls_to_modify:
            fresh_fic_data = self.library_service.get_fic_by_url(url)
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

    def _add_to_library(self) -> None:
        """
        Aggiunge l'opera attualmente selezionata alla libreria, avvia lo sync dello
        stato (kudos/commenti) se necessario, e aggiorna la UI.
        """
        if not self.selected_url:
            return

        fic_data = self.fics_in_memory.get(self.selected_url)
        if not fic_data:
            return

        from ao3_helper.core.database import set_fic_in_library

        set_fic_in_library(self.selected_url)

        logger.info(f"Fic '{fic_data.get('title')}' added to library. Triggering status sync.")
        self.worker_manager.start_auto_sync_for_fic(fic_data)

        self.add_to_library_button.setVisible(False)

        self.fics_in_memory[self.selected_url]["is_in_library"] = True

        row_to_update = self._find_row_by_url(self.selected_url)
        if row_to_update is not None:

            self._populate_table_row(row_to_update, fic_data)

        QMessageBox.information(
            self, "Success", "Work has been added to your library! Status is being synced in the background."
        )  # noqa: E501

    def refresh_bulk_edit_dialog_tags(self) -> None:

        if not self.bulk_edit_dialog:
            return

        urls = self._get_selected_urls_from_table()
        if not urls:
            self.bulk_edit_dialog.populate_remove_tags_list([])
            return

        all_tags_sets = [{tag_name for _, tag_name in self.library_service.get_tags_for_fic(url)} for url in urls]
        common_tags = list(set.intersection(*all_tags_sets)) if all_tags_sets else []
        self.bulk_edit_dialog.populate_remove_tags_list(common_tags)

    def _get_selected_urls_from_table(self) -> List[str]:
        selected_urls = []
        proxy_indexes = self.fics_table.selectionModel().selectedRows()

        for proxy_idx in proxy_indexes:
            source_idx = self.proxy_model.mapToSource(proxy_idx)
            fic = self.fic_model.get_fic_at(source_idx.row())
            if fic and "url" in fic:
                selected_urls.append(fic["url"])

        return sorted(list(set(selected_urls)))

    def _find_row_by_url(self, url: str) -> Optional[int]:
        for i, fic in enumerate(self.fic_model._data):
            if fic.get("url") == url:
                return i
        return None

    def _populate_table_row(self, row_num: int, fic: Dict[str, Any]):

        pass

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        logger.info("Close event triggered. Shutting down active threads.")
        self.worker_manager.pause_all_long_workers()
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

        all_fics_in_db = self.library_service.get_all_fics(view_filter="all")

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
        self.notifications_button.setText(f"🔔 ({count})") if count > 0 else "🔔"
        self.notifications_button.setStyleSheet("background-color: #48cae4; color: white;" if count > 0 else "")

    def _generate_startup_notification(self) -> None:
        if count := count_read_uncommented_fics():
            add_notification(f"You have {count} read fics that you haven't commented on yet.")
            self.update_notification_indicator()

    def _on_update_check_finished(self) -> None:
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("Update check finished.", 3000)
        self.refresh_button.setEnabled(True)
        self._update_fics_table()

    def _on_mass_import_finished(self) -> None:
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("Mass import finished.", 3000)

        self.ui_manager.update_search_completer()

    def _on_bookmarks_import_finished(self) -> None:
        """
        Slot eseguito al termine dell'importazione dei bookmark.
        """
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("Bookmarks import finished.", 3000)

        self.ui_manager.update_search_completer()
        self.ui_manager.update_tag_completer()
        logger.info("Bookmarks import process has finished.")

    def _on_history_import_finished(self) -> None:

        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("History import finished.", 3000)

        self.ui_manager.update_search_completer()
        self.ui_manager.update_tag_completer()
        logger.info("History import process has finished.")

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
            self.library_service.update_status(url, new_status, 1)
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
            self.worker_manager.start_mass_import(text.strip())

    def _update_fics_table(self, fics_to_display: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Aggiorna la tabella passando i nuovi dati al modello.
        Molto più efficiente della vecchia versione.
        """
        self._ignore_selection_change = True

        if fics_to_display is None:

            all_fics_raw = self.library_service.get_all_fics(view_filter=self.current_view_filter)

            fics_to_render = self.analysis_engine.generate_recommendations(all_fics_raw)
        else:
            fics_to_render = fics_to_display

        self.fics_in_memory = {fic["url"]: fic for fic in fics_to_render}

        self.fic_model.update_data(fics_to_render)

        self._ignore_selection_change = False
        self.ui_manager.update_status_bar()
        self.ui_manager.update_gamification_panel()
        self.ui_manager.update_recommendations_panel()

    def format_link(self, text: Optional[str], link_type: str) -> str:
        """Helper method to format a comma-separated string into clickable HTML links."""
        if not text:
            return ""
        return ", ".join([f'<a href="{link_type}:{i.strip()}">{i.strip()}</a>' for i in text.split(",") if i.strip()])

    def _on_fic_selection_changed(self) -> None:
        if self._ignore_selection_change:
            return

        selected_indexes = self.fics_table.selectionModel().selectedRows()

        if not selected_indexes:
            self._hide_details_panel()
            return

        central_widget = self.centralWidget()
        if central_widget:
            right_widget = central_widget.findChild(QWidget, "right_widget")
            if right_widget:
                right_widget.setVisible(True)

        proxy_index = selected_indexes[0]
        source_index = self.proxy_model.mapToSource(proxy_index)

        data = self.fic_model.get_fic_at(source_index.row())

        if not data:
            return

        self.selected_url = data["url"]

        kudos = data.get("kudos", 0) or 0
        bookmarks = data.get("bookmarks", 0) or 0
        comments = data.get("comments", 0) or 0
        hits = data.get("hits", 0) or 0
        word_count = data.get("word_count", 0) or 0
        last_visit = data.get("last_visit_date")
        visit_count = data.get("visit_count")

        self.detail_title.setText(data.get("title", "Unknown Title"))
        self.detail_author.setText(f"by {self.format_link(data.get('author'), 'author')}")

        series_html = ""
        if data.get("series_name"):
            series_link = f'<a href="series_name:{data["series_name"]}">{data["series_name"]}</a>'
            series_html = f"Part {data.get('series_part', '?')} of the series {series_link}<br>"

        history_html = ""
        if last_visit:
            history_html = f"<b>Your History:</b> Last visit on {last_visit} ({visit_count} total visits)<br>"

        self.detail_info.setText(
            f"{series_html}"
            f"<b>Fandom:</b> {self.format_link(data.get('fandoms'), 'fandoms')}<br>"
            f"<b>Published:</b> {data.get('date_published', '-')} | <b>Updated:</b> {data.get('date_updated', '-')}<br>"
            f"<b>Rating:</b> {data.get('rating', '-')} | <b>Language:</b> {data.get('language', '-')}<br>"
            f"<b>Words:</b> {word_count:,} | <b>Chapters:</b> {data.get('chapters', '?')}<br>"
            f"<b>AO3 Stats:</b> Kudos: {kudos:,} | Bookmarks: {bookmarks:,} | Comments: {comments:,} | Hits: {hits:,}<br>"  # noqa: E501
            f"{history_html}"
        )

        self.detail_category.setText(f"<b>Category:</b> {self.format_link(data.get('category'), 'category')}")
        self.detail_relationships.setText(
            f"<b>Relationships:</b> {self.format_link(data.get('relationships'), 'relationships')}"
        )
        self.detail_characters.setText(f"<b>Characters:</b> {self.format_link(data.get('characters'), 'characters')}")
        self.detail_tags.setText(f"<b>Tags:</b> {self.format_link(data.get('tags'), 'tags')}")

        user_tags_html = self.format_link(data.get("user_tags"), const.SEARCH_USER_TAGS)
        self.detail_user_tags.setText(user_tags_html if user_tags_html else "<i>No tags assigned.</i>")

        self.detail_summary.setText(data.get("summary", ""))
        self.detail_notes.setText(data.get("user_notes", ""))

        is_in_library = data.get("is_in_library", False)
        self.add_to_library_button.setVisible(not is_in_library)

        rating = data.get("user_rating", 0) or 0
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

        tag_id = self.library_service.get_or_create_tag(tag_name)
        if tag_id:
            self.library_service.assign_tag_to_fic(self.selected_url, tag_id)
            self.tag_input.clear()

            fresh_fic_data = self.library_service.get_fic_by_url(self.selected_url)

            if fresh_fic_data:

                self._update_single_fic_row(fresh_fic_data)

                self._on_fic_selection_changed()

            self.ui_manager.update_tag_completer()
            self.ui_manager.update_search_completer()

    def _save_notes(self) -> None:
        if not self.selected_url:
            return
        current_notes_in_memory = self.fics_in_memory[self.selected_url]["user_notes"]
        new_notes = self.detail_notes.toPlainText()
        if new_notes != current_notes_in_memory:
            self.library_service.update_notes(self.selected_url, new_notes)
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
        self.library_service.update_rating(self.selected_url, new_rating)

        new_fic_data = self.library_service.get_fic_by_url(self.selected_url)
        if new_fic_data:
            self.analysis_engine.update_fic(old_fic_data, new_fic_data)

        self._update_current_selection_details()

        fresh_fic_data = self.library_service.get_fic_by_url(self.selected_url)
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

        row = self._find_row_by_url(url)
        if row is not None:

            self.fic_model._data[row] = fic_data
            self.fics_in_memory[url] = fic_data  # Legacy cache

            top_left = self.fic_model.index(row, 0)
            bottom_right = self.fic_model.index(row, self.fic_model.columnCount() - 1)

            self.fic_model.dataChanged.emit(top_left, bottom_right)

    def _on_auto_sync_finished(self, url: str):
        """
        When an auto-sync finishes, get the final fic state and update the engine one last time.
        """
        final_fic_data = self.library_service.get_fic_by_url(url)

        old_fic_data = self.fics_in_memory.get(url)
        if final_fic_data and old_fic_data:
            self.analysis_engine.update_fic(dict(old_fic_data), final_fic_data)

    def _change_fic_status(self, new_status: str, verified: int = 0) -> None:
        if not self.selected_url:
            return

        self.library_service.update_status(self.selected_url, new_status, verified=bool(verified))

        fresh_fic_data = self.library_service.get_fic_by_url(self.selected_url)

        if fresh_fic_data:

            self.analysis_engine.add_fic(fresh_fic_data)

            self._update_single_fic_row(fresh_fic_data)

            if check_for_achievements(
                self.library_service.calculate_stats(),
                self.library_service.get_data_for_charts("lette"),
                self.library_service.count_verified_stats(),
                newly_modified_fic=fresh_fic_data,
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

        if self.worker_manager.add_fic_thread and self.worker_manager.add_fic_thread.isRunning():
            QMessageBox.warning(self, "In Progress", "A fic is already being added. Please wait.")
            return

        url_type, identifier = parse_ao3_url(url)
        is_long_request = url_type in ["author", "collection", "series"]

        if self.worker_manager.is_long_worker_running():

            if is_long_request:
                QMessageBox.warning(
                    self,
                    "Import in Progress",
                    "Another import process is already running in the background.\n"
                    "Please wait for it to finish before starting a new one.",
                )
                return

            elif url_type == "work":
                self.worker_manager.pause_all_long_workers()
                self.worker_manager.start_single_fic_add(url)
                return

        match url_type:
            case "work":
                self.worker_manager.start_single_fic_add(url)

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
                    self.worker_manager.start_mass_import(identifier)

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
                    self.worker_manager.start_collection_import(identifier)

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
                    self.worker_manager.start_series_import(identifier)

            case "unknown":
                QMessageBox.critical(
                    self,
                    "Invalid URL",
                    "The provided URL is not a recognized AO3 work, author, or collection page.",
                )

    def _on_add_fic_finished(self, data: Optional[Dict[str, Any]]):
        if data is None:
            logger.debug("AddFicWorker finished without data, likely handled by private_fic_detected.")
            self.worker_manager.resume_all_long_workers()
            return

        status_bar = self.statusBar()

        success, reason = self.library_service.add_fic(data)

        if success:
            logger.info(f"Successfully added '{data['title']}' to the database via worker.")
            QMessageBox.information(self, "Success", f"'{data['title']}' has been added!")
            self.url_input.clear()
            self.search_input.clear()
            self.status_filter_combo.setCurrentIndex(0)

            new_fic_data = self.library_service.get_fic_by_url(data["url"])
            if new_fic_data:
                self.analysis_engine.self.library_service.add_fic(new_fic_data)

                if not new_fic_data.get("from_history"):
                    self.worker_manager.start_auto_sync_for_fic(new_fic_data)

            self._update_fics_table()
            self.ui_manager.update_search_completer()

        elif reason == "exists":
            logger.warning(f"Worker tried to add a fic that is already in the database: {data['url']}")

            existing_fic = self.library_service.get_fic_by_url(data["url"])
            if existing_fic and not existing_fic.get("is_in_library"):

                logger.info("Fic exists and is not in library. Promoting it.")

                from ao3_helper.core.database import set_fic_in_library

                set_fic_in_library(data["url"])

                self.worker_manager.start_auto_sync_for_fic(existing_fic)

                QMessageBox.information(
                    self,
                    "Promoted to Library",
                    "This work was already in your history and has now been added to your library.\n"
                    "Status is being synced in the background.",
                )

                self._refresh_rows_by_url([data["url"]])
            else:

                QMessageBox.warning(self, "Already in Library", "This work is already in your library.")

        else:
            QMessageBox.critical(self, "Database Error", "An unexpected error occurred while saving the fic.")

        if status_bar:
            status_bar.clearMessage()
        self.worker_manager.resume_all_long_workers()

        if self.worker_manager.history_import_thread and self.worker_manager.history_import_thread.isRunning():
            if self.worker_manager.history_import_worker:
                self.worker_manager.history_import_worker.resume()

    @pyqtSlot(dict)
    def _on_new_fic_from_worker(self, fic_data: Dict[str, Any]) -> None:
        """
        Gestore unificato per ogni nuova opera aggiunta da un worker di importazione di massa.
        """
        logger.debug(f"MainWindow received fic_data: {fic_data}")

        self._update_fics_table()

        self.analysis_engine.add_fic(fic_data)

        if not fic_data.get("from_history"):
            logger.debug("fic_data does not have 'from_history' flag. Starting auto-sync.")

            self.worker_manager.start_auto_sync_for_fic(fic_data)
        else:
            logger.debug("fic_data has 'from_history' flag. Skipping auto-sync.")

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
                self.library_service.delete_fic(url)
            self.search_input.clear()
            self.status_filter_combo.setCurrentIndex(0)
            self._hide_details_panel()
            self._update_fics_table()
            self.ui_manager.update_search_completer()

    def _change_theme(self, theme_name: str) -> None:

        self.current_theme = theme_name

        if theme_name == const.THEME_DARK:

            self.ui_manager.apply_theme(const.PALETTE_DARK)

        elif theme_name == const.THEME_LIGHT:

            self.ui_manager.apply_theme(const.PALETTE_LIGHT)

        else:

            self.ui_manager.apply_theme(None)

        config_manager.set(const.CONFIG_SECTION_SETTINGS, const.CONFIG_KEY_THEME, self.current_theme)

        config_manager.save_config()

    def _on_add_fic_error(self, error_message: str):
        logger.error(f"An error occurred in the AddFicWorker: {error_message}")
        QMessageBox.critical(self, "Error", f"An unexpected error occurred: {error_message}")
        status_bar = self.statusBar()
        if status_bar:
            status_bar.clearMessage()
        self.worker_manager.resume_all_long_workers()

        if self.worker_manager.history_import_thread and self.worker_manager.history_import_thread.isRunning():
            if self.worker_manager.history_import_worker:
                self.worker_manager.history_import_worker.resume()

    def _open_user_tag_context_menu(self, position: QPoint) -> None:
        """
        Apre un menu contestuale che permette di rimuovere qualsiasi tag
        attualmente assegnato alla fic selezionata.
        """
        if not self.selected_url:
            return

        all_fic_tags = self.library_service.get_tags_for_fic(self.selected_url)
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

        fresh_fic_data = self.library_service.get_fic_by_url(self.selected_url)
        if not fresh_fic_data:

            self._hide_details_panel()
            self._update_fics_table(self.library_service.get_all_fics())
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
        self.ui_manager.update_tag_completer()
        self.ui_manager.update_search_completer()

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
        Esegue il logout dell'utente cancellando le credenziali, salvando la configurazione
        e forzando un riavvio dell'applicazione per caricare il profilo "guest".
        """
        reply = QMessageBox.question(
            self,
            "Confirm Logout",
            "Are you sure you want to log out? Your saved credentials will be removed.\n\n"
            "The application will restart with the guest profile.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        logger.info("User initiated logout. Clearing credentials and preparing for restart.")

        from ao3_helper.core import security_manager

        username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME)
        security_manager.delete_password(username)

        config_manager.set(
            const.CONFIG_SECTION_CREDS,
            const.CONFIG_KEY_USERNAME,
            "",
        )
        config_manager.save_config()

        QMessageBox.information(
            self, "Logged Out", "You have been successfully logged out. The application will now restart."
        )  # noqa: E501

        QApplication.quit()
        QProcess.startDetached(sys.executable, sys.argv or [])

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

            self.worker_manager.start_single_fic_add(url, use_auth=True)
        else:
            logger.info(f"User declined authenticated fetch for {url}.")
            self.worker_manager.resume_all_long_workers()

    def _on_total_sync_finished(self) -> None:
        logger.info("Total sync process has concluded.")

    def _add_selected_to_queue(self) -> None:
        """Adds all currently selected fics to the reading queue."""
        urls = self._get_selected_urls_from_table()
        if not urls:
            return

        self.library_service.add_to_queue(urls)
        self._refresh_rows_by_url(urls)

    def _remove_selected_from_queue(self) -> None:
        """Removes all currently selected fics from the reading queue."""
        urls = self._get_selected_urls_from_table()
        if not urls:
            return

        self.library_service.remove_from_queue(urls)
        self._refresh_rows_by_url(urls)

    def _refresh_rows_by_url(self, urls: List[str]) -> None:
        """
        Refreshes the data and visuals for specific rows in the table without
        doing a full reload, preserving user selection and scroll position.
        """
        for url in urls:

            fresh_fic_data = self.library_service.get_fic_by_url(url)
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

    def _open_author_recs_dialog(self):
        dialog = AuthorRecsDialog(self)
        dialog.reroll_requested.connect(lambda: self.worker_manager.start_author_recs_worker(dialog))
        dialog.import_fic_requested.connect(self.worker_manager.start_single_fic_add)
        dialog.add_to_queue_requested.connect(self._handle_add_to_queue_request)

        dialog.finished.connect(self.worker_manager.stop_author_recs_worker)

        self.worker_manager.start_author_recs_worker(dialog)
        dialog.exec()

    @pyqtSlot()
    def _on_recommendation_select(self) -> None:
        """Handles the 'Select Fic' button click."""
        self.ui_manager.on_recommendation_select()

    @pyqtSlot()
    def _on_recommendation_shuffle(self) -> None:
        """Handles the 'Suggest Another' button click by showing the next recommendation."""
        self.ui_manager.on_recommendation_shuffle()

    @pyqtSlot()
    def _open_recommendation_center(self) -> None:
        """Opens the recommendation center dialog with all current recommendations."""
        self.ui_manager.open_recommendation_center()

    @pyqtSlot(list)
    def _handle_add_to_queue_request(self, urls: List[str]) -> None:
        """Aggiunge una lista di URL alla coda e aggiorna la UI."""
        self.library_service.add_to_queue(urls)
        self._refresh_rows_by_url(urls)

    @pyqtSlot(str)
    def _select_fic_from_url(self, url: str) -> None:
        """Seleziona una fic nella tabella gestendo la conversione tra Modello e Vista."""

        source_row = self._find_row_by_url(url)

        if source_row is not None:

            source_index = self.fic_model.index(source_row, 0)

            proxy_index = self.proxy_model.mapFromSource(source_index)

            if proxy_index.isValid():

                self.fics_table.selectRow(proxy_index.row())
                self.fics_table.scrollTo(proxy_index)

    def _open_filter_builder(self) -> None:
        """Apre il Costruttore di Filtri, passando i dati per i suggerimenti."""

        completer_data = self._prepare_completer_data()
        dialog = FilterBuilderDialog(completer_data, self)

        dialog.filter_generated.connect(self._apply_advanced_filter)
        dialog.exec()

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

    def _update_welcome_message(self) -> None:
        username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME, fallback="")
        if username and username != const.CONFIG_DEFAULT_USER:
            self.welcome_label.setText(f"Welcome, {username}!")
        else:
            self.welcome_label.setText("Welcome, Guest!")
