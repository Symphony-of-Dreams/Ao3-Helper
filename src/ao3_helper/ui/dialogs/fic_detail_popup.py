import webbrowser
from typing import Any, Dict, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class FicDetailPopup(QDialog):
    import_requested = pyqtSignal(str)
    add_to_queue_requested = pyqtSignal(str)

    def __init__(self, fic_data: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.fic_url = fic_data.get("url", "")
        self.setWindowTitle("Fic Details")
        self.setMinimumSize(500, 400)

        main_layout = QVBoxLayout(self)

        title = QLabel(f"<h2>{fic_data.get('title', 'N/A')}</h2>")
        title.setWordWrap(True)
        author = QLabel(f"<i>by {fic_data.get('author', 'N/A')}</i>")

        info_text = (
            f"<b>Fandom:</b> {fic_data.get('fandoms', 'N/A')}<br>"
            f"<b>Rating:</b> {fic_data.get('rating', 'N/A')} | "
            f"<b>Words:</b> {fic_data.get('word_count', 0):,}"
        )
        info = QLabel(info_text)

        summary = QTextEdit()
        summary.setReadOnly(True)
        summary.setHtml(fic_data.get("summary", "<i>No summary provided.</i>"))

        main_layout.addWidget(title)
        main_layout.addWidget(author)
        main_layout.addWidget(info)
        main_layout.addWidget(QLabel("<b>Summary:</b>"))
        main_layout.addWidget(summary, 1)

        button_layout = QHBoxLayout()
        self.import_button = QPushButton("📥 Import to Library")
        self.queue_button = QPushButton("🔖 Add to Reading Queue")
        self.open_button = QPushButton("🌐 Open on AO3")

        button_layout.addStretch()
        button_layout.addWidget(self.open_button)
        button_layout.addWidget(self.queue_button)
        button_layout.addWidget(self.import_button)
        main_layout.addLayout(button_layout)

        self.import_button.clicked.connect(self._on_import)
        self.queue_button.clicked.connect(self._on_add_to_queue)
        self.open_button.clicked.connect(lambda: webbrowser.open(self.fic_url))

    def _on_import(self) -> None:
        self.import_requested.emit(self.fic_url)
        self.import_button.setText("Import Requested!")
        self.import_button.setEnabled(False)
        self.queue_button.setEnabled(False)

    def _on_add_to_queue(self) -> None:
        self.add_to_queue_requested.emit(self.fic_url)

        self.import_requested.emit(self.fic_url)
        self.queue_button.setText("Added to Queue!")
        self.queue_button.setEnabled(False)
        self.import_button.setEnabled(False)
