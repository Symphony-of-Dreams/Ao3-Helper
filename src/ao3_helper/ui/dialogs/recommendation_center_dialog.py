from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QModelIndex, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ao3_helper.ui.dialogs.fic_detail_popup import FicDetailPopup
from ao3_helper.ui.ui_components import NumericTableWidgetItem


class RecommendationCenterDialog(QDialog):
    """
    Una finestra di dialogo multi-scheda per visualizzare suggerimenti di opere
    sia dalla libreria locale ('To Read') sia da nuove scoperte su AO3.
    """

    fic_selected = pyqtSignal(str)
    discover_fics_requested = pyqtSignal(dict)
    import_fic_requested = pyqtSignal(str)
    add_to_queue_requested = pyqtSignal(list)

    def __init__(self, recommendations: List[Dict[str, Any]], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("✨ Recommendation & Discovery Center")
        self.setMinimumSize(850, 650)

        self.external_results_data: Dict[str, Dict[str, Any]] = {}

        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.internal_tab = self._create_internal_tab(recommendations)
        self.external_tab = self._create_external_tab()

        self.tabs.addTab(self.internal_tab, "📚 From Your 'To Read' List")
        self.tabs.addTab(self.external_tab, "🔭 Discover from AO3")

        main_layout.addWidget(self.tabs)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        main_layout.addWidget(self.close_button, alignment=Qt.AlignmentFlag.AlignRight)

    def _create_internal_tab(self, recommendations: List[Dict[str, Any]]) -> QWidget:
        """Crea il widget per la scheda dei suggerimenti interni."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)

        self.internal_table = QTableWidget()
        self.internal_table.setColumnCount(4)
        self.internal_table.setHorizontalHeaderLabels(["Match Score", "Title", "Author", "Fandom"])
        self.internal_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.internal_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.internal_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.internal_table.setSortingEnabled(True)

        header = self.internal_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.internal_table)

        self.select_button = QPushButton("➡️ Select in Library")
        self.select_button.setEnabled(False)
        layout.addWidget(self.select_button, alignment=Qt.AlignmentFlag.AlignRight)

        self.internal_table.itemSelectionChanged.connect(self._on_internal_selection_changed)
        self.internal_table.doubleClicked.connect(self._on_select_internal_fic)
        self.select_button.clicked.connect(self._on_select_internal_fic)

        self._populate_internal_table(recommendations)
        self.internal_table.sortByColumn(0, Qt.SortOrder.DescendingOrder)

        return tab_widget

    def _create_external_tab(self) -> QWidget:
        """Crea il widget per la scheda di scoperta (SENZA Author-Curated)."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)

        controls_group = QGroupBox("1. Set Discovery Parameters")
        form_layout = QFormLayout(controls_group)

        self.strategy_combo = QComboBox()

        self.strategy_combo.addItems(["The Safe Bet", "Hidden Gem"])
        self.strategy_combo.setToolTip(
            "Safe Bet: Matches your top tastes.\n" "Hidden Gem: Finds quality fics with low popularity."
        )

        self.word_count_input = QLineEdit()
        self.word_count_input.setPlaceholderText("e.g., >10000 or 5000-10000")

        self.complete_combo = QComboBox()
        self.complete_combo.addItems(["Any Status", "Complete Fics Only", "Incomplete Fics Only"])

        self.sort_by_combo = QComboBox()
        self.sort_by_combo.addItems(["Best Match (Default)", "Most Kudos", "Most Hits", "Most Recently Updated"])

        form_layout.addRow("Strategy:", self.strategy_combo)
        form_layout.addRow("Word Count:", self.word_count_input)
        form_layout.addRow("Status:", self.complete_combo)
        form_layout.addRow("Sort by:", self.sort_by_combo)

        self.discover_button = QPushButton("🚀 Discover New Fics!")
        form_layout.addRow(self.discover_button)
        layout.addWidget(controls_group)

        results_group = QGroupBox("2. Discovery Results (Double-click a row for details and actions)")
        results_layout = QVBoxLayout(results_group)
        self.external_table = QTableWidget()
        self.external_table.setColumnCount(7)
        self.external_table.setHorizontalHeaderLabels(
            ["Match Score", "Title", "Author", "Fandom", "Relationships", "Rating", "Words"]
        )

        self.external_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.external_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.external_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.external_table.setSortingEnabled(True)

        header = self.external_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        results_layout.addWidget(self.external_table)
        layout.addWidget(results_group, 1)

        self.discover_button.clicked.connect(self._on_discover)
        self.external_table.doubleClicked.connect(self._on_external_double_clicked)

        return tab_widget

    def _populate_internal_table(self, recommendations: List[Dict[str, Any]]) -> None:
        self.internal_table.setRowCount(len(recommendations))
        for row, fic in enumerate(recommendations):
            score_item = NumericTableWidgetItem(f"{fic.get('recommendation_score', 0.0):.2f}")
            score_item.setData(Qt.ItemDataRole.UserRole, fic["url"])
            self.internal_table.setItem(row, 0, score_item)
            self.internal_table.setItem(row, 1, QTableWidgetItem(fic.get("title")))
            self.internal_table.setItem(row, 2, QTableWidgetItem(fic.get("author")))
            self.internal_table.setItem(row, 3, QTableWidgetItem(fic.get("fandoms")))

    def _populate_external_table(self, results: List[Dict[str, Any]]) -> None:
        self.external_results_data = {fic["url"]: fic for fic in results}
        self.external_table.setSortingEnabled(False)
        self.external_table.setRowCount(len(results))
        for row, fic in enumerate(results):
            score_item = NumericTableWidgetItem(f"{fic.get('recommendation_score', 0.0):.2f}")
            score_item.setData(Qt.ItemDataRole.UserRole, fic["url"])

            self.external_table.setItem(row, 0, score_item)
            self.external_table.setItem(row, 1, QTableWidgetItem(fic.get("title")))
            self.external_table.setItem(row, 2, QTableWidgetItem(fic.get("author")))
            self.external_table.setItem(row, 3, QTableWidgetItem(fic.get("fandoms")))
            self.external_table.setItem(row, 4, QTableWidgetItem(fic.get("relationships")))
            self.external_table.setItem(row, 5, QTableWidgetItem(fic.get("rating")))
            self.external_table.setItem(row, 6, NumericTableWidgetItem(f"{fic.get('word_count', 0):,}"))
        self.external_table.setSortingEnabled(True)
        self.external_table.sortByColumn(0, Qt.SortOrder.DescendingOrder)

    def _on_internal_selection_changed(self) -> None:
        self.select_button.setEnabled(len(self.internal_table.selectedItems()) > 0)

    def _on_select_internal_fic(self) -> None:
        selected_items = self.internal_table.selectedItems()
        if not selected_items:
            return

        item = self.internal_table.item(selected_items[0].row(), 0)
        if item:
            url = item.data(Qt.ItemDataRole.UserRole)
            self.fic_selected.emit(url)
            self.accept()

    def _on_discover(self) -> None:
        strategy_map = {"The Safe Bet": "safe_bet", "The Hidden Gem": "hidden_gem", "The Wildcard": "wildcard"}
        sort_map = {
            "Best Match (Default)": "best_match",
            "Most Kudos": "kudos_count",
            "Most Hits": "hits",
            "Most Recently Updated": "date_updated",
        }

        is_complete: Optional[bool] = None
        if self.complete_combo.currentIndex() == 1:
            is_complete = True
        elif self.complete_combo.currentIndex() == 2:
            is_complete = False

        search_params = {
            "strategy": strategy_map.get(self.strategy_combo.currentText()),
            "word_count": self.word_count_input.text().strip() or None,
            "is_complete": is_complete,
            "sort_by": sort_map.get(self.sort_by_combo.currentText()),
        }
        self.discover_fics_requested.emit(search_params)
        self.on_discovery_start()

    def _on_external_double_clicked(self, index: QModelIndex) -> None:
        url_item = self.external_table.item(index.row(), 0)
        if not url_item:
            return
        url = url_item.data(Qt.ItemDataRole.UserRole)
        fic_data = self.external_results_data.get(url)
        if not fic_data:
            return

        popup = FicDetailPopup(fic_data, self)
        popup.import_requested.connect(self.import_fic_requested.emit)
        popup.add_to_queue_requested.connect(lambda url: self.add_to_queue_requested.emit([url]))
        popup.exec()

    def on_discovery_start(self) -> None:
        self.discover_button.setText("Discovering...")
        self.discover_button.setEnabled(False)
        self.external_table.setRowCount(0)

    def on_discovery_finished(self, results: List[Dict[str, Any]]) -> None:
        self.discover_button.setText("🚀 Discover New Fics!")
        self.discover_button.setEnabled(True)
        if not results:
            QMessageBox.information(
                self, "No New Fics Found", "Your search didn't return any new fics that aren't already in your library."
            )
            return
        self._populate_external_table(results)
        self.tabs.setCurrentWidget(self.external_tab)

    def on_discovery_error(self, message: str) -> None:
        self.discover_button.setText("🚀 Discover New Fics!")
        self.discover_button.setEnabled(True)
        QMessageBox.warning(self, "Discovery Failed", f"An error occurred while searching on AO3:\n\n{message}")
