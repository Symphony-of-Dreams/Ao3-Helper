import sys
from typing import Optional

from PyQt6.QtCore import QProcess
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

from ao3_helper import constants as const
from ao3_helper.core import security_manager
from ao3_helper.core.config_manager import config_manager


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
        """
        Salva le impostazioni. Se il nome utente viene cambiato, forza un riavvio
        dell'applicazione per caricare il profilo corretto.
        """
        old_username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME, fallback="")
        new_username = self.user_input.text().strip()
        new_password = self.pass_input.text()

        # Salva le impostazioni non relative all'utente (possono essere cambiate senza riavvio)
        config_manager.set(
            const.CONFIG_SECTION_SETTINGS,
            const.CONFIG_KEY_MANUAL_OVERRIDE,
            "true" if self.override_checkbox.isChecked() else "false",
        )
        # Applichiamo subito questa modifica per non perderla
        config_manager.save_config()

        # Controlla se l'utente è cambiato
        if new_username != old_username:
            reply = QMessageBox.question(
                self,
                "Restart Required",
                f"You are changing the active user from '{old_username or 'guest'}' to '{new_username or 'guest'}'.\n\n"
                "The application must restart to load the correct profile.\n\n"
                "Do you want to proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Salva le nuove credenziali
                config_manager.set(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME, new_username)
                config_manager.save_config()

                if new_password:
                    security_manager.set_password(new_username, new_password)
                else:  # Se la password è vuota, assicurati di cancellare quella vecchia
                    security_manager.delete_password(new_username)

                # Riavvia l'applicazione
                from PyQt6.QtWidgets import QApplication

                QApplication.quit()
                QProcess.startDetached(sys.executable, sys.argv or [])
            else:
                # L'utente ha annullato, non fare nulla
                return
        else:
            # L'utente non è cambiato, possiamo procedere senza riavvio
            # Salva la password (potrebbe essere cambiata)
            if new_password:
                security_manager.set_password(new_username, new_password)
            else:
                security_manager.delete_password(new_username)

            # Ricarica la sessione AO3 per applicare eventuali cambi di password
            from ao3_helper.core.ao3_manager import ao3_client

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

            # Chiudi la finestra di dialogo
            self.accept()
