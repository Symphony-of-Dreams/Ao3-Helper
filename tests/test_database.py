from ao3_helper import constants as const
from ao3_helper.core.database import (
    add_fic,
    assign_tag_to_fic,
    calculate_base_stats,
    create_user_tag,
    delete_fic,
    delete_user_tag,
    get_activity_by_month,
    get_all_user_tags,
    get_fic_by_url,
    get_filtered_fics,
    get_tags_for_fic,
    remove_tag_from_fic,
    update_fic_status,
)
from ao3_helper.core.domain import FicDTO
from ao3_helper.core.models import Author, Fandom, Fic, FicAuthor

BASE_FIC_DATA = {
    "url": "https://archiveofourown.org/works/12345",
    "title": "My Test Fic",
    "author": "Test Author",
    "fandoms": "Test Fandom",
    "tags": "Test Tag",
    "rating": "General Audiences",
    "word_count": 1000,
    "summary": "A test summary.",
    "category": "M/M",
    "relationships": "A/B",
    "characters": "A",
    "is_complete": True,
    "series_name": "Test Series",
    "series_url": "/series/1",
    "series_part": 1,
    "chapters": "1/1",
    "date_published": "2025-01-01",
    "date_updated": "2025-01-01",
    "source": "manual",
    "language": "English",
    "hits": 100,
    "kudos": 10,
    "bookmarks": 5,
    "comments": 2,
    "is_in_history": False,
    "last_visit_date": None,
    "visit_count": None,
}


def test_add_fic_populates_relational_tables(db_connection):
    """
    Verifica critica Fase 2: salvare un DTO deve popolare le tabelle normalizzate.
    """
    dto = FicDTO(
        url="http://test",
        work_id=1,
        title="Relational Fic",
        authors=["Jane Doe", "John Smith"],
        fandoms=["Star Wars"],
        tags=["Force"],
    )

    success, msg = add_fic(dto)
    assert success is True

    fic = Fic.get(Fic.url == "http://test")
    assert fic.author == "Jane Doe, John Smith"

    assert Author.select().count() == 2
    assert Fandom.select().count() == 1

    jane = Author.get(Author.name == "Jane Doe")
    john = Author.get(Author.name == "John Smith")

    assert FicAuthor.select().where(FicAuthor.fic == fic, FicAuthor.author == jane).exists()
    assert FicAuthor.select().where(FicAuthor.fic == fic, FicAuthor.author == john).exists()


def test_add_and_get_fic(db_connection):
    """
    Verifica che possiamo aggiungere una fic e poi recuperarla.
    """

    Fic.create(**BASE_FIC_DATA, is_in_library=True)

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
    assert add_fic(BASE_FIC_DATA) == (True, "created")
    assert add_fic(BASE_FIC_DATA) == (False, "exists")
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


def test_get_activity_by_month(db_connection):
    """
    Tests the activity aggregation logic with various filters and date fields.
    """

    fics_data = [
        {
            **BASE_FIC_DATA,
            "url": "fic1",
            "is_in_library": True,
            "is_in_history": True,
            "date_added": "2025-01-10",
            "date_updated": "2025-02-05",
            "last_visit_date": "2025-03-15",
        },
        {
            **BASE_FIC_DATA,
            "url": "fic2",
            "is_in_library": True,
            "is_in_history": False,
            "date_added": "2025-01-20",
            "date_updated": "2025-03-10",
            "last_visit_date": None,
        },
        {
            **BASE_FIC_DATA,
            "url": "fic3",
            "is_in_library": False,
            "is_in_history": True,
            "date_added": "2025-02-15",
            "date_updated": "2025-02-20",
            "last_visit_date": "2025-04-01",
        },
        {
            **BASE_FIC_DATA,
            "url": "fic4",
            "is_in_library": False,
            "is_in_history": False,
            "date_added": "2025-02-25",
            "date_updated": "2025-02-26",
            "last_visit_date": None,
        },
    ]
    for fic in fics_data:
        Fic.create(**fic)

    result = get_activity_by_month(view_filter="all", date_field="date_added")
    assert result == [("2025-01", 2), ("2025-02", 2)]

    result = get_activity_by_month(view_filter="library", date_field="date_added")
    assert result == [("2025-01", 2)]

    result = get_activity_by_month(view_filter="history", date_field="date_added")
    assert result == [("2025-01", 1), ("2025-02", 1)]

    result = get_activity_by_month(view_filter="all", date_field="date_updated")
    assert result == [("2025-02", 3), ("2025-03", 1)]

    result = get_activity_by_month(view_filter="history", date_field="last_visit_date")
    assert result == [("2025-03", 1), ("2025-04", 1)]

    result = get_activity_by_month(view_filter="library", date_field="last_visit_date")
    assert result == [("2025-03", 1)]

    result = get_activity_by_month(view_filter="library", date_field="last_visit_date")

    assert ("2025-01", 1) not in result


