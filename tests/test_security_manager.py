from unittest.mock import patch

from ao3_helper.core import security_manager

KEYRING_PATH = "ao3_helper.core.security_manager.keyring"


@patch(KEYRING_PATH)
def test_get_password_success(mock_keyring):
    """
    Verifica che get_password recuperi correttamente una password esistente.
    """
    mock_keyring.get_password.return_value = "supersecret"

    password = security_manager.get_password("test_user")

    mock_keyring.get_password.assert_called_once_with("ao3_helper", "test_user")
    assert password == "supersecret"


@patch(KEYRING_PATH)
def test_get_password_not_found(mock_keyring):
    """
    Verifica che get_password restituisca None se la password non viene trovata.
    """
    mock_keyring.get_password.return_value = None

    password = security_manager.get_password("non_existent_user")

    mock_keyring.get_password.assert_called_once_with("ao3_helper", "non_existent_user")
    assert password is None


@patch(KEYRING_PATH)
def test_set_password_success(mock_keyring):
    """
    Verifica che set_password chiami correttamente keyring per salvare una password.
    """
    security_manager.set_password("test_user", "new_password")

    mock_keyring.set_password.assert_called_once_with("ao3_helper", "test_user", "new_password")


@patch(KEYRING_PATH)
def test_set_password_empty_password_deletes(mock_keyring):
    """
    Verifica che chiamare set_password con una stringa vuota o None
    risulti in una chiamata a delete_password.
    """

    security_manager.set_password("test_user", "")
    mock_keyring.delete_password.assert_called_once_with("ao3_helper", "test_user")

    mock_keyring.reset_mock()

    security_manager.set_password("test_user", None)
    mock_keyring.delete_password.assert_called_once_with("ao3_helper", "test_user")


@patch(KEYRING_PATH)
def test_delete_password(mock_keyring):
    """
    Verifica che delete_password chiami correttamente keyring.
    """
    security_manager.delete_password("user_to_delete")

    mock_keyring.delete_password.assert_called_once_with("ao3_helper", "user_to_delete")
