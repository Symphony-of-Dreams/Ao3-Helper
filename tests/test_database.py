
import constants as const
from database import (
    add_fic,
    calculate_base_stats,
    delete_fic,
    get_filtered_fics,
    update_fic_status,
)

BASE_FIC_DATA = {
    "url": "https://archiveofourown.org/works/12345",
    "title": "My Test Fic",
    "author": "Test Author",
    "word_count": 1000,
    "is_complete": True,
    "chapters": "1/1",
    "date_published": "2025-01-01",
    "date_updated": "2025-01-01",
    "language": "English",
    "hits": 100,
    "kudos": 10,
    "bookmarks": 5,
    "comments": 2,
    "series_name": "",
    "series_url": "",
    "series_part": None,
    "source": "manual",
    "last_read_date": "",
    "visit_count": None,
    "rating": "General Audiences",
    "fandoms": "Test Fandom",
    "tags": "Test Tag",
    "category": "M/M",
    "relationships": "A/B",
    "characters": "A",
    "summary": "A test summary.",
}


def test_add_and_get_fic(db_connection):
    """
    Verifica che possiamo aggiungere una fic e poi recuperarla.
    """
    result = add_fic(BASE_FIC_DATA)
    assert result is True, "add_fic dovrebbe ritornare True in caso di successo."

    all_fics = get_filtered_fics()
    assert len(all_fics) == 1

    retrieved_fic = all_fics[0]
    assert retrieved_fic["title"] == BASE_FIC_DATA["title"]
    assert retrieved_fic["author"] == BASE_FIC_DATA["author"]
    assert retrieved_fic["status"] == const.STATUS_TO_READ


def test_add_fic_prevents_duplicates(db_connection):
    """
    Verifica che add_fic ritorni False se si tenta di inserire una fic con la stessa URL.
    """
    assert add_fic(BASE_FIC_DATA) is True
    assert add_fic(BASE_FIC_DATA) is False  # Tentativo duplicato
    assert len(get_filtered_fics()) == 1


def test_update_fic_status(db_connection):
    """
    Verifica che lo stato di una fic possa essere aggiornato correttamente.
    """
    add_fic(BASE_FIC_DATA)
    update_fic_status(BASE_FIC_DATA["url"], const.STATUS_READ, verified=1)

    fic = get_filtered_fics()[0]
    assert fic["status"] == const.STATUS_READ
    assert fic["status_verified"] == 1


def test_delete_fic(db_connection):
    """
    Verifica che una fic possa essere cancellata.
    """
    add_fic(BASE_FIC_DATA)
    assert len(get_filtered_fics()) == 1

    delete_fic(BASE_FIC_DATA["url"])
    assert len(get_filtered_fics()) == 0


def test_calculate_base_stats_empty_db(db_connection):
    """
    Verifica che le statistiche siano tutte a zero quando il database è vuoto.
    """
    stats = calculate_base_stats()

    assert stats["total_fics"] == 0
    assert stats["fics_read"] == 0
    assert stats["fics_commented"] == 0
    assert stats["total_words_read"] == 0


def test_calculate_base_stats_with_data(db_connection):
    """
    Verifica che le statistiche vengano calcolate correttamente con dati di esempio.
    """
    fics = [
        {**BASE_FIC_DATA, "url": "fic1", "word_count": 1000},
        {**BASE_FIC_DATA, "url": "fic2", "word_count": 2500},
        {**BASE_FIC_DATA, "url": "fic3", "word_count": 5000},
        {**BASE_FIC_DATA, "url": "fic4", "word_count": 10000},
    ]
    for fic in fics:
        add_fic(fic)

    update_fic_status("fic1", const.STATUS_READ)
    update_fic_status("fic2", const.STATUS_COMMENTED)
    update_fic_status("fic4", const.STATUS_DROPPED)

    stats = calculate_base_stats()

    assert stats["total_fics"] == 4
    assert stats["fics_read"] == 1
    assert stats["fics_commented"] == 1
    assert stats["fics_to_read"] == 1
    assert stats["fics_dropped"] == 1
    assert stats["total_words_read"] == 1000 + 2500
