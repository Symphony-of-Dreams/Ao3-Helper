import peewee
import pytest

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
    db as peewee_db,
)

MODELS = [
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


@pytest.fixture
def db_connection():
    """
    Crea un database SQLite in-memory pulito con lo schema COMPLETO (V2).
    """
    test_db = peewee.SqliteDatabase(":memory:")
    peewee_db.initialize(test_db)

    if peewee_db.is_closed():
        peewee_db.connect()

    peewee_db.create_tables(MODELS)

    yield

    peewee_db.drop_tables(MODELS)
    if not peewee_db.is_closed():
        peewee_db.close()
