from database import get_discovery_rate_by_month, get_reread_statistics
from models import Fic, db as peewee_db

# Useremo la fixture db_connection che abbiamo appena corretto!
# pytest la inietterà automaticamente.


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

    # Usa direttamente peewee_db importato
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


def test_get_discovery_rate_by_month(db_connection):
    """
    Verifica che get_discovery_rate_by_month raggruppi correttamente
    le opere per mese e anno e le restituisca in ordine cronologico.
    """
    # 1. Setup: Usa la stessa funzione helper per popolare il DB.
    # I dati sono già adatti a questo test.
    populate_test_data()

    # 2. Azione: Chiama la funzione da testare.
    discovery_rate = get_discovery_rate_by_month()

    # 3. Asserzioni: Verifica il risultato.

    # Ci aspettiamo 3 gruppi: 2023-10, 2023-11, 2024-01
    assert len(discovery_rate) == 3

    # Controlliamo che ogni gruppo sia corretto e in ordine

    # Primo gruppo: Ottobre 2023
    assert discovery_rate[0][0] == "2023-10"
    assert discovery_rate[0][1] == 2  # fic1 e fic2

    # Secondo gruppo: Novembre 2023
    assert discovery_rate[1][0] == "2023-11"
    assert discovery_rate[1][1] == 2  # fic3 e fic4

    # Terzo gruppo: Gennaio 2024
    assert discovery_rate[2][0] == "2024-01"
    assert discovery_rate[2][1] == 2  # fic5 e fic6
