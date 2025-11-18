import os

APP_VERSION = "1.9.8"
APP_NAME = "AO3_Helper"

LATEST_DB_VERSION = 6

STATUS_TO_READ = "To Read"
STATUS_READ = "Read"
STATUS_DROPPED = "Dropped"
STATUS_KUDOSED = "Kudosed"
STATUS_COMMENTED = "Commented"

COMPLETED_STATUSES = (STATUS_READ, STATUS_KUDOSED, STATUS_COMMENTED)

DEFAULT_REQUEST_DELAY = 2
SYNC_REQUEST_DELAY = 1
FAST_SYNC_DELAY = 3
HUMAN_SYNC_DELAY_MIN = 5
HUMAN_SYNC_DELAY_MAX = 15
RATE_LIMIT_DELAY = 60

COLUMN_TITLE = "Title"
COLUMN_AUTHOR = "Author"
COLUMN_FANDOM = "Fandom"
COLUMN_CHAPTERS = "Chapters"
COLUMN_DATE_UPDATED = "Updated"
COLUMN_SERIES = "Series"
COLUMN_RATING = "Rating"
COLUMN_WORDS = "Words"
COLUMN_STATUS = "Status"
COLUMN_USER_RATING = "Your Rating"
COLUMN_HITS = "Hits"
COLUMN_KUDOS = "Kudos"
COLUMN_CATEGORY = "Category"
COLUMN_RELATIONSHIPS = "Relationships"
COLUMN_CHARACTERS = "Characters"
COLUMN_USER_TAGS = "Your Tags"
COLUMN_LAST_VISIT = "Last Visit"
COLUMN_VISIT_COUNT = "Visits"
COLUMN_MATCH_SCORE = "Match Score"

COLUMN_MAP = [
    COLUMN_TITLE,
    COLUMN_AUTHOR,
    COLUMN_FANDOM,
    COLUMN_CHAPTERS,
    COLUMN_DATE_UPDATED,
    COLUMN_SERIES,
    COLUMN_RATING,
    COLUMN_WORDS,
    COLUMN_HITS,
    COLUMN_KUDOS,
    COLUMN_STATUS,
    COLUMN_USER_RATING,
    COLUMN_MATCH_SCORE,
    COLUMN_CATEGORY,
    COLUMN_RELATIONSHIPS,
    COLUMN_CHARACTERS,
    COLUMN_USER_TAGS,
    COLUMN_LAST_VISIT,
    COLUMN_VISIT_COUNT,
]


ACH_WORD_COUNT_10K = "word_count_10k"
ACH_WORD_COUNT_100K = "word_count_100k"
ACH_WORD_COUNT_500K = "word_count_500k"
ACH_WORD_COUNT_1M = "word_count_1M"
ACH_FIRST_FIC = "first_fic_read"
ACH_10_FICS = "10_fics_read"
ACH_50_FICS = "50_fics_read"
ACH_MARATHON = "fic_marathon"
ACH_FIRST_KUDOS = "first_kudos"
ACH_FIRST_COMMENT = "first_comment"
ACH_10_COMMENTS = "10_comments"
ACH_FANDOM_HOPPER = "fandom_hopper"
ACH_FIVE_STARS = "five_stars"


THEME_DARK = "dark"
THEME_LIGHT = "light"
THEME_DEFAULT = "default"


CONFIG_SECTION_CREDS = "AO3_Credentials"
CONFIG_KEY_USERNAME = "username"


CONFIG_SECTION_SETTINGS = "Settings"
CONFIG_KEY_MANUAL_OVERRIDE = "manual_override"
CONFIG_KEY_THEME = "theme"

CONFIG_SECTION_UI = "UI_Settings"
CONFIG_KEY_GEOMETRY = "window_geometry"
CONFIG_KEY_COL_ORDER = "column_order"

CONFIG_DEFAULT_USER = "MIO_USERNAME"


SEARCH_ALL = "tutti"
SEARCH_TITLE = "title"
SEARCH_AUTHOR = "author"
SEARCH_FANDOMS = "fandoms"
SEARCH_RATING = "rating"
SEARCH_TAGS = "tags"
SEARCH_CATEGORY = "category"
SEARCH_RELATIONSHIPS = "relationships"
SEARCH_CHARACTERS = "characters"
SEARCH_USER_TAGS = "user_tags"
SEARCH_SERIES = "series_name"

CLR_STATUS_READ_THEMED = "#e63946"
CLR_STATUS_KUDOSED_THEMED = "#fca311"
CLR_STATUS_COMMENTED_THEMED = "#2a9d8f"


CLR_STATUS_READ_DEFAULT = "#E53935"
CLR_STATUS_KUDOSED_DEFAULT = "#FB8C00"
CLR_STATUS_COMMENTED_DEFAULT = "#43A047"
CLR_STATUS_NEUTRAL_DEFAULT = "#AAAAAA"
CLR_STATUS_DROPPED_DEFAULT = "#606060"

PALETTE_LIGHT = {
    "window_bg": "#f0f0f0",
    "widget_bg": "white",
    "text": "black",
    "text_accent": "#555555",
    "border": "#cccccc",
    "highlight": "#3399ff",
    "highlight_text": "white",
}
PALETTE_DARK = {
    "window_bg": "#2b2b2b",
    "widget_bg": "#3c3c3c",
    "text": "#dddddd",
    "text_accent": "#aaaaaa",
    "border": "#555555",
    "highlight": "#007acc",
    "highlight_text": "white",
}


if "APPDATA" in os.environ:

    ROAMING_DIR = os.path.join(os.environ["APPDATA"], APP_NAME)

    LOCAL_DIR = os.path.join(os.environ["LOCALAPPDATA"], APP_NAME)
else:

    ROAMING_DIR = os.path.abspath(".")
    LOCAL_DIR = os.path.abspath(".")


os.makedirs(ROAMING_DIR, exist_ok=True)
os.makedirs(LOCAL_DIR, exist_ok=True)


PROFILES_DIR = os.path.join(LOCAL_DIR, "profiles")
CONFIG_PATH = os.path.join(ROAMING_DIR, "config.ini")
LOG_PATH = os.path.join(LOCAL_DIR, "ao3_helper.log")
