from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ao3_helper.core.database import delete_user_tag, get_all_user_tags, rename_user_tag


class TagManagementWindow(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manage Your Tags")
        self.setMinimumSize(450, 300)

        main_layout = QHBoxLayout(self)
        self.tag_list_widget = QListWidget()
        main_layout.addWidget(self.tag_list_widget, 1)

        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(controls_widget, 0)

        controls_layout.addWidget(QLabel("<b>Rename Selected Tag:</b>"))
        self.rename_input = QLineEdit()
        self.rename_input.setPlaceholderText("Enter new name...")
        self.rename_button = QPushButton("Rename")
        controls_layout.addWidget(self.rename_input)
        controls_layout.addWidget(self.rename_button)

        controls_layout.addSpacing(20)
        self.delete_button = QPushButton("Delete Selected Tag")
        self.delete_button.setStyleSheet("background-color: #a13333; color: white;")
        controls_layout.addWidget(self.delete_button)

        self.tag_list_widget.currentItemChanged.connect(self._on_selection_changed)
        self.rename_button.clicked.connect(self._rename_tag)
        self.delete_button.clicked.connect(self._delete_tag)

        self._populate_tag_list()
        self._on_selection_changed()

    def _populate_tag_list(self) -> None:
        self.tag_list_widget.clear()
        all_tags = get_all_user_tags()
        for tag_id, tag_name in all_tags:
            item = QListWidgetItem(tag_name)
            item.setData(Qt.ItemDataRole.UserRole, tag_id)
            self.tag_list_widget.addItem(item)

    def _on_selection_changed(self) -> None:
        """Gestisce l'abilitazione/disabilitazione dei controlli."""
        selected_item = self.tag_list_widget.currentItem()

        is_item_selected = selected_item is not None
        self.rename_input.setEnabled(is_item_selected)
        self.rename_button.setEnabled(is_item_selected)
        self.delete_button.setEnabled(is_item_selected)

        if selected_item is not None:
            self.rename_input.setText(selected_item.text())
        else:
            self.rename_input.clear()

    def _rename_tag(self) -> None:
        """Logica per rinominare un tag."""
        selected_item = self.tag_list_widget.currentItem()
        if not selected_item:
            return
        assert selected_item is not None

        tag_id = selected_item.data(Qt.ItemDataRole.UserRole)
        old_name = selected_item.text()
        new_name = self.rename_input.text().strip()

        if not new_name or new_name == old_name:
            return

        success = rename_user_tag(tag_id, new_name)
        if success:
            QMessageBox.information(self, "Success", f"Tag '{old_name}' renamed to '{new_name}'.")
            self._populate_tag_list()
            items = self.tag_list_widget.findItems(new_name, Qt.MatchFlag.MatchExactly)
            if items:
                self.tag_list_widget.setCurrentItem(items[0])
        else:
            QMessageBox.warning(self, "Error", f"A tag named '{new_name}' already exists.")

    def _delete_tag(self) -> None:
        """Gestisce la cancellazione di un tag con conferma."""
        selected_item = self.tag_list_widget.currentItem()
        if not selected_item:
            return
        assert selected_item is not None

        tag_id = selected_item.data(Qt.ItemDataRole.UserRole)
        tag_name = selected_item.text()

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to permanently delete the tag '<b>{tag_name}</b>'?<br><br>"
            "This will remove the tag from all fics it's assigned to. This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            delete_user_tag(tag_id)
            self._populate_tag_list()
