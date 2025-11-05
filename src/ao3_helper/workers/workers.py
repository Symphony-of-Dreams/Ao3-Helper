import random
import time
from typing import TYPE_CHECKING, Any, Dict, List, Tuple, cast

import AO3
from playhouse.shortcuts import model_to_dict
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from wordcloud import WordCloud

from ao3_helper import constants as const
from ao3_helper.core.analysis_engine import AnalysisEngine
from ao3_helper.core.ao3_manager import ao3_client
from ao3_helper.core.config_manager import config_manager
from ao3_helper.core.database import (
    Fic,
    add_fic,
    add_or_update_fic_from_history,
    get_existing_urls,
    get_fic_by_url,
    get_fics_to_update,
    set_fic_in_library,
    update_fic_data,
    update_fic_status,
)
from ao3_helper.core.query_builder import build_discovery_query
from ao3_helper.logger_setup import logger

if TYPE_CHECKING:
    from ao3_helper.core.analysis_engine import AnalysisEngine


class BaseImportWorker(QObject):
    """
    Abstract base class for workers that import a list of fics from AO3.
    Handles the common logic of fetching existing URLs, iterating through
    work IDs, fetching data, adding fics, and emitting progress signals.
    """

    finished = pyqtSignal()
    progress = pyqtSignal(int, int)
    new_fic_added = pyqtSignal(dict)
    fic_promoted = pyqtSignal(dict)
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

        for i, work_id in enumerate(work_ids):
            if self._is_cancelled:
                logger.warning("Import worker was cancelled.")
                break

            while self._is_paused:
                time.sleep(1)

            self.progress.emit(i + 1, total_works)
            fic_url = f"https://archiveofourown.org/works/{work_id}"

            try:
                data = ao3_client.fetch_fic_data(fic_url)
                if data:
                    success, reason = add_fic(data)
                    if success:
                        self.new_fic_added.emit(data)

                    elif reason == "exists":
                        existing_fic = get_fic_by_url(fic_url)
                        if existing_fic and not existing_fic.get("is_in_library"):
                            logger.info(f"Promoting existing fic to library during mass import: {fic_url}")
                            set_fic_in_library(fic_url)

                            # MODIFICA CHIAVE: Emettiamo il nuovo segnale con i dati dell'opera
                            self.fic_promoted.emit(existing_fic)
                        else:
                            logger.debug(f"Skipping existing and already-in-library fic: {fic_url}")

                time.sleep(const.DEFAULT_REQUEST_DELAY)

            except Exception:
                logger.exception(f"An error occurred while importing work ID {work_id}")
                continue

        logger.info("BaseImportWorker finished its run.")
        self.finished.emit()


class AddFicWorker(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    private_fic_detected = pyqtSignal(str)  # Segnale già esistente

    def __init__(self, url: str, use_auth_fallback: bool = False):
        super().__init__()
        self.url = url
        self.use_auth_fallback = use_auth_fallback

    @pyqtSlot()
    def run(self):
        logger.info(f"AddFicWorker started for URL: {self.url} (Authenticated: {self.use_auth_fallback})")
        try:
            data = ao3_client.fetch_fic_data(self.url, use_auth=self.use_auth_fallback)

            if data:
                self.finished.emit(data)
            else:
                # Se i dati non vengono trovati E non stavamo già usando l'autenticazione,
                # allora è un'opera potenzialmente privata.
                if not self.use_auth_fallback:
                    self.private_fic_detected.emit(self.url)
                    # Emettiamo finished(None) per dire alla MainWindow che questo specifico
                    # tentativo è concluso, ma non è un errore.
                    self.finished.emit(None)
                else:
                    # Se anche con l'autenticazione non troviamo nulla, è un errore.
                    self.error.emit("Could not retrieve data. The work might be deleted or the URL is incorrect.")
        except Exception as e:
            logger.exception(f"Exception in AddFicWorker for URL {self.url}")
            self.error.emit(str(e))


class UpdateCheckWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int, int)
    new_notification = pyqtSignal(str, str)

    def run(self) -> None:

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
    new_fic_added = pyqtSignal(dict)
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
                    _, fic_instance = add_or_update_fic_from_history(item)
                    if fic_instance:
                        fic_data_dict = model_to_dict(fic_instance)
                        fic_data_dict["from_history"] = True
                        logger.debug(f"HistoryWorker emitting existing fic: {fic_data_dict}")
                        self.new_fic_added.emit(fic_data_dict)
                else:
                    logger.debug(f"Work {work_id} is new. Fetching full metadata.")
                    data = ao3_client.fetch_fic_data(fic_url)
                    if data:
                        data["last_visit_date"] = item.get("last_visit_date")
                        data["visit_count"] = item.get("visit_count")
                        data["from_history"] = True  # Aggiungiamo il flag
                        created, fic_instance = add_or_update_fic_from_history(data)
                        if created and fic_instance:
                            # Convertiamo il modello Peewee in un dizionario
                            fic_data_dict_new = model_to_dict(fic_instance)
                            # Assicuriamoci che il flag sia presente anche qui
                            fic_data_dict_new["from_history"] = True
                            # DEBUG: Controlliamo cosa stiamo per emettere
                            logger.debug(f"HistoryWorker emitting new fic: {fic_data_dict_new}")
                            self.new_fic_added.emit(fic_data_dict_new)

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

    finished = pyqtSignal(dict, str)

    error = pyqtSignal(str)

    def __init__(self, work_id: int, url: str, username: str) -> None:
        super().__init__()
        self.work_id, self.url, self.username = work_id, url, username

    def run(self) -> None:
        try:
            has_commented = ao3_client.check_comment(self.work_id, self.username)
            time.sleep(const.SYNC_REQUEST_DELAY)
            has_kudosed = ao3_client.check_kudos(self.work_id, self.username)

            sync_results = {"commented": has_commented, "kudosed": has_kudosed}
            self.finished.emit(sync_results, self.url)

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

    def __init__(self, fics_to_sync: List[Dict[str, Any]]) -> None:
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

                # Introduce a random delay to humanize the requests
                time.sleep(random.uniform(const.HUMAN_SYNC_DELAY_MIN, const.HUMAN_SYNC_DELAY_MAX))

                has_commented = ao3_client.check_comment(work_id, username)

                # Introduce another random delay between checks for the same fic
                time.sleep(random.uniform(const.HUMAN_SYNC_DELAY_MIN, const.HUMAN_SYNC_DELAY_MAX))

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
                    from ao3_helper.core.database import get_fic_by_url

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


