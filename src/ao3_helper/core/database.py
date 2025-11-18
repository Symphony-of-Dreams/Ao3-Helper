import operator
import os
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import peewee
from peewee import JOIN, fn
from playhouse.shortcuts import model_to_dict

from ao3_helper import constants as const
from ao3_helper.core.models import (
    Achievement,
    Author,
    Category,
    Character,
    ContentTag,
    Fandom,
    Fic,
    FicAuthor,
    FicCategory,
    FicCharacter,
    FicContentTag,
    FicFandom,
    FicRelationship,
    FicTag,
    Notification,
    Relationship,
    SavedFilter,
    UserTag,
    db,
)
from ao3_helper.logger_setup import logger


def get_db_path_for_user(username: str) -> str:
    """
    Costruisce e restituisce il percorso del database per un dato utente.
    Crea la directory dei profili se non esiste.
    """
    if not username or username == const.CONFIG_DEFAULT_USER:
        username = "guest"

    os.makedirs(const.PROFILES_DIR, exist_ok=True)
    return os.path.join(const.PROFILES_DIR, f"{username}.db")


def run_database_migrations(db_path: str) -> None:
    """
    Assicura che lo schema del database sia aggiornato.
    1. Crea le nuove tabelle relazionali (Fase 2) se non esistono.
    2. Applica le vecchie migrazioni manuali (colonne legacy) se il DB è vecchio.
    """
    try:

        db.connect(reuse_if_open=True)

        all_models = [
            Fic,
            UserTag,
            FicTag,
            Notification,
            Achievement,
            SavedFilter,
            Author,
            Fandom,
            Character,
            Relationship,
            ContentTag,
            Category,
            FicAuthor,
            FicFandom,
            FicCharacter,
            FicRelationship,
            FicContentTag,
            FicCategory,
        ]

        db.create_tables(all_models, safe=True)

        logger.info("Database tables verification complete (V2 relational schema checked).")

        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                c = conn.cursor()

                try:
                    current_version = c.execute("PRAGMA user_version").fetchone()[0]
                except TypeError:
                    current_version = 0

                logger.info(
                    f"Checking legacy migrations. DB Version: {current_version} -> Target: {const.LATEST_DB_VERSION}"
                )

                if current_version < const.LATEST_DB_VERSION:

                    if current_version < 3:
                        columns_v3 = {
                            "series_name": "TEXT",
                            "series_url": "TEXT",
                            "series_part": "INTEGER",
                            "chapters": "TEXT",
                            "date_published": "TEXT",
                            "date_updated": "TEXT",
                            "source": "TEXT DEFAULT 'manual'",
                            "language": "TEXT",
                            "hits": "INTEGER",
                            "kudos": "INTEGER",
                            "bookmarks": "INTEGER",
                            "comments": "INTEGER",
                        }
                        for col, dtype in columns_v3.items():
                            try:
                                c.execute(f"ALTER TABLE fics ADD COLUMN {col} {dtype}")
                            except sqlite3.OperationalError:
                                pass

                    if current_version < 4:
                        cols_v4 = [
                            "is_in_library INTEGER DEFAULT 1",
                            "is_in_history INTEGER DEFAULT 0",
                            "last_visit_date TEXT",
                            "visit_count INTEGER",
                        ]
                        for col_def in cols_v4:
                            try:
                                c.execute(f"ALTER TABLE fics ADD COLUMN {col_def}")
                            except sqlite3.OperationalError:
                                pass

                    if current_version < 5:
                        cols_v5 = ["is_in_reading_queue INTEGER DEFAULT 0", "queue_order INTEGER"]
                        for col_def in cols_v5:
                            try:
                                c.execute(f"ALTER TABLE fics ADD COLUMN {col_def}")
                            except sqlite3.OperationalError:
                                pass

                    c.execute(f"PRAGMA user_version = {const.LATEST_DB_VERSION}")
                    logger.info("Database migration successful.")
                else:
                    logger.info("Database schema is up to date.")
        _migrate_legacy_data_to_v2()
    except Exception as e:
        logger.exception(f"A critical error occurred during database setup/migration: {e}")
        raise
    finally:
        if not db.is_closed():
            db.close()


