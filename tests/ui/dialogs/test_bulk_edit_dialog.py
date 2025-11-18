from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QListWidgetItem

from ao3_helper.ui.dialogs.bulk_edit_dialog import BulkEditDialog


@pytest.fixture
def dialog(qtbot):
    """Creates a BulkEditDialog instance."""
    dialog = BulkEditDialog(fic_count=5)
    qtbot.addWidget(dialog)
    return dialog


def test_initialization(dialog):
    """Test that the dialog initializes in the correct state."""
    assert not dialog.status_group.isChecked()
    assert not dialog.add_tags_group.isChecked()
    assert not dialog.remove_tags_group.isChecked()
    assert dialog.remove_tags_group.isEnabled()


def test_populate_remove_tags(dialog):
    """Test the logic for populating the removable tags list."""
    dialog.populate_remove_tags_list(["tag a", "tag b"])
    assert dialog.remove_tags_group.isEnabled()
    assert dialog.remove_tags_list.count() == 2

    dialog.populate_remove_tags_list([])
    assert not dialog.remove_tags_group.isEnabled()
    assert dialog.remove_tags_list.count() == 0


def test_close_button_accepts(qtbot, dialog):
    """Test that the close button accepts the dialog."""
    qtbot.mouseClick(dialog.close_button, Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_apply_no_action_warning(qtbot, dialog, mocker):
    """Test that a warning is shown if no action is checked."""
    mock_msgbox = mocker.patch("ao3_helper.ui.dialogs.bulk_edit_dialog.QMessageBox")
    mock_signal = MagicMock()
    dialog.changes_requested.connect(mock_signal)

    qtbot.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)

    mock_msgbox.warning.assert_called_once()
    mock_signal.assert_not_called()


def test_apply_valid_changes_emits_signal(qtbot, dialog, mocker):
    """Test that valid changes are correctly emitted in the signal."""
    mock_msgbox = mocker.patch("ao3_helper.ui.dialogs.bulk_edit_dialog.QMessageBox")
    mock_signal = MagicMock()
    dialog.changes_requested.connect(mock_signal)

    dialog.status_group.setChecked(True)
    dialog.status_combo.setCurrentText("Read")

    dialog.add_tags_group.setChecked(True)
    dialog.add_tags_input.setText("  tag1, tag2  ")

    dialog.populate_remove_tags_list(["old_tag"])
    dialog.remove_tags_group.setChecked(True)
    dialog.remove_tags_list.addItem(QListWidgetItem("old_tag"))
    dialog.remove_tags_list.item(0).setSelected(True)

    qtbot.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)

    expected_changes = {
        "status": "Read",
        "add_tags": ["tag1", "tag2"],
        "remove_tags": ["old_tag"],
    }
    mock_signal.assert_called_once_with(expected_changes)
    mock_msgbox.information.assert_called_once()


def test_apply_invalid_input_warnings(qtbot, dialog, mocker):
    """Test that warnings are shown for invalid inputs."""
    mock_msgbox = mocker.patch("ao3_helper.ui.dialogs.bulk_edit_dialog.QMessageBox")
    mock_signal = MagicMock()
    dialog.changes_requested.connect(mock_signal)

    dialog.add_tags_group.setChecked(True)
    dialog.add_tags_input.setText("   ")
    qtbot.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)
    mock_msgbox.warning.assert_called_once_with(dialog, "Input Error", "Please enter at least one tag to add.")
    mock_signal.assert_not_called()
    dialog.add_tags_group.setChecked(False)
    mock_msgbox.warning.reset_mock()

    dialog.populate_remove_tags_list(["some_tag"])
    dialog.remove_tags_group.setChecked(True)
    qtbot.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)
    mock_msgbox.warning.assert_called_once_with(dialog, "Input Error", "Please select at least one tag to remove.")
    mock_signal.assert_not_called()
