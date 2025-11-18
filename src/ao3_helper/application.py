from playhouse.sqlite_ext import SqliteExtDatabase
from PyQt6.QtWidgets import QApplication, QMessageBox

from ao3_helper import constants as const
from ao3_helper.core.config_manager import config_manager
from ao3_helper.core.database import get_db_path_for_user, run_database_migrations
from ao3_helper.core.models import db
from ao3_helper.logger_setup import logger
from ao3_helper.ui.main_window import MainWindow


class App(QApplication):
    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.setStyle("Fusion")
        self._main_window: MainWindow | None = None

    def run(self) -> int:
        logger.info("=========================================")
        logger.info("Application starting...")

        try:

            username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME, fallback="")

            db_path = get_db_path_for_user(username)
            logger.info(f"Loading profile for user: '{username if username else 'guest'}'. DB Path: {db_path}")
            database_instance = SqliteExtDatabase(
                db_path,
                pragmas={
                    "journal_mode": "WAL",
                    "cache_size": -1024 * 64,
                    "foreign_keys": 1,
                    "ignore_check_constraints": 0,
                    "synchronous": 0,
                },
                timeout=30,
            )
            db.initialize(database_instance)

            run_database_migrations(db_path)

        except Exception:
            logger.critical("Database initialization or migration failed. The application cannot start.", exc_info=True)

            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setText("A critical error occurred with the database.")
            msg_box.setInformativeText("The application cannot start. Please check the logs for details.")
            msg_box.setWindowTitle("Startup Error")
            msg_box.exec()
            return 1

        is_logged_in = username and username != const.CONFIG_DEFAULT_USER

        if not is_logged_in:
            logger.info("User is not logged in. Displaying WelcomeDialog.")
            from ao3_helper.ui.dialogs.welcome_dialog import WelcomeDialog

            welcome_dialog = WelcomeDialog()
            welcome_dialog.exec()

        self._main_window = MainWindow()
        self._main_window.show()
        logger.info("Application startup complete. Main window is now visible.")

        return self.exec()