def _migrate_legacy_data_to_v2() -> None:
    """
    Versione robusta: Controlla lo stato dei dati e migra se necessario.
    """
    try:
        logger.info("--- CONTROLLO STATO MIGRAZIONE DATI V2 ---")

        fic_count = Fic.select().count()

        v2_count = FicAuthor.select().count()

        logger.info(f"Diagnostica DB: {fic_count} Fics totali | {v2_count} Relazioni Autore (V2)")

        if fic_count > 0 and v2_count < fic_count:
            logger.warning(f"!!! RILEVATO SCHEMA V2 INCOMPLETO ({v2_count}/{fic_count}) !!! Avvio backfilling...")

            all_fics = Fic.select()
            count = 0

            with db.atomic():
                for fic in all_fics.iterator():
                    fic_data = model_to_dict(fic)

                    _sync_fic_relations(fic, fic_data)

                    count += 1
                    if count % 50 == 0:
                        logger.info(f"Backfilling in corso: elaborate {count}/{fic_count}...")

            logger.info(f"✅ Migrazione V2 completata! {count} fics processate.")
        else:
            logger.info("✅ Schema V2 già allineato. Nessuna migrazione necessaria.")

    except Exception as e:
        logger.exception(f"Errore critico durante la migrazione dati V2: {e}")


def _sync_fic_relations(fic_instance: Fic, fic_data: Dict[str, Any]) -> None:
    """
    Helper function to populate the normalized Many-to-Many tables (Phase 2).
    It handles Authors, Fandoms, Tags, Relationships, Characters, Categories.
    """
    try:

        relations_map = [
            ("authors", Author, FicAuthor, "author"),
            ("fandoms", Fandom, FicFandom, "fandom"),
            ("tags", ContentTag, FicContentTag, "tag"),
            ("relationships", Relationship, FicRelationship, "relationship"),
            ("characters", Character, FicCharacter, "character"),
            ("categories", Category, FicCategory, "category"),
        ]

        for key, EntityModel, JunctionModel, junction_field_name in relations_map:
            items = fic_data.get(key)

            if not items:
                legacy_key = key[:-1] if key.endswith("s") else key
                if key == "categories":
                    legacy_key = "category"
                items = fic_data.get(legacy_key)

            if isinstance(items, str):
                items = [x.strip() for x in items.split(",") if x.strip()]

            if not items or not isinstance(items, list):
                continue

            for item_name in items:
                if not item_name or not isinstance(item_name, str):
                    continue

                entity, _ = EntityModel.get_or_create(name=item_name)
                junction_kwargs = {"fic": fic_instance, junction_field_name: entity}
                JunctionModel.get_or_create(**junction_kwargs)

    except Exception as e:
        logger.error(f"Failed to sync relations for fic {fic_instance.title}: {e}")


def add_fic(fic_details: Any) -> Tuple[bool, str]:
    """
    Adds a new fic to the database using the Peewee ORM.
    Accepts either a Dictionary (legacy) or FicDTO (new).
    Populates both Legacy Columns and New Relational Tables.
    """

    if is_dataclass(fic_details):
        dto = fic_details
        fic_details = asdict(dto)

        fic_details["author"] = ", ".join(dto.authors)
        fic_details["fandoms"] = ", ".join(dto.fandoms)
        fic_details["tags"] = ", ".join(dto.tags)
        fic_details["relationships"] = ", ".join(dto.relationships)
        fic_details["characters"] = ", ".join(dto.characters)
        fic_details["category"] = ", ".join(dto.categories)

        total = str(dto.expected_chapters) if dto.expected_chapters else "?"
        fic_details["chapters"] = f"{dto.chapter_count}/{total}"

        if not fic_details.get("source"):
            fic_details["source"] = "manual"

    try:

        fic_data_for_model = {
            "url": fic_details.get("url"),
            "title": fic_details.get("title"),
            "author": fic_details.get("author"),
            "fandoms": fic_details.get("fandoms"),
            "tags": fic_details.get("tags"),
            "rating": fic_details.get("rating"),
            "word_count": fic_details.get("word_count"),
            "summary": fic_details.get("summary"),
            "category": fic_details.get("category"),
            "relationships": fic_details.get("relationships"),
            "characters": fic_details.get("characters"),
            "is_complete": fic_details.get("is_complete", False),
            "series_name": fic_details.get("series_name"),
            "series_url": fic_details.get("series_url"),
            "series_part": fic_details.get("series_part"),
            "chapters": fic_details.get("chapters"),
            "date_published": fic_details.get("date_published"),
            "date_updated": fic_details.get("date_updated"),
            "source": fic_details.get("source", "manual"),
            "language": fic_details.get("language"),
            "hits": fic_details.get("hits"),
            "kudos": fic_details.get("kudos"),
            "bookmarks": fic_details.get("bookmarks"),
            "comments": fic_details.get("comments"),
            "is_in_library": True,
            "status": const.STATUS_TO_READ,
            "date_added": datetime.now(),
            "user_notes": "",
            "user_rating": 0,
            "status_verified": False,
        }

        new_fic = Fic.create(**fic_data_for_model)

        _sync_fic_relations(new_fic, fic_details)

        logger.info(f"Successfully added fic '{fic_data_for_model['title']}' using Peewee ORM.")
        return True, "created"

    except peewee.IntegrityError:
        logger.warning(f"Attempted to add a fic that already exists (ORM): {fic_details.get('url')}")
        return False, "exists"
    except Exception as e:
        logger.exception(f"Failed to add fic to database using ORM: {e}")
        return False, "error"


