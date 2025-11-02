import pytest

from models import Achievement, Fic, FicTag, Notification, UserTag, db as peewee_db

MODELS = [Fic, UserTag, FicTag, Notification, Achievement]


@pytest.fixture
def db_connection():
    """
    Crea un database SQLite in-memory pulito per ogni test,
    lo inizializza con lo schema completo usando Peewee e lo collega
    all'istanza del database usata dall'applicazione.
    """

    peewee_db.init(":memory:")

    peewee_db.connect()
    peewee_db.create_tables(MODELS)

    yield

    peewee_db.drop_tables(MODELS)
    peewee_db.close()
