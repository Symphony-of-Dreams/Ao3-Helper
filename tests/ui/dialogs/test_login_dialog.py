from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog

from ao3_helper.ui.dialogs.login_dialog import LoginDialog


@pytest.fixture
def mock_dependencies(mocker):
    """Mocks all external dependencies for the LoginDialog."""
    mock_config = mocker.patch("ao3_helper.ui.dialogs.login_dialog.config_manager")
    mock_security = mocker.patch("ao3_helper.ui.dialogs.login_dialog.security_manager")

    mock_ao3_client = mocker.patch("ao3_helper.core.ao3_manager.ao3_client")
    mock_qmessagebox = mocker.patch("ao3_helper.ui.dialogs.login_dialog.QMessageBox")

    mock_qapp_quit = mocker.patch("PyQt6.QtWidgets.QApplication.quit")
    mock_qprocess_start = mocker.patch("PyQt6.QtCore.QProcess.startDetached")

    def get_side_effect(section, key, fallback=None):
        if key == "username":
            return "test_user"
        if key == "manual_override":
            return False
        return fallback

    mock_config.get.side_effect = get_side_effect
    mock_config.getboolean.return_value = False
    mock_security.get_password.return_value = "password123"

    return (
        mock_config,
        mock_security,
        mock_ao3_client,
        mock_qmessagebox,
        mock_qapp_quit,
        mock_qprocess_start,
    )


def test_dialog_initialization(qtbot, mock_dependencies):
    """Test that the dialog initializes with values from config."""
    dialog = LoginDialog()
    qtbot.addWidget(dialog)

    assert dialog.user_input.text() == "test_user"
    assert dialog.pass_input.text() == "password123"
    assert not dialog.override_checkbox.isChecked()


def test_cancel_button_rejects(qtbot, mock_dependencies):
    """Test that clicking the cancel button calls reject."""
    dialog = LoginDialog()
    qtbot.addWidget(dialog)

    qtbot.mouseClick(dialog.cancel_button, Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_save_no_username_change_success(qtbot, mock_dependencies):
    """Test saving settings without changing the username, with a successful login."""
    mock_config, mock_security, mock_ao3_client, mock_qmessagebox, _, _ = mock_dependencies
    mock_ao3_client.reload_session.return_value = True
    mock_ao3_client.session = MagicMock()
    mock_ao3_client.session.username = "test_user"

    dialog = LoginDialog()
    qtbot.addWidget(dialog)
    dialog.accept = MagicMock()

    dialog.pass_input.setText("new_password")
    dialog.override_checkbox.setChecked(True)

    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    mock_security.set_password.assert_called_with("test_user", "new_password")
    mock_config.set.assert_any_call("Settings", "manual_override", "true")
    mock_ao3_client.reload_session.assert_called_once()
    mock_qmessagebox.information.assert_called_once()
    dialog.accept.assert_called_once()


def test_save_username_change_restart_yes(qtbot, mock_dependencies):
    """Test saving with a username change and clicking Yes to restart."""
    (
        mock_config,
        mock_security,
        _,
        mock_qmessagebox,
        mock_qapp_quit,
        mock_qprocess_start,
    ) = mock_dependencies
    mock_qmessagebox.question.return_value = mock_qmessagebox.StandardButton.Yes

    dialog = LoginDialog()
    qtbot.addWidget(dialog)
    dialog.accept = MagicMock()

    dialog.user_input.setText("new_user")

    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    mock_qmessagebox.question.assert_called_once()
    mock_config.set.assert_any_call("AO3_Credentials", "username", "new_user")
    mock_qapp_quit.assert_called_once()
    mock_qprocess_start.assert_called_once()
    dialog.accept.assert_not_called()


def test_save_username_change_restart_no(qtbot, mock_dependencies):
    """Test saving with a username change and clicking No to restart."""
    _, _, _, mock_qmessagebox, mock_qapp_quit, mock_qprocess_start = mock_dependencies
    mock_qmessagebox.question.return_value = mock_qmessagebox.StandardButton.No

    dialog = LoginDialog()
    qtbot.addWidget(dialog)
    dialog.accept = MagicMock()

    dialog.user_input.setText("new_user")
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    mock_qmessagebox.question.assert_called_once()
    mock_qapp_quit.assert_not_called()
    mock_qprocess_start.assert_not_called()
    dialog.accept.assert_not_called()
