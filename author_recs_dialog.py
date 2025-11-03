from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from fic_detail_popup import FicDetailPopup


class AuthorRecsDialog(QDialog):
    reroll_requested = pyqtSignal()
    import_fic_requested = pyqtSignal(str)
    add_to_queue_requested = pyqtSignal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("🌟 Suggestions From Your Favorite Authors")
        self.setMinimumSize(600, 500)

        main_layout = QVBoxLayout(self)
        self.results_list = QListWidget()
        self.results_list.setStyleSheet("QListWidget::item { padding: 6px; }")
        self.reroll_button = QPushButton("🔄 Reroll Suggestions")
        self.close_button = QPushButton("Close")

        main_layout.addWidget(self.results_list)
        main_layout.addWidget(self.reroll_button)
        main_layout.addWidget(self.close_button)

        self.reroll_button.clicked.connect(self.reroll_requested.emit)
        self.close_button.clicked.connect(self.accept)
        self.results_list.itemDoubleClicked.connect(self._on_item_double_clicked)

    def on_loading(self):
        self.results_list.clear()
        self.results_list.addItem("Searching authors' bookmarks... Please wait, this may take a minute...")
        self.reroll_button.setEnabled(False)

    def on_results_ready(self, results: List[Dict[str, Any]]):
        self.results_list.clear()
        if not results:
            self.results_list.addItem("No new fics found in your favorite authors' bookmarks.")

        grouped_results: Dict[str, List[Dict[str, Any]]] = {}
        for fic in results:
            author = fic.get("recommended_by", "Unknown")
            if author not in grouped_results:
                grouped_results[author] = []
            grouped_results[author].append(fic)

        for author, fics in grouped_results.items():

            header_item = QListWidgetItem(f"From {author}'s Bookmarks:")
            header_item.setFlags(header_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            header_item.setForeground(Qt.GlobalColor.gray)
            self.results_list.addItem(header_item)

            for fic in sorted(fics, key=lambda x: x.get("recommendation_score", 0), reverse=True):
                item_text = f"<b>{fic['title']}</b><br>Match Score: {fic['recommendation_score']}"
                label = QLabel(item_text)
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, fic)
                self.results_list.addItem(item)
                self.results_list.setItemWidget(item, label)
                item.setSizeHint(label.sizeHint())

        self.reroll_button.setEnabled(True)

    def on_error(self, message: str):
        self.results_list.clear()
        self.results_list.addItem(f"An error occurred: {message}")
        self.reroll_button.setEnabled(True)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        fic_data = item.data(Qt.ItemDataRole.UserRole)
        if not fic_data:
            return

        popup = FicDetailPopup(fic_data, self)
        popup.import_requested.connect(self.import_fic_requested.emit)
        popup.add_to_queue_requested.connect(lambda url: self.add_to_queue_requested.emit([url]))
        popup.exec()
