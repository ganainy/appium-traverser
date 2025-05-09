import logging
import colorlog
import os
import sys
import json # Added for reading cache file
# Import crawler only after basic checks - MOVED LATER

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
config = None  # Define config before try block to ensure it's in scope
try:
    import config as cfg # Try importing config
    config = cfg # Assign to the outer scope variable if successful
    # Test if a known variable from config is accessible
    _ = config.APP_PACKAGE # This will raise AttributeError if config is None or not loaded properly
except ImportError as e:
    logging.critical(f"CRITICAL: Failed to import 'config' module. The error was: {e}", exc_info=True)
    logging.critical("Please ensure 'config.py' is in the same directory as 'main.py' (traverser_ai_api).")
    logging.critical("Also, ensure all dependencies required by 'config.py' (like 'python-dotenv') are installed in your active Python virtual environment.")
    logging.critical(f"Python executable being used: {sys.executable}")
    logging.critical(f"Python sys.path: {sys.path}")
    sys.exit(1)
except AttributeError as e:
    logging.critical(f"CRITICAL: 'config' module was imported but seems incomplete or variables are missing. Error: {e}", exc_info=True)
    logging.critical("This might happen if 'config.py' has an issue or did not load environment variables correctly.")
    logging.critical(f"Python executable being used: {sys.executable}")
    logging.critical(f"Python sys.path: {sys.path}")
    sys.exit(1)
except Exception as e:
    logging.critical(f"CRITICAL: An unexpected error occurred while trying to import 'config' module. Error: {e}", exc_info=True)
    logging.critical(f"Python executable being used: {sys.executable}")
    logging.critical(f"Python sys.path: {sys.path}")
    sys.exit(1)

