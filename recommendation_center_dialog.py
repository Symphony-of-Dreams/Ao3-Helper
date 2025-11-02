from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui_components import NumericTableWidgetItem


class RecommendationCenterDialog(QDialog):
    # Segnale che emette l'URL di un'opera quando l'utente vuole selezionarla
    fic_selected = pyqtSignal(str)

    def __init__(self, recommendations: List[Dict[str, Any]], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Recommendation Center")
        self.setMinimumSize(800, 500)

        # Layout principale
        main_layout = QVBoxLayout(self)

        # Tabella per i suggerimenti
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Match Score", "Title", "Author", "Fandom"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)

        # Impostazioni di visualizzazione della tabella
        header = self.table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        main_layout.addWidget(self.table)

        # Pulsanti di azione
        self.select_button = QPushButton("Select in Library")
        self.select_button.setEnabled(False)  # Abilitato solo quando una riga è selezionata
        self.close_button = QPushButton("Close")

        button_layout = QVBoxLayout()
        button_layout.addWidget(self.select_button)
        button_layout.addWidget(self.close_button)

        main_layout.addLayout(button_layout)

        # Connessioni dei segnali
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self._on_select_and_close)
        self.select_button.clicked.connect(self._on_select_and_close)
        self.close_button.clicked.connect(self.accept)

        # Popola la tabella con i dati
        self._populate_table(recommendations)

        # Ordina per score di default
        self.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)

    def _populate_table(self, recommendations: List[Dict[str, Any]]) -> None:
        """Riempie la tabella con la lista di suggerimenti."""
        self.table.setRowCount(len(recommendations))
        for row, fic in enumerate(recommendations):
            score_item = NumericTableWidgetItem(f"{fic.get('recommendation_score', 0.0):.2f}")
            score_item.setData(Qt.ItemDataRole.UserRole, fic["url"])  # Memorizziamo l'URL qui

            title_item = QTableWidgetItem(fic.get("title", "N/A"))
            author_item = QTableWidgetItem(fic.get("author", "N/A"))
            fandom_item = QTableWidgetItem(fic.get("fandoms", "N/A"))

            self.table.setItem(row, 0, score_item)
            self.table.setItem(row, 1, title_item)
            self.table.setItem(row, 2, author_item)
            self.table.setItem(row, 3, fandom_item)

    def _on_selection_changed(self) -> None:
        """Abilita il pulsante 'Seleziona' se c'è una selezione."""
        self.select_button.setEnabled(len(self.table.selectedItems()) > 0)

    def _on_select_and_close(self) -> None:
        """Emette il segnale con l'URL e chiude la finestra."""
        selected_items = self.table.selectedItems()
        if not selected_items:
            return

        # L'URL è memorizzato nel primo item (score) della riga
        url_item = self.table.item(selected_items[0].row(), 0)
        if url_item:
            url = url_item.data(Qt.ItemDataRole.UserRole)
            self.fic_selected.emit(url)

        self.accept()  # Chiude la finestra di dialogo
