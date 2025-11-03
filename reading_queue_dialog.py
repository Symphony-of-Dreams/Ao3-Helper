from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database import get_reading_queue, remove_fics_from_queue, update_queue_order


class ReadingQueueDialog(QDialog):

    queue_changed = pyqtSignal(list)
    fic_selected = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📚 Reading Queue")
        self.setMinimumSize(600, 450)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel("Drag and drop fics to set your reading order."))

        self.queue_list = QListWidget()
        self.queue_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.queue_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.queue_list.setStyleSheet("QListWidget::item { padding: 5px; }")
        main_layout.addWidget(self.queue_list)

        button_layout = QHBoxLayout()
        self.select_button = QPushButton("Select in Library")
        self.remove_button = QPushButton("Remove from Queue")
        self.close_button = QPushButton("Close")

        button_layout.addStretch()
        button_layout.addWidget(self.select_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.close_button)
        main_layout.addLayout(button_layout)

        model = self.queue_list.model()
        if model:
            model.rowsMoved.connect(self._on_order_changed)

        self.queue_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.queue_list.itemDoubleClicked.connect(self._on_select_button_clicked)

        self.select_button.clicked.connect(self._on_select_button_clicked)
        self.remove_button.clicked.connect(self._on_remove_button_clicked)
        self.close_button.clicked.connect(self.accept)

        self._load_queue()
        self._on_selection_changed()

    def _load_queue(self) -> None:
        """Carica e visualizza le opere dalla coda di lettura del database."""
        self.queue_list.clear()
        fics = get_reading_queue()
        for fic in fics:

            item_text = f"{fic.get('title', 'N/A')}  —  by {fic.get('author', 'N/A')}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, fic["url"])
            item.setToolTip(item_text)

            self.queue_list.addItem(item)

    def _on_order_changed(self) -> None:
        """Chiamato dopo un'operazione di drag-and-drop per salvare il nuovo ordine."""
        updates = []
        urls_affected = []
        for i in range(self.queue_list.count()):
            item = self.queue_list.item(i)

            if item:
                url = item.data(Qt.ItemDataRole.UserRole)
                if url:
                    updates.append((url, i + 1))
                    urls_affected.append(url)

        if updates:
            update_queue_order(updates)
            self.queue_changed.emit(urls_affected)

    def _on_selection_changed(self) -> None:
        """Abilita/disabilita i pulsanti in base alla selezione."""
        has_selection = len(self.queue_list.selectedItems()) > 0
        self.select_button.setEnabled(has_selection)
        self.remove_button.setEnabled(has_selection)

    def _on_select_button_clicked(self) -> None:
        """Emette il segnale per selezionare l'opera nella libreria principale."""
        selected_items = self.queue_list.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        if item:
            url = item.data(Qt.ItemDataRole.UserRole)
            self.fic_selected.emit(url)
            self.accept()

    def _on_remove_button_clicked(self) -> None:
        """Rimuove le opere selezionate dalla coda."""
        selected_items = self.queue_list.selectedItems()
        if not selected_items:
            return

        fic_count = len(selected_items)
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Are you sure you want to remove {fic_count} fic(s) from the Reading Queue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if reply == QMessageBox.StandardButton.Yes:

            urls_to_remove = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items if item is not None]

            if urls_to_remove:
                remove_fics_from_queue(urls_to_remove)
                self.queue_changed.emit(urls_to_remove)
                self._load_queue()
