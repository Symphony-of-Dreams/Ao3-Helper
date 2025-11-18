import keyring
from keyring.errors import NoKeyringError

from ao3_helper.logger_setup import logger

SERVICE_NAME = "ao3_helper"


def set_password(username: str, password: str) -> None:
    """
    Salva in modo sicuro la password dell'utente nel portachiavi del sistema operativo.
    """
    if not username:
        logger.warning("Attempted to set a password with no associated username.")
        return

    if not password:
        delete_password(username)
        return

    try:
        keyring.set_password(SERVICE_NAME, username, password)
        logger.info(f"Password for user '{username}' securely stored in the system keyring.")
    except NoKeyringError:
        logger.error("Keyring backend not found. Password cannot be stored securely.")
    except Exception:
        logger.exception(f"An unexpected error occurred while storing the password for '{username}'.")


def get_password(username: str) -> str | None:
    """
    Recupera in modo sicuro la password dell'utente dal portachiavi del sistema operativo.
    """
    if not username:
        return None
    try:
        return keyring.get_password(SERVICE_NAME, username)
    except NoKeyringError:
        logger.error("Keyring backend not found. Password cannot be retrieved.")
        return None
    except Exception:
        logger.exception(f"An unexpected error occurred while retrieving the password for '{username}'.")
        return None


def delete_password(username: str) -> None:
    """
    Rimuove in modo sicuro la password dell'utente dal portachiavi del sistema operativo.
    """
    if not username:
        return
    try:
        keyring.delete_password(SERVICE_NAME, username)
        logger.info(f"Password for user '{username}' deleted from the system keyring.")
    except NoKeyringError:
        logger.error("Keyring backend not found. Password could not be deleted.")
    except Exception:
        logger.exception(f"An unexpected error occurred while deleting the password for '{username}'.")
