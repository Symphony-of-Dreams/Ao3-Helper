from ao3_helper.core.database import get_activity_by_month, get_reread_statistics
from ao3_helper.core.models import Fic, db as peewee_db


def populate_test_data():
    """
    Helper function per inserire un set di dati di test realistici.
    """
    test_fics = [
        {
            "url": "fic1",
            "title": "Reread Champion",
            "date_added": "2023-10-05",
            "is_in_history": True,
            "visit_count": 20,
        },
        {"url": "fic2", "title": "One Time Read", "date_added": "2023-10-15", "is_in_history": True, "visit_count": 1},
        {
            "url": "fic3",
            "title": "Not In History",
            "date_added": "2023-11-01",
            "is_in_history": False,
            "visit_count": 10,
        },
        {"url": "fic4", "title": "Bronze Medal", "date_added": "2023-11-20", "is_in_history": True, "visit_count": 5},
        {"url": "fic5", "title": "Silver Medal", "date_added": "2024-01-10", "is_in_history": True, "visit_count": 12},
        {
            "url": "fic6",
            "title": "Another One Time Read",
            "date_added": "2024-01-25",
            "is_in_history": True,
            "visit_count": 1,
        },
    ]

    with peewee_db.atomic():
        for data in test_fics:
            full_data = {"author": "Test Author", "status": "Read", "is_complete": True, **data}
            Fic.create(**full_data)


def test_get_reread_statistics(db_connection):
    """
    Verifica che get_reread_statistics restituisca le opere corrette,
    nell'ordine corretto e rispettando i filtri.
    """

    populate_test_data()

    top_rereads = get_reread_statistics(limit=10)

    assert len(top_rereads) == 3

    assert top_rereads[0]["title"] == "Reread Champion"
    assert top_rereads[0]["visit_count"] == 20

    assert top_rereads[1]["title"] == "Silver Medal"
    assert top_rereads[1]["visit_count"] == 12

    assert top_rereads[2]["title"] == "Bronze Medal"
    assert top_rereads[2]["visit_count"] == 5

    titles_in_result = {fic["title"] for fic in top_rereads}
    assert "One Time Read" not in titles_in_result
    assert "Not In History" not in titles_in_result
    assert "Another One Time Read" not in titles_in_result


def test_get_reread_statistics_respects_limit(db_connection):
    """
    Verifica che il parametro 'limit' funzioni correttamente.
    """

    populate_test_data()

    top_2_rereads = get_reread_statistics(limit=2)

    assert len(top_2_rereads) == 2
    assert top_2_rereads[0]["title"] == "Reread Champion"
    assert top_2_rereads[1]["title"] == "Silver Medal"


def test_get_activity_by_month_default(db_connection):
    """
    Verifica che get_activity_by_month, con i parametri di default,
    raggruppi correttamente le opere per mese di aggiunta.
    """
    populate_test_data()

    activity_rate = get_activity_by_month(view_filter="all", date_field="date_added")

    assert len(activity_rate) == 3
    assert activity_rate[0] == ("2023-10", 2)
    assert activity_rate[1] == ("2023-11", 2)
    assert activity_rate[2] == ("2024-01", 2)
