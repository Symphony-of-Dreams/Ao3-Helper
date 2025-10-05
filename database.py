import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Set, Tuple

import constants as const
from logger_setup import logger

DB_NAME = "ao3_helper.db"


def initialize_database() -> None:
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS fics (
                    url TEXT PRIMARY KEY, title TEXT NOT NULL, author TEXT, fandoms TEXT,
                    tags TEXT, rating TEXT, word_count INTEGER, summary TEXT, status TEXT NOT NULL,
                    date_added TEXT, user_notes TEXT, user_rating INTEGER, category TEXT,
                    relationships TEXT, characters TEXT, is_complete INTEGER NOT NULL DEFAULT 0,
                    status_verified INTEGER NOT NULL DEFAULT 0
                )"""
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT NOT NULL, timestamp TEXT NOT NULL,
                    is_read INTEGER NOT NULL DEFAULT 0, related_url TEXT
                )"""
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS achievements (
                    id TEXT PRIMARY KEY,
                    unlocked_date TEXT NOT NULL
                )"""
            )
        logger.info("Database initialized successfully.")
    except sqlite3.Error as e:
        logger.exception(f"Database initialization failed: {e}")


def run_database_migrations() -> None:
    """
    Checks the database version and applies necessary migrations.
    """
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            current_version = c.execute("PRAGMA user_version").fetchone()[0]
            logger.info(f"DB version: Current is v{current_version}, Latest is v{const.LATEST_DB_VERSION}.")

            if current_version < const.LATEST_DB_VERSION:
                logger.warning(f"DB schema is outdated. Migrating from v{current_version}...")

                if current_version < 2:
                    logger.info("Applying migration to v2: Creating user_tags and fic_tags tables...")
                    try:
                        c.execute(
                            """
                            CREATE TABLE user_tags (
                                tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT NOT NULL UNIQUE
                            )
                        """
                        )
                        c.execute(
                            """
                            CREATE TABLE fic_tags (
                                fic_url TEXT NOT NULL,
                                tag_id INTEGER NOT NULL,
                                PRIMARY KEY (fic_url, tag_id),
                                FOREIGN KEY (fic_url) REFERENCES fics (url) ON DELETE CASCADE,
                                FOREIGN KEY (tag_id) REFERENCES user_tags (tag_id) ON DELETE CASCADE
                            )
                        """
                        )
                        logger.info("Successfully created tag tables for v2.")
                    except sqlite3.OperationalError as e:
                        logger.warning(
                            f"Could not create tag tables, they might exist already. This is usually safe. Error: {e}"
                        )

                if current_version < 3:
                    logger.info("Applying migration to v3: Adding 14 new data columns...")
                    try:
                        columns_to_add = {
                            "series_name": "TEXT",
                            "series_url": "TEXT",
                            "series_part": "INTEGER",
                            "chapters": "TEXT",
                            "date_published": "TEXT",
                            "date_updated": "TEXT",
                            "source": "TEXT DEFAULT 'manual'",
                            "last_read_date": "TEXT",
                            "visit_count": "INTEGER",
                            "language": "TEXT",
                            "hits": "INTEGER",
                            "kudos": "INTEGER",
                            "bookmarks": "INTEGER",
                            "comments": "INTEGER",
                        }
                        for col_name, col_type in columns_to_add.items():
                            c.execute(f"ALTER TABLE fics ADD COLUMN {col_name} {col_type}")
                        logger.info("Successfully added all columns for v3.")
                    except sqlite3.OperationalError as e:
                        logger.warning(
                            f"Could not add all columns for v3, some might exist already. This is usually safe. Error: {e}"  # noqa: E501
                        )

                logger.info(f"Setting database version to {const.LATEST_DB_VERSION}.")
                c.execute(f"PRAGMA user_version = {const.LATEST_DB_VERSION}")
                logger.info("Database migration successful.")
            else:
                logger.info("Database schema is up to date.")

    except sqlite3.Error as e:
        logger.exception(f"A critical error occurred during database migration: {e}")
        raise


def add_fic(fic_details: Dict[str, Any]) -> bool:
    """Adds a new fic to the database with all available metadata."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()

            columns = [
                "url",
                "title",
                "author",
                "fandoms",
                "tags",
                "rating",
                "word_count",
                "summary",
                "status",
                "date_added",
                "user_notes",
                "user_rating",
                "category",
                "relationships",
                "characters",
                "is_complete",
                "status_verified",
                "series_name",
                "series_url",
                "series_part",
                "chapters",
                "date_published",
                "date_updated",
                "source",
                "last_read_date",
                "visit_count",
                "language",
                "hits",
                "kudos",
                "bookmarks",
                "comments",
            ]

            values = (
                fic_details.get("url"),
                fic_details.get("title"),
                fic_details.get("author", ""),
                fic_details.get("fandoms", ""),
                fic_details.get("tags", ""),
                fic_details.get("rating", ""),
                fic_details.get("word_count", 0),
                fic_details.get("summary", ""),
                const.STATUS_TO_READ,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "",
                0,
                fic_details.get("category", ""),
                fic_details.get("relationships", ""),
                fic_details.get("characters", ""),
                1 if fic_details.get("is_complete", False) else 0,
                0,
                fic_details.get("series_name", ""),
                fic_details.get("series_url", ""),
                fic_details.get("series_part"),
                fic_details.get("chapters", "1/?"),
                fic_details.get("date_published", ""),
                fic_details.get("date_updated", ""),
                fic_details.get("source", "manual"),
                fic_details.get("last_read_date", ""),
                fic_details.get("visit_count"),
                fic_details.get("language", ""),
                fic_details.get("hits"),
                fic_details.get("kudos"),
                fic_details.get("bookmarks"),
                fic_details.get("comments"),
            )

            query = f"INSERT INTO fics ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})"
            c.execute(query, values)

        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Attempted to add a fic that already exists: {fic_details.get('url')}")
        return False
    except sqlite3.Error as e:
        logger.exception(f"Failed to add fic to database: {e}")
        return False