# If we reach here, config is imported and seems okay.
# Now, proceed with the rest of the setup that might use 'config'.
try:
    # Removed: from app_info_manager import discover_and_filter_apps

    get_device_serial = None # Initialize
    generate_app_info_cache = None # Initialize
    try:
        # Attempt to import get_device_serial to construct cache filename
        # and generate_app_info_cache to regenerate it if needed.
        from find_app_info import get_device_serial, generate_app_info_cache
    except ImportError:
        # get_device_serial and generate_app_info_cache remain None
        logging.warning("Could not import get_device_serial or generate_app_info_cache from find_app_info.py.")
        logging.warning("Cannot automatically check for or regenerate app info cache.")

    # --- Retrieve Target App Info ---
    logging.info(f"Attempting to retrieve information for target app: {config.APP_PACKAGE}")
    # Ensure APP_INFO_OUTPUT_DIR exists
    os.makedirs(config.APP_INFO_OUTPUT_DIR, exist_ok=True)

    app_info_successfully_configured = False
    initial_target_package = config.APP_PACKAGE # Store initial target for lookup
    cache_filepath = None # Initialize for use in error messages if construction fails

    # Attempt to load app info from cache (up to two times)
    for attempt in range(2): # Max 2 attempts: 1st try, then 1 regenerate and retry
        if get_device_serial:
            try:
                device_id = get_device_serial()
                if device_id and device_id != "unknown_device":
                    filter_suffix = "health_filtered" if config.USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY else "all"
                    cache_filename = f"{device_id}_app_info_{filter_suffix}.json"
                    cache_filepath = os.path.join(config.APP_INFO_OUTPUT_DIR, cache_filename)

                    logging.info(f"Attempt {attempt + 1}: Checking for app info in cache file: {cache_filepath}")
                    if os.path.exists(cache_filepath):
                        with open(cache_filepath, 'r', encoding='utf-8') as f:
                            all_cached_apps = json.load(f)
                        
                        found_app_in_cache = None
                        if isinstance(all_cached_apps, list):
                            for app_entry in all_cached_apps:
                                if app_entry.get('package_name') == initial_target_package:
                                    found_app_in_cache = app_entry
                                    break
                        
                        if found_app_in_cache and found_app_in_cache.get('activity_name'):
                            logging.info(f"Found cached info for {initial_target_package} in {cache_filename}: Activity '{found_app_in_cache['activity_name']}'")
                            config.APP_PACKAGE = found_app_in_cache['package_name']
                            config.APP_ACTIVITY = found_app_in_cache['activity_name']
                            app_info_successfully_configured = True
                            break # Exit loop if successful
                        else:
                            logging.info(f"Info for {initial_target_package} not found in cache file {cache_filepath} or activity missing.")
                    else:
                        logging.info(f"Cache file {cache_filepath} not found.")
                else:
                    logging.warning("Could not get a valid device ID; cannot construct cache file name.")
            except FileNotFoundError:
                logging.info(f"Cache file {cache_filepath} not found (FileNotFoundError).")
            except json.JSONDecodeError:
                logging.error(f"Error decoding JSON from cache file: {cache_filepath or 'Path not constructed'}.")
            except Exception as e:
                logging.error(f"Error during cache check for app info: {e}", exc_info=True)
        else:
            logging.warning("get_device_serial is not available. Cannot check for app info cache file.")
            # If get_device_serial is missing, we can't proceed with cache logic, so break the loop.
            break 

        # If app info not configured and this is the first attempt, try to generate cache
        if not app_info_successfully_configured and attempt == 0:
            if generate_app_info_cache:
                logging.info("App info not found or incomplete. Attempting to generate app info cache by calling find_app_info.py logic...")
                try:
                    # Determine if AI filtering should be used for this cache generation based on config
                    use_ai_for_cache_gen = config.USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY
                    logging.info(f"Calling generate_app_info_cache with use_ai_filtering_for_this_cache={use_ai_for_cache_gen}")
                    
                    generated_cache_path, _ = generate_app_info_cache(
                        target_package_name_filter=initial_target_package,
                        use_ai_filtering_for_this_cache=use_ai_for_cache_gen # Pass the flag here
                    )
                    if generated_cache_path:
                        logging.info(f"App info cache generation process completed. Output: {generated_cache_path}")
                        # The next iteration of the loop will try to read this new/updated cache.
                        # Update cache_filepath to the one that was just generated, if different
                        # This is important if the device_id or filter_suffix logic in find_app_info
                        # somehow differs, though ideally it should align.
                        # For now, we assume the next loop iteration will correctly find the file
                        # based on the re-calculated cache_filepath.
                    else:
                        logging.error("Cache generation function did not return a file path. Will not be able to load info.")
                        break # Stop trying if generation failed to produce a path
                except Exception as e:
                    logging.error(f"An error occurred while trying to generate app info cache: {e}", exc_info=True)
                    break # Stop trying if generation itself failed
            else:
                logging.warning("generate_app_info_cache function is not available. Cannot regenerate cache.")
                break # Stop trying if we can't regenerate
        elif app_info_successfully_configured: # Should have broken already, but as a safeguard
            break


    # Final check and exit if not configured
    if not app_info_successfully_configured:
        error_message_parts = [
            f"Could not determine app info (package/activity) for target package '{initial_target_package}'.",
            "This script now relies on a pre-generated JSON file from 'find_app_info.py'."
        ]
        if cache_filepath:
            error_message_parts.append(f"Checked for cache file: {cache_filepath}")
        elif get_device_serial is None:
            error_message_parts.append("Could not attempt cache check because 'get_device_serial' from 'find_app_info.py' is unavailable.")
        else:
            error_message_parts.append("Could not construct cache file path (likely failed to get device ID).")

        error_message_parts.extend([
            "Please ensure:",
            "  1. 'find_app_info.py' has been run successfully for the connected device.",
            f"  2. It generated the expected JSON output file in the '{config.APP_INFO_OUTPUT_DIR}' directory.",
            "  3. The JSON file contains the target application's package name and main activity.",
            "Also, verify ADB connection and that the target app is installed on the device.",
            "Exiting."
        ])
        logging.critical("\\n".join(error_message_parts))
        sys.exit(1)
    else:
        # This log confirms the final configured values
        logging.info(f"App info successfully configured: PACKAGE='{config.APP_PACKAGE}', ACTIVITY='{config.APP_ACTIVITY}'")

    if not config.GEMINI_API_KEY:
        logging.critical("GEMINI_API_KEY environment variable not set. Please set it in a .env file or system environment.")
        sys.exit(1)

    # Handle existing data based on CONTINUE_EXISTING_RUN flag
    if not config.CONTINUE_EXISTING_RUN:
        logging.info("Starting fresh run - clearing existing data...")
        import shutil # Import shutil here to keep it scoped
        # Remove existing screenshots
        if hasattr(config, 'SCREENSHOTS_DIR') and os.path.exists(config.SCREENSHOTS_DIR):
            shutil.rmtree(config.SCREENSHOTS_DIR)
        # Remove existing annotated screenshots
        if hasattr(config, 'ANNOTATED_SCREENSHOTS_DIR') and os.path.exists(config.ANNOTATED_SCREENSHOTS_DIR):
            shutil.rmtree(config.ANNOTATED_SCREENSHOTS_DIR)
        # Remove existing database
        if hasattr(config, 'DB_NAME') and os.path.exists(config.DB_NAME):
            os.remove(config.DB_NAME)
        logging.info("Existing data cleared successfully.")
    else:
        logging.info("Continuing from existing data - keeping database and screenshots.")

    # Create necessary directories if they don't exist
    if hasattr(config, 'SCREENSHOTS_DIR'):
        os.makedirs(config.SCREENSHOTS_DIR, exist_ok=True)
    if hasattr(config, 'ANNOTATED_SCREENSHOTS_DIR'):
        os.makedirs(config.ANNOTATED_SCREENSHOTS_DIR, exist_ok=True)
    if hasattr(config, 'DB_NAME'):
        db_dir = os.path.dirname(config.DB_NAME)
        if db_dir: # Ensure db_dir is not empty if DB_NAME is just a filename
            os.makedirs(db_dir, exist_ok=True)
    # The TRAFFIC_CAPTURE_OUTPUT_DIR is created in crawler.py if enabled

except ImportError as e: # Catch import errors from find_app_info or shutil
    logging.critical(f"CRITICAL: An ImportError occurred during the main setup phase. The error was: {e}", exc_info=True)
    logging.critical(f"This could be due to an issue in 'find_app_info.py', or 'shutil' (used for clearing data).")
    logging.critical(f"Python executable being used: {sys.executable}")
    logging.critical(f"Python sys.path: {sys.path}")
    sys.exit(1)
except Exception as e: # General errors during setup
    logging.critical(f"An unexpected error occurred during initial setup after config import: {e}", exc_info=True)
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