
import constants as const
from database import add_fic, get_unlocked_achievements, unlock_achievement, update_fic_status
from gamification import calculate_xp_level, check_for_achievements

FIC_DATA_GAMING = {"url": "fic_gaming", "title": "t_game", "author": "a_game", "word_count": 1000}


def test_calculate_xp_level_zero_words():
    result = calculate_xp_level(0)
    assert result["level"] == 1 and result["xp_current"] == 0


def test_calculate_xp_level_negative_words_is_handled():
    result = calculate_xp_level(-100)
    assert result["level"] == 1 and result["xp_current"] == 0


def test_calculate_xp_level_within_first_level():
    result = calculate_xp_level(30000)
    assert result["level"] == 1 and result["xp_current"] == 30000


def test_calculate_xp_level_exactly_one_level_up():
    result = calculate_xp_level(50000)
    assert result["level"] == 2 and result["xp_current"] == 0


def test_calculate_xp_level_multiple_levels_up():
    result = calculate_xp_level(125000)
    assert result["level"] == 3 and result["xp_current"] == 25000


def test_achievement_first_fic_read(db_connection):
    """
    Verifica che l'achievement 'First Step' venga sbloccato dopo aver letto la prima fic.
    """
    assert not get_unlocked_achievements()

    add_fic(FIC_DATA_GAMING)
    update_fic_status("fic_gaming", const.STATUS_READ)

    general_stats = {"total_words_read": 1000, "fics_read": 1, "fics_commented": 0}
    chart_data = {"top_fandoms": []}

    result = check_for_achievements(general_stats, chart_data)

    assert result is True, "La funzione dovrebbe ritornare True se un achievement è stato sbloccato."
    unlocked = get_unlocked_achievements()
    assert const.ACH_FIRST_FIC in unlocked


def test_word_count_achievements_are_unlocked(db_connection):
    """
    Verifica che gli achievement basati sul conteggio parole vengano sbloccati.
    """
    assert not get_unlocked_achievements()

    general_stats = {"total_words_read": 120000, "fics_read": 0, "fics_commented": 0}
    chart_data = {"top_fandoms": []}

    check_for_achievements(general_stats, chart_data)

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

    result = check_for_achievements(general_stats, chart_data)

    assert result is False, "La funzione dovrebbe ritornare False se nessun *nuovo* achievement è stato sbloccato."
    assert len(get_unlocked_achievements()) == 1


def test_marathon_achievement_requires_completed_status(db_connection):
    """
    Verifica che l'achievement 'Marathon Runner' richieda che la fic sia completata.
    """
    fic_to_read = {"word_count": 150000, "status": const.STATUS_TO_READ, "user_rating": 0}
    fic_read = {"word_count": 120000, "status": const.STATUS_READ, "user_rating": 0}

    result1 = check_for_achievements({}, {}, newly_modified_fic=fic_to_read)
    assert result1 is False
    assert not get_unlocked_achievements()

    result2 = check_for_achievements({}, {}, newly_modified_fic=fic_read)
    assert result2 is True
    assert const.ACH_MARATHON in get_unlocked_achievements()
