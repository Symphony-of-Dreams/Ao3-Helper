import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from ao3_helper.ui.dialogs.tag_management_window import TagManagementWindow

SAMPLE_TAGS = [
    (1, "Fandom A"),
    (2, "Character B"),
    (3, "Genre C"),
]


@pytest.fixture
def mock_db(mocker):
    """Mocks the database functions used by the dialog."""
    mock_get_all = mocker.patch("ao3_helper.ui.dialogs.tag_management_window.get_all_user_tags")
    mock_rename = mocker.patch("ao3_helper.ui.dialogs.tag_management_window.rename_user_tag")
    mock_delete = mocker.patch("ao3_helper.ui.dialogs.tag_management_window.delete_user_tag")
    return mock_get_all, mock_rename, mock_delete


@pytest.fixture
def mock_messagebox(mocker):
    """Mocks QMessageBox static methods."""
    mock_info = mocker.patch("PyQt6.QtWidgets.QMessageBox.information")
    mock_warning = mocker.patch("PyQt6.QtWidgets.QMessageBox.warning")
    mock_question = mocker.patch("PyQt6.QtWidgets.QMessageBox.question")
    return mock_info, mock_warning, mock_question


@pytest.fixture
def dialog(qtbot, mock_db):
    """Creates a TagManagementWindow instance."""
    mock_get_all, _, _ = mock_db
    mock_get_all.return_value = SAMPLE_TAGS
    dialog = TagManagementWindow()
    qtbot.addWidget(dialog)
    return dialog


def test_init_no_tags(qtbot, mock_db):
    """Test initialization when there are no tags."""
    mock_get_all, _, _ = mock_db
    mock_get_all.return_value = []

    dialog = TagManagementWindow()
    qtbot.addWidget(dialog)

    assert dialog.tag_list_widget.count() == 0
    assert not dialog.rename_input.isEnabled()
    assert not dialog.rename_button.isEnabled()
    assert not dialog.delete_button.isEnabled()


def test_init_with_tags(dialog, mock_db, qtbot):
    """Test initialization with sample tags."""
    mock_get_all, _, _ = mock_db
    mock_get_all.return_value = SAMPLE_TAGS

    dialog = TagManagementWindow()
    qtbot.addWidget(dialog)

    assert dialog.tag_list_widget.count() == len(SAMPLE_TAGS)
    assert dialog.tag_list_widget.item(0).text() == "Fandom A"
    assert dialog.tag_list_widget.item(0).data(Qt.ItemDataRole.UserRole) == 1
    assert not dialog.rename_input.isEnabled()
    assert not dialog.rename_button.isEnabled()
    assert not dialog.delete_button.isEnabled()


def test_on_selection_changed(dialog, qtbot):
    """Test that controls enable/disable and input updates on selection change."""
    dialog.tag_list_widget.setCurrentRow(0)
    assert dialog.rename_input.isEnabled()
    assert dialog.rename_button.isEnabled()
    assert dialog.delete_button.isEnabled()
    assert dialog.rename_input.text() == "Fandom A"

    dialog.tag_list_widget.setCurrentRow(-1)
    assert not dialog.rename_input.isEnabled()
    assert not dialog.rename_button.isEnabled()
    assert not dialog.delete_button.isEnabled()
    assert dialog.rename_input.text() == ""


def test_rename_tag_success(dialog, mock_db, mock_messagebox, qtbot):
    """Test renaming a tag successfully."""
    mock_get_all, mock_rename, _ = mock_db
    mock_info, _, _ = mock_messagebox

    dialog.tag_list_widget.setCurrentRow(0)
    dialog.rename_input.setText("New Fandom Name")
    mock_rename.return_value = True

    qtbot.mouseClick(dialog.rename_button, Qt.MouseButton.LeftButton)

    mock_rename.assert_called_once_with(1, "New Fandom Name")
    mock_get_all.assert_called_with()
    mock_info.assert_called_once()
    assert "New Fandom Name" in mock_info.call_args[0][2]


def test_rename_tag_invalid_input(dialog, mock_db, mock_messagebox, qtbot):
    """Test renaming a tag with invalid input (empty or same name)."""
    mock_get_all, mock_rename, _ = mock_db
    mock_info, mock_warning, _ = mock_messagebox

    dialog.tag_list_widget.setCurrentRow(0)

    dialog.rename_input.setText("")
    qtbot.mouseClick(dialog.rename_button, Qt.MouseButton.LeftButton)
    mock_rename.assert_not_called()

    dialog.rename_input.setText("Fandom A")
    qtbot.mouseClick(dialog.rename_button, Qt.MouseButton.LeftButton)
    mock_rename.assert_not_called()

    mock_info.assert_not_called()
    mock_warning.assert_not_called()


def test_rename_tag_failure_exists(dialog, mock_db, mock_messagebox, qtbot):
    """Test renaming a tag when the new name already exists."""
    mock_get_all, mock_rename, _ = mock_db
    mock_info, mock_warning, _ = mock_messagebox

    dialog.tag_list_widget.setCurrentRow(0)
    dialog.rename_input.setText("Existing Tag")
    mock_rename.return_value = False

    qtbot.mouseClick(dialog.rename_button, Qt.MouseButton.LeftButton)

    mock_rename.assert_called_once_with(1, "Existing Tag")
    mock_warning.assert_called_once()
    assert "Existing Tag" in mock_warning.call_args[0][2]
    mock_info.assert_not_called()


def test_delete_tag_confirmed(dialog, mock_db, mock_messagebox, qtbot):
    """Test deleting a tag when confirmed by the user."""
    mock_get_all, _, mock_delete = mock_db
    _, _, mock_question = mock_messagebox

    dialog.tag_list_widget.setCurrentRow(0)
    mock_question.return_value = QMessageBox.StandardButton.Yes

    qtbot.mouseClick(dialog.delete_button, Qt.MouseButton.LeftButton)

    mock_question.assert_called_once()
    mock_delete.assert_called_once_with(1)
    mock_get_all.assert_called_with()


def test_delete_tag_cancelled(dialog, mock_db, mock_messagebox, qtbot):
    """Test deleting a tag when cancelled by the user."""
    mock_get_all, _, mock_delete = mock_db
    _, _, mock_question = mock_messagebox

    dialog.tag_list_widget.setCurrentRow(0)
    mock_question.return_value = QMessageBox.StandardButton.No

    qtbot.mouseClick(dialog.delete_button, Qt.MouseButton.LeftButton)

    mock_question.assert_called_once()
    mock_delete.assert_not_called()
    mock_get_all.assert_called_once()
