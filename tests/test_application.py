import sys
from unittest.mock import MagicMock

import pytest

from ao3_helper.application import App


@pytest.fixture
def mock_qt_app(mocker):
    """Mocks the QApplication to prevent it from actually running."""
    return mocker.patch("ao3_helper.application.QApplication")


@pytest.fixture
def mock_main_window(mocker):
    """Mocks the MainWindow and its show method."""
    return mocker.patch("ao3_helper.application.MainWindow")


@pytest.fixture
def mock_db_init(mocker):
    """Mocks all database related functions."""
    mocker.patch("ao3_helper.application.get_db_path_for_user", return_value="dummy_path.db")
    mocker.patch("ao3_helper.application.run_database_migrations")
    return mocker.patch("peewee.Proxy.initialize")


@pytest.fixture
def mock_config(mocker):
    """Mocks the config manager."""
    return mocker.patch("ao3_helper.application.config_manager")


@pytest.fixture
def mock_welcome_dialog(mocker):
    """Mocks the WelcomeDialog."""
    return mocker.patch("ao3_helper.ui.dialogs.welcome_dialog.WelcomeDialog")


@pytest.fixture
def mock_message_box(mocker):
    """Mocks the QMessageBox."""
    return mocker.patch("ao3_helper.application.QMessageBox")


def test_app_run_logged_in(mock_qt_app, mock_main_window, mock_db_init, mock_config, mock_welcome_dialog):
    """
    Smoke test: Verifica la sequenza di avvio per un utente loggato.
    """
    mock_config.get.return_value = "test_user"

    app = App(sys.argv)
    app.exec = MagicMock(return_value=0)

    return_code = app.run()

    mock_db_init.assert_called_once()
    mock_main_window.assert_called_once()
    mock_main_window.return_value.show.assert_called_once()
    mock_welcome_dialog.assert_not_called()
    app.exec.assert_called_once()
    assert return_code == 0


def test_app_run_guest_user(mock_qt_app, mock_main_window, mock_db_init, mock_config, mock_welcome_dialog):
    """
    Smoke test: Verifica la sequenza di avvio per un utente non loggato (guest).
    """
    mock_config.get.return_value = ""

    app = App(sys.argv)
    app.exec = MagicMock(return_value=0)

    app.run()

    mock_db_init.assert_called_once()
    mock_welcome_dialog.assert_called_once()
    mock_welcome_dialog.return_value.exec.assert_called_once()
    mock_main_window.assert_called_once()
    mock_main_window.return_value.show.assert_called_once()
    app.exec.assert_called_once()


def test_app_run_db_failure(mock_qt_app, mock_db_init, mock_config, mock_message_box):
    """
    Verifica che in caso di errore del DB venga mostrato un messaggio di errore
    e l'applicazione termini con un codice di errore.
    """
    mock_db_init.side_effect = Exception("DB Boom!")

    app = App(sys.argv)
    app.exec = MagicMock()

    return_code = app.run()

    mock_message_box.assert_called_once()
    mock_message_box.return_value.exec.assert_called_once()
    app.exec.assert_not_called()
    assert return_code == 1
