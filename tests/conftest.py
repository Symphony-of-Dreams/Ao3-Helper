import pytest

from models import Achievement, Fic, FicTag, Notification, UserTag, db as peewee_db

# Lista di tutti i modelli che usiamo. Necessario per Peewee.
MODELS = [Fic, UserTag, FicTag, Notification, Achievement]


@pytest.fixture
def db_connection():
    """
    Crea un database SQLite in-memory pulito per ogni test,
    lo inizializza con lo schema completo usando Peewee e lo collega
    all'istanza del database usata dall'applicazione.
    """
    # Inizializza l'oggetto database di Peewee per usare un db in memoria.
    # Il nome del file ':memory:' è uno standard di sqlite3.
    # Usiamo init() che è il metodo corretto.
    peewee_db.init(":memory:")

    # Collega l'istanza del database e crea le tabelle
    peewee_db.connect()
    peewee_db.create_tables(MODELS)

    yield  # Il test viene eseguito qui

    # Pulizia dopo il test
    peewee_db.drop_tables(MODELS)
    peewee_db.close()