class ExportWorker(QObject):
    """
    A dedicated worker to generate and export a high-quality word cloud
    in a background thread, preventing the UI from freezing.
    """

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, frequencies: Dict[str, float], options: Dict[str, Any], filepath: str, file_format: str):
        super().__init__()
        self.frequencies = frequencies
        self.options = options
        self.filepath = filepath
        self.file_format = file_format

    @pyqtSlot()
    def run(self) -> None:
        """The main execution method for the worker."""
        try:
            if not self.frequencies:
                raise ValueError("No frequency data provided to generate the word cloud.")

            wc = WordCloud(
                width=self.options.get("width", 1200),
                height=self.options.get("height", 800),
                scale=self.options.get("scale", 1),
                background_color=self.options.get("background_color", "white"),
                colormap=self.options.get("colormap", "viridis"),
                max_words=self.options.get("max_words", 100),
                mask=self.options.get("mask"),
                contour_width=self.options.get("contour_width", 0),
                contour_color=self.options.get("contour_color", "steelblue"),
                relative_scaling=self.options.get("relative_scaling", 0.5),
            ).generate_from_frequencies(self.frequencies)

            if self.file_format == "png":
                wc.to_file(self.filepath)
            elif self.file_format == "svg":
                svg_data = wc.to_svg(embed_font=True)
                with open(self.filepath, "w", encoding="utf-8") as f:
                    f.write(svg_data)

            self.finished.emit(self.filepath)

        except Exception as e:
            logger.exception("Error during word cloud export worker execution.")
            self.error.emit(str(e))


class AnalysisWorker(QObject):
    """
    A dedicated worker to perform the initial, potentially long-running,
    full analysis of the database. Emits a signal when done.
    """

    finished = pyqtSignal()

    def __init__(self, analysis_engine: "AnalysisEngine"):

        super().__init__()
        self.analysis_engine = analysis_engine

    @pyqtSlot()
    def run(self) -> None:
        """The main execution method for the worker."""
        try:
            logger.info("Starting full database analysis...")
            self.analysis_engine.full_recalculation()
            logger.info("Full database analysis finished successfully.")
        except Exception as e:
            logger.exception(f"A critical error occurred during full analysis: {e}")
        finally:

            self.finished.emit()


