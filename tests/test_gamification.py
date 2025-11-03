import pytest
from peewee import SqliteDatabase

import constants as const
from database import (
    add_fic,
    get_unlocked_achievements,
    unlock_achievement,
    update_fic_status,
)
from gamification import check_for_achievements
from models import Achievement, Fic, FicTag, Notification, UserTag

MODELS = [Fic, Achievement, UserTag, FicTag, Notification]
test_db = SqliteDatabase(":memory:")


FIC_DATA_GAMING = {
    "url": "fic_gaming",
    "title": "t_game",
    "author": "a_game",
    "word_count": 1000,
}


@pytest.fixture
def db_connection():
    """
    Fixture per creare e pulire le tabelle del database per ogni test.
    """
    test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
    test_db.connect()
    test_db.create_tables(MODELS)
    yield
    test_db.drop_tables(MODELS)
    test_db.close()


def test_achievement_first_fic_read(db_connection):
    """
    Verifica che l'achievement 'First Step' venga sbloccato dopo aver letto la prima fic.
    """
    assert not get_unlocked_achievements()

    add_fic(FIC_DATA_GAMING)
    update_fic_status("fic_gaming", const.STATUS_READ)

    general_stats = {"total_words_read": 1000, "fics_read": 1, "fics_commented": 0}
    chart_data = {"top_fandoms": []}
    verified_stats = {"kudos": 0, "comments": 0}  # FIX

    result = check_for_achievements(general_stats, chart_data, verified_stats)  # FIX
    assert result is True

    unlocked = get_unlocked_achievements()
    assert const.ACH_FIRST_FIC in unlocked
    assert len(unlocked) == 1


def test_word_count_achievements_are_unlocked(db_connection):
    """
    Verifica che gli achievement basati sul conteggio parole vengano sbloccati.
    """
    assert not get_unlocked_achievements()

    general_stats = {"total_words_read": 120000, "fics_read": 0, "fics_commented": 0}
    chart_data = {"top_fandoms": []}
    verified_stats = {"kudos": 0, "comments": 0}  # FIX

    check_for_achievements(general_stats, chart_data, verified_stats)  # FIX

    unlocked = get_unlocked_achievements()
    assert const.ACH_WORD_COUNT_10K in unlocked
    assert const.ACH_WORD_COUNT_100K in unlocked
    assert const.ACH_FIRST_FIC not in unlocked
    assert len(unlocked) == 2


def test_no_achievements_if_already_unlocked(db_connection):
    """
    Verifica che la funzione non sblocchi di nuovo un achievement già ottenuto.
    """
    unlock_achievement(const.ACH_FIRST_FIC)
    assert len(get_unlocked_achievements()) == 1

    general_stats = {"total_words_read": 1000, "fics_read": 1, "fics_commented": 0}
    chart_data = {"top_fandoms": []}
    verified_stats = {"kudos": 0, "comments": 0}  # FIX

    result = check_for_achievements(general_stats, chart_data, verified_stats)  # FIX

    assert result is False, "La funzione dovrebbe ritornare False se nessun *nuovo* achievement è stato sbloccato."
    assert len(get_unlocked_achievements()) == 1


def test_marathon_achievement_requires_completed_status(db_connection):
    """
    Verifica che l'achievement 'Marathon Runner' richieda che la fic sia completata.
    """
    fic_to_read = {"word_count": 150000, "status": const.STATUS_TO_READ, "user_rating": 0}
    fic_read = {"word_count": 120000, "status": const.STATUS_READ, "user_rating": 0}
    verified_stats = {"kudos": 0, "comments": 0}  # FIX

    result1 = check_for_achievements({}, {}, verified_stats, newly_modified_fic=fic_to_read)  # FIX
    assert result1 is False

    result2 = check_for_achievements({}, {}, verified_stats, newly_modified_fic=fic_read)  # FIX
    assert result2 is True
    assert const.ACH_MARATHON in get_unlocked_achievements()


def test_verified_achievements(db_connection):
    """
    Verifica che gli achievement per kudos e commenti vengano sbloccati.
    """
    verified_stats = {"kudos": 1, "comments": 10}  # FIX

    check_for_achievements({}, {}, verified_stats)  # FIX

    unlocked = get_unlocked_achievements()
    assert const.ACH_FIRST_KUDOS in unlocked
    assert const.ACH_FIRST_COMMENT in unlocked
    assert const.ACH_10_COMMENTS in unlocked
    assert len(unlocked) == 3


def test_five_star_achievement(db_connection):
    """
    Verifica l'achievement per la valutazione a 5 stelle.
    """
    fic = {"user_rating": 5, "word_count": 100, "status": "Read"}
    verified_stats = {"kudos": 0, "comments": 0}  # FIX

    result = check_for_achievements({}, {}, verified_stats, newly_modified_fic=fic)  # FIX
    assert result is True
    assert const.ACH_FIVE_STARS in get_unlocked_achievements()
