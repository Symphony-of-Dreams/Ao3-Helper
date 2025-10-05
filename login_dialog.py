from typing import Optional

from PyQt6.QtWidgets import (
    QCheckBox,
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
from config_manager import config_manager


class LoginDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")

        user = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME, fallback="")

        pwd = security_manager.get_password(user) or ""

        override = config_manager.getboolean(
            const.CONFIG_SECTION_SETTINGS,
            const.CONFIG_KEY_MANUAL_OVERRIDE,
            fallback=False,
        )

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>AO3 Credentials</b>"))
        layout.addWidget(
            QLabel(
                "Username is used to sync Kudos/Comment status.\nPassword is optional, only for accessing locked fics."
            )
        )

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Username")
        self.user_input.setText(user if user != const.CONFIG_DEFAULT_USER else "")
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Password")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_input.setText(pwd)
        layout.addWidget(self.user_input)
        layout.addWidget(self.pass_input)

        layout.addSpacing(15)
        layout.addWidget(QLabel("<b>App Behaviour</b>"))
        self.override_checkbox = QCheckBox("Allow manual setting of 'Kudosed' and 'Commented' status")
        self.override_checkbox.setChecked(override)
        layout.addWidget(self.override_checkbox)

        btn_layout = QHBoxLayout()
        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Cancel")
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_button)
        btn_layout.addWidget(self.cancel_button)
        layout.addLayout(btn_layout)

        self.save_button.clicked.connect(self._save_settings)
        self.cancel_button.clicked.connect(self.reject)

    def _save_settings(self) -> None:
        new_username = self.user_input.text().strip()

        config_manager.set(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME, new_username)
        config_manager.set(
            const.CONFIG_SECTION_SETTINGS,
            const.CONFIG_KEY_MANUAL_OVERRIDE,
            "true" if self.override_checkbox.isChecked() else "false",
        )
        config_manager.save_config()

        new_password = self.pass_input.text()

        if new_password:
            security_manager.set_password(new_username, new_password)
        else:
            security_manager.delete_password(new_username)

        from ao3_manager import ao3_client

        login_successful = ao3_client.reload_session()

        if login_successful and ao3_client.session:
            QMessageBox.information(
                self,
                "Success",
                f"Settings saved. Logged in successfully as '{ao3_client.session.username}'.",
            )
        elif not new_username or new_username == const.CONFIG_DEFAULT_USER:
            QMessageBox.information(
                self,
                "Settings Saved",
                "Settings saved. You are now browsing as a guest.",
            )
        else:
            QMessageBox.warning(
                self,
                "Login Failed",
                "Settings saved, but the AO3 login failed. Please check your credentials.\n"
                "You are currently browsing as a guest.",
            )

        self.accept()
