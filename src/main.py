import sys

from ao3_helper.application import App
from ao3_helper.logger_setup import logger

if __name__ == "__main__":
    try:
        app = App(sys.argv)
        exit_code = app.run()
        sys.exit(exit_code)
    except Exception as e:
        logger.critical(f"An unhandled exception occurred: {e}", exc_info=True)
        sys.exit(1)
