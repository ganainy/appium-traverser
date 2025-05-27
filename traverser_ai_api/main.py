import logging 
import time 
import sys
import os
import json
import shutil
from config import Config

# Import logging utilities and SCRIPT_START_TIME from utils.py
# This assumes utils.py is in the same directory or accessible via PYTHONPATH.
try:
    from utils import SCRIPT_START_TIME, LoggerManager, ElapsedTimeFormatter
except ImportError as e:
    # Fallback or error if utils.py is not found, crucial for logging.
    sys.stderr.write(f"Error: Could not import logging utilities from utils.py: {e}\n")
    sys.stderr.write("Please ensure utils.py is in the correct location and contains SCRIPT_START_TIME, LoggerManager, and ElapsedTimeFormatter.\n")
    # As a very basic fallback, define SCRIPT_START_TIME here so the script can attempt to run further,
    # but proper logging will likely fail.
    if 'SCRIPT_START_TIME' not in globals(): # Check if it was somehow defined before error
        SCRIPT_START_TIME = time.time()
    # A mock LoggerManager could be defined here for extreme fallback, but it's better to fix the import.
    sys.exit(1) # Exit if crucial utils are missing


# --- Global Logger Manager instance (instantiated from the imported class) ---
logger_manager_global = LoggerManager()

