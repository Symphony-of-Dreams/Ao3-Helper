
import sqlite3
import time
from typing import List, cast

import AO3
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

import constants as const
from ao3_manager import ao3_client
from config_manager import config_manager
from database import add_fic, get_existing_urls, update_fic_status
from logger_setup import logger


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
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error checking for updates on {fic['url']}: {e}")
        logger.info("Update check finished.")
        self.finished.emit()


class MassImportWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int, int)
    new_fic_added = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, url_or_name: str) -> None:
        super().__init__()
        self.url_or_name = url_or_name

    def run(self) -> None:
        existing_urls = get_existing_urls()
        result = ao3_client.get_work_ids_from_user(self.url_or_name)
        if isinstance(result, dict) and "error" in result:
            self.error.emit(result["error"])
            self.finished.emit()
            return
        work_ids = cast(List[int], result)
        for i, work_id in enumerate(work_ids):
            self.progress.emit(i + 1, len(work_ids))
            fic_url = f"https://archiveofourown.org/works/{work_id}"
            if fic_url in existing_urls:
                continue
            data = ao3_client.fetch_fic_data(fic_url)
            if data:
                add_fic(data)
                self.new_fic_added.emit()
            time.sleep(2)
        self.finished.emit()


class ImportBookmarksWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int, int)
    new_fic_added = pyqtSignal()
    error = pyqtSignal(str)

    def run(self) -> None:
        result = ao3_client.get_bookmarks_from_user()
        if isinstance(result, dict) and "error" in result:
            self.error.emit(result["error"])
            self.finished.emit()
            return
        work_ids = cast(List[int], result)
        existing_urls = get_existing_urls()
        for i, work_id in enumerate(work_ids):
            self.progress.emit(i + 1, len(work_ids))
            fic_url = f"https://archiveofourown.org/works/{work_id}"
            if fic_url in existing_urls:
                continue
            data = ao3_client.fetch_fic_data(fic_url)
            if data:
                add_fic(data)
                self.new_fic_added.emit()
            time.sleep(2)
        self.finished.emit()


class ImportCollectionWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int, int)
    new_fic_added = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, collection_name: str) -> None:
        super().__init__()
        self.collection_name = collection_name

    def run(self) -> None:
        existing_urls = get_existing_urls()
        result = ao3_client.get_work_ids_from_collection(self.collection_name)
        if isinstance(result, dict) and "error" in result:
            self.error.emit(result["error"])
            self.finished.emit()
            return
        work_ids = cast(List[int], result)
        for i, work_id in enumerate(work_ids):
            self.progress.emit(i + 1, len(work_ids))
            fic_url = f"https://archiveofourown.org/works/{work_id}"
            if fic_url in existing_urls:
                continue
            data = ao3_client.fetch_fic_data(fic_url)
            if data:
                add_fic(data)
                self.new_fic_added.emit()
            time.sleep(2)
        self.finished.emit()


class ImportSeriesWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int, int)
    new_fic_added = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, series_id: str) -> None:
        super().__init__()
        self.series_id = series_id

    def run(self) -> None:
        existing_urls = get_existing_urls()
        result = ao3_client.get_work_ids_from_series(self.series_id)

        if isinstance(result, dict) and "error" in result:
            self.error.emit(result["error"])
            self.finished.emit()
            return

        work_ids = cast(List[int], result)
        for i, work_id in enumerate(work_ids):
            self.progress.emit(i + 1, len(work_ids))
            fic_url = f"https://archiveofourown.org/works/{work_id}"
            if fic_url in existing_urls:
                continue
            data = ao3_client.fetch_fic_data(fic_url)
            if data:
                add_fic(data)
                self.new_fic_added.emit()
            time.sleep(2)
        self.finished.emit()


class SyncStatusWorker(QObject):
    finished = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, work_id: int, url: str, username: str) -> None:
        super().__init__()
        self.work_id, self.url, self.username = work_id, url, username

    def run(self) -> None:
        try:
            has_commented = ao3_client.check_comment(self.work_id, self.username)
            time.sleep(1)
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


                time.sleep(3)

                has_commented = ao3_client.check_comment(work_id, username)

                time.sleep(3)

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
                time.sleep(60)
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