def update_fic_status(url: str, new_status: str, verified: int = 0) -> None:
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute(
                "UPDATE fics SET status = ?, status_verified = ? WHERE url = ?",
                (new_status, verified, url),
            )
    except sqlite3.Error as e:
        logger.exception(f"Failed to update fic status for {url}: {e}")


def unlock_achievement(achievement_id: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d")
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT OR IGNORE INTO achievements (id, unlocked_date) VALUES (?, ?)",
                (achievement_id, ts),
            )
    except sqlite3.Error as e:
        logger.exception(f"Failed to unlock achievement {achievement_id}: {e}")


def get_unlocked_achievements() -> Dict[str, str]:
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT id, unlocked_date FROM achievements")
            return {row[0]: row[1] for row in c.fetchall()}
    except sqlite3.Error as e:
        logger.exception(f"Failed to get unlocked achievements: {e}")
        return {}


def count_verified_statuses() -> Dict[str, int]:
    counts = {"kudos": 0, "comments": 0}
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT COUNT(*) FROM fics WHERE status = ? AND status_verified = 1",
                (const.STATUS_COMMENTED,),
            )
            counts["comments"] = c.fetchone()[0]
            c.execute(
                "SELECT COUNT(*) FROM fics WHERE status IN (?, ?) AND status_verified = 1",
                (const.STATUS_KUDOSED, const.STATUS_COMMENTED),
            )
            counts["kudos"] = c.fetchone()[0]
    except sqlite3.Error as e:
        logger.exception(f"Failed to count verified statuses: {e}")
    return counts


def get_filtered_fics(search_text: str | None = None, search_field: str = "tutti") -> List[sqlite3.Row]:
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            base_query = """
                SELECT f.*, GROUP_CONCAT(ut.name, ', ') AS user_tags
                FROM fics f
                LEFT JOIN fic_tags ft ON f.url = ft.fic_url
                LEFT JOIN user_tags ut ON ft.tag_id = ut.tag_id
            """
            params = []
            where_clauses = []
            having_clauses = []

            if search_text and search_text.strip():
                term = f"%{search_text}%"
                fields = {
                    "title": "f.title LIKE ?",
                    "author": "f.author LIKE ?",
                    "fandoms": "f.fandoms LIKE ?",
                    "tags": "f.tags LIKE ?",
                    "category": "f.category LIKE ?",
                    "relationships": "f.relationships LIKE ?",
                    "characters": "f.characters LIKE ?",
                    "series_name": "f.series_name LIKE ?",
                }

                if search_field == const.SEARCH_USER_TAGS:
                    having_clauses.append("user_tags LIKE ?")
                    params.append(term)
                elif search_field == "tutti":
                    all_fields_query = " OR ".join(fields.values())
                    where_clauses.append(f"({all_fields_query})")
                    params.extend([term] * len(fields))
                    having_clauses.append("user_tags LIKE ?")
                    params.append(term)
                elif search_field in fields:
                    where_clauses.append(fields[search_field])
                    params.append(term)

            if where_clauses:
                base_query += " WHERE " + " AND ".join(where_clauses)

            base_query += " GROUP BY f.url"

            if having_clauses:
                joiner = " OR " if search_field == "tutti" else " AND "
                base_query += " HAVING " + joiner.join(having_clauses)

            base_query += " ORDER BY f.date_added DESC"

            c.execute(base_query, params)
            return c.fetchall()
    except sqlite3.Error as e:
        logger.exception(f"Failed to get filtered fics: {e}")
        return []


