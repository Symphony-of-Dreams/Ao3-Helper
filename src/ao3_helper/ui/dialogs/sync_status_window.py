from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from ao3_helper.workers.workers import TotalSyncWorker


class SyncStatusWindow(QDialog):
    def __init__(self, worker: "TotalSyncWorker", total_fics: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.worker = worker

        self.setWindowTitle("Syncing Statuses...")
        self.setMinimumWidth(450)
        self.setModal(False)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        self.status_label = QLabel(f"Preparing to sync {total_fics} fics...")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(total_fics)
        self.progress_bar.setTextVisible(True)

        self.eta_label = QLabel("ETA: Calculating...")
        self.eta_label.setStyleSheet("color: #666;")

        self.cancel_button = QPushButton("Cancel")

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.eta_label, 1, Qt.AlignmentFlag.AlignLeft)
        bottom_layout.addWidget(self.cancel_button, 0, Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addLayout(bottom_layout)

        self.cancel_button.clicked.connect(self._cancel_sync)

    @pyqtSlot(int, int)
    def update_progress(self, current: int, total: int) -> None:
        self.progress_bar.setValue(current)

    @pyqtSlot(str)
    def update_status_text(self, text: str) -> None:
        self.status_label.setText(text)

    @pyqtSlot(str)
    def update_eta(self, eta_string: str) -> None:
        self.eta_label.setText(f"ETA: {eta_string}")

    @pyqtSlot(str)
    def on_sync_finished(self, summary: str) -> None:
        self.setWindowTitle("Sync Finished")

        self.cancel_button.clicked.disconnect(self._cancel_sync)
        self.cancel_button.clicked.connect(self.accept)

        self.cancel_button.setText("Close")
        self.eta_label.setVisible(False)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowCloseButtonHint)
        self.show()

    def _cancel_sync(self) -> None:
        self.worker.cancel()
        self.status_label.setText("Cancelling... Please wait.")
        self.cancel_button.setEnabled(False)

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        self._cancel_sync()
        super().closeEvent(event)
