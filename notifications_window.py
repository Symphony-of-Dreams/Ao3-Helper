from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QDialog, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from database import get_unread_notifications, mark_notifications_as_read


class NotificationsWindow(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Notification Center")
        self.setGeometry(400, 400, 500, 300)

        layout = QVBoxLayout(self)

        self.notification_list = QListWidget()
        self.notifications = get_unread_notifications()

        if not self.notifications:
            item = QListWidgetItem("No new notifications.")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.notification_list.addItem(item)
        else:
            for notification in self.notifications:
                message = f"{notification['message']}\n(received on {notification['timestamp']})"
                item = QListWidgetItem(message)
                item.setData(Qt.ItemDataRole.UserRole, notification.get("related_url"))
                self.notification_list.addItem(item)

        layout.addWidget(self.notification_list)

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        """Executed when the window is closed."""
        if self.notifications:
            mark_notifications_as_read()
            parent = self.parent()
            if parent and hasattr(parent, "update_notification_indicator"):
                parent.update_notification_indicator()  # type: ignore
        super().closeEvent(event)
