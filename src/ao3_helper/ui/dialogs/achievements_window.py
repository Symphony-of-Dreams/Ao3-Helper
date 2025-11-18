from typing import Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ao3_helper.core.database import get_unlocked_achievements
from ao3_helper.workers.gamification import ACHIEVEMENTS


class AchievementsWindow(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("My Achievements")
        self.setMinimumSize(600, 400)

        main_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)
        container = QWidget()
        scroll_area.setWidget(container)
        self.grid_layout = QGridLayout(container)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._populate_grid()

    def _populate_grid(self) -> None:
        unlocked = get_unlocked_achievements()

        columns = 4
        row, col = 0, 0

        for achievement_id, info in sorted(ACHIEVEMENTS.items()):
            is_unlocked = achievement_id in unlocked
            unlock_date = unlocked.get(achievement_id)

            badge_widget = self._create_badge_widget(info, is_unlocked, unlock_date)

            self.grid_layout.addWidget(badge_widget, row, col)

            col += 1
            if col >= columns:
                col = 0
                row += 1

    def _create_badge_widget(self, info: Dict[str, str], is_unlocked: bool, unlock_date: Optional[str]) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("QWidget { border: 1px solid #cccccc; border-radius: 5px; }")

        layout = QVBoxLayout(widget)

        tooltip_text = f"<b>{info['name']}</b><br>{info['description']}"
        if is_unlocked and unlock_date:
            tooltip_text += f"<br><i>Unlocked on: {unlock_date}</i>"
        widget.setToolTip(tooltip_text)

        icon_label = QLabel(info["icon"])
        icon_label.setObjectName("icon_label")

        name_label = QLabel(f"<b>{info['name']}</b>")
        name_label.setObjectName("name_label")

        date_label = QLabel(f"<i>{unlock_date}</i>" if is_unlocked else "")
        date_label.setObjectName("date_label")

        if not is_unlocked:
            widget.setEnabled(False)
            name_label.setText("???")
            icon_label.setText("🔒")

        layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(date_label, alignment=Qt.AlignmentFlag.AlignCenter)

        return widget
