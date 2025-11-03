import configparser
import os
from typing import Any

import constants as const
from logger_setup import logger


class ConfigManager:
    filename: str
    config: configparser.ConfigParser

    def __init__(self, filename: str = const.CONFIG_PATH) -> None:
        """
        Loads the configuration from the file.
        Ensures all necessary sections and default values exist.
        Preserves existing user settings.
        """
        self.filename = filename
        self.config = configparser.ConfigParser()
        self.config.read(self.filename, encoding="utf-8")

        default_config = {
            const.CONFIG_SECTION_CREDS: {
                const.CONFIG_KEY_USERNAME: const.CONFIG_DEFAULT_USER,
            },
            const.CONFIG_SECTION_SETTINGS: {
                const.CONFIG_KEY_MANUAL_OVERRIDE: "false",
                const.CONFIG_KEY_THEME: const.THEME_DEFAULT,
                "welcome_dialog_shown": "false",
                "full_history_import_completed": "false",
            },
            const.CONFIG_SECTION_UI: {
                const.CONFIG_KEY_GEOMETRY: "",
                const.CONFIG_KEY_COL_ORDER: "",
                "hidden_columns": "",
            },
        }

        something_changed = False

        for section, keys in default_config.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
                logger.debug(f"Added missing config section: [{section}]")
                something_changed = True

            for key, default_value in keys.items():
                if not self.config.has_option(section, key):
                    self.config.set(section, key, default_value)
                    logger.debug(
                        f"Added missing config key '{key}' to section '{section}' with default value '{default_value}'."
                    )
                    something_changed = True

        if something_changed:
            logger.info("Configuration file was updated with missing default settings.")
            self.save_config()

        logger.info("Configuration file loaded and validated.")

    def save_config(self) -> None:
        """Saves the current configuration to the file."""
        try:
            os.makedirs(os.path.dirname(self.filename) or ".", exist_ok=True)
            with open(self.filename, "w", encoding="utf-8") as config_file:
                self.config.write(config_file)
            logger.info("Configuration saved successfully.")
        except Exception:
            logger.exception("Failed to save configuration file.")

    def get(self, section: str, key: str, fallback: Any = None) -> Any:
        """Gets a value from the config, providing a fallback."""
        try:
            return self.config.get(section, key, fallback=fallback)
        except Exception:
            logger.warning(
                f"Attempted to get missing config key '{key}' from section '{section}'. Using fallback: {fallback}"
            )
            return fallback

    def getboolean(self, section: str, key: str, fallback: bool = False) -> bool:
        """Gets a boolean value from the config, providing a fallback."""
        try:
            return self.config.getboolean(section, key, fallback=fallback)
        except Exception:
            logger.warning(
                f"Attempted to get missing boolean config key '{key}' from section '{section}'. Using fallback: {fallback}"  # noqa: E501
            )
            return fallback

    def set(self, section: str, key: str, value: Any) -> None:
        """Sets a value in the config. Remember to call save_config() to persist."""
        if not self.config.has_section(section):
            self.config.add_section(section)
            logger.debug(f"Added section '{section}' before setting key '{key}'.")
        self.config.set(section, key, str(value))
        logger.debug(f"Set config key '{key}' in section '{section}' to '{value}'.")


config_manager = ConfigManager(const.CONFIG_PATH)
