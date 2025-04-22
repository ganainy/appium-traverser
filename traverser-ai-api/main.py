import logging
import colorlog
import os
import sys

# Configure colored logging
handler = colorlog.StreamHandler(sys.stdout)
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
))

logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)  # Set to DEBUG to see all logs

# Remove any existing handlers to avoid duplicate logs
for old_handler in logger.handlers[:-1]:
    logger.removeHandler(old_handler)

# Make sure environment variables are loaded (especially API key)
try:
    import config
    if not config.GEMINI_API_KEY:
        logging.critical("GEMINI_API_KEY environment variable not set. Please set it in a .env file or system environment.")
        sys.exit(1)

    # Handle existing data based on CONTINUE_EXISTING_RUN flag
    if not config.CONTINUE_EXISTING_RUN:
        logging.info("Starting fresh run - clearing existing data...")
        # Remove existing screenshots
        if os.path.exists(config.SCREENSHOTS_DIR):
            import shutil
            shutil.rmtree(config.SCREENSHOTS_DIR)
        # Remove existing database
        if os.path.exists(config.DB_NAME):
            os.remove(config.DB_NAME)
        logging.info("Existing data cleared successfully.")
    else:
        logging.info("Continuing from existing data - keeping database and screenshots.")

    # Create screenshots directory if it doesn't exist
    os.makedirs(config.SCREENSHOTS_DIR, exist_ok=True)

except ImportError:
    logging.critical("Could not import configuration. Make sure config.py exists.")
    sys.exit(1)
except Exception as e:
    logging.critical(f"Error during initial setup: {e}")
    sys.exit(1)


# Import crawler only after basic checks
from crawler import AppCrawler

if __name__ == "__main__":
    logging.info("Initializing crawler...")
    crawler = AppCrawler()
    try:
        crawler.run()
    except Exception as e:
        logging.critical(f"Crawler run failed with unexpected error: {e}", exc_info=True)

    logging.info("Crawler execution complete.")