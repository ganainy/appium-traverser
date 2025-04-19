import logging
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
        # Optional: Add FileHandler
        # logging.FileHandler("crawler.log")
    ]
)

# Make sure environment variables are loaded (especially API key)
try:
    import config
    if not config.GEMINI_API_KEY:
        logging.critical("GEMINI_API_KEY environment variable not set. Please set it in a .env file or system environment.")
        sys.exit(1)
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