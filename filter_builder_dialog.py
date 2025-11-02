from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QStringListModel, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QCompleter,
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
from ui_components import TagCompleter


class FilterBuilderDialog(QDialog):

    filter_generated = pyqtSignal(dict, bool)

    def __init__(self, completer_data: Dict[str, List[str]], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Advanced Filter Builder")
        self.setMinimumWidth(550)

        main_layout = QVBoxLayout(self)

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

        tags_group = QGroupBox("Tag Filters (comma-separated)")
        tags_layout = QFormLayout(tags_group)
        self.tags_and_input = QLineEdit()
        self.tags_or_input = QLineEdit()
        self.tags_not_input = QLineEdit()
        tags_layout.addRow("Contains ALL of:", self.tags_and_input)
        tags_layout.addRow("Contains ANY of:", self.tags_or_input)
        tags_layout.addRow("Does NOT contain:", self.tags_not_input)
        main_layout.addWidget(tags_group)

        self._setup_completers(completer_data)

        main_layout.addStretch()

        button_layout = QHBoxLayout()
        self.apply_button = QPushButton("Apply Filter")
        self.save_button = QPushButton("Save & Apply")
        self.cancel_button = QPushButton("Cancel")

        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.save_button)
        main_layout.addLayout(button_layout)

        self.apply_button.clicked.connect(self._on_apply)
        self.save_button.clicked.connect(self._on_save_and_apply)
        self.cancel_button.clicked.connect(self.reject)

    def _setup_completers(self, completer_data: Dict[str, List[str]]) -> None:
        """Crea e collega i QCompleter ai campi di input, assicurandone la persistenza."""

        self.fandom_model = QStringListModel(completer_data.get("fandoms", []))
        self.fandom_completer = QCompleter(self.fandom_model, self)
        self.fandom_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.fandom_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.fandom_input.setCompleter(self.fandom_completer)

        self.author_model = QStringListModel(completer_data.get("authors", []))
        self.author_completer = QCompleter(self.author_model, self)
        self.author_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.author_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.author_input.setCompleter(self.author_completer)

        self.tag_model = QStringListModel(completer_data.get("tags", []))
        self.tag_completer = TagCompleter(self.tag_model, self)
        self.tag_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.tag_completer.setFilterMode(Qt.MatchFlag.MatchContains)

        self.tags_and_input.setCompleter(self.tag_completer)
        self.tags_or_input.setCompleter(self.tag_completer)
        self.tags_not_input.setCompleter(self.tag_completer)

    def _build_filter_object(self) -> Dict[str, Any]:
        """Legge i widget e costruisce il dizionario del filtro."""
        filters: Dict[str, Any] = {"conditions": {}, "tags": {}}

        if self.fandom_input.text():
            filters["conditions"]["fandoms"] = self.fandom_input.text().strip()
        if self.author_input.text():
            filters["conditions"]["author"] = self.author_input.text().strip()
        if self.title_input.text():
            filters["conditions"]["title"] = self.title_input.text().strip()
        if self.status_combo.currentIndex() > 0:
            filters["conditions"]["status"] = self.status_combo.currentText()

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
