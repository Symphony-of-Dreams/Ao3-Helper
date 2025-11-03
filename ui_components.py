from PyQt6.QtWidgets import QCompleter, QTableWidgetItem


class TagCompleter(QCompleter):
    """
    A custom QCompleter that handles comma-separated tags.
    It provides suggestions for the term currently being typed after the last comma.
    """

    def __init__(self, *args):
        super().__init__(*args)

    def pathFromIndex(self, index):
        """Returns the full text to be inserted from a selected suggestion."""
        path = super().pathFromIndex(index)

        text = self.widget().text()

        last_comma = text.rfind(",")

        if last_comma == -1:

            return path
        else:

            prefix = text[:last_comma].strip()
            return f"{prefix}, {path}"

    def splitPath(self, path):
        """Splits the input text to find the part to be completed."""

        last_comma = path.rfind(",")

        return [path[last_comma + 1 :].lstrip()]


class NumericTableWidgetItem(QTableWidgetItem):
    """
    A QTableWidgetItem subclass that provides correct numeric sorting
    instead of lexical sorting.
    """

    def __lt__(self, other: QTableWidgetItem) -> bool:

        try:

            self_data = float(self.text())
            other_data = float(other.text())
            return self_data < other_data
        except (ValueError, TypeError):

            return super().__lt__(other)
