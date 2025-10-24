from typing import Dict, List, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import constants as const


class BulkEditDialog(QDialog):
    changes_requested = pyqtSignal(dict)

    def __init__(self, fic_count: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Bulk Edit {fic_count} Fics")
        self.setMinimumWidth(450)
        self.parent_window = parent

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.status_group = QGroupBox("1. Change Status")
        self.status_group.setCheckable(True)
        self.status_group.setChecked(False)
        status_layout = QVBoxLayout()
        self.status_combo = QComboBox()
        self.status_combo.addItems(
            [
                const.STATUS_TO_READ,
                const.STATUS_READ,
                const.STATUS_DROPPED,
                const.STATUS_KUDOSED,
                const.STATUS_COMMENTED,
            ]
        )
        status_layout.addWidget(self.status_combo)
        self.status_group.setLayout(status_layout)
        form_layout.addRow(self.status_group)

        self.add_tags_group = QGroupBox("2. Add Tags")
        self.add_tags_group.setCheckable(True)
        self.add_tags_group.setChecked(False)
        add_tags_layout = QVBoxLayout()
        self.add_tags_input = QLineEdit()
        self.add_tags_input.setPlaceholderText("tag1, tag2, another tag...")
        add_tags_layout.addWidget(QLabel("Separate multiple tags with a comma:"))
        add_tags_layout.addWidget(self.add_tags_input)
        self.add_tags_group.setLayout(add_tags_layout)
        form_layout.addRow(self.add_tags_group)

        self.remove_tags_group = QGroupBox("3. Remove Common Tags")
        self.remove_tags_group.setCheckable(True)
        self.remove_tags_group.setChecked(False)
        remove_tags_layout = QVBoxLayout()

        self.remove_tags_list = QListWidget()
        self.remove_tags_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)

        remove_tags_layout.addWidget(QLabel("Select one or more tags to remove:"))
        remove_tags_layout.addWidget(self.remove_tags_list)
        self.remove_tags_group.setLayout(remove_tags_layout)
        form_layout.addRow(self.remove_tags_group)

        main_layout.addLayout(form_layout)

        self.apply_button = QPushButton("Apply Changes")
        self.close_button = QPushButton("Close")
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.close_button)
        main_layout.addLayout(button_layout)

        self.apply_button.clicked.connect(self._apply_changes)
        self.close_button.clicked.connect(self.accept)

    def populate_remove_tags_list(self, common_tags: List[str]) -> None:
        """Popola la lista con i tag che possono essere rimossi."""
        self.remove_tags_list.clear()
        if not common_tags:
            self.remove_tags_group.setEnabled(False)
            self.remove_tags_group.setToolTip("No tags are shared across all selected fics.")
        else:
            self.remove_tags_group.setEnabled(True)
            self.remove_tags_list.addItems(sorted(common_tags))

    def _apply_changes(self) -> None:
        """Valida l'input ed emette un segnale con le modifiche."""
        if not (self.status_group.isChecked() or self.add_tags_group.isChecked() or self.remove_tags_group.isChecked()):
            QMessageBox.warning(
                self, "No Action Selected", "Please check at least one section (1, 2, or 3) to apply a change."
            )
            return

        changes: Dict[str, Optional[List[str] | str]] = {"status": None, "add_tags": None, "remove_tags": None}

        if self.status_group.isChecked():
            changes["status"] = self.status_combo.currentText()

        if self.add_tags_group.isChecked():
            tags_raw = self.add_tags_input.text().strip()
            if tags_raw:
                changes["add_tags"] = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]
            if not changes["add_tags"]:
                QMessageBox.warning(self, "Input Error", "Please enter at least one tag to add.")
                return

        if self.remove_tags_group.isChecked():
            selected_items = self.remove_tags_list.selectedItems()
            if selected_items:
                changes["remove_tags"] = [item.text() for item in selected_items]
            if not changes["remove_tags"]:
                QMessageBox.warning(self, "Input Error", "Please select at least one tag to remove.")
                return

        self.changes_requested.emit(changes)

        QMessageBox.information(self, "Success", "Changes have been applied.")
        self.reset_form()

        if hasattr(self.parent_window, "refresh_bulk_edit_dialog_tags"):
            if self.parent_window and hasattr(self.parent_window, "refresh_bulk_edit_dialog_tags"):

                self.parent_window.refresh_bulk_edit_dialog_tags()

    def reset_form(self) -> None:
        """Resetta i controlli per la prossima operazione."""
        self.status_group.setChecked(False)
        self.add_tags_group.setChecked(False)
        self.add_tags_input.clear()
        self.remove_tags_group.setChecked(False)
        self.remove_tags_list.clearSelection()
