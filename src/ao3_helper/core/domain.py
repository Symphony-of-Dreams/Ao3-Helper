from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FicDTO:
    """
    Data Transfer Object che rappresenta un'opera (Fic).
    Questo oggetto è l'unica fonte di verità per i dati di una fic in transito
    tra AO3, la Logica di Business e la UI.
    """

    url: str
    work_id: int
    title: str

    authors: List[str] = field(default_factory=list)
    fandoms: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    relationships: List[str] = field(default_factory=list)
    characters: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)

    rating: str = ""
    language: str = ""
    word_count: int = 0
    chapter_count: int = 0
    expected_chapters: int = 0
    is_complete: bool = False
    summary: str = ""

    series_name: Optional[str] = None
    series_url: Optional[str] = None
    series_part: Optional[int] = None

    date_published: str = ""
    date_updated: str = ""

    hits: int = 0
    kudos: int = 0
    bookmarks: int = 0
    comments: int = 0

    status: str = "To Read"
    user_rating: int = 0
    user_notes: str = ""
    is_in_library: bool = False
    is_in_history: bool = False
    last_visit_date: Optional[str] = None
    visit_count: int = 0

    @property
    def authors_str(self) -> str:
        return ", ".join(self.authors)

    @property
    def fandoms_str(self) -> str:
        return ", ".join(self.fandoms)

    @property
    def tags_str(self) -> str:
        return ", ".join(self.tags)

    @property
    def relationships_str(self) -> str:
        return ", ".join(self.relationships)

    @property
    def characters_str(self) -> str:
        return ", ".join(self.characters)

    @property
    def categories_str(self) -> str:
        return ", ".join(self.categories)

    @property
    def chapters_formatted(self) -> str:
        """Ritorna il formato '5/?' o '10/10'"""
        total = str(self.expected_chapters) if self.expected_chapters else "?"
        return f"{self.chapter_count}/{total}"
