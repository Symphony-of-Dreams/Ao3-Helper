from typing import Any, Dict, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import constants as const


class FilterBuilderDialog(QDialog):
    # Emette il filtro costruito. Il booleano indica se salvarlo o no.
    filter_generated = pyqtSignal(dict, bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Advanced Filter Builder")
        self.setMinimumWidth(550)

        # Layout principale
        main_layout = QVBoxLayout(self)

        # Sezione Filtri Generali
        general_group = QGroupBox("General Filters")
        form_layout = QFormLayout(general_group)
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        self.fandom_input = QLineEdit()
        self.author_input = QLineEdit()
        self.title_input = QLineEdit()
        self.status_combo = QComboBox()
        self.status_combo.addItems(
            [
                "Any",
                const.STATUS_TO_READ,
                const.STATUS_READ,
                const.STATUS_KUDOSED,
                const.STATUS_COMMENTED,
                const.STATUS_DROPPED,
            ]
        )

        form_layout.addRow("Fandom contains:", self.fandom_input)
        form_layout.addRow("Author contains:", self.author_input)
        form_layout.addRow("Title contains:", self.title_input)
        form_layout.addRow("Status is:", self.status_combo)

        main_layout.addWidget(general_group)

        # Sezione Filtri Tag
        tags_group = QGroupBox("Tag Filters (comma-separated)")
        tags_layout = QFormLayout(tags_group)
        self.tags_and_input = QLineEdit()
        self.tags_or_input = QLineEdit()
        self.tags_not_input = QLineEdit()
        tags_layout.addRow("Contains ALL of:", self.tags_and_input)
        tags_layout.addRow("Contains ANY of:", self.tags_or_input)
        tags_layout.addRow("Does NOT contain:", self.tags_not_input)

        main_layout.addWidget(tags_group)
        main_layout.addStretch()

        # Pulsanti di azione
        button_layout = QHBoxLayout()
        self.apply_button = QPushButton("Apply Filter")
        self.save_button = QPushButton("Save & Apply")
        self.cancel_button = QPushButton("Cancel")

        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.save_button)
        main_layout.addLayout(button_layout)

        # Connessioni
        self.apply_button.clicked.connect(self._on_apply)
        self.save_button.clicked.connect(self._on_save_and_apply)
        self.cancel_button.clicked.connect(self.reject)

    def _build_filter_object(self) -> Dict[str, Any]:
        """Legge i widget e costruisce il dizionario del filtro."""
        filters: Dict[str, Any] = {"conditions": {}, "tags": {}}

        # Popola le condizioni generali
        if self.fandom_input.text():
            filters["conditions"]["fandoms"] = self.fandom_input.text().strip()
        if self.author_input.text():
            filters["conditions"]["author"] = self.author_input.text().strip()
        if self.title_input.text():
            filters["conditions"]["title"] = self.title_input.text().strip()
        if self.status_combo.currentIndex() > 0:
            filters["conditions"]["status"] = self.status_combo.currentText()

        # Popola i filtri dei tag
        if self.tags_and_input.text():
            filters["tags"]["and"] = [t.strip() for t in self.tags_and_input.text().split(",") if t.strip()]
        if self.tags_or_input.text():
            filters["tags"]["or"] = [t.strip() for t in self.tags_or_input.text().split(",") if t.strip()]
        if self.tags_not_input.text():
            filters["tags"]["not"] = [t.strip() for t in self.tags_not_input.text().split(",") if t.strip()]

        return filters

    def _on_apply(self) -> None:
        """Emette il segnale per applicare il filtro senza salvarlo."""
        filters = self._build_filter_object()
        self.filter_generated.emit(filters, False)
        self.accept()

    def _on_save_and_apply(self) -> None:
        """Emette il segnale per salvare e poi applicare il filtro."""
        filters = self._build_filter_object()
        self.filter_generated.emit(filters, True)
        self.accept()