def test_get_fic_by_url(db_connection):
    """
    Verifica che get_fic_by_url recuperi i dati corretti e gestisca i casi non trovati.
    """
    Fic.create(**BASE_FIC_DATA, is_in_library=True)

    fic = get_fic_by_url(BASE_FIC_DATA["url"])
    assert fic is not None
    assert fic["title"] == BASE_FIC_DATA["title"]

    fic_none = get_fic_by_url("http://non.existent.url")
    assert fic_none is None


FIC_URL_TAGS = "https://archiveofourown.org/works/1"
FIC_DATA_TAGS = {"url": FIC_URL_TAGS, "title": "Test Fic for Tags", "author": "Test Author"}


def test_create_and_get_tags(db_connection):
    """
    Verifica che possiamo creare nuovi tag e recuperarli tutti.
    """
    tag1_id = create_user_tag("Da rileggere")
    tag2_id = create_user_tag("Preferiti del 2025")

    assert tag1_id is not None
    assert tag2_id is not None
    assert tag1_id != tag2_id

    duplicate_id = create_user_tag("Da rileggere")
    assert duplicate_id is None, "La creazione di un tag duplicato dovrebbe ritornare None."

    all_tags = get_all_user_tags()
    assert len(all_tags) == 2
    assert (tag1_id, "Da rileggere") in all_tags
    assert (tag2_id, "Preferiti del 2025") in all_tags


def test_assign_and_get_tags_for_fic(db_connection):
    """
    Verifica che possiamo assegnare tag a una fic e recuperarli.
    """
    add_fic(FIC_DATA_TAGS)
    tag1_id = create_user_tag("Angst")
    tag2_id = create_user_tag("Fluff")
    create_user_tag("Irrilevante")

    assign_tag_to_fic(FIC_URL_TAGS, tag1_id)
    assign_tag_to_fic(FIC_URL_TAGS, tag2_id)

    fic_tags = get_tags_for_fic(FIC_URL_TAGS)
    assert len(fic_tags) == 2
    assert (tag1_id, "Angst") in fic_tags
    assert (tag2_id, "Fluff") in fic_tags


def test_remove_tag_from_fic(db_connection):
    """
    Verifica che possiamo rimuovere un'associazione tra fic e tag.
    """
    add_fic(FIC_DATA_TAGS)
    tag_id = create_user_tag("Da rimuovere")
    assign_tag_to_fic(FIC_URL_TAGS, tag_id)
    assert len(get_tags_for_fic(FIC_URL_TAGS)) == 1

    remove_tag_from_fic(FIC_URL_TAGS, tag_id)
    assert len(get_tags_for_fic(FIC_URL_TAGS)) == 0


def test_delete_tag_cascades_to_fic_tags(db_connection):
    """
    Verifica che la cancellazione di un tag rimuova le associazioni.
    """
    add_fic(FIC_DATA_TAGS)
    fic2_url = "https://archiveofourown.org/works/2"
    add_fic({"url": fic2_url, "title": "Fic 2", "author": "Author 2"})

    tag_to_delete_id = create_user_tag("Temporaneo")
    tag_to_keep_id = create_user_tag("Permanente")

    assign_tag_to_fic(FIC_URL_TAGS, tag_to_delete_id)
    assign_tag_to_fic(fic2_url, tag_to_delete_id)
    assign_tag_to_fic(FIC_URL_TAGS, tag_to_keep_id)

    assert len(get_tags_for_fic(FIC_URL_TAGS)) == 2
    assert len(get_tags_for_fic(fic2_url)) == 1

    delete_user_tag(tag_to_delete_id)

    assert len(get_all_user_tags()) == 1, "Il tag 'Temporaneo' dovrebbe essere stato cancellato."
    fic1_tags = get_tags_for_fic(FIC_URL_TAGS)
    assert len(fic1_tags) == 1
    assert fic1_tags[0][1] == "Permanente"
    assert len(get_tags_for_fic(fic2_url)) == 0
