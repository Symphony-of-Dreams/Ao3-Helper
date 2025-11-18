from typing import Any, Dict, List, Optional, Tuple

from ao3_helper.core import database as db_repo
from ao3_helper.core.domain import FicDTO
from ao3_helper.logger_setup import logger


class LibraryService:
    """
    Gestisce la logica di business per la libreria.
    Agisce come intermediario tra la UI (MainWindow) e il Database (Persistence).
    """

    def add_fic(self, fic_data: FicDTO | Dict[str, Any]) -> Tuple[bool, str]:
        """
        Aggiunge una fic alla libreria. Accetta sia DTO (preferito) che Dict (legacy).
        """

        return db_repo.add_fic(fic_data)

    def get_all_fics(
        self, view_filter: str = "library", filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Recupera le fic filtrate.
        Accetta 'filters' per la ricerca avanzata.
        """
        return db_repo.get_filtered_fics(view_filter=view_filter, filters=filters)

    def get_fic_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Recupera i dettagli di una singola fic."""
        return db_repo.get_fic_by_url(url)

    def delete_fic(self, url: str) -> None:
        """Elimina una fic e fa pulizia (se necessaria in futuro)."""
        logger.info(f"Service: Deleting fic {url}")
        db_repo.delete_fic(url)

    def update_status(self, url: str, new_status: str, verified: bool = False) -> None:
        """Aggiorna lo stato di lettura."""
        verified_int = 1 if verified else 0
        db_repo.update_fic_status(url, new_status, verified_int)

    def update_rating(self, url: str, rating: int) -> None:
        """Aggiorna il rating utente."""
        db_repo.update_fic_rating(url, rating)

    def update_notes(self, url: str, notes: str) -> None:
        """Aggiorna le note utente."""
        db_repo.update_fic_notes(url, notes)

    def add_to_queue(self, urls: List[str]) -> None:
        """Aggiunge una lista di URL alla coda di lettura."""
        db_repo.add_fics_to_queue(urls)

    def remove_from_queue(self, urls: List[str]) -> None:
        """Rimuove una lista di URL dalla coda di lettura."""
        db_repo.remove_fics_from_queue(urls)

    def bulk_update_status(self, urls: List[str], new_status: str) -> None:
        db_repo.bulk_update_status(urls, new_status)

    def bulk_add_tags(self, urls: List[str], tags: List[str]) -> None:
        db_repo.bulk_add_tags(urls, tags)

    def bulk_remove_tags(self, urls: List[str], tags: List[str]) -> None:
        db_repo.bulk_remove_tags(urls, tags)

    def get_all_user_tags(self) -> List[Tuple[int, str]]:
        return db_repo.get_all_user_tags()

    def rename_user_tag(self, tag_id: int, new_name: str) -> bool:
        return db_repo.rename_user_tag(tag_id, new_name)

    def delete_user_tag(self, tag_id: int) -> None:
        db_repo.delete_user_tag(tag_id)

    def get_tags_for_fic(self, url: str) -> List[Tuple[int, str]]:
        return db_repo.get_tags_for_fic(url)

    def remove_tag_from_fic(self, url: str, tag_id: int) -> None:
        db_repo.remove_tag_from_fic(url, tag_id)

    def assign_tag_to_fic(self, url: str, tag_id: int) -> None:
        db_repo.assign_tag_to_fic(url, tag_id)

    def get_or_create_tag(self, name: str) -> Optional[int]:
        return db_repo.get_or_create_tag(name)

    def get_saved_filters(self) -> List[Dict[str, Any]]:
        return db_repo.get_all_filters()

    def save_filter(self, name: str, filter_data: str) -> None:
        db_repo.save_filter(name, filter_data)

    def get_data_for_charts(self, chart_filter: str = "lette") -> Dict[str, Any]:
        return db_repo.get_data_for_charts(chart_filter)

    def calculate_stats(self) -> Dict[str, int]:
        return db_repo.calculate_base_stats()

    def count_verified_stats(self) -> Dict[str, int]:
        return db_repo.count_verified_statuses()
