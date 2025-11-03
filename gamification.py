from typing import Any, Dict

import constants as const
from database import (
    add_notification,
    get_unlocked_achievements,
    unlock_achievement,
)

ACHIEVEMENTS = {
    const.ACH_WORD_COUNT_10K: {
        "name": "Apprentice Reader",
        "description": "Read your first 10,000 words.",
        "icon": "📖",
    },
    const.ACH_WORD_COUNT_100K: {
        "name": "Journeyman Reader",
        "description": "Read a total of 100,000 words.",
        "icon": "📚",
    },
    const.ACH_WORD_COUNT_500K: {
        "name": "Adept Reader",
        "description": "Read a total of 500,000 words.",
        "icon": "📜",
    },
    const.ACH_WORD_COUNT_1M: {
        "name": "Loremaster",
        "description": "Read a total of 1,000,000 words.",
        "icon": "👑",
    },
    const.ACH_FIRST_FIC: {
        "name": "First Step",
        "description": "Finish your first fic.",
        "icon": "👣",
    },
    const.ACH_10_FICS: {
        "name": "Bookworm",
        "description": "Finish 10 fics.",
        "icon": "🐛",
    },
    const.ACH_50_FICS: {
        "name": "Librarian",
        "description": "Finish 50 fics.",
        "icon": "🏛️",
    },
    const.ACH_MARATHON: {
        "name": "Marathon Runner",
        "description": "Finish a fic with more than 100,000 words.",
        "icon": "🏃",
    },
    const.ACH_FIRST_KUDOS: {
        "name": "Applause",
        "description": "Give kudos to a fic (verified).",
        "icon": "👏",
    },
    const.ACH_FIRST_COMMENT: {
        "name": "Giving Back",
        "description": "Mark your first fic as 'Commented' (verified).",
        "icon": "💬",
    },
    const.ACH_10_COMMENTS: {
        "name": "Patron of the Arts",
        "description": "Comment on 10 different fics (verified).",
        "icon": "🎭",
    },
    const.ACH_FANDOM_HOPPER: {
        "name": "Fandom Hopper",
        "description": "Read fics from 5 different fandoms.",
        "icon": "🐇",
    },
    const.ACH_FIVE_STARS: {
        "name": "Critic",
        "description": "Give a 5-star rating to a fic.",
        "icon": "⭐",
    },
}


def calculate_xp_level(total_words_read: int) -> Dict[str, int]:
    if total_words_read < 0:
        total_words_read = 0
    xp_per_level = 50000
    level = int(total_words_read // xp_per_level) + 1
    xp_in_current_level = total_words_read % xp_per_level
    return {
        "level": level,
        "xp_current": xp_in_current_level,
        "xp_needed": xp_per_level,
    }


def check_for_achievements(
    general_stats: Dict[str, int],
    chart_data: Dict[str, Any],
    verified_stats: Dict[str, int],
    newly_modified_fic: Dict[str, Any] | None = None,
) -> bool:
    """
    Comprehensive function that checks if new achievements have been unlocked.
    :param general_stats: The dictionary of basic statistics.
    :param chart_data: Aggregated data for charts (e.g., top fandoms).
    :param verified_stats: A dictionary with counts for 'kudos' and 'comments'.
    :param newly_modified_fic: (Optional) The data of the fic that triggered the check.
    """
    unlocked_ids = get_unlocked_achievements().keys()
    newly_unlocked = []

    words_read = general_stats.get("total_words_read", 0)
    if words_read >= 10000 and const.ACH_WORD_COUNT_10K not in unlocked_ids:
        newly_unlocked.append(const.ACH_WORD_COUNT_10K)
    if words_read >= 100000 and const.ACH_WORD_COUNT_100K not in unlocked_ids:
        newly_unlocked.append(const.ACH_WORD_COUNT_100K)
    if words_read >= 500000 and const.ACH_WORD_COUNT_500K not in unlocked_ids:
        newly_unlocked.append(const.ACH_WORD_COUNT_500K)
    if words_read >= 1000000 and const.ACH_WORD_COUNT_1M not in unlocked_ids:
        newly_unlocked.append(const.ACH_WORD_COUNT_1M)

    total_fics_read = general_stats.get("fics_read", 0) + general_stats.get("fics_commented", 0)
    if total_fics_read >= 1 and const.ACH_FIRST_FIC not in unlocked_ids:
        newly_unlocked.append(const.ACH_FIRST_FIC)
    if total_fics_read >= 10 and const.ACH_10_FICS not in unlocked_ids:
        newly_unlocked.append(const.ACH_10_FICS)
    if total_fics_read >= 50 and const.ACH_50_FICS not in unlocked_ids:
        newly_unlocked.append(const.ACH_50_FICS)

    if verified_stats.get("kudos", 0) >= 1 and const.ACH_FIRST_KUDOS not in unlocked_ids:
        newly_unlocked.append(const.ACH_FIRST_KUDOS)
    if verified_stats.get("comments", 0) >= 1 and const.ACH_FIRST_COMMENT not in unlocked_ids:
        newly_unlocked.append(const.ACH_FIRST_COMMENT)
    if verified_stats.get("comments", 0) >= 10 and const.ACH_10_COMMENTS not in unlocked_ids:
        newly_unlocked.append(const.ACH_10_COMMENTS)

    if len(chart_data.get("top_fandoms", [])) >= 5 and const.ACH_FANDOM_HOPPER not in unlocked_ids:
        newly_unlocked.append(const.ACH_FANDOM_HOPPER)

    if newly_modified_fic:
        if newly_modified_fic.get("word_count", 0) >= 100000 and const.ACH_MARATHON not in unlocked_ids:
            if newly_modified_fic.get("status") in const.COMPLETED_STATUSES:
                newly_unlocked.append(const.ACH_MARATHON)

        if newly_modified_fic.get("user_rating") == 5 and const.ACH_FIVE_STARS not in unlocked_ids:
            newly_unlocked.append(const.ACH_FIVE_STARS)

    for ach_id in newly_unlocked:
        unlock_achievement(ach_id)
        info = ACHIEVEMENTS[ach_id]
        add_notification(f"Achievement Unlocked: {info['name']}! ({info['description']})")

    return len(newly_unlocked) > 0
