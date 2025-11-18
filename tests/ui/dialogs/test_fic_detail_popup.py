from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QTextEdit

from ao3_helper.ui.dialogs.fic_detail_popup import FicDetailPopup

SAMPLE_FIC_DATA = {
    "url": "https://archiveofourown.org/works/12345",
    "title": "My Test Fic",
    "author": "TestAuthor",
    "fandoms": "Test Fandom",
    "rating": "Explicit",
    "word_count": 123456,
    "summary": "<p>This is a <b>test summary</b>.</p>",
}


@pytest.fixture
def dialog(qtbot):
    """Creates a FicDetailPopup instance with sample data."""
    dialog = FicDetailPopup(SAMPLE_FIC_DATA)
    qtbot.addWidget(dialog)
    return dialog


def test_initialization_and_population(dialog):
    """Test that the dialog widgets are populated correctly on init."""
    assert dialog.windowTitle() == "Fic Details"

    title_label = None
    author_label = None
    info_label = None

    labels = dialog.findChildren(QLabel)
    for label in labels:
        if "My Test Fic" in label.text():
            title_label = label
        if "by TestAuthor" in label.text():
            author_label = label
        if "Test Fandom" in label.text():
            info_label = label

    summary_text = dialog.findChild(QTextEdit)

    assert title_label is not None
    assert author_label is not None
    assert info_label is not None
    assert summary_text is not None

    assert "123,456" in info_label.text()
    assert "This is a test summary." in summary_text.toPlainText()


def test_open_on_ao3_button(dialog, mocker, qtbot):
    """Test that the Open on AO3 button calls webbrowser.open."""
    mock_webbrowser = mocker.patch("ao3_helper.ui.dialogs.fic_detail_popup.webbrowser")
    qtbot.mouseClick(dialog.open_button, Qt.MouseButton.LeftButton)
    mock_webbrowser.open.assert_called_once_with(SAMPLE_FIC_DATA["url"])


def test_import_button_emits_signal(dialog, qtbot):
    """Test that the import button emits the correct signal and disables buttons."""
    mock_signal = MagicMock()
    dialog.import_requested.connect(mock_signal)

    assert dialog.import_button.isEnabled()
    assert dialog.queue_button.isEnabled()

    qtbot.mouseClick(dialog.import_button, Qt.MouseButton.LeftButton)

    mock_signal.assert_called_once_with(SAMPLE_FIC_DATA["url"])
    assert not dialog.import_button.isEnabled()
    assert not dialog.queue_button.isEnabled()
    assert "Requested" in dialog.import_button.text()


def test_add_to_queue_button_emits_signals(dialog, qtbot):
    """Test that the queue button emits both signals and disables buttons."""
    mock_import_signal = MagicMock()
    mock_queue_signal = MagicMock()
    dialog.import_requested.connect(mock_import_signal)
    dialog.add_to_queue_requested.connect(mock_queue_signal)

    qtbot.mouseClick(dialog.queue_button, Qt.MouseButton.LeftButton)

    mock_import_signal.assert_called_once_with(SAMPLE_FIC_DATA["url"])
    mock_queue_signal.assert_called_once_with(SAMPLE_FIC_DATA["url"])
    assert not dialog.import_button.isEnabled()
    assert not dialog.queue_button.isEnabled()
    assert "Added" in dialog.queue_button.text()