def get_fic_by_url(url: str) -> sqlite3.Row | None:
    """Recupera una singola fic e i suoi tag utente tramite URL."""
    query = """
        SELECT f.*, GROUP_CONCAT(ut.name, ', ') AS user_tags
        FROM fics f
        LEFT JOIN fic_tags ft ON f.url = ft.fic_url
        LEFT JOIN user_tags ut ON ft.tag_id = ut.tag_id
        WHERE f.url = ?
        GROUP BY f.url
    """
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(query, (url,))
            return c.fetchone()
    except sqlite3.Error as e:
        logger.exception(f"Failed to get fic by URL {url}: {e}")
        return None


def delete_fic(url: str) -> None:
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("DELETE FROM fics WHERE url = ?", (url,))
    except sqlite3.Error as e:
        logger.exception(f"Failed to delete fic {url}: {e}")


def update_fic_notes(url: str, notes: str) -> None:
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("UPDATE fics SET user_notes = ? WHERE url = ?", (notes, url))
    except sqlite3.Error as e:
        logger.exception(f"Failed to update notes for fic {url}: {e}")


def update_fic_rating(url: str, rating: int) -> None:
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("UPDATE fics SET user_rating = ? WHERE url = ?", (rating, url))
    except sqlite3.Error as e:
        logger.exception(f"Failed to update rating for fic {url}: {e}")


def create_user_tag(name: str) -> int | None:
    """
    Crea un nuovo tag utente nel database.
    Restituisce l'ID del nuovo tag se creato con successo.
    Restituisce None se il tag esiste già.
    """
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO user_tags (name) VALUES (?)", (name,))
            return c.lastrowid
    except sqlite3.IntegrityError:
        logger.warning(f"Attempted to create a duplicate tag: '{name}'")
        return None
    except sqlite3.Error as e:
        logger.exception(f"Failed to create user tag '{name}': {e}")
        return None


def get_or_create_tag(name: str) -> int | None:
    """
    Tenta di creare un tag. Se esiste già, ne recupera l'ID.
    Restituisce l'ID del tag in ogni caso.
    """
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            try:
                c.execute("INSERT INTO user_tags (name) VALUES (?)", (name,))
                return c.lastrowid
            except sqlite3.IntegrityError:
                c.execute("SELECT tag_id FROM user_tags WHERE name = ?", (name,))
                result = c.fetchone()
                return result[0] if result else None
    except sqlite3.Error as e:
        logger.exception(f"Failed to get or create tag '{name}': {e}")
        return None


def get_all_user_tags() -> List[Tuple[int, str]]:
    """Recupera tutti i tag utente dal database, ordinati per nome."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT tag_id, name FROM user_tags ORDER BY name ASC")
            return c.fetchall()
    except sqlite3.Error as e:
        logger.exception(f"Failed to get all user tags: {e}")
        return []


def assign_tag_to_fic(fic_url: str, tag_id: int) -> None:
    """Associa un tag a una fic nella tabella di collegamento."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT OR IGNORE INTO fic_tags (fic_url, tag_id) VALUES (?, ?)", (fic_url, tag_id))
    except sqlite3.Error as e:
        logger.exception(f"Failed to assign tag_id {tag_id} to fic {fic_url}: {e}")


