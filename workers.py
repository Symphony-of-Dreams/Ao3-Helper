import sqlite3
import time
from typing import Any, Dict, List, cast

import AO3
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

import constants as const
from ao3_manager import ao3_client
from config_manager import config_manager
from database import Fic, add_fic, add_or_update_fic_from_history, get_existing_urls, update_fic_status
from logger_setup import logger


class BaseImportWorker(QObject):
    """
    Abstract base class for workers that import a list of fics from AO3.
    Handles the common logic of fetching existing URLs, iterating through
    work IDs, fetching data, adding fics, and emitting progress signals.
    """

    finished = pyqtSignal()
    progress = pyqtSignal(int, int)
    new_fic_added = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, identifier: str) -> None:
        super().__init__()
        self.identifier = identifier
        self._is_cancelled = False
        self._is_paused = False

    def pause(self) -> None:
        logger.info("Pause requested for import worker.")
        self._is_paused = True

    def resume(self) -> None:
        logger.info("Resume requested for import worker.")
        self._is_paused = False

    def _fetch_work_ids(self) -> List[int] | Dict[str, str]:
        """
        This method must be implemented by subclasses.
        It should call the appropriate ao3_client method to get a list of work IDs.
        """
        raise NotImplementedError("Subclasses must implement _fetch_work_ids")

    @pyqtSlot()
    def run(self) -> None:
        """The main execution loop for all import workers."""
        logger.info(f"BaseImportWorker started for identifier: {self.identifier}")

        result = self._fetch_work_ids()
        if isinstance(result, dict) and "error" in result:
            self.error.emit(result["error"])
            self.finished.emit()
            return

        work_ids = cast(List[int], result)
        total_works = len(work_ids)
        logger.info(f"Found {total_works} works to process.")

        existing_urls = get_existing_urls()

        for i, work_id in enumerate(work_ids):
            if self._is_cancelled:
                logger.warning("Import worker was cancelled.")
                break

            while self._is_paused:
                time.sleep(1)

            self.progress.emit(i + 1, total_works)
            fic_url = f"https://archiveofourown.org/works/{work_id}"

            if fic_url in existing_urls:
                continue

            try:
                data = ao3_client.fetch_fic_data(fic_url)
                if data:
                    add_fic(data)
                    self.new_fic_added.emit()

                time.sleep(const.DEFAULT_REQUEST_DELAY)

            except Exception:
                logger.exception(f"An error occurred while importing work ID {work_id}")
                continue

        logger.info("BaseImportWorker finished its run.")
        self.finished.emit()


class AddFicWorker(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    @pyqtSlot()
    def run(self):
        logger.info(f"AddFicWorker started for URL: {self.url}")
        try:
            data = ao3_client.fetch_fic_data(self.url)
            self.finished.emit(data)
        except Exception as e:
            logger.exception(f"Exception in AddFicWorker for URL {self.url}")
            self.error.emit(str(e))


class UpdateCheckWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int, int)
    new_notification = pyqtSignal(str, str)

    def run(self) -> None:
        from database import get_fics_to_update, update_fic_data

        fics_to_check = get_fics_to_update()
        logger.info(f"Starting update check for {len(fics_to_check)} incomplete fics.")
        for i, fic in enumerate(fics_to_check):
            try:
                data = ao3_client.fetch_fic_data(fic["url"])
                if data and data["word_count"] > fic["word_count"]:
                    update_fic_data(fic["url"], data)
                    self.new_notification.emit(f"New update for '{data['title']}'!", fic["url"])
                self.progress.emit(i + 1, len(fics_to_check))
                time.sleep(const.SYNC_REQUEST_DELAY)
            except Exception as e:
                logger.error(f"Error checking for updates on {fic['url']}: {e}")
        logger.info("Update check finished.")
        self.finished.emit()


class MassImportWorker(BaseImportWorker):
    """Worker to import all works from a specific author."""

    def _fetch_work_ids(self) -> List[int] | Dict[str, str]:
        return ao3_client.get_work_ids_from_user(self.identifier)


