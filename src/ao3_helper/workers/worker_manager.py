from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

from ao3_helper import constants as const
from ao3_helper.core.analysis_engine import AnalysisEngine
from ao3_helper.core.ao3_manager import ao3_client
from ao3_helper.core.config_manager import config_manager
from ao3_helper.core.database import get_fics_for_sync
from ao3_helper.ui.dialogs.author_recs_dialog import AuthorRecsDialog
from ao3_helper.ui.dialogs.sync_status_window import SyncStatusWindow

from .workers import (
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


class WorkerManager(QObject):
    """Manages all background worker threads for the application."""

    analysis_ready = pyqtSignal()
    update_check_finished = pyqtSignal()
    mass_import_finished = pyqtSignal()
    bookmarks_import_finished = pyqtSignal()
    history_import_finished = pyqtSignal()
    status_sync_finished = pyqtSignal(dict, str)
    status_sync_error = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)
    new_notification = pyqtSignal(str, object)
    new_fic_from_worker = pyqtSignal(dict)
    add_fic_finished = pyqtSignal(object)
    add_fic_error = pyqtSignal(str)
    private_fic_detected = pyqtSignal(str)
    total_sync_finished = pyqtSignal()
    discovery_finished = pyqtSignal(list)
    discovery_error = pyqtSignal(str)
    author_recs_finished = pyqtSignal(list)
    author_recs_error = pyqtSignal(str)
    single_fic_row_updated = pyqtSignal(dict)

    def __init__(self, parent: QObject, analysis_engine: AnalysisEngine) -> None:
        super().__init__(parent)
        self.parent = parent
        self.analysis_engine = analysis_engine

        self.add_fic_thread: Optional[QThread] = None
        self.worker: Optional[AddFicWorker] = None
        self.update_thread: Optional[QThread] = None
        self.update_worker: Optional[UpdateCheckWorker] = None
        self.import_thread: Optional[QThread] = None
        self.import_worker: Optional[MassImportWorker] = None
        self.sync_thread: Optional[QThread] = None
        self.sync_worker: Optional[SyncStatusWorker] = None
        self.bookmarks_import_thread: Optional[QThread] = None
        self.bookmarks_import_worker: Optional[ImportBookmarksWorker] = None
        self.history_import_thread: Optional[QThread] = None
        self.history_import_worker: Optional[ImportHistoryWorker] = None
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
        self.analysis_thread: Optional[QThread] = None
        self.analysis_worker: Optional[AnalysisWorker] = None
        self.active_sync_threads_and_workers: List[tuple[QThread, SyncStatusWorker]] = []

    def setup_analysis_engine(self):
        self.analysis_thread = QThread(self.parent)
        self.analysis_worker = AnalysisWorker(self.analysis_engine)
        self.analysis_worker.moveToThread(self.analysis_thread)
        self.analysis_thread.started.connect(self.analysis_worker.run)
        self.analysis_worker.finished.connect(self.analysis_ready.emit)
        self.analysis_worker.finished.connect(self.analysis_thread.quit)
        self.analysis_worker.finished.connect(self.analysis_worker.deleteLater)
        self.analysis_thread.finished.connect(self.analysis_thread.deleteLater)
        self.analysis_thread.start()

    def start_update_check(self):
        if self.update_thread and self.update_thread.isRunning():
            return
        self.update_thread = QThread()
        self.update_worker = UpdateCheckWorker()
        self.update_worker.moveToThread(self.update_thread)
        self.update_thread.started.connect(self.update_worker.run)
        self.update_worker.progress.connect(self.progress_updated.emit)
        self.update_worker.new_notification.connect(self.new_notification.emit)
        self.update_worker.finished.connect(self.update_check_finished.emit)
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_worker.finished.connect(self.update_worker.deleteLater)
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_thread.finished.connect(lambda: setattr(self, "update_thread", None))
        self.update_thread.start()

    def start_mass_import(self, url_or_name: str):
        if (self.import_thread and self.import_thread.isRunning()) or (
            self.bookmarks_import_thread and self.bookmarks_import_thread.isRunning()
        ):
            return
        self.import_thread = QThread()
        self.import_worker = MassImportWorker(url_or_name)
        self.import_worker.moveToThread(self.import_thread)
        self.import_thread.started.connect(self.import_worker.run)
        self.import_worker.progress.connect(self.progress_updated.emit)
        self.import_worker.new_fic_added.connect(self.new_fic_from_worker.emit)
        self.import_worker.fic_promoted.connect(self.new_fic_from_worker.emit)
        self.import_worker.error.connect(self.add_fic_error.emit)
        self.import_worker.finished.connect(self.mass_import_finished.emit)
        self.import_worker.finished.connect(self.import_thread.quit)
        self.import_worker.finished.connect(self.import_worker.deleteLater)
        self.import_thread.finished.connect(self.import_thread.deleteLater)
        self.import_thread.finished.connect(lambda: setattr(self, "import_thread", None))
        self.import_thread.start()

    def start_bookmarks_import(self):
        if (self.import_thread and self.import_thread.isRunning()) or (
            self.bookmarks_import_thread and self.bookmarks_import_thread.isRunning()
        ):
            return
        if not ao3_client.session:
            return
        self.bookmarks_import_thread = QThread()
        self.bookmarks_import_worker = ImportBookmarksWorker()
        self.bookmarks_import_worker.moveToThread(self.bookmarks_import_thread)
        self.bookmarks_import_thread.started.connect(self.bookmarks_import_worker.run)
        self.bookmarks_import_worker.progress.connect(self.progress_updated.emit)
        self.bookmarks_import_worker.new_fic_added.connect(self.new_fic_from_worker.emit)
        self.bookmarks_import_worker.error.connect(self.add_fic_error.emit)
        self.bookmarks_import_worker.finished.connect(self.bookmarks_import_finished.emit)
        self.bookmarks_import_worker.finished.connect(self.bookmarks_import_thread.quit)
        self.bookmarks_import_worker.finished.connect(self.bookmarks_import_worker.deleteLater)
        self.bookmarks_import_thread.finished.connect(self.bookmarks_import_thread.deleteLater)
        self.bookmarks_import_thread.finished.connect(lambda: setattr(self, "bookmarks_import_thread", None))
        self.bookmarks_import_thread.start()

    def start_history_import(self):
        active_imports = [
            self.import_thread,
            self.bookmarks_import_thread,
            self.history_import_thread,
        ]
        if any(thread and thread.isRunning() for thread in active_imports):
            return
        if not ao3_client.session:
            return
        self.history_import_thread = QThread()
        self.history_import_worker = ImportHistoryWorker()
        self.history_import_worker.moveToThread(self.history_import_thread)
        self.history_import_thread.started.connect(self.history_import_worker.run)
        self.history_import_worker.progress.connect(self.progress_updated.emit)
        self.history_import_worker.new_fic_added.connect(self.new_fic_from_worker.emit)
        self.history_import_worker.error.connect(self.add_fic_error.emit)
        self.history_import_worker.finished.connect(self.history_import_finished.emit)
        self.history_import_worker.finished.connect(self.history_import_thread.quit)
        self.history_import_worker.finished.connect(self.history_import_worker.deleteLater)
        self.history_import_thread.finished.connect(self.history_import_thread.deleteLater)
        self.history_import_thread.finished.connect(lambda: setattr(self, "history_import_thread", None))
        self.history_import_thread.start()

    def start_status_sync(self, url: str):
        if self.sync_thread and self.sync_thread.isRunning():
            return
        username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME, fallback=None)
        if not username or not username.strip() or username == const.CONFIG_DEFAULT_USER:
            return
        work_id = int(url.split("/")[-1])
        self.sync_thread = QThread()
        self.sync_worker = SyncStatusWorker(work_id, url, username)
        self.sync_worker.moveToThread(self.sync_thread)
        self.sync_thread.started.connect(self.sync_worker.run)
        self.sync_worker.finished.connect(self.status_sync_finished.emit)
        self.sync_worker.error.connect(self.status_sync_error.emit)
        self.sync_worker.finished.connect(self.sync_thread.quit)
        self.sync_worker.finished.connect(self.sync_worker.deleteLater)
        self.sync_thread.finished.connect(self.sync_thread.deleteLater)
        self.sync_thread.finished.connect(lambda: setattr(self, "sync_thread", None))
        self.sync_thread.start()

    def start_series_import(self, series_id: str):
        if self.series_import_thread and self.series_import_thread.isRunning():
            return
        self.series_import_thread = QThread()
        self.series_import_worker = ImportSeriesWorker(series_id)
        self.series_import_worker.moveToThread(self.series_import_thread)
        self.series_import_thread.started.connect(self.series_import_worker.run)
        self.series_import_worker.progress.connect(self.progress_updated.emit)
        self.series_import_worker.new_fic_added.connect(self.new_fic_from_worker.emit)
        self.series_import_worker.error.connect(self.add_fic_error.emit)
        self.series_import_worker.finished.connect(self.mass_import_finished.emit)
        self.series_import_worker.finished.connect(self.series_import_thread.quit)
        self.series_import_worker.finished.connect(self.series_import_worker.deleteLater)
        self.series_import_thread.finished.connect(self.series_import_thread.deleteLater)
        self.series_import_thread.finished.connect(lambda: setattr(self, "series_import_thread", None))
        self.series_import_thread.start()

    def start_collection_import(self, collection_name: str):
        if self.collection_import_thread and self.collection_import_thread.isRunning():
            return
        self.collection_import_thread = QThread()
        self.collection_import_worker = ImportCollectionWorker(collection_name)
        self.collection_import_worker.moveToThread(self.collection_import_thread)
        self.collection_import_thread.started.connect(self.collection_import_worker.run)
        self.collection_import_worker.progress.connect(self.progress_updated.emit)
        self.collection_import_worker.new_fic_added.connect(self.new_fic_from_worker.emit)
        self.collection_import_worker.error.connect(self.add_fic_error.emit)
        self.collection_import_worker.finished.connect(self.mass_import_finished.emit)
        self.collection_import_worker.finished.connect(self.collection_import_thread.quit)
        self.collection_import_worker.finished.connect(self.collection_import_worker.deleteLater)
        self.collection_import_thread.finished.connect(self.collection_import_thread.deleteLater)
        self.collection_import_thread.finished.connect(lambda: setattr(self, "collection_import_thread", None))
        self.collection_import_thread.start()

    def start_total_sync(self):
        if self.total_sync_thread and self.total_sync_thread.isRunning():
            return
        username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME)
        if not username or username == const.CONFIG_DEFAULT_USER:
            return
        fics_to_sync = get_fics_for_sync()
        if not fics_to_sync:
            return
        self.total_sync_thread = QThread()
        self.total_sync_worker = TotalSyncWorker(fics_to_sync)
        self.total_sync_worker.moveToThread(self.total_sync_thread)
        self.sync_dialog = SyncStatusWindow(self.total_sync_worker, len(fics_to_sync), self.parent)
        self.total_sync_worker.progress.connect(self.sync_dialog.update_progress)
        self.total_sync_worker.status_update.connect(self.sync_dialog.update_status_text)
        self.total_sync_worker.eta_update.connect(self.sync_dialog.update_eta)
        self.total_sync_worker.finished.connect(self.sync_dialog.on_sync_finished)
        self.total_sync_worker.fic_updated.connect(self.single_fic_row_updated.emit)
        self.total_sync_worker.error.connect(lambda msg: QMessageBox.critical(self.sync_dialog, "Error", msg))
        self.total_sync_worker.finished.connect(self.total_sync_thread.quit)
        self.total_sync_worker.finished.connect(self.total_sync_worker.deleteLater)
        self.total_sync_thread.finished.connect(self.total_sync_thread.deleteLater)
        self.total_sync_thread.finished.connect(self.total_sync_finished.emit)
        self.total_sync_thread.started.connect(self.total_sync_worker.run)
        self.total_sync_thread.start()
        self.sync_dialog.show()

    def start_single_fic_add(self, url: str, use_auth: bool = False):
        if self.add_fic_thread and self.add_fic_thread.isRunning():
            return
        if self.history_import_thread and self.history_import_thread.isRunning():
            if self.history_import_worker:
                self.history_import_worker.pause()

        self.add_fic_thread = QThread()

        self.worker = AddFicWorker(url, use_auth_fallback=use_auth)
        self.worker.moveToThread(self.add_fic_thread)

        self.add_fic_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.add_fic_finished.emit)
        self.worker.error.connect(self.add_fic_error.emit)
        self.worker.private_fic_detected.connect(self.private_fic_detected.emit)
        self.worker.finished.connect(self.add_fic_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.add_fic_thread.finished.connect(lambda: setattr(self, "add_fic_thread", None))
        self.add_fic_thread.start()

    def start_author_recs_worker(self, dialog: AuthorRecsDialog):
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

    def stop_author_recs_worker(self):
        if self.author_recs_worker:
            self.author_recs_worker.stop()

    def start_discovery_worker(self, search_params: Dict[str, Any]):
        if self.discovery_thread and self.discovery_thread.isRunning():
            return
        self.discovery_thread = QThread()
        self.discovery_worker = DiscoverFicsWorker(self.analysis_engine, search_params)
        self.discovery_worker.moveToThread(self.discovery_thread)
        self.discovery_worker.finished.connect(self.discovery_finished.emit)
        self.discovery_worker.error.connect(self.discovery_error.emit)
        self.discovery_worker.finished.connect(self.discovery_thread.quit)
        self.discovery_worker.finished.connect(self.discovery_worker.deleteLater)
        self.discovery_thread.finished.connect(self.discovery_thread.deleteLater)
        self.discovery_thread.finished.connect(lambda: setattr(self, "discovery_thread", None))
        self.discovery_thread.started.connect(self.discovery_worker.run)
        self.discovery_thread.start()

    def is_long_worker_running(self) -> bool:
        threads = [
            self.import_thread,
            self.bookmarks_import_thread,
            self.history_import_thread,
            self.collection_import_thread,
            self.series_import_thread,
            self.total_sync_thread,
        ]
        return any(thread and thread.isRunning() for thread in threads)

    def pause_all_long_workers(self) -> None:
        workers_map = {
            self.import_thread: self.import_worker,
            self.bookmarks_import_thread: self.bookmarks_import_worker,
            self.history_import_thread: self.history_import_worker,
            self.collection_import_thread: self.collection_import_worker,
            self.series_import_thread: self.series_import_worker,
        }
        for thread, worker in workers_map.items():
            if thread and thread.isRunning() and worker and hasattr(worker, "pause"):
                worker.pause()

    def resume_all_long_workers(self) -> None:
        workers_map = {
            self.import_thread: self.import_worker,
            self.bookmarks_import_thread: self.bookmarks_import_worker,
            self.history_import_thread: self.history_import_worker,
            self.collection_import_thread: self.collection_import_worker,
            self.series_import_thread: self.series_import_worker,
        }
        for thread, worker in workers_map.items():
            if thread and thread.isRunning() and worker and hasattr(worker, "resume"):
                worker.resume()

    def start_auto_sync_for_fic(self, fic_data: Dict[str, Any]):
        username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME)
        if not username or username == const.CONFIG_DEFAULT_USER:
            return
        work_id = int(fic_data["url"].split("/")[-1])
        thread = QThread()
        worker = SyncStatusWorker(work_id, fic_data["url"], username)
        worker.moveToThread(thread)
        worker.finished.connect(self.status_sync_finished.emit)
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