def add_or_update_fic_from_history(fic_details: Dict[str, Any]) -> Tuple[bool, Optional[Fic]]:
    """
    Adds a new fic from the history or updates an existing one with history data.
    Populates relational tables on creation.
    """
    fic_url = fic_details.get("url")
    if not fic_url:
        return (False, None)

    try:
        existing_fic = Fic.get_or_none(Fic.url == fic_url)

        if existing_fic:

            query = Fic.update(
                is_in_history=True,
                last_visit_date=fic_details.get("last_visit_date"),
                visit_count=fic_details.get("visit_count"),
            ).where(Fic.url == fic_url)

            rows_affected = query.execute()

            if rows_affected > 0:
                logger.info(f"Updated existing fic '{existing_fic.title}' with history data.")
                return (False, existing_fic)
            return (False, None)

        else:

            fic_data_for_model = {
                "url": fic_details.get("url"),
                "title": fic_details.get("title"),
                "author": fic_details.get("author"),
                "fandoms": fic_details.get("fandoms"),
                "tags": fic_details.get("tags"),
                "rating": fic_details.get("rating"),
                "word_count": fic_details.get("word_count"),
                "summary": fic_details.get("summary"),
                "category": fic_details.get("category"),
                "relationships": fic_details.get("relationships"),
                "characters": fic_details.get("characters"),
                "is_complete": fic_details.get("is_complete", False),
                "series_name": fic_details.get("series_name"),
                "series_url": fic_details.get("series_url"),
                "series_part": fic_details.get("series_part"),
                "chapters": fic_details.get("chapters"),
                "date_published": fic_details.get("date_published"),
                "date_updated": fic_details.get("date_updated"),
                "source": "history",
                "language": fic_details.get("language"),
                "hits": fic_details.get("hits"),
                "kudos": fic_details.get("kudos"),
                "bookmarks": fic_details.get("bookmarks"),
                "comments": fic_details.get("comments"),
                "is_in_library": False,
                "is_in_history": True,
                "last_visit_date": fic_details.get("last_visit_date"),
                "visit_count": fic_details.get("visit_count"),
                "status": const.STATUS_READ,
                "date_added": datetime.now(),
                "user_notes": "",
                "user_rating": 0,
                "status_verified": False,
            }

            new_fic = Fic.create(**fic_data_for_model)

            _sync_fic_relations(new_fic, fic_details)

            logger.info(f"Created new fic '{fic_data_for_model['title']}' from history.")
            return (True, new_fic)

    except Exception as e:
        logger.exception(f"Failed to add or update fic from history for URL {fic_url}: {e}")
        return (False, None)


def update_fic_status(url: str, new_status: str, verified: int = 0) -> None:
    """Updates the status of a fic using the Peewee ORM."""
    try:

        fic_to_update = Fic.get(Fic.url == url)

        fic_to_update.status = new_status

        fic_to_update.status_verified = bool(verified)

        fic_to_update.save()

    except Fic.DoesNotExist:

        logger.error(f"Attempted to update status for a non-existent fic URL: {url}")
    except Exception as e:
        logger.exception(f"Failed to update fic status for {url} using ORM: {e}")