def get_tags_for_fic(fic_url: str) -> List[Tuple[int, str]]:
    """
    Recupera tutti i tag associati a una specifica fic, unendo le tabelle.
    """
    query = """
        SELECT ut.tag_id, ut.name
        FROM user_tags ut
        JOIN fic_tags ft ON ut.tag_id = ft.tag_id
        WHERE ft.fic_url = ?
        ORDER BY ut.name ASC
    """
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute(query, (fic_url,))
            return c.fetchall()
    except sqlite3.Error as e:
        logger.exception(f"Failed to get tags for fic {fic_url}: {e}")
        return []


def remove_tag_from_fic(fic_url: str, tag_id: int) -> None:
    """Rimuove un'associazione tra una fic e un tag."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("DELETE FROM fic_tags WHERE fic_url = ? AND tag_id = ?", (fic_url, tag_id))
    except sqlite3.Error as e:
        logger.exception(f"Failed to remove tag_id {tag_id} from fic {fic_url}: {e}")


def delete_user_tag(tag_id: int) -> None:
    """
    Cancella un tag dalla tabella user_tags.
    Grazie a ON DELETE CASCADE, questo cancellerà anche tutte le sue associazioni.
    """
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("DELETE FROM user_tags WHERE tag_id = ?", (tag_id,))
    except sqlite3.Error as e:
        logger.exception(f"Failed to delete tag_id {tag_id}: {e}")


def add_notification(msg: str, url: str | None = None) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(
                "INSERT INTO notifications (message, timestamp, related_url, is_read) VALUES (?, ?, ?, 0)",
                (msg, ts, url),
            )
    except sqlite3.Error as e:
        logger.exception(f"Failed to add notification: {e}")


def get_unread_notifications() -> List[sqlite3.Row]:
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute("SELECT * FROM notifications WHERE is_read = 0 ORDER BY timestamp DESC").fetchall()
    except sqlite3.Error as e:
        logger.exception(f"Failed to get unread notifications: {e}")
        return []


def mark_notifications_as_read() -> None:
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("UPDATE notifications SET is_read = 1 WHERE is_read = 0")
    except sqlite3.Error as e:
        logger.exception(f"Failed to mark notifications as read: {e}")


def count_read_uncommented_fics() -> int:
    try:
        with sqlite3.connect(DB_NAME) as conn:
            return conn.execute("SELECT COUNT(*) FROM fics WHERE status = ?", (const.STATUS_READ,)).fetchone()[0]
    except sqlite3.Error as e:
        logger.exception(f"Failed to count read/uncommented fics: {e}")
        return 0


def get_fics_to_update() -> List[sqlite3.Row]:
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute("SELECT url, word_count FROM fics WHERE is_complete = 0").fetchall()
    except sqlite3.Error as e:
        logger.exception(f"Failed to get fics to update: {e}")
        return []


def update_fic_data(url: str, data: Dict[str, Any]) -> None:
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(
                "UPDATE fics SET word_count = ?, is_complete = ? WHERE url = ?",
                (data["word_count"], 1 if data.get("is_complete", False) else 0, url),
            )
    except sqlite3.Error as e:
        logger.exception(f"Failed to update fic data for {url}: {e}")


def get_existing_urls() -> Set[str]:
    try:
        with sqlite3.connect(DB_NAME) as conn:
            return {r[0] for r in conn.execute("SELECT url FROM fics").fetchall()}
    except sqlite3.Error as e:
        logger.exception(f"Failed to get existing URLs: {e}")
        return set()


def calculate_base_stats() -> Dict[str, int]:
    stats = {}
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            stats["total_fics"] = c.execute("SELECT COUNT(*) FROM fics").fetchone()[0]
            stats["fics_read"] = c.execute(
                "SELECT COUNT(*) FROM fics WHERE status = ?", (const.STATUS_READ,)
            ).fetchone()[0]
            stats["fics_commented"] = c.execute(
                "SELECT COUNT(*) FROM fics WHERE status = ?", (const.STATUS_COMMENTED,)
            ).fetchone()[0]
            stats["fics_to_read"] = c.execute(
                "SELECT COUNT(*) FROM fics WHERE status = ?", (const.STATUS_TO_READ,)
            ).fetchone()[0]
            stats["fics_dropped"] = c.execute(
                "SELECT COUNT(*) FROM fics WHERE status = ?", (const.STATUS_DROPPED,)
            ).fetchone()[0]

            words_query = (
                f"SELECT SUM(word_count) FROM fics WHERE status IN ({','.join('?' for _ in const.COMPLETED_STATUSES)})"
            )
            words = c.execute(words_query, const.COMPLETED_STATUSES).fetchone()[0]
            stats["total_words_read"] = words if words else 0
    except sqlite3.Error as e:
        logger.exception(f"Failed to calculate base stats: {e}")
    return stats


def get_data_for_charts(chart_filter: str = "lette") -> Dict[str, List[Tuple[str, int]]]:
    data: Dict[str, Any] = {"top_fandoms": {}, "top_ratings": {}, "status_breakdown": {}, "top_categories": {}}
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            where_clause = (
                f"WHERE status IN ({','.join('?' for _ in const.COMPLETED_STATUSES)})"
                if chart_filter == "lette"
                else ""
            )
            params = const.COMPLETED_STATUSES if chart_filter == "lette" else []
            filtered_rows = c.execute(f"SELECT fandoms, rating, category FROM fics {where_clause}", params).fetchall()
            all_rows = c.execute("SELECT status FROM fics").fetchall()
            for row in filtered_rows:
                if row["fandoms"]:
                    [
                        data["top_fandoms"].update({i: data["top_fandoms"].get(i, 0) + 1})
                        for i in [x.strip() for x in row["fandoms"].split(",")]
                        if i
                    ]
                if row["rating"]:
                    [
                        data["top_ratings"].update({i: data["top_ratings"].get(i, 0) + 1})
                        for i in [x.strip() for x in row["rating"].split(",")]
                        if i
                    ]
                if row["category"]:
                    [
                        data["top_categories"].update({i: data["top_categories"].get(i, 0) + 1})
                        for i in [x.strip() for x in row["category"].split(",")]
                        if i
                    ]
            for row in all_rows:
                if row["status"]:
                    data["status_breakdown"][row["status"]] = data["status_breakdown"].get(row["status"], 0) + 1
    except sqlite3.Error as e:
        logger.exception(f"Failed to get data for charts: {e}")

    return {
        "top_fandoms": sorted(data["top_fandoms"].items(), key=lambda x: x[1], reverse=True)[:5],
        "top_ratings": sorted(data["top_ratings"].items(), key=lambda x: x[1], reverse=True),
        "status_breakdown": sorted(data["status_breakdown"].items(), key=lambda x: x[1], reverse=True),
        "top_categories": sorted(data["top_categories"].items(), key=lambda x: x[1], reverse=True),
    }


def get_frequencies_for_wordclouds(cloud_filter: str = "lette") -> Dict[str, Dict[str, int]]:
    freq: Dict[str, Dict[str, int]] = {"tags": {}, "relationships": {}, "characters": {}}
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            where_clause = (
                f"WHERE status IN ({','.join('?' for _ in const.COMPLETED_STATUSES)})"
                if cloud_filter == "lette"
                else ""
            )
            params = const.COMPLETED_STATUSES if cloud_filter == "lette" else []
            rows = c.execute(
                f"SELECT tags, relationships, characters FROM fics {where_clause}",
                params,
            ).fetchall()
            for row in rows:
                if row["tags"]:
                    [
                        freq["tags"].update({i: freq["tags"].get(i, 0) + 1})
                        for i in [x.strip() for x in row["tags"].split(",")]
                        if i
                    ]
                if row["relationships"]:
                    [
                        freq["relationships"].update({i: freq["relationships"].get(i, 0) + 1})
                        for i in [x.strip() for x in row["relationships"].split(",")]
                        if i
                    ]
                if row["characters"]:
                    [
                        freq["characters"].update({i: freq["characters"].get(i, 0) + 1})
                        for i in [x.strip() for x in row["characters"].split(",")]
                        if i
                    ]
    except sqlite3.Error as e:
        logger.exception(f"Failed to get frequencies for word clouds: {e}")
    return freq


def get_data_for_publication_year_chart(chart_filter: str = "lette") -> List[Tuple[str, int]]:
    """
    Aggrega il numero di opere per anno di pubblicazione.

    Args:
        chart_filter: "lette" per le sole opere completate, "tutte" per tutte le opere.

    Returns:
        Una lista di tuple (anno, numero_di_opere), ordinata per anno.
    """

    where_clause = ""
    params = []

    if chart_filter == "lette":
        completed_statuses_placeholders = ",".join("?" for _ in const.COMPLETED_STATUSES)
        where_clause = f"WHERE status IN ({completed_statuses_placeholders})"
        params = list(const.COMPLETED_STATUSES)

    query = f"""
        SELECT
            strftime('%Y', date_published) as year,
            COUNT(url) as total_fics
        FROM fics
        {where_clause}
        GROUP BY year
        HAVING year IS NOT NULL
        ORDER BY year ASC
    """

    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute(query, params)
            return c.fetchall()

    except sqlite3.Error as e:
        logger.exception(f"Failed to get data for publication year chart: {e}")
        return []


def rename_user_tag(tag_id: int, new_name: str) -> bool:
    """
    Rinomina un tag utente esistente.
    Restituisce True se l'operazione ha successo.
    Restituisce False se il nuovo nome esiste già (violazione di UNIQUE).
    """
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("UPDATE user_tags SET name = ? WHERE tag_id = ?", (new_name, tag_id))
            return True
    except sqlite3.IntegrityError:
        logger.warning(f"Failed to rename tag_id {tag_id} to '{new_name}' because it already exists.")
        return False
    except sqlite3.Error as e:
        logger.exception(f"Failed to rename tag_id {tag_id}: {e}")
        return False


def get_fics_for_sync() -> List[sqlite3.Row]:
    """
    Recupera tutte le fic che non sono nello stato 'Commented',
    ideali per una sincronizzazione di massa dello stato.
    Restituisce solo i campi necessari (url, title, status) per efficienza.
    """
    statuses_to_check = (
        const.STATUS_TO_READ,
        const.STATUS_READ,
        const.STATUS_KUDOSED,
    )
    query = f"""
        SELECT url, title, status
        FROM fics
        WHERE status IN ({",".join("?" for _ in statuses_to_check)})
    """
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(query, statuses_to_check)
            return c.fetchall()
    except sqlite3.Error as e:
        logger.exception(f"Failed to get fics for sync: {e}")
        return []


def bulk_update_status(urls: List[str], new_status: str) -> None:
    """Aggiorna lo stato per una lista di URL in una singola transazione."""
    if not urls:
        return
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            placeholders = ",".join("?" for _ in urls)
            query = f"UPDATE fics SET status = ? WHERE url IN ({placeholders})"
            params = [new_status] + urls
            c.execute(query, params)
        logger.info(f"Bulk updated status to '{new_status}' for {len(urls)} fics.")
    except sqlite3.Error as e:
        logger.exception(f"Failed to bulk update status for {len(urls)} fics: {e}")


def bulk_add_tags(urls: List[str], tags_to_add: List[str]) -> None:
    """Associa una lista di tag a una lista di fic."""
    if not urls or not tags_to_add:
        return
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            tag_ids = [get_or_create_tag(tag_name) for tag_name in tags_to_add]
            valid_tag_ids = [tid for tid in tag_ids if tid is not None]

            associations = [(url, tag_id) for url in urls for tag_id in valid_tag_ids]

            c.executemany("INSERT OR IGNORE INTO fic_tags (fic_url, tag_id) VALUES (?, ?)", associations)
        logger.info(f"Bulk added tags {tags_to_add} to {len(urls)} fics.")
    except sqlite3.Error as e:
        logger.exception(f"Failed to bulk add tags for {len(urls)} fics: {e}")


def bulk_remove_tags(urls: List[str], tags_to_remove: List[str]) -> None:
    """Rimuove l'associazione di una lista di tag da una lista di fic."""
    if not urls or not tags_to_remove:
        return
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            tag_placeholders = ",".join("?" for _ in tags_to_remove)
            c.execute(f"SELECT tag_id FROM user_tags WHERE name IN ({tag_placeholders})", tags_to_remove)
            tag_ids_to_remove = [row[0] for row in c.fetchall()]

            if not tag_ids_to_remove:
                return

            url_placeholders = ",".join("?" for _ in urls)
            tag_id_placeholders = ",".join("?" for _ in tag_ids_to_remove)

            query = f"DELETE FROM fic_tags WHERE fic_url IN ({url_placeholders}) AND tag_id IN ({tag_id_placeholders})"
            params = urls + tag_ids_to_remove
            c.execute(query, params)
        logger.info(f"Bulk removed tags {tags_to_remove} from {len(urls)} fics.")
    except sqlite3.Error as e:
        logger.exception(f"Failed to bulk remove tags for {len(urls)} fics: {e}")