# --- Initial Bootstrap Logging (before config is fully loaded) ---
# This allows the Config class itself to log its loading process.
# It uses the standard logging.basicConfig until LoggerManager takes over.
logging.basicConfig(level=os.getenv("INIT_LOG_LEVEL", "INFO").upper(),
                    format="[%(levelname)s] %(asctime)s - %(module)s:%(lineno)d - %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)]) # Basic console handler
logging.info("Bootstrap logging initialized (main.py).")


# --- Configuration Setup ---
_current_script_dir = os.path.dirname(os.path.abspath(__file__))
# Assuming config.py contains both default variable assignments AND the Config class definition
DEFAULT_CONFIG_MODULE_PATH = os.path.join(_current_script_dir, 'config.py')
USER_CONFIG_JSON_FILENAME = "user_config.json"
USER_CONFIG_JSON_PATH = os.path.join(_current_script_dir, USER_CONFIG_JSON_FILENAME)

try:
    cfg = Config(defaults_module_path=DEFAULT_CONFIG_MODULE_PATH,
                user_config_json_path=USER_CONFIG_JSON_PATH)
    # Set the shutdown flag path on the cfg instance, making it accessible globally via cfg
    cfg.SHUTDOWN_FLAG_PATH = os.path.join(cfg.BASE_DIR, "crawler_shutdown.flag")

except Exception as e:
    logging.critical(f"CRITICAL: Failed to initialize Config object during startup. Error: {e}", exc_info=True)
    sys.exit(100) # Specific exit code for config failure

# --- Re-initialize Main Logging with settings from cfg using LoggerManager from utils ---
# Ensure OUTPUT_DATA_DIR is valid before using it for log paths
if not cfg.OUTPUT_DATA_DIR or not os.path.isdir(os.path.dirname(cfg.OUTPUT_DATA_DIR)): # Check if base exists or is creatable
    logging.warning(f"cfg.OUTPUT_DATA_DIR ('{cfg.OUTPUT_DATA_DIR}') is not set or invalid. Defaulting log directory to current script directory.")
    _log_base_dir = _current_script_dir
else:
    _log_base_dir = cfg.OUTPUT_DATA_DIR

_final_log_dir = os.path.join(_log_base_dir, "logs")
_final_log_file_path = os.path.join(_final_log_dir, cfg.LOG_FILE_NAME)

root_logger = logger_manager_global.setup_logging(log_level_str=cfg.LOG_LEVEL, log_file=_final_log_file_path)
root_logger.info(f"Main application logging re-initialized by LoggerManager. Level: {cfg.LOG_LEVEL.upper()}. File: '{_final_log_file_path}'")
root_logger.info(f"Using configuration from: Defaults='{cfg.DEFAULTS_MODULE_PATH}', User='{cfg.USER_CONFIG_FILE_PATH}'")
root_logger.info(f"Effective APP_PACKAGE: {cfg.APP_PACKAGE}")
root_logger.info(f"Effective APP_ACTIVITY: {cfg.APP_ACTIVITY}")
root_logger.info(f"Shutdown flag file path set to: {cfg.SHUTDOWN_FLAG_PATH}")


# --- Project Root and other important paths (derived from script location) ---
PROJECT_ROOT_DIR = os.path.abspath(os.path.join(_current_script_dir, "..")) # If main.py is in a subfolder


# --- Late Imports (after config and logging are stable) ---
# Example:
# try:
#     from .find_app_info import get_device_serial, generate_app_info_cache
#     from .crawler import AppCrawler # Assuming AppCrawler is in crawler.py in the same package
#     logging.info("Successfully imported AppCrawler and app info functions.")
# except ImportError as e:
#     logging.critical(f"CRITICAL: Failed to import core modules (AppCrawler/find_app_info). Error: {e}", exc_info=True)
#     sys.exit(101) # Specific exit code for import failure
# except Exception as e: # Catch other unexpected errors during import
#    logging.critical(f"CRITICAL: Unexpected error importing core modules. Error: {e}", exc_info=True)
#    sys.exit(102)


# --- Main Execution Block (Example) ---
if __name__ == "__main__":
    main_process_start_time = time.time() # For duration of this specific block
    logging.info(f"======== Script '{os.path.basename(__file__)}' __main__ block started. PID: {os.getpid()} ========")
    logging.info(f"Python: {sys.version.splitlines()[0]} on {sys.platform}")
    logging.info(f"Project Root (guessed): {PROJECT_ROOT_DIR}")
    logging.info(f"Base Config Dir (for defaults/flag): {cfg.BASE_DIR}")
    logging.info(f"Output Data Dir: {cfg.OUTPUT_DATA_DIR}")

    if os.path.exists(cfg.SHUTDOWN_FLAG_PATH): # Use path from cfg
        logging.warning(f"Found existing shutdown flag at startup: {cfg.SHUTDOWN_FLAG_PATH}. Removing it.")
        try:
            os.remove(cfg.SHUTDOWN_FLAG_PATH)
        except OSError as e_remove_flag:
            logging.error(f"Error removing stale shutdown flag at startup: {e_remove_flag}")

    # 1. Validate Essential Configurations from cfg
    if not cfg.APP_PACKAGE:
        logging.critical("APP_PACKAGE is not defined in configuration. Cannot proceed. Exiting.")
        sys.exit(1)
    if not cfg.APP_ACTIVITY:
        logging.critical("APP_ACTIVITY is not defined in configuration. Cannot proceed. Exiting.")
        sys.exit(1)
    if cfg.ENABLE_TRAFFIC_CAPTURE and not cfg.PCAPDROID_API_KEY and cfg.PCAPDROID_PACKAGE == "com.emanuelef.remote_capture":
        logging.warning("PCAPDROID_API_KEY is not set, but traffic capture is enabled for PCAPdroid. Capture might fail if API key is required by PCAPdroid version.")
    if not cfg.GEMINI_API_KEY:
        logging.warning("GEMINI_API_KEY is not set in environment or configuration. AI-dependent features will likely fail.")
    else:
        logging.info("GEMINI_API_KEY is set.")

    current_app_package = cfg.APP_PACKAGE
    current_app_activity = cfg.APP_ACTIVITY
    logging.info(f"Application will target: PACKAGE='{current_app_package}', ACTIVITY='{current_app_activity}'")

    # 2. Handle Existing Run Data
    if not cfg.CONTINUE_EXISTING_RUN:
        logging.info(f"CONTINUE_EXISTING_RUN is False. Clearing existing crawl data for '{current_app_package}' (if any)...")
        paths_to_clear = [cfg.DB_NAME, cfg.SCREENSHOTS_DIR, cfg.ANNOTATED_SCREENSHOTS_DIR, cfg.TRAFFIC_CAPTURE_OUTPUT_DIR]
        db_suffixes_to_clear = ['-shm', '-wal'] # For SQLite auxiliary files
        for path_str in paths_to_clear:
            if not path_str: continue # Skip if a path is not defined (e.g. DB_NAME could be None if not used)
            if os.path.exists(path_str):
                try:
                    if os.path.isfile(path_str):
                        os.remove(path_str)
                        logging.info(f"Removed file: {path_str}")
                        if path_str == cfg.DB_NAME: # Also remove SQLite journal files if DB file is removed
                            for suffix in db_suffixes_to_clear:
                                aux_file = path_str + suffix
                                if os.path.exists(aux_file):
                                    os.remove(aux_file)
                                    logging.info(f"Removed SQLite auxiliary file: {aux_file}")
                    elif os.path.isdir(path_str):
                        shutil.rmtree(path_str)
                        logging.info(f"Removed directory and its contents: {path_str}")
                except OSError as e:
                    logging.error(f"Error removing '{path_str}': {e}", exc_info=True)
    else:
        logging.info(f"CONTINUE_EXISTING_RUN is True. Existing data for '{current_app_package}' will be used/appended if found.")

    # 3. Ensure Necessary Directories Exist (Config class _resolve_all_paths already does some of this)
    # This is more of a double-check or for dirs not explicitly created by Config.
    dirs_to_ensure_exist = [
        os.path.dirname(cfg.DB_NAME) if cfg.DB_NAME else None,
        cfg.SCREENSHOTS_DIR,
        cfg.ANNOTATED_SCREENSHOTS_DIR,
        cfg.TRAFFIC_CAPTURE_OUTPUT_DIR,
        cfg.APP_INFO_OUTPUT_DIR
    ]
    for dir_path in filter(None, dirs_to_ensure_exist): # filter(None, ...) removes None entries
        if dir_path: # Ensure dir_path is not empty string either
            try:
                os.makedirs(dir_path, exist_ok=True)
            except OSError as e:
                logging.error(f"Could not create directory '{dir_path}': {e}. This might cause issues.", exc_info=True)

    # 4. Prepare Configuration Dictionary for AppCrawler (or other components)
    #    Create a dictionary view of the config, excluding methods and private/internal members.
    app_component_config = {
        key: getattr(cfg, key) for key in dir(cfg)
        if not key.startswith('_') and not key.isupper() and hasattr(cfg,key) and not callable(getattr(cfg, key))
           and key not in ['DEFAULTS_MODULE_PATH', 'USER_CONFIG_FILE_PATH', 'BASE_DIR', 'SHUTDOWN_FLAG_PATH'] # Exclude internal/path attributes
    }
    # Add specific uppercase constants if they are part of the expected dict for components
    for const_key in ['APP_PACKAGE', 'APP_ACTIVITY', 'LOG_LEVEL', 'OUTPUT_DATA_DIR', 'DB_NAME', 'GEMINI_API_KEY', 'ALLOWED_EXTERNAL_PACKAGES']: # etc.
        if hasattr(cfg, const_key):
             app_component_config[const_key] = getattr(cfg, const_key)

    app_component_config["SHUTDOWN_FLAG_PATH"] = cfg.SHUTDOWN_FLAG_PATH # Ensure this is passed
    
    logging.debug(f"Configuration dictionary for components (sample): \n{json.dumps(app_component_config, indent=2, default=str, ensure_ascii=False)}")

    # 5. Initialize and Run the Core Application Logic (e.g., Crawler)    logging.info(f"Initializing application core for '{current_app_package}'...")
    app_exit_code = 0
    crawler_instance = None
    try:        
        logging.info("Importing and initializing AppCrawler...")
        # Import using absolute path since we're not running as a package
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import sys
        from crawler import AppCrawler
        crawler_instance = AppCrawler(app_config=cfg)
        logging.info("AppCrawler initialized. Starting crawl...")
        crawler_instance.run()
        logging.info("AppCrawler crawl process finished normally.")

    except KeyboardInterrupt:
        logging.warning("KeyboardInterrupt received in main.py. Signaling application shutdown.")
        app_exit_code = 130  # Standard exit code for Ctrl+C
    except SystemExit as se:
        logging.info(f"SystemExit caught in main.py with code: {se.code}. Assuming controlled application exit.")
        app_exit_code = int(se.code) if isinstance(se.code, int) else 0
    except Exception as e_core_app:
        logging.critical(f"Unexpected error running application core: {e_core_app}", exc_info=True)
        app_exit_code = 1
    finally:
        if crawler_instance is not None and hasattr(crawler_instance, 'perform_full_cleanup'):
            logging.info("Main.py finally: Calling crawler_instance.perform_full_cleanup().")
            try:
                crawler_instance.perform_full_cleanup()
            except Exception as e_cleanup:
                logging.error(f"Main.py finally: Error during final cleanup: {e_cleanup}", exc_info=True)
        if os.path.exists(cfg.SHUTDOWN_FLAG_PATH):
            logging.warning(f"Main.py finally: Shutdown flag file ('{cfg.SHUTDOWN_FLAG_PATH}') still exists. Removing.")
            try:
                os.remove(cfg.SHUTDOWN_FLAG_PATH)
            except OSError as e_remove_final:
                logging.error(f"Main.py finally: Error removing shutdown flag: {e_remove_final}")
        
        main_process_end_time = time.time()
        total_main_block_duration = main_process_end_time - main_process_start_time
        # SCRIPT_START_TIME is imported from utils
        total_elapsed_from_script_start = main_process_end_time - SCRIPT_START_TIME 
        
        logging.info(f"======== Script '{os.path.basename(__file__)}' __main__ block finished with exit_code: {app_exit_code} ========")
        logging.info(f"Total execution time for __main__ block: {time.strftime('%H:%M:%S', time.gmtime(total_main_block_duration))}.{int((total_main_block_duration % 1) * 1000):03d}")
        logging.info(f"Total elapsed time since script import (SCRIPT_START_TIME): {time.strftime('%H:%M:%S', time.gmtime(total_elapsed_from_script_start))}.{int((total_elapsed_from_script_start % 1) * 1000):03d}")

    sys.exit(app_exit_code)