class ImportBookmarksWorker(BaseImportWorker):
    """Worker to import all bookmarks from the logged-in user."""

    def __init__(self) -> None:
        super().__init__(identifier="user_bookmarks")

    def _fetch_work_ids(self) -> List[int] | Dict[str, str]:
        return ao3_client.get_bookmarks_from_user()


class ImportHistoryWorker(QObject):
    """
    Worker to import the full reading history for the logged-in user.
    This worker has a custom run loop to handle both creation and updates.
    """

    finished = pyqtSignal()
    progress = pyqtSignal(int, int)
    new_fic_added = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._is_cancelled = False
        self._is_paused = False

    def pause(self) -> None:
        logger.info("Pause requested for history import worker.")
        self._is_paused = True

    def resume(self) -> None:
        logger.info("Resume requested for history import worker.")
        self._is_paused = False

    @pyqtSlot()
    def run(self) -> None:
        logger.info("ImportHistoryWorker started.")

        full_import_done = config_manager.getboolean("Settings", "full_history_import_completed")
        if full_import_done:
            logger.info("Starting INCREMENTAL history sync.")
        else:
            logger.warning("Starting FULL history import. This may take a while.")

        result = ao3_client.get_history_from_user()
        if isinstance(result, dict) and "error" in result:
            self.error.emit(result["error"])
            self.finished.emit()
            return

        history_items = cast(List[Dict[str, Any]], result)
        total_items = len(history_items)

        existing_urls = get_existing_urls()

        import_completed_successfully = True

        for i, item in enumerate(history_items):

            if self._is_cancelled:
                import_completed_successfully = False
                break

            while self._is_paused:
                time.sleep(1)

            work_id = item.get("work_id")
            fic_url = f"https://archiveofourown.org/works/{work_id}"

            if full_import_done and fic_url in existing_urls:

                fic_in_db = Fic.get_or_none(Fic.url == fic_url)
                if fic_in_db and fic_in_db.is_in_history:

                    if fic_in_db.last_visit_date == item.get("last_visit_date") and fic_in_db.visit_count == item.get(
                        "visit_count"
                    ):
                        logger.info(f"Incremental sync complete. Reached unchanged fic: {fic_url}")
                        break

            self.progress.emit(i + 1, total_items)

            try:

                if fic_url in existing_urls:

                    logger.debug(f"Work {work_id} already exists. Updating history data only.")
                    query = Fic.update(
                        is_in_history=True,
                        last_visit_date=item.get("last_visit_date"),
                        visit_count=item.get("visit_count"),
                    ).where(Fic.url == fic_url)
                    query.execute()
                    self.new_fic_added.emit()
                else:

                    logger.debug(f"Work {work_id} is new. Fetching full metadata.")
                    data = ao3_client.fetch_fic_data(fic_url)
                    if data:

                        data["last_visit_date"] = item.get("last_visit_date")
                        data["visit_count"] = item.get("visit_count")
                        created, _ = add_or_update_fic_from_history(data)
                        if created:
                            self.new_fic_added.emit()

                            existing_urls.add(fic_url)

                time.sleep(const.DEFAULT_REQUEST_DELAY)

            except Exception:
                logger.exception(f"An error occurred while importing history for work ID {work_id}")
                import_completed_successfully = False
                continue

        if not full_import_done and import_completed_successfully:
            logger.info("Full history import completed successfully! Flag set to 'true'.")
            config_manager.set("Settings", "full_history_import_completed", "true")
            config_manager.save_config()
        elif not import_completed_successfully:
            logger.warning("History import did not complete successfully. The 'full import' flag remains 'false'.")

        logger.info("ImportHistoryWorker finished its run.")
        self.finished.emit()


class ImportCollectionWorker(BaseImportWorker):
    """Worker to import all works from a specific collection."""

    def _fetch_work_ids(self) -> List[int] | Dict[str, str]:
        return ao3_client.get_work_ids_from_collection(self.identifier)


class ImportSeriesWorker(BaseImportWorker):
    """Worker to import all works from a specific series."""

    def _fetch_work_ids(self) -> List[int] | Dict[str, str]:
        return ao3_client.get_work_ids_from_series(self.identifier)


