from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, QVariant
from PyQt6.QtGui import QColor

from ao3_helper import constants as const


class FicTableModel(QAbstractTableModel):
    """
    Modello dati per la QTableView.
    Gestisce la visualizzazione efficiente delle fic senza creare widget per ogni cella.
    """

    def __init__(self, fics: List[Dict[str, Any]] = None):
        super().__init__()
        self._data = fics or []

        self._headers = const.COLUMN_MAP

        self._status_colors = {
            const.STATUS_TO_READ: QColor(const.CLR_STATUS_NEUTRAL_DEFAULT),
            const.STATUS_READ: QColor(const.CLR_STATUS_READ_THEMED),
            const.STATUS_DROPPED: QColor(const.CLR_STATUS_DROPPED_DEFAULT),
            const.STATUS_KUDOSED: QColor(const.CLR_STATUS_KUDOSED_THEMED),
            const.STATUS_COMMENTED: QColor(const.CLR_STATUS_COMMENTED_THEMED),
        }

    def update_data(self, new_data: List[Dict[str, Any]]):
        """Sostituisce l'intero dataset e notifica la vista."""
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return QVariant()

    def get_fic_at(self, row: int) -> Optional[Dict[str, Any]]:
        """Restituisce il dizionario dati completo per una data riga."""
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return QVariant()

        row = index.row()
        col = index.column()
        fic = self._data[row]
        column_name = self._headers[col]

        if role == Qt.ItemDataRole.DisplayRole:
            if column_name == const.COLUMN_TITLE:

                icons = []
                if fic.get("is_in_reading_queue"):
                    icons.append("🔖")
                if fic.get("is_in_library"):
                    icons.append("📚")
                icons.append("✅" if fic.get("is_complete") else "📖")
                return f"{' '.join(icons)} {fic.get('title')}"

            elif column_name == const.COLUMN_AUTHOR:
                return fic.get("author")
            elif column_name == const.COLUMN_FANDOM:
                return fic.get("fandoms")
            elif column_name == const.COLUMN_STATUS:
                verified = "🔹" if fic.get("status_verified") else "🔸"
                return f"{verified} {fic.get('status')}"
            elif column_name == const.COLUMN_WORDS:
                return f"{fic.get('word_count', 0):,}"
            elif column_name == const.COLUMN_CHAPTERS:
                return fic.get("chapters")
            elif column_name == const.COLUMN_DATE_UPDATED:
                return fic.get("date_updated")
            elif column_name == const.COLUMN_RATING:
                return fic.get("rating")
            elif column_name == const.COLUMN_USER_RATING:

                rating = fic.get("user_rating", 0) or 0
                return "★" * rating

            key = column_name.lower().replace(" ", "_")

            if column_name == const.COLUMN_MATCH_SCORE:
                key = "recommendation_score"
            if column_name == const.COLUMN_VISIT_COUNT:
                key = "visit_count"

            val = fic.get(key)
            if isinstance(val, (int, float)):
                return str(val)
            return val

        elif role == Qt.ItemDataRole.ForegroundRole:
            status = fic.get("status")
            return self._status_colors.get(status, QColor("black"))

        elif role == Qt.ItemDataRole.UserRole:

            if column_name == const.COLUMN_TITLE:
                return fic.get("url")

            key_map = {
                const.COLUMN_WORDS: "word_count",
                const.COLUMN_HITS: "hits",
                const.COLUMN_KUDOS: "kudos",
                const.COLUMN_VISIT_COUNT: "visit_count",
                const.COLUMN_MATCH_SCORE: "recommendation_score",
                const.COLUMN_USER_RATING: "user_rating",
                const.COLUMN_CHAPTERS: "chapter_count",
                const.COLUMN_AUTHOR: "author",
                const.COLUMN_FANDOM: "fandoms",
                const.COLUMN_STATUS: "status",
                const.COLUMN_DATE_UPDATED: "date_updated",
                const.COLUMN_RATING: "rating",
            }

            db_key = key_map.get(column_name)

            if db_key:
                val = fic.get(db_key)

                if val is None:
                    return 0 if column_name in [const.COLUMN_WORDS, const.COLUMN_HITS] else ""
                return val

            generic_key = column_name.lower().replace(" ", "_")
            val = fic.get(generic_key)

            if val is not None:
                return val

            return

        return QVariant()
