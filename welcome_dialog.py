from typing import Optional

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import constants as const
import security_manager
from ao3_manager import ao3_client
from config_manager import config_manager


class LoginWorker(QObject):
    finished = pyqtSignal()

    @pyqtSlot()
    def run(self) -> None:
        """Attempts to reload the AO3 session."""
        ao3_client.reload_session()
        self.finished.emit()


class WelcomeDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome to AO3 Helper!")
        self.setMinimumWidth(500)

        self.login_thread: Optional[QThread] = None

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel("<h2>Welcome to AO3 Helper!</h2>"))
        main_layout.addWidget(QLabel("To get the most out of the application, you can log in with your AO3 account."))

        privacy_button = QPushButton("Read our Privacy Promise (Your data is 100% local)")
        privacy_button.setStyleSheet("text-align: left; border: none; color: #007acc; text-decoration: underline;")
        privacy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        privacy_button.clicked.connect(self._show_privacy_info)
        main_layout.addWidget(privacy_button)
        main_layout.addSpacing(15)
        main_layout.addWidget(QLabel("<b>How it works:</b>"))
        explanation = (
            "<ul>"
            "<li><b>Guest (no login):</b> Add fics manually and manage your local library.</li>"
            "<li><b>Username only:</b> Automatically sync Kudos & Comment status.</li>"
        )
        main_layout.addWidget(QLabel(explanation))

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("AO3 Username")
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Password (optional, for full access)")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        main_layout.addWidget(self.user_input)
        main_layout.addWidget(self.pass_input)

        btn_layout = QHBoxLayout()
        self.save_button = QPushButton("Save & Connect")
        self.guest_button = QPushButton("Proceed as Guest")
        btn_layout.addStretch()
        btn_layout.addWidget(self.guest_button)
        btn_layout.addWidget(self.save_button)
        main_layout.addLayout(btn_layout)

        self.save_button.clicked.connect(self._save_and_connect)
        self.guest_button.clicked.connect(self.reject)

    def _show_privacy_info(self) -> None:
        QMessageBox.information(
            self,
            "Our Privacy Promise",
            "<h3>Your Data Stays With You. Period.</h3>"
            "<p>This application is designed with a 'privacy-first' principle:</p>"
            "<ul>"
            "<li><b>100% Local:</b> All your data is stored ONLY on your computer. Nothing is ever sent to a third-party server.</li>"  # noqa: E501
            "<li><b>Direct to AO3:</b> The app only communicates directly with Archive of Our Own's servers, just like your web browser.</li>"  # noqa: E501
            "<li><b>Purpose-Driven:</b> Your password is only used to authenticate a session to access locked works and your personal data like bookmarks.</li>"  # noqa: E501
            "</ul>",
        )

    def _save_and_connect(self) -> None:
        """Salva le credenziali, tenta il login e fornisce un feedback chiaro all'utente."""
        new_username = self.user_input.text().strip()
        new_password = self.pass_input.text()

        config_manager.set(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME, new_username)
        config_manager.save_config()

        if new_password:
            security_manager.set_password(new_username, new_password)
        else:

            security_manager.delete_password(new_username)

        login_successful = ao3_client.reload_session()

        if login_successful and ao3_client.session:
            QMessageBox.information(
                self,
                "Success!",
                f"You have successfully logged in as '{ao3_client.session.username}'. Welcome to AO3 Helper!",
            )
        elif not new_username or new_username == const.CONFIG_DEFAULT_USER:

            QMessageBox.information(
                self,
                "Proceeding as Guest",
                "No username was entered. You will proceed as a guest.",
            )
        else:
            QMessageBox.warning(
                self,
                "Login Failed",
                "Your settings have been saved, but the AO3 login failed. Please check your credentials.\n"
                "You will proceed as a guest for now. You can try logging in again via the File > Settings menu.",
            )

        self.accept()