class SyncStatusWorker(QObject):
    finished = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, work_id: int, url: str, username: str) -> None:
        super().__init__()
        self.work_id, self.url, self.username = work_id, url, username

    def run(self) -> None:
        try:
            has_commented = ao3_client.check_comment(self.work_id, self.username)
            time.sleep(const.SYNC_REQUEST_DELAY)
            has_kudosed = ao3_client.check_kudos(self.work_id, self.username)
            new_status = (
                const.STATUS_COMMENTED if has_commented else const.STATUS_KUDOSED if has_kudosed else const.STATUS_READ
            )
            self.finished.emit(new_status, self.url)
        except Exception as e:
            logger.exception(f"Critical error during status sync for work ID {self.work_id}")
            self.error.emit(str(e))


class TotalSyncWorker(QObject):
    progress = pyqtSignal(int, int)
    status_update = pyqtSignal(str)
    eta_update = pyqtSignal(str)
    fic_updated = pyqtSignal(dict)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, fics_to_sync: List[sqlite3.Row]) -> None:
        super().__init__()
        self.fics_to_sync = fics_to_sync
        self._is_cancelled = False
        self.start_time = 0.0

    def _format_time(self, seconds: float) -> str:
        """Converte i secondi in una stringa formattata MM:SS o HH:MM:SS."""
        if seconds < 0:
            return "00:00"

        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)

        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        else:
            return f"{m:02d}:{s:02d}"

    def run(self) -> None:
        logger.info(f"Starting total sync for {len(self.fics_to_sync)} fics.")
        username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME)
        if not username or username == const.CONFIG_DEFAULT_USER:
            self.error.emit("Username not configured. Sync cannot proceed.")
            self.finished.emit("Sync aborted: Not logged in.")
            return

        updated_count = 0
        total_fics = len(self.fics_to_sync)
        self.start_time = time.time()

        for i, fic in enumerate(self.fics_to_sync):
            if self._is_cancelled:
                logger.warning("Total sync was cancelled by the user.")
                break

            current_fic_number = i + 1
            self.progress.emit(current_fic_number, total_fics)
            self.status_update.emit(f"({current_fic_number}/{total_fics}) Checking: {fic['title'][:50]}...")

            if i > 0:
                elapsed_time = time.time() - self.start_time
                avg_time_per_fic = elapsed_time / current_fic_number
                fics_remaining = total_fics - current_fic_number
                eta_seconds = avg_time_per_fic * fics_remaining
                self.eta_update.emit(self._format_time(eta_seconds))
            else:
                self.eta_update.emit("Calculating...")

            try:
                work_id = int(fic["url"].split("/")[-1])

                time.sleep(const.FAST_SYNC_DELAY)

                has_commented = ao3_client.check_comment(work_id, username)

                time.sleep(const.FAST_SYNC_DELAY)

                has_kudosed = ao3_client.check_kudos(work_id, username)

                new_status = fic["status"]
                if has_commented:
                    new_status = const.STATUS_COMMENTED
                elif has_kudosed:
                    new_status = const.STATUS_KUDOSED

                if new_status != fic["status"]:
                    update_fic_status(fic["url"], new_status, verified=1)
                    updated_count += 1
                    logger.info(f"Updated status for '{fic['title']}' to '{new_status}'.")
                    from database import get_fic_by_url

                    updated_fic_data = get_fic_by_url(fic["url"])
                    if updated_fic_data:
                        self.fic_updated.emit(dict(updated_fic_data))

            except AO3.utils.HTTPError as e:
                logger.warning(f"Rate-limit hit while checking {fic['url']}. Pausing for 60 seconds. Details: {e}")
                self.status_update.emit("Rate-limit detected. Pausing for 60 seconds...")
                time.sleep(const.RATE_LIMIT_DELAY)
                continue

            except Exception as e:
                logger.error(f"Failed to sync status for {fic['url']}: {e}")
                continue
        summary = (
            f"Sync cancelled. {updated_count} fics updated."
            if self._is_cancelled
            else f"Sync complete! {updated_count} fics updated."
        )
        self.status_update.emit(summary)
        self.finished.emit(summary)

    def cancel(self) -> None:
        self.status_update.emit("Cancellation requested...")
        self._is_cancelled = True