class DiscoverFicsWorker(QObject):
    """
    Orchestra la scoperta di nuove opere basata su query, delegando la costruzione
    della logica di ricerca al modulo query_builder.
    """

    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, analysis_engine: "AnalysisEngine", search_params: Dict[str, Any]):
        super().__init__()
        self.analysis_engine = analysis_engine
        self.search_params = search_params

    @pyqtSlot()
    def run(self) -> None:
        try:
            logger.info("--- DiscoverFicsWorker (Refactored) START ---")

            profile = self.analysis_engine.get_analysis_results()

            search_query = build_discovery_query(profile, self.search_params)

            logger.info("Executing AO3 search via Query Builder...")
            search_query.update()
            logger.info(f"AO3 search returned {len(search_query.results)} initial results.")

            existing_urls = get_existing_urls()
            candidates: List[Tuple[str, AO3.Work]] = []
            for result in search_query.results:
                if len(candidates) >= 5:
                    break
                if result.url not in existing_urls:
                    candidates.append((result.url, result))

            logger.info(f"Found {len(candidates)} new candidates after filtering.")
            if not candidates:
                self.finished.emit([])
                return

            logger.info(f"Fetching full metadata for {len(candidates)} candidates as GUEST...")
            fetched_fics = []
            for i, (url, work_obj) in enumerate(candidates):
                logger.debug(f"Processing ({i+1}/{len(candidates)}): {url}")
                try:
                    work_obj._requester = ao3_client.guest_requester
                    work_obj.reload()
                    data = {
                        "url": work_obj.url,
                        "title": work_obj.title,
                        "author": ", ".join(a.username for a in work_obj.authors),
                        "summary": work_obj.summary,
                        "rating": ", ".join(work_obj.rating) if isinstance(work_obj.rating, list) else work_obj.rating,
                        "fandoms": ", ".join(work_obj.fandoms),
                        "tags": ", ".join(work_obj.tags),
                        "word_count": work_obj.words,
                        "relationships": ", ".join(work_obj.relationships),
                        "kudos": work_obj.kudos,
                    }
                    fetched_fics.append(data)
                except Exception as e:
                    logger.error(f"Failed to fetch full metadata for {url}: {e}")
                time.sleep(const.DEFAULT_REQUEST_DELAY)

            logger.info("Scoring and sorting final candidates...")
            scored_recommendations = self.analysis_engine.generate_recommendations(fetched_fics)

            self.finished.emit(scored_recommendations)
            logger.info(f"--- DiscoverFicsWorker END --- Found {len(scored_recommendations)} new recommendations.")

        except Exception as e:
            logger.exception("CRITICAL ERROR in DiscoverFicsWorker.")
            self.error.emit(str(e))


class AuthorRecsWorker(QObject):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, analysis_engine: "AnalysisEngine"):
        super().__init__()
        self.analysis_engine = analysis_engine
        self._is_running = True

    def stop(self):
        self._is_running = False

    @pyqtSlot()
    def run(self) -> None:
        try:
            logger.info("--- AuthorRecsWorker v2 START ---")
            profile = self.analysis_engine.get_analysis_results()

            author_pool = profile.get("authors", [])[:5]
            if len(author_pool) < 3:
                raise ValueError("Not enough author data in profile (need at least 3).")

            author_names = [a["name"] for a in author_pool]
            author_weights = [a["tws"] for a in author_pool]

            selected_authors = []

            temp_names = list(author_names)
            temp_weights = list(author_weights)

            for _ in range(3):
                if not temp_names:
                    break

                chosen_author = random.choices(temp_names, weights=temp_weights, k=1)[0]
                selected_authors.append(chosen_author)

                idx_to_remove = temp_names.index(chosen_author)
                temp_names.pop(idx_to_remove)
                temp_weights.pop(idx_to_remove)

            logger.info(f"Selected authors for curation: {selected_authors}")

            existing_urls = get_existing_urls()
            all_candidates = []
            for author_name in selected_authors:
                if not self._is_running:
                    break
                logger.info(f"Fetching random bookmarks from: {author_name}")

                bookmarked_ids = ao3_client.get_random_bookmarks_from_author(author_name, num_to_sample=5)

                for work_id in bookmarked_ids:
                    url = f"https://archiveofourown.org/works/{work_id}"
                    if url not in existing_urls:
                        all_candidates.append({"url": url, "recommended_by": author_name})

            if not self._is_running or not all_candidates:
                self.finished.emit([])
                return

            logger.info(f"Fetching metadata for {len(all_candidates)} total candidates...")
            fetched_fics = []
            for candidate in all_candidates:
                if not self._is_running:
                    break
                data = ao3_client.fetch_fic_data(candidate["url"])
                if data:
                    data["recommended_by"] = candidate["recommended_by"]
                    fetched_fics.append(data)
                time.sleep(const.DEFAULT_REQUEST_DELAY)

            if not self._is_running:
                self.finished.emit([])
                return

            scored_recs = self.analysis_engine.generate_recommendations(fetched_fics)

            final_results = []
            processed_authors = set()
            for fic in scored_recs:
                recommender = fic["recommended_by"]
                if recommender not in processed_authors:
                    final_results.append(fic)
                    processed_authors.add(recommender)

            self.finished.emit(final_results)
            logger.info(f"--- AuthorRecsWorker END --- Final recommendations: {len(final_results)}")

        except Exception as e:
            logger.exception("CRITICAL ERROR in AuthorRecsWorker.")
            self.error.emit(str(e))
