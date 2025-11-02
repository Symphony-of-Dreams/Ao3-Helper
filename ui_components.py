# ui_components.py

from PyQt6.QtWidgets import QTableWidgetItem


class NumericTableWidgetItem(QTableWidgetItem):
    """
    A QTableWidgetItem subclass that provides correct numeric sorting
    instead of lexical sorting.
    """

    def __lt__(self, other: QTableWidgetItem) -> bool:
        # Try to convert item data to float for comparison.
        # This handles both integers and floats correctly.
        try:
            # We use the item's text for display, which is what we need to compare.
            self_data = float(self.text())
            other_data = float(other.text())
            return self_data < other_data
        except (ValueError, TypeError):
            # If conversion fails for any reason, fall back to standard string comparison.
            return super().__lt__(other)
