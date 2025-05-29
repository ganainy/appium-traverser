import logging
import time
import sys
import os
import json
import shutil
from config import Config # Ensure this imports the updated Config class

try:
    from utils import SCRIPT_START_TIME, LoggerManager, ElapsedTimeFormatter
except ImportError as e:
    sys.stderr.write(f"Error: Could not import logging utilities from utils.py: {e}\n")
    if 'SCRIPT_START_TIME' not in globals():
        SCRIPT_START_TIME = time.time()
    sys.exit(1)

logger_manager_global = LoggerManager()

logging.basicConfig(level=os.getenv("INIT_LOG_LEVEL", "INFO").upper(),
                    format="[%(levelname)s] %(asctime)s - %(module)s:%(lineno)d - %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
logging.info("Bootstrap logging initialized (main.py).")

_current_script_dir = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_MODULE_PATH = os.path.join(_current_script_dir, 'config.py')
USER_CONFIG_JSON_FILENAME = "user_config.json"
USER_CONFIG_JSON_PATH = os.path.join(_current_script_dir, USER_CONFIG_JSON_FILENAME)

try:
    cfg = Config(defaults_module_path=DEFAULT_CONFIG_MODULE_PATH,
                user_config_json_path=USER_CONFIG_JSON_PATH)
    # SHUTDOWN_FLAG_PATH is now set inside Config constructor relative to BASE_DIR
    # If you need to enforce a specific location for the flag regardless of config.py's location:
    # cfg.SHUTDOWN_FLAG_PATH = os.path.join(_current_script_dir, "crawler_shutdown.flag")
    # However, using cfg.BASE_DIR (where config.py is) for the flag is generally good practice.
    # Ensure cfg.SHUTDOWN_FLAG_PATH is being correctly set as per your needs. For this example,
    # I'll assume it's correctly set by the Config class using its BASE_DIR.

except Exception as e:
    logging.critical(f"CRITICAL: Failed to initialize Config object during startup. Error: {e}", exc_info=True)
    sys.exit(100)

# --- Re-initialize Main Logging with settings from cfg ---
# cfg.LOG_DIR is now the app-specific directory path resolved by Config class
if not cfg.LOG_DIR or not os.path.isdir(cfg.LOG_DIR): # cfg.LOG_DIR should be an absolute path
    logging.warning(f"cfg.LOG_DIR ('{cfg.LOG_DIR}') is not set or not a valid directory. Defaulting log file to current script directory.")
    _final_log_file_path = os.path.join(_current_script_dir, cfg.LOG_FILE_NAME)
    os.makedirs(_current_script_dir, exist_ok=True) # Ensure script dir exists for log
else:
    # cfg.LOG_DIR is already the specific path e.g. output_data/logs/com.example.app
    os.makedirs(cfg.LOG_DIR, exist_ok=True) # Ensure the app-specific log directory exists
    _final_log_file_path = os.path.join(cfg.LOG_DIR, cfg.LOG_FILE_NAME)


root_logger = logger_manager_global.setup_logging(log_level_str=cfg.LOG_LEVEL, log_file=_final_log_file_path)
root_logger.info(f"Main application logging re-initialized by LoggerManager. Level: {cfg.LOG_LEVEL.upper()}. File: '{_final_log_file_path}'")
root_logger.info(f"Using configuration from: Defaults='{cfg.DEFAULTS_MODULE_PATH}', User='{cfg.USER_CONFIG_FILE_PATH}'")
root_logger.info(f"Effective APP_PACKAGE: {cfg.APP_PACKAGE}")
root_logger.info(f"Effective APP_ACTIVITY: {cfg.APP_ACTIVITY}")
root_logger.info(f"Shutdown flag file path set to: {cfg.SHUTDOWN_FLAG_PATH}") # Verify this path
root_logger.info(f"Log directory for this run: {cfg.LOG_DIR}")


PROJECT_ROOT_DIR = os.path.abspath(os.path.join(_current_script_dir, ".."))


def remove_with_retry(path, max_retries=3, retry_delay=1):
    """Try to remove a file or directory with retries if it's locked."""
    for attempt in range(max_retries):
        try:
            if os.path.isfile(path):
                os.remove(path)
                return True
            elif os.path.isdir(path):
                shutil.rmtree(path)
                return True
        except (OSError, PermissionError) as e:
            if attempt < max_retries - 1:
                logging.warning(f"Attempt {attempt + 1}/{max_retries} to remove '{path}' failed: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                logging.error(f"Failed to remove '{path}' after {max_retries} attempts: {e}")
                return False
    return False

if __name__ == "__main__":
    main_process_start_time = time.time()
    logging.info(f"======== Script '{os.path.basename(__file__)}' __main__ block started. PID: {os.getpid()} ========")
    logging.info(f"Python: {sys.version.splitlines()[0]} on {sys.platform}")
    logging.info(f"Project Root (guessed): {PROJECT_ROOT_DIR}")
    logging.info(f"Base Config Dir (for defaults/flag): {cfg.BASE_DIR}")
    logging.info(f"Output Data Dir: {cfg.OUTPUT_DATA_DIR}") # Top-level output_data

    if cfg.SHUTDOWN_FLAG_PATH and os.path.exists(cfg.SHUTDOWN_FLAG_PATH):
        logging.warning(f"Found existing shutdown flag at startup: {cfg.SHUTDOWN_FLAG_PATH}. Removing it.")
        try:
            os.remove(cfg.SHUTDOWN_FLAG_PATH)
        except OSError as e_remove_flag:
            logging.error(f"Error removing stale shutdown flag at startup: {e_remove_flag}")

    if not cfg.APP_PACKAGE:
        logging.critical("APP_PACKAGE is not defined in configuration. Cannot proceed. Exiting.")
        sys.exit(1)
    if not cfg.APP_ACTIVITY:
        logging.critical("APP_ACTIVITY is not defined in configuration. Cannot proceed. Exiting.")
        sys.exit(1)
    if cfg.ENABLE_TRAFFIC_CAPTURE and not cfg.PCAPDROID_API_KEY and cfg.PCAPDROID_PACKAGE == "com.emanuelef.remote_capture":
        logging.warning("PCAPDROID_API_KEY is not set, but traffic capture is enabled for PCAPdroid. Capture might fail if API key is required.")
    if not cfg.GEMINI_API_KEY:
        logging.warning("GEMINI_API_KEY is not set. AI-dependent features will likely fail.")
    else:
        logging.info("GEMINI_API_KEY is set.")

    current_app_package = cfg.APP_PACKAGE
    current_app_activity = cfg.APP_ACTIVITY
    logging.info(f"Application will target: PACKAGE='{current_app_package}', ACTIVITY='{current_app_activity}'")

    if not cfg.CONTINUE_EXISTING_RUN:
        logging.info(f"CONTINUE_EXISTING_RUN is False. Clearing existing crawl data for '{current_app_package}' (if any)...")
        # Paths are now correctly resolved by Config to be app-specific
        paths_to_clear = [
            cfg.DB_NAME, # e.g., output_data/database_output/com.example/com.example_crawl_data.db
            cfg.SCREENSHOTS_DIR, # e.g., output_data/screenshots/crawl_screenshots_com.example
            cfg.ANNOTATED_SCREENSHOTS_DIR, # e.g., output_data/screenshots/annotated_crawl_screenshots_com.example
            cfg.TRAFFIC_CAPTURE_OUTPUT_DIR, # e.g., output_data/traffic_captures/com.example
            cfg.LOG_DIR # e.g., output_data/logs/com.example
        ]
        db_suffixes_to_clear = ['-shm', '-wal']
        for path_str in paths_to_clear:
            if not path_str: continue
            if os.path.exists(path_str):
                if path_str == cfg.DB_NAME:
                    # Handle SQLite auxiliary files first
                    for suffix in db_suffixes_to_clear:
                        aux_file = path_str + suffix
                        if os.path.exists(aux_file):
                            if remove_with_retry(aux_file):
                                logging.info(f"Removed SQLite auxiliary file: {aux_file}")
                
                if remove_with_retry(path_str):
                    logging.info(f"Removed {'directory' if os.path.isdir(path_str) else 'file'}: {path_str}")
    else:
        logging.info(f"CONTINUE_EXISTING_RUN is True. Existing data for '{current_app_package}' will be used/appended.")

    # Directories are created by cfg._resolve_all_paths now.
    # Double-check specific ones if needed, but should be handled.
    # Example: os.makedirs(cfg.SCREENSHOTS_DIR, exist_ok=True)

    app_component_config = {
        key: getattr(cfg, key) for key in dir(cfg)
        if not key.startswith('_') and not key.isupper() and hasattr(cfg,key) and not callable(getattr(cfg, key))
           and key not in ['DEFAULTS_MODULE_PATH', 'USER_CONFIG_FILE_PATH', 'BASE_DIR']
    }
    # Explicitly add constants needed by components if not caught by above
    for const_key in ['APP_PACKAGE', 'APP_ACTIVITY', 'LOG_LEVEL', 'OUTPUT_DATA_DIR', 'LOG_DIR',
                      'DB_NAME', 'GEMINI_API_KEY', 'ALLOWED_EXTERNAL_PACKAGES', 'SHUTDOWN_FLAG_PATH']:
        if hasattr(cfg, const_key):
             app_component_config[const_key] = getattr(cfg, const_key)
    
    logging.debug(f"Configuration dictionary for components (sample): \n{json.dumps(app_component_config, indent=2, default=str, ensure_ascii=False)}")

    app_exit_code = 0
    crawler_instance = None
    try:
        logging.info("Importing and initializing AppCrawler...")
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))) # Ensure local imports work
        from crawler import AppCrawler # Assuming crawler.py is in the same directory
        crawler_instance = AppCrawler(app_config=cfg)
        logging.info("AppCrawler initialized. Starting crawl...")
        crawler_instance.run()
        logging.info("AppCrawler crawl process finished normally.")

    except KeyboardInterrupt:
        logging.warning("KeyboardInterrupt received in main.py. Signaling application shutdown.")
        app_exit_code = 130
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
        
        if cfg.SHUTDOWN_FLAG_PATH and os.path.exists(cfg.SHUTDOWN_FLAG_PATH):
            logging.warning(f"Main.py finally: Shutdown flag file ('{cfg.SHUTDOWN_FLAG_PATH}') still exists. Removing.")
            try:
                os.remove(cfg.SHUTDOWN_FLAG_PATH)
            except OSError as e_remove_final:
                logging.error(f"Main.py finally: Error removing shutdown flag: {e_remove_final}")
        
        main_process_end_time = time.time()
        total_main_block_duration = main_process_end_time - main_process_start_time
        total_elapsed_from_script_start = main_process_end_time - SCRIPT_START_TIME
        
        logging.info(f"======== Script '{os.path.basename(__file__)}' __main__ block finished with exit_code: {app_exit_code} ========")
        logging.info(f"Total execution time for __main__ block: {time.strftime('%H:%M:%S', time.gmtime(total_main_block_duration))}.{int((total_main_block_duration % 1) * 1000):03d}")
        logging.info(f"Total elapsed time since script import (SCRIPT_START_TIME): {time.strftime('%H:%M:%S', time.gmtime(total_elapsed_from_script_start))}.{int((total_elapsed_from_script_start % 1) * 1000):03d}")

    sys.exit(app_exit_code)