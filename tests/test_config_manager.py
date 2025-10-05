
import os
from configparser import ConfigParser

import pytest

import config_manager
import constants as const
from config_manager import ConfigManager



@pytest.fixture
def temp_config_file(tmp_path):
    """
    Crea un percorso file temporaneo per config.ini e si assicura
    che il singleton ConfigManager venga reinizializzato per ogni test.
    """
    config_path = tmp_path / "test_config.ini"

    yield config_path

    import importlib

    importlib.reload(config_manager)




def test_config_manager_creates_file_with_defaults(temp_config_file):
    """
    Verifica che, se il file non esiste, ConfigManager lo crei
    con tutte le sezioni e le chiavi di default.
    """
    assert not os.path.exists(temp_config_file)

    cm = ConfigManager(filename=str(temp_config_file))  # noqa: F841

    assert os.path.exists(temp_config_file)

    parser = ConfigParser()
    parser.read(str(temp_config_file))

    assert parser.has_section(const.CONFIG_SECTION_CREDS)
    assert parser.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME) == const.CONFIG_DEFAULT_USER

    assert parser.has_section(const.CONFIG_SECTION_SETTINGS)
    assert parser.getboolean(const.CONFIG_SECTION_SETTINGS, const.CONFIG_KEY_MANUAL_OVERRIDE) is False


def test_config_manager_reads_existing_values(temp_config_file):
    """
    Verifica che ConfigManager carichi correttamente i valori da un file esistente.
    """
    config_content = f"""
    [{const.CONFIG_SECTION_CREDS}]
    {const.CONFIG_KEY_USERNAME} = test_user

    [{const.CONFIG_SECTION_SETTINGS}]
    {const.CONFIG_KEY_THEME} = dark
    """
    with open(temp_config_file, "w") as f:
        f.write(config_content)

    cm = ConfigManager(filename=str(temp_config_file))

    assert cm.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME) == "test_user"
    assert cm.get(const.CONFIG_SECTION_SETTINGS, const.CONFIG_KEY_THEME) == "dark"


def test_config_manager_fills_missing_keys(temp_config_file):
    """
    Verifica che ConfigManager aggiunga le chiavi di default mancanti senza
    sovrascrivere quelle esistenti.
    """
    config_content = f"""
    [{const.CONFIG_SECTION_CREDS}]
    {const.CONFIG_KEY_USERNAME} = my_real_user
    """
    with open(temp_config_file, "w") as f:
        f.write(config_content)

    cm = ConfigManager(filename=str(temp_config_file))

    assert cm.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME) == "my_real_user"


    assert cm.get(const.CONFIG_SECTION_SETTINGS, const.CONFIG_KEY_THEME) == const.THEME_DEFAULT


def test_set_and_save_config(temp_config_file):
    """
    Verifica che i metodi set() e save_config() funzionino correttamente.
    """
    cm = ConfigManager(filename=str(temp_config_file))
    cm.set(const.CONFIG_SECTION_UI, const.CONFIG_KEY_GEOMETRY, "12345")
    cm.save_config()

    parser = ConfigParser()
    parser.read(str(temp_config_file))
    assert parser.get(const.CONFIG_SECTION_UI, const.CONFIG_KEY_GEOMETRY) == "12345"

    cm_new = ConfigManager(filename=str(temp_config_file))

    assert cm_new.get(const.CONFIG_SECTION_UI, const.CONFIG_KEY_GEOMETRY) == "12345"
