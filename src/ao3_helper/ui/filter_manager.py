from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QInputDialog, QMessageBox

from ao3_helper.core.database import get_all_filters, get_filtered_fics, save_filter
from ao3_helper.logger_setup import logger
from ao3_helper.ui.dialogs.filter_builder_dialog import FilterBuilderDialog

if TYPE_CHECKING:
    from ao3_helper.ui.main_window import MainWindow


class FilterManager(QObject):
    """Manages search, filtering, and saved filters."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.main_window = main_window

    def load(self) -> None:
        """Loads saved filters from the DB and populates the ComboBox."""
        self.main_window.saved_filters_combo.blockSignals(True)
        self.main_window.saved_filters_combo.clear()
        self.main_window.saved_filters_combo.addItem("Saved Filters...")

        filters = get_all_filters()
        for f in filters:
            self.main_window.saved_filters_combo.addItem(f["name"], userData=f)

        self.main_window.saved_filters_combo.blockSignals(False)

    @pyqtSlot()
    def trigger_search(self) -> None:
        """
        Builds a 'Filter Object' based on the current state of the search UI
        and updates the table.
        """

        filters: Dict[str, Any] = {"conditions": {}, "tags": {}, "user_tags": {}}

        search_text = self.main_window.search_input.text().strip()
        field_idx = self.main_window.search_combo.currentIndex()
        status_idx = self.main_window.status_filter_combo.currentIndex()

        if status_idx > 0:
            filters["conditions"]["status"] = self.main_window.status_filter_combo.currentText()

        field_map = {
            0: "all",
            1: "title",
            2: "author",
            3: "fandoms",
            4: "rating",
            5: "tags",
            6: "category",
            7: "relationships",
            8: "characters",
            9: "user_tags",
            10: "series_name",
        }
        field_key = field_map.get(field_idx, "all")

        if search_text:
            if field_key == "tags":
                filters["tags"]["and"] = [t.strip() for t in search_text.split(",")]
            elif field_key == "user_tags":
                filters["user_tags"]["and"] = [t.strip() for t in search_text.split(",")]
            else:
                filters["conditions"][field_key] = search_text

        fics_found = get_filtered_fics(view_filter=self.main_window.current_view_filter, filters=filters)
        self.main_window._update_fics_table(fics_found)

    @pyqtSlot()
    def clear_search(self) -> None:
        """Resets all search and filter controls to their default state."""

        self.main_window.search_input.blockSignals(True)
        self.main_window.search_combo.blockSignals(True)
        self.main_window.status_filter_combo.blockSignals(True)
        self.main_window.saved_filters_combo.blockSignals(True)

        self.main_window.search_input.clear()
        self.main_window.search_combo.setCurrentIndex(0)
        self.main_window.status_filter_combo.setCurrentIndex(0)
        self.main_window.saved_filters_combo.setCurrentIndex(0)

        self.main_window.search_input.blockSignals(False)
        self.main_window.search_combo.blockSignals(False)
        self.main_window.status_filter_combo.blockSignals(False)
        self.main_window.saved_filters_combo.blockSignals(False)

        self.trigger_search()

    @pyqtSlot()
    def on_view_filter_changed(self) -> None:
        """
        Handles the view change between Library, History, and All.
        Updates the internal state and reloads the fics table.
        """
        if self.main_window.library_button.isChecked():
            self.main_window.current_view_filter = "library"
        elif self.main_window.history_button.isChecked():
            self.main_window.current_view_filter = "history"
        elif self.main_window.inbox_button.isChecked():
            self.main_window.current_view_filter = "inbox"
        else:
            self.main_window.current_view_filter = "all"

        logger.info(f"View filter changed to: '{self.main_window.current_view_filter}'")

        self.main_window.search_input.clear()
        self.main_window.status_filter_combo.setCurrentIndex(0)

        self.main_window._update_fics_table()

    @pyqtSlot()
    def save_current_filter(self) -> None:
        """Saves the current state of the filters as a new filter."""

        filters: Dict[str, Any] = {"conditions": {}, "tags": {}, "user_tags": {}}

        search_text = self.main_window.search_input.text().strip()
        field_idx = self.main_window.search_combo.currentIndex()
        status_idx = self.main_window.status_filter_combo.currentIndex()
        if status_idx > 0:
            filters["conditions"]["status"] = self.main_window.status_filter_combo.currentText()
        field_map = {
            0: "all",
            1: "title",
            2: "author",
            3: "fandoms",
            4: "rating",
            5: "tags",
            6: "category",
            7: "relationships",
            8: "characters",
            9: "user_tags",
            10: "series_name",
        }
        field_key = field_map.get(field_idx, "all")
        if search_text:
            if field_key == "tags":
                filters["tags"]["and"] = [t.strip() for t in search_text.split(",")]
            elif field_key == "user_tags":
                filters["user_tags"]["and"] = [t.strip() for t in search_text.split(",")]
            else:
                filters["conditions"][field_key] = search_text

        filter_name, ok = QInputDialog.getText(self.main_window, "Save Filter", "Enter a name for this filter:")
        if ok and filter_name:
            try:

                save_filter(filter_name, json.dumps(filters))
                QMessageBox.information(self.main_window, "Success", f"Filter '{filter_name}' saved.")
                self.load()
            except Exception:
                QMessageBox.warning(self.main_window, "Error", f"A filter named '{filter_name}' already exists.")

    @pyqtSlot(int)
    def apply_saved_filter(self, index: int) -> None:
        """
        Applies a saved filter selected from the ComboBox, visibly
        updating all UI controls to reflect the active filter.
        """
        if index == 0:
            return

        filter_data = self.main_window.saved_filters_combo.itemData(index)
        if not filter_data or "filter_data" not in filter_data:
            return

        try:
            filters = json.loads(filter_data["filter_data"])
        except json.JSONDecodeError:
            logger.error(f"Failed to parse saved filter data: {filter_data['filter_data']}")
            return

        self.main_window.search_input.blockSignals(True)
        self.main_window.search_combo.blockSignals(True)
        self.main_window.status_filter_combo.blockSignals(True)

        self.main_window.search_input.clear()
        self.main_window.search_combo.setCurrentIndex(0)
        self.main_window.status_filter_combo.setCurrentIndex(0)

        conditions = filters.get("conditions", {})
        tags_filter = filters.get("tags", {})
        user_tags_filter = filters.get("user_tags", {})

        if "status" in conditions:

            status_index = self.main_window.status_filter_combo.findText(conditions["status"])
            if status_index != -1:
                self.main_window.status_filter_combo.setCurrentIndex(status_index)
            conditions.pop("status")

        field_map_inv = {
            "all": 0,
            "title": 1,
            "author": 2,
            "fandoms": 3,
            "rating": 4,
            "category": 6,
            "relationships": 7,
            "characters": 8,
            "series_name": 10,
        }

        found_main_search = False
        for field, value in conditions.items():
            if field in field_map_inv:
                self.main_window.search_combo.setCurrentIndex(field_map_inv[field])
                self.main_window.search_input.setText(value)
                found_main_search = True
                break

        if not found_main_search:
            if tags_filter.get("and"):
                self.main_window.search_combo.setCurrentIndex(5)
                self.main_window.search_input.setText(", ".join(tags_filter["and"]))
            elif user_tags_filter.get("and"):
                self.main_window.search_combo.setCurrentIndex(9)
                self.main_window.search_input.setText(", ".join(user_tags_filter["and"]))

        self.main_window.search_input.blockSignals(False)
        self.main_window.search_combo.blockSignals(False)
        self.main_window.status_filter_combo.blockSignals(False)

        self.trigger_search()

        self.main_window.saved_filters_combo.setCurrentIndex(0)

    @pyqtSlot()
    def open_filter_builder(self) -> None:
        """Opens the Filter Builder, passing data for suggestions."""

        completer_data = self.main_window._prepare_completer_data()
        dialog = FilterBuilderDialog(completer_data, self.main_window)

        dialog.filter_generated.connect(self.apply_advanced_filter)
        dialog.exec()

    @pyqtSlot(dict, bool)
    def apply_advanced_filter(self, filters: Dict[str, Any], should_save: bool) -> None:
        """
        Applies a complex filter from the FilterBuilder, optionally
        saves it, and updates the main search UI.
        """
        if should_save:
            filter_name, ok = QInputDialog.getText(self.main_window, "Save Filter", "Enter a name for this filter:")
            if ok and filter_name:
                try:
                    save_filter(filter_name, json.dumps(filters))
                    self.load()
                except Exception:
                    QMessageBox.warning(self.main_window, "Error", f"A filter named '{filter_name}' already exists.")
                    return
            elif not ok:
                return

        self.clear_search()

        fics_found = get_filtered_fics(view_filter=self.main_window.current_view_filter, filters=filters)
        self.main_window._update_fics_table(fics_found)

        self.main_window.search_input.blockSignals(True)
        self.main_window.search_input.setText("[Advanced Filter Active]")
        self.main_window.search_input.blockSignals(False)

    def execute_search_from_link(self, link: str) -> None:
        """
        Handler for clicking a search link in the details panel.
        """
        logger.debug(f"DEBUG: _execute_search_from_link received: '{link}'")
        try:
            field, value = link.split(":", 1)
        except ValueError:
            return

        combo_map = {
            "author": 2,
            "fandoms": 3,
            "rating": 4,
            "tags": 5,
            "category": 6,
            "relationships": 7,
            "characters": 8,
            "user_tags": 9,
            "series_name": 10,
        }

        if (idx := combo_map.get(field)) is not None:
            self.main_window.search_combo.setCurrentIndex(idx)
            self.main_window.search_input.setText(value)