def unlock_achievement(achievement_id: str) -> None:
    """
    Unlocks an achievement using the Peewee ORM.
    Uses get_or_create to be robust and idempotent.
    """
    try:
        ts = datetime.now().strftime("%Y-%m-%d")

        Achievement.get_or_create(id=achievement_id, defaults={"unlocked_date": ts})
    except Exception as e:
        logger.exception(f"Failed to unlock achievement {achievement_id} using ORM: {e}")


def get_unlocked_achievements() -> Dict[str, str]:
    """Retrieves all unlocked achievements as a dictionary using the Peewee ORM."""
    try:

        achievements_query = Achievement.select().dicts()
        return {ach["id"]: ach["unlocked_date"] for ach in achievements_query}
    except Exception as e:
        logger.exception(f"Failed to get unlocked achievements using ORM: {e}")
        return {}


def count_verified_statuses() -> Dict[str, int]:
    counts = {"kudos": 0, "comments": 0}
    db_path = db.database
    try:
        with sqlite3.connect(db_path) as conn:
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


def get_filtered_fics(
    view_filter: str = "library",
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves fics based on a structured filter object.

    Args:
        view_filter: "library", "history", "inbox", or "all".
        filters: A dictionary representing the complex search query.
    """
    try:
        query = Fic.select()

        if view_filter == "library":
            query = query.where(Fic.is_in_library)
        elif view_filter == "history":
            query = query.where(Fic.is_in_history)
        elif view_filter == "inbox":
            query = query.where((Fic.is_in_history) & (not Fic.is_in_library))

        if not filters:
            filters = {}

        conditions = filters.get("conditions", {})
        search_all_term = conditions.pop("all", None)
        for field, value in conditions.items():
            if hasattr(Fic, field) and value:
                query = query.where(getattr(Fic, field).contains(value))
        if search_all_term:
            term = search_all_term
            fics_with_user_tag = Fic.select(Fic.url).join(FicTag).join(UserTag).where(UserTag.name.contains(term))

            or_clauses = [
                (Fic.title.contains(term)),
                (Fic.author.contains(term)),
                (Fic.fandoms.contains(term)),
                (Fic.tags.contains(term)),
                (Fic.series_name.contains(term)),
                (Fic.url.in_(fics_with_user_tag)),
            ]
            query = query.where(peewee.reduce(operator.or_, or_clauses))

        tags_filter = filters.get("tags", {})

        for tag in tags_filter.get("and", []):
            query = query.where(Fic.tags.contains(tag))

        for tag in tags_filter.get("not", []):
            query = query.where(~Fic.tags.contains(tag))

        or_tags = tags_filter.get("or", [])
        if or_tags:
            or_clauses = [(Fic.tags.contains(tag)) for tag in or_tags]
            query = query.where(peewee.reduce(operator.or_, or_clauses))

        user_tags_filter = filters.get("user_tags", {})

        for tag_name in user_tags_filter.get("and", []):
            fics_with_tag = Fic.select(Fic.url).join(FicTag).join(UserTag).where(UserTag.name == tag_name)
            query = query.where(Fic.url.in_(fics_with_tag))

        final_query = (
            query.select(Fic, fn.GROUP_CONCAT(UserTag.name, ", ").alias("user_tags"))
            .join(FicTag, JOIN.LEFT_OUTER, on=(Fic.url == FicTag.fic))
            .join(UserTag, JOIN.LEFT_OUTER, on=(FicTag.tag == UserTag.tag_id))
            .group_by(Fic.url)
            .order_by(Fic.date_added.desc())
        )

        results = []
        for fic_model in final_query.iterator():
            fic_dict = model_to_dict(fic_model)
            fic_dict["user_tags"] = fic_model.user_tags
            results.append(fic_dict)

        return results

    except Exception as e:
        logger.exception(f"Failed to get filtered fics using ORM: {e}")
        return []


def get_fic_by_url(url: str) -> Dict[str, Any] | None:
    """
    Retrieves a single fic and its user tags by URL using the Peewee ORM.
    This function is designed to be a drop-in replacement for the raw SQL version,
    returning a dictionary for backward compatibility. It now ensures the 'user_tags'
    key is always present.
    """
    try:
        query = (
            Fic.select(Fic, fn.GROUP_CONCAT(UserTag.name, ", ").alias("user_tags"))
            .join(FicTag, JOIN.LEFT_OUTER, on=(Fic.url == FicTag.fic))
            .join(UserTag, JOIN.LEFT_OUTER, on=(FicTag.tag == UserTag.tag_id))
            .where(Fic.url == url)
            .group_by(Fic.url)
        )

        fic_model = query.get()

        fic_dict = model_to_dict(fic_model)

        fic_dict["user_tags"] = fic_model.user_tags

        return fic_dict

    except Fic.DoesNotExist:
        logger.warning(f"ORM query for URL {url} returned no results.")
        return None
    except Exception as e:
        logger.exception(f"Failed to get fic by URL {url} using ORM: {e}")
        return None


def delete_fic(url: str) -> None:
    """Deletes a fic from the database using the Peewee ORM."""
    try:

        fic_to_delete = Fic.get(Fic.url == url)

        fic_to_delete.delete_instance()

    except Fic.DoesNotExist:

        logger.warning(f"Attempted to delete a non-existent fic URL: {url}")
    except Exception as e:
        logger.exception(f"Failed to delete fic {url} using ORM: {e}")


def update_fic_notes(url: str, notes: str) -> None:
    """Updates the notes for a fic using the Peewee ORM."""
    try:
        fic_to_update = Fic.get(Fic.url == url)
        fic_to_update.user_notes = notes
        fic_to_update.save()
    except Fic.DoesNotExist:
        logger.error(f"Attempted to update notes for a non-existent fic URL: {url}")
    except Exception as e:
        logger.exception(f"Failed to update notes for fic {url} using ORM: {e}")


def update_fic_rating(url: str, rating: int) -> None:
    """Updates the rating for a fic using the Peewee ORM."""
    try:
        fic_to_update = Fic.get(Fic.url == url)
        fic_to_update.user_rating = rating
        fic_to_update.save()
    except Fic.DoesNotExist:
        logger.error(f"Attempted to update rating for a non-existent fic URL: {url}")
    except Exception as e:
        logger.exception(f"Failed to update rating for fic {url} using ORM: {e}")


def set_fic_in_library(url: str) -> None:
    """Imposta il flag is_in_library a True per una data fic."""
    try:
        query = Fic.update(is_in_library=True).where(Fic.url == url)
        query.execute()
        logger.info(f"Fic {url} has been marked as 'in library'.")
    except Exception as e:
        logger.exception(f"Failed to set fic {url} as 'in library': {e}")


def create_user_tag(name: str) -> int | None:

    try:
        tag, created = UserTag.get_or_create(name=name)
        if created:
            return tag.tag_id
        else:
            logger.warning(f"Attempted to create a duplicate tag: '{name}'")
            return None
    except Exception as e:
        logger.exception(f"Failed to create user tag '{name}' using ORM: {e}")
        return None


def get_or_create_tag(name: str) -> int | None:
    """
    Tries to create a tag. If it already exists, retrieves its ID using Peewee.
    Returns the tag's ID in either case.
    """
    try:

        tag_instance, created = UserTag.get_or_create(name=name)
        if created:
            logger.info(f"Created new user tag '{name}' with id {tag_instance.tag_id}.")
        return tag_instance.tag_id
    except Exception as e:
        logger.exception(f"Failed to get or create tag '{name}' using ORM: {e}")
        return None


def get_all_user_tags() -> List[Tuple[int, str]]:
    """Retrieves all user tags from the database using the Peewee ORM."""
    try:

        query = UserTag.select(UserTag.tag_id, UserTag.name).order_by(UserTag.name.asc())
        return list(query.tuples().iterator())
    except Exception as e:
        logger.exception(f"Failed to get all user tags using ORM: {e}")
        return []


def assign_tag_to_fic(fic_url: str, tag_id: int) -> None:
    """Associates a tag with a fic in the junction table using Peewee."""
    try:

        FicTag.get_or_create(fic=fic_url, tag=tag_id)
    except Exception as e:
        logger.exception(f"Failed to assign tag_id {tag_id} to fic {fic_url} using ORM: {e}")


def get_tags_for_fic(fic_url: str) -> List[Tuple[int, str]]:
    """Retrieves all tags associated with a specific fic using Peewee joins."""
    try:
        query = (
            UserTag.select(UserTag.tag_id, UserTag.name)
            .join(FicTag, on=(UserTag.tag_id == FicTag.tag))
            .join(Fic, on=(FicTag.fic == Fic.url))
            .where(Fic.url == fic_url)
            .order_by(UserTag.name.asc())
        )
        return list(query.tuples().iterator())
    except Exception as e:
        logger.exception(f"Failed to get tags for fic {fic_url} using ORM: {e}")
        return []


def remove_tag_from_fic(fic_url: str, tag_id: int) -> None:
    """Removes an association between a fic and a tag using Peewee."""
    try:

        query = FicTag.delete().where((FicTag.fic == fic_url) & (FicTag.tag == tag_id))
        query.execute()
    except Exception as e:
        logger.exception(f"Failed to remove tag_id {tag_id} from fic {fic_url} using ORM: {e}")


def delete_user_tag(tag_id: int) -> None:
    """Deletes a tag from the user_tags table using the Peewee ORM."""
    try:
        tag_to_delete = UserTag.get_by_id(tag_id)

        tag_to_delete.delete_instance()
    except UserTag.DoesNotExist:
        logger.warning(f"Attempted to delete a non-existent tag_id: {tag_id}")
    except Exception as e:
        logger.exception(f"Failed to delete tag_id {tag_id} using ORM: {e}")


def add_notification(msg: str, url: str | None = None) -> None:
    """Adds a new notification to the database using the Peewee ORM."""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        Notification.create(message=msg, timestamp=ts, related_url=url, is_read=False)
    except Exception as e:
        logger.exception(f"Failed to add notification using ORM: {e}")


def get_unread_notifications() -> List[Dict[str, Any]]:
    """Retrieves all unread notifications using the Peewee ORM."""
    try:
        query = Notification.select().where(~Notification.is_read).order_by(Notification.timestamp.desc())

        return [model_to_dict(n) for n in query]
    except Exception as e:
        logger.exception(f"Failed to get unread notifications using ORM: {e}")
        return []


def mark_notifications_as_read() -> None:
    """Marks all unread notifications as read using the Peewee ORM."""
    try:
        query = Notification.update(is_read=True).where(~Notification.is_read)
        query.execute()
    except Exception as e:
        logger.exception(f"Failed to mark notifications as read using ORM: {e}")


def count_read_uncommented_fics() -> int:
    db_path = db.database
    try:
        with sqlite3.connect(db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM fics WHERE status = ?", (const.STATUS_READ,)).fetchone()[0]
    except sqlite3.Error as e:
        logger.exception(f"Failed to count read/uncommented fics: {e}")
        return 0


def get_fics_to_update() -> List[Dict[str, Any]]:
    """
    Retrieves fics that are not marked as complete for the update check worker.
    Returns a list of dictionaries for compatibility with the worker.
    """
    try:
        query = Fic.select(Fic.url, Fic.word_count).where(~Fic.is_complete).dicts()
        return list(query)
    except Exception as e:
        logger.exception(f"Failed to get fics to update using ORM: {e}")
        return []


def update_fic_data(url: str, data: Dict[str, Any]) -> None:
    """Updates a fic's data after a successful update check, using Peewee ORM."""
    try:
        query = Fic.update(word_count=data.get("word_count"), is_complete=bool(data.get("is_complete", False))).where(
            Fic.url == url
        )
        query.execute()
    except Exception as e:
        logger.exception(f"Failed to update fic data for {url} using ORM: {e}")


def get_existing_urls() -> Set[str]:
    db_path = db.database
    try:
        with sqlite3.connect(db_path) as conn:
            return {r[0] for r in conn.execute("SELECT url FROM fics").fetchall()}
    except sqlite3.Error as e:
        logger.exception(f"Failed to get existing URLs: {e}")
        return set()


def get_latest_history_date() -> str | None:
    """
    Retrieves the most recent 'last_visit_date' from all fics marked as being in the user's history.

    Returns:
        The latest date as a 'YYYY-MM-DD' string, or None if no history entries exist.
    """
    try:

        latest_date = Fic.select(fn.MAX(Fic.last_visit_date)).where(Fic.is_in_history).scalar()
        return latest_date
    except Exception as e:
        logger.exception(f"Failed to get the latest history date using ORM: {e}")
        return None


def calculate_base_stats() -> Dict[str, int]:

    stats = {
        "total_fics": 0,
        "fics_read": 0,
        "fics_commented": 0,
        "fics_to_read": 0,
        "fics_dropped": 0,
        "total_words_read": 0,
    }
    try:
        stats["total_fics"] = Fic.select().count()
        stats["fics_read"] = Fic.select().where(Fic.status == const.STATUS_READ).count()
        stats["fics_commented"] = Fic.select().where(Fic.status == const.STATUS_COMMENTED).count()
        stats["fics_to_read"] = Fic.select().where(Fic.status == const.STATUS_TO_READ).count()
        stats["fics_dropped"] = Fic.select().where(Fic.status == const.STATUS_DROPPED).count()

        words_query = Fic.select(fn.SUM(Fic.word_count)).where(Fic.status.in_(const.COMPLETED_STATUSES)).scalar()
        stats["total_words_read"] = words_query or 0

    except Exception as e:
        logger.exception(f"Failed to calculate base stats using ORM: {e}")
    return stats


def get_data_for_charts(chart_filter: str = "lette") -> Dict[str, List[Tuple[str, int]]]:
    data: Dict[str, Any] = {"top_fandoms": {}, "top_ratings": {}, "status_breakdown": {}, "top_categories": {}}
    db_path = db.database
    try:
        with sqlite3.connect(db_path) as conn:
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
    db_path = db.database
    try:
        with sqlite3.connect(db_path) as conn:
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

    db_path = db.database
    try:
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute(query, params)
            return c.fetchall()

    except sqlite3.Error as e:
        logger.exception(f"Failed to get data for publication year chart: {e}")
        return []


def rename_user_tag(tag_id: int, new_name: str) -> bool:
    """Renames an existing user tag using the Peewee ORM."""
    try:
        tag_to_rename = UserTag.get_by_id(tag_id)
        tag_to_rename.name = new_name
        tag_to_rename.save()
        return True
    except peewee.IntegrityError:

        logger.warning(f"Failed to rename tag_id {tag_id} to '{new_name}' because it already exists (ORM).")
        return False
    except UserTag.DoesNotExist:
        logger.error(f"Attempted to rename a non-existent tag_id: {tag_id}")
        return False
    except Exception as e:
        logger.exception(f"Failed to rename tag_id {tag_id} using ORM: {e}")
        return False


def get_fics_for_sync() -> List[Dict[str, Any]]:
    """
    Retrieves fics that may need a status sync (not yet commented).
    Returns a list of dictionaries for compatibility with the sync worker.
    """
    try:
        statuses_to_check = (
            const.STATUS_TO_READ,
            const.STATUS_READ,
            const.STATUS_KUDOSED,
        )
        query = Fic.select(Fic.url, Fic.title, Fic.status).where(Fic.status.in_(statuses_to_check)).dicts()
        return list(query)
    except Exception as e:
        logger.exception(f"Failed to get fics for sync using ORM: {e}")
        return []


def bulk_update_status(urls: List[str], new_status: str) -> None:
    """Aggiorna lo stato per una lista di URL in una singola transazione."""
    if not urls:
        return
    db_path = db.database
    try:
        with sqlite3.connect(db_path) as conn:
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
    db_path = db.database
    try:
        with sqlite3.connect(db_path) as conn:
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
    db_path = db.database
    try:
        with sqlite3.connect(db_path) as conn:
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


def get_reread_statistics(limit: int = 10) -> List[Dict[str, Any]]:

    try:
        query = (
            Fic.select(Fic.title, Fic.author, Fic.visit_count)
            .where((Fic.is_in_history) & (Fic.visit_count > 1))
            .order_by(Fic.visit_count.desc())
            .limit(limit)
            .dicts()
        )
        return list(query)
    except Exception as e:
        logger.exception(f"Failed to get reread statistics using ORM: {e}")
        return []


def get_activity_by_month(view_filter: str = "all", date_field: str = "date_added") -> List[Tuple[str, int]]:
    """
    Aggregates fic count per month based on a selectable date field and data filter.

    Args:
        view_filter: "all", "library", or "history". Defines which fics to include.
        date_field: "date_added", "date_updated", or "last_visit_date". Defines the date for grouping.

    Returns:
        A list of tuples (year-month, fic_count), sorted by month.
    """
    try:

        date_column_map = {
            "date_added": Fic.date_added,
            "date_updated": Fic.date_updated,
            "last_visit_date": Fic.last_visit_date,
        }

        selected_date_column = date_column_map.get(date_field, Fic.date_added)

        base_query = Fic.select(
            fn.strftime("%Y-%m", selected_date_column).alias("month_year"),
            fn.COUNT(Fic.url).alias("fic_count"),
        ).where(selected_date_column.is_null(False) & (selected_date_column != ""))

        if view_filter == "library":
            base_query = base_query.where(Fic.is_in_library)
        elif view_filter == "history":
            base_query = base_query.where(Fic.is_in_history)

        final_query = (
            base_query.group_by(fn.strftime("%Y-%m", selected_date_column))
            .order_by(fn.strftime("%Y-%m", selected_date_column).asc())
            .tuples()
        )

        return list(final_query)

    except Exception as e:
        logger.exception(f"Failed to get activity data for filter '{view_filter}' and date_field '{date_field}': {e}")
        return []


def add_fics_to_queue(urls: List[str]) -> None:
    """Adds a list of fics to the reading queue, placing them at the end."""
    if not urls:
        return
    try:

        max_order_query = Fic.select(fn.MAX(Fic.queue_order)).where(Fic.is_in_reading_queue)
        max_order = max_order_query.scalar() or 0

        with db.atomic():

            for i, url in enumerate(urls):
                new_order = max_order + i + 1
                query = Fic.update(is_in_reading_queue=True, queue_order=new_order).where(Fic.url == url)
                query.execute()

        logger.info(f"Added {len(urls)} fics to the reading queue.")

    except Exception as e:
        logger.exception(f"Failed to add fics to queue: {e}")


def remove_fics_from_queue(urls: List[str]) -> None:
    """Removes a list of fics from the reading queue."""
    if not urls:
        return
    try:
        query = Fic.update(is_in_reading_queue=False, queue_order=None).where(Fic.url.in_(urls))
        query.execute()
        logger.info(f"Removed {len(urls)} fics from the reading queue.")
    except Exception as e:
        logger.exception(f"Failed to remove fics from queue: {e}")


def get_reading_queue() -> List[Dict[str, Any]]:
    """Retrieves all fics in the reading queue, sorted by their order."""
    try:
        query = Fic.select().where(Fic.is_in_reading_queue).order_by(Fic.queue_order.asc()).dicts()
        return list(query)
    except Exception as e:
        logger.exception(f"Failed to retrieve reading queue: {e}")
        return []


def update_queue_order(updates: List[Tuple[str, int]]) -> None:
    """
    Updates the queue_order for a list of fics in a single transaction.
    Args:
        updates: A list of tuples, where each tuple is (fic_url, new_order_index).
    """
    if not updates:
        return
    try:
        with db.atomic():
            for url, order in updates:
                query = Fic.update(queue_order=order).where(Fic.url == url)
                query.execute()
        logger.info(f"Successfully updated queue order for {len(updates)} fics.")
    except Exception:
        logger.exception("Failed to update queue order.")


def save_filter(name: str, filter_data: str) -> None:
    """Saves a new filter to the database."""
    try:
        SavedFilter.create(name=name, filter_data=filter_data)
        logger.info(f"Saved new filter '{name}'.")
    except peewee.IntegrityError:
        logger.warning(f"A filter with the name '{name}' already exists.")
        raise
    except Exception:
        logger.exception(f"Failed to save filter '{name}'.")
        raise


def get_all_filters() -> List[Dict[str, Any]]:
    """Retrieves all saved filters from the database."""
    try:
        query = SavedFilter.select().order_by(SavedFilter.name.asc()).dicts()
        return list(query)
    except Exception:
        logger.exception("Failed to get all saved filters.")
        return []


def delete_filter(filter_id: int) -> None:
    """Deletes a saved filter by its ID."""
    try:
        query = SavedFilter.delete().where(SavedFilter.id == filter_id)
        query.execute()
        logger.info(f"Deleted filter with id {filter_id}.")
    except Exception:
        logger.exception(f"Failed to delete filter with id {filter_id}.")
