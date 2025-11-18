from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QWidget

from ao3_helper.ui.dialogs.notifications_window import NotificationsWindow


@pytest.fixture
def mock_db(mocker):
    """Mocks the database functions used by the dialog."""
    mock_get = mocker.patch("ao3_helper.ui.dialogs.notifications_window.get_unread_notifications")
    mock_mark = mocker.patch("ao3_helper.ui.dialogs.notifications_window.mark_notifications_as_read")
    return mock_get, mock_mark


def test_init_no_notifications(qtbot, mock_db):
    """Test initialization when there are no unread notifications."""
    mock_get, _ = mock_db
    mock_get.return_value = []

    dialog = NotificationsWindow()
    qtbot.addWidget(dialog)

    assert dialog.notification_list.count() == 1
    assert "No new notifications" in dialog.notification_list.item(0).text()


def test_init_with_notifications(qtbot, mock_db):
    """Test initialization with a list of notifications."""
    mock_get, _ = mock_db
    notifications = [
        {"message": "Fic updated: Fic A", "timestamp": "2025-01-01"},
        {"message": "New comment on Fic B", "timestamp": "2025-01-02"},
    ]
    mock_get.return_value = notifications

    dialog = NotificationsWindow()
    qtbot.addWidget(dialog)

    assert dialog.notification_list.count() == 2
    assert "Fic A" in dialog.notification_list.item(0).text()
    assert "Fic B" in dialog.notification_list.item(1).text()


def test_close_event_with_notifications(qtbot, mock_db):
    """Test that closing the window marks notifications as read."""
    mock_get, mock_mark = mock_db
    mock_get.return_value = [{"message": "Test", "timestamp": "2025-01-01"}]

    class MockParent(QWidget):
        def __init__(self):
            super().__init__()
            self.update_notification_indicator = MagicMock()

    mock_parent = MockParent()
    qtbot.addWidget(mock_parent)

    dialog = NotificationsWindow(parent=mock_parent)
    qtbot.addWidget(dialog)

    dialog.close()

    mock_mark.assert_called_once()
    mock_parent.update_notification_indicator.assert_called_once()


def test_close_event_no_notifications(qtbot, mock_db):
    """Test that closing does nothing if there were no notifications."""
    mock_get, mock_mark = mock_db
    mock_get.return_value = []

    dialog = NotificationsWindow()
    qtbot.addWidget(dialog)

    dialog.close()

    mock_mark.assert_not_called()
