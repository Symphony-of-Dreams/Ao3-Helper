from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QPushButton

from ao3_helper.ui.dialogs.welcome_dialog import WelcomeDialog


@pytest.fixture
def mock_dependencies(mocker):
    """Mocks all external dependencies for the WelcomeDialog."""
    mock_config = mocker.patch("ao3_helper.ui.dialogs.welcome_dialog.config_manager")
    mock_security = mocker.patch("ao3_helper.ui.dialogs.welcome_dialog.security_manager")
    mock_ao3_client = mocker.patch("ao3_helper.ui.dialogs.welcome_dialog.ao3_client")
    mock_qmessagebox = mocker.patch("ao3_helper.ui.dialogs.welcome_dialog.QMessageBox")
    return mock_config, mock_security, mock_ao3_client, mock_qmessagebox


def test_guest_button_rejects(qtbot):
    """Test that clicking the guest button calls reject."""
    dialog = WelcomeDialog()
    qtbot.addWidget(dialog)

    qtbot.mouseClick(dialog.guest_button, Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_privacy_button_shows_message(qtbot, mock_dependencies):
    """Test that clicking the privacy button shows the privacy info message."""
    _, _, _, mock_qmessagebox = mock_dependencies
    dialog = WelcomeDialog()
    qtbot.addWidget(dialog)

    privacy_button = dialog.findChild(QPushButton, "privacy_button")

    if not privacy_button:
        for child in dialog.findChildren(QPushButton):
            if "Privacy Promise" in child.text():
                privacy_button = child
                break

    assert privacy_button is not None, "Privacy button not found"
    qtbot.mouseClick(privacy_button, Qt.MouseButton.LeftButton)
    mock_qmessagebox.information.assert_called_once()


def test_save_and_connect_success(qtbot, mock_dependencies):
    """Test the full flow for a successful login."""
    mock_config, mock_security, mock_ao3_client, mock_qmessagebox = mock_dependencies
    mock_ao3_client.reload_session.return_value = True

    mock_ao3_client.session = MagicMock()
    mock_ao3_client.session.username = "TestUser"

    dialog = WelcomeDialog()
    qtbot.addWidget(dialog)
    dialog.accept = MagicMock()

    dialog.user_input.setText("TestUser")
    dialog.pass_input.setText("password123")

    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    mock_config.set.assert_called_with("AO3_Credentials", "username", "TestUser")
    mock_security.set_password.assert_called_with("TestUser", "password123")
    mock_ao3_client.reload_session.assert_called_once()
    mock_qmessagebox.information.assert_called_once_with(
        dialog, "Success!", "You have successfully logged in as 'TestUser'. Welcome to AO3 Helper!"
    )
    dialog.accept.assert_called_once()


def test_save_and_connect_failure(qtbot, mock_dependencies):
    """Test the flow for a failed login."""
    mock_config, mock_security, mock_ao3_client, mock_qmessagebox = mock_dependencies
    mock_ao3_client.reload_session.return_value = False

    dialog = WelcomeDialog()
    qtbot.addWidget(dialog)
    dialog.accept = MagicMock()

    dialog.user_input.setText("TestUser")
    dialog.pass_input.setText("wrongpassword")

    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    mock_ao3_client.reload_session.assert_called_once()
    mock_qmessagebox.warning.assert_called_once()
    dialog.accept.assert_called_once()


def test_save_and_connect_no_password(qtbot, mock_dependencies):
    """Test that not providing a password calls delete_password."""
    mock_config, mock_security, mock_ao3_client, _ = mock_dependencies

    dialog = WelcomeDialog()
    qtbot.addWidget(dialog)

    dialog.user_input.setText("TestUserNoPass")
    dialog.pass_input.setText("")

    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    mock_security.delete_password.assert_called_with("TestUserNoPass")


def test_save_and_connect_guest(qtbot, mock_dependencies):
    """Test the flow for saving no username, which proceeds as guest."""
    mock_config, _, mock_ao3_client, mock_qmessagebox = mock_dependencies
    mock_ao3_client.reload_session.return_value = False

    dialog = WelcomeDialog()
    qtbot.addWidget(dialog)
    dialog.accept = MagicMock()

    dialog.user_input.setText("  ")

    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    mock_qmessagebox.information.assert_called_once_with(
        dialog, "Proceeding as Guest", "No username was entered. You will proceed as a guest."
    )
    dialog.accept.assert_called_once()
