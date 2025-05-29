import logging
import time
import sys
import os
import json
import shutil
import asyncio 
from typing import Optional

from config import Config

try:
    from utils import SCRIPT_START_TIME, LoggerManager, ElapsedTimeFormatter
except ImportError as e:
    sys.stderr.write(f"Error: Could not import logging utilities from utils.py: {e}\n")
    if 'SCRIPT_START_TIME' not in globals():
        SCRIPT_START_TIME = time.time()
    sys.exit(1)

# Initial bootstrap logging
bootstrap_logger = logging.getLogger("bootstrap")
bootstrap_handler = logging.StreamHandler(sys.stdout)
bootstrap_formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(module)s:%(lineno)d - %(message)s (bootstrap)")
bootstrap_handler.setFormatter(bootstrap_formatter)
bootstrap_logger.addHandler(bootstrap_handler)
bootstrap_logger.setLevel(os.getenv("INIT_LOG_LEVEL", "INFO").upper())
bootstrap_logger.info("Bootstrap logging initialized (main.py).")


_current_script_dir = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_MODULE_PATH = os.path.join(_current_script_dir, 'config.py')
USER_CONFIG_JSON_FILENAME = "user_config.json"
USER_CONFIG_JSON_PATH = os.path.join(_current_script_dir, USER_CONFIG_JSON_FILENAME)

cfg: Optional[Config] = None # Define cfg early for wider scope

try:
    cfg = Config(defaults_module_path=DEFAULT_CONFIG_MODULE_PATH,
                user_config_json_path=USER_CONFIG_JSON_PATH)
except Exception as e:
    bootstrap_logger.critical(f"CRITICAL: Failed to initialize Config object during startup. Error: {e}", exc_info=True)
    sys.exit(100)


PROJECT_ROOT_DIR = os.path.abspath(os.path.join(_current_script_dir, ".."))

def close_file_handlers(logger_instance: logging.Logger, log_file_path_to_close: Optional[str] = None):
    """Closes and removes file handlers from a logger instance, optionally specific to a path."""
    if not logger_instance:
        return
    
    handlers_to_remove = []
    for handler in logger_instance.handlers:
        if isinstance(handler, logging.FileHandler):
            if log_file_path_to_close is None or handler.baseFilename == log_file_path_to_close:
                handler.close()
                handlers_to_remove.append(handler)
        # For console handlers, if they were added by LoggerManager and are duplicates of bootstrap
        # elif isinstance(handler, logging.StreamHandler) and logger_instance.name != "bootstrap":
            # Potentially remove console handlers if reconfiguring globally
            # For now, focus on file handlers for deletion conflict
            # pass 

    for handler in handlers_to_remove:
        logger_instance.removeHandler(handler)
    
    # If a global root logger was configured by LoggerManager, ensure its handlers are also checked
    # This depends on how LoggerManager structures its loggers.
    # Assuming LoggerManager configures the root logger directly:
    if logging.getLogger().hasHandlers():
         root_handlers_to_remove = []
         for handler in logging.getLogger().handlers:
             if isinstance(handler, logging.FileHandler):
                if log_file_path_to_close is None or handler.baseFilename == log_file_path_to_close:
                    handler.close()
                    root_handlers_to_remove.append(handler)
         for handler in root_handlers_to_remove:
            logging.getLogger().removeHandler(handler)


def remove_with_retry(path, max_retries=3, retry_delay=1):
    # bootstrap_logger should still be available here
    for attempt in range(max_retries):
        try:
            if os.path.isfile(path):
                os.remove(path)
                bootstrap_logger.info(f"Successfully removed file: {path}")
                return True
            elif os.path.isdir(path):
                shutil.rmtree(path)
                bootstrap_logger.info(f"Successfully removed directory: {path}")
                return True
        except (OSError, PermissionError) as e:
            if attempt < max_retries - 1:
                bootstrap_logger.warning(f"Attempt {attempt + 1}/{max_retries} to remove '{path}' failed: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                bootstrap_logger.error(f"Failed to remove '{path}' after {max_retries} attempts: {e}")
                return False
    # If path didn't exist in the first place
    if not os.path.exists(path):
        bootstrap_logger.debug(f"Path '{path}' not found for removal, assuming already clean.")
        return True
    return False


if __name__ == "__main__":
    main_process_start_time = time.time()
    bootstrap_logger.info(f"======== Script '{os.path.basename(__file__)}' __main__ block started. PID: {os.getpid()} ========")
    
    # Config is already loaded, use it (cfg will not be None here due to earlier sys.exit)
    assert cfg is not None, "Config object (cfg) should not be None at this point."

    bootstrap_logger.info(f"Python: {sys.version.splitlines()[0]} on {sys.platform}")
    bootstrap_logger.info(f"Project Root (guessed): {PROJECT_ROOT_DIR}")
    bootstrap_logger.info(f"Base Config Dir (for defaults/flag): {cfg.BASE_DIR}")
    bootstrap_logger.info(f"Output Data Dir: {cfg.OUTPUT_DATA_DIR}")

    if cfg.SHUTDOWN_FLAG_PATH and os.path.exists(cfg.SHUTDOWN_FLAG_PATH):
        bootstrap_logger.warning(f"Found existing shutdown flag at startup: {cfg.SHUTDOWN_FLAG_PATH}. Removing it.")
        remove_with_retry(cfg.SHUTDOWN_FLAG_PATH)


    if not cfg.APP_PACKAGE:
        bootstrap_logger.critical("APP_PACKAGE is not defined in configuration. Cannot proceed. Exiting.")
        sys.exit(1)
    if not cfg.APP_ACTIVITY:
        bootstrap_logger.critical("APP_ACTIVITY is not defined in configuration. Cannot proceed. Exiting.")
        sys.exit(1)
    # These checks can remain with bootstrap_logger
    if cfg.ENABLE_TRAFFIC_CAPTURE and not cfg.PCAPDROID_API_KEY and cfg.PCAPDROID_PACKAGE == "com.emanuelef.remote_capture":
        bootstrap_logger.warning("PCAPDROID_API_KEY is not set, but traffic capture is enabled for PCAPdroid. Capture might fail if API key is required.")
    if not cfg.GEMINI_API_KEY:
        bootstrap_logger.warning("GEMINI_API_KEY is not set. AI-dependent features will likely fail.")
    else:
        bootstrap_logger.info("GEMINI_API_KEY is set.")

    current_app_package = cfg.APP_PACKAGE
    current_app_activity = cfg.APP_ACTIVITY
    bootstrap_logger.info(f"Application will target: PACKAGE='{current_app_package}', ACTIVITY='{current_app_activity}'")

    # --- Determine log file path BEFORE potential deletion of its directory ---
    # cfg.LOG_DIR is the app-specific directory path resolved by Config class
    target_log_directory = cfg.LOG_DIR
    target_log_file_path = os.path.join(target_log_directory, cfg.LOG_FILE_NAME) if target_log_directory else os.path.join(_current_script_dir, cfg.LOG_FILE_NAME)


    if not cfg.CONTINUE_EXISTING_RUN:
        bootstrap_logger.info(f"CONTINUE_EXISTING_RUN is False. Clearing existing crawl data for '{current_app_package}' (if any)...")
        
        # Close existing file handlers, especially the one for the log file about to be deleted.
        # This assumes LoggerManager might have configured root logger or a specific logger.
        # If LoggerManager returns the logger it configured, use that.
        # For simplicity, trying to close handlers on the root logger.
        close_file_handlers(logging.getLogger(), target_log_file_path) # Close specific log file
        # Also close the bootstrap handler on the bootstrap_logger if it's a file handler (it's not here)

        paths_to_clear = [
            cfg.DB_NAME, 
            cfg.SCREENSHOTS_DIR, 
            cfg.ANNOTATED_SCREENSHOTS_DIR, 
            cfg.TRAFFIC_CAPTURE_OUTPUT_DIR, 
            target_log_directory # Clear the entire log directory for the app
        ]
        db_suffixes_to_clear = ['-shm', '-wal']
        for path_str in paths_to_clear:
            if not path_str: continue # Skip if path is None or empty
            if os.path.exists(path_str):
                if path_str == cfg.DB_NAME:
                    for suffix in db_suffixes_to_clear:
                        aux_file = path_str + suffix
                        if os.path.exists(aux_file):
                            remove_with_retry(aux_file) # Logging is inside remove_with_retry
                remove_with_retry(path_str)
    else:
        bootstrap_logger.info(f"CONTINUE_EXISTING_RUN is True. Existing data for '{current_app_package}' will be used/appended.")

    # --- Re-initialize Main Application Logging ---
    # This happens AFTER potential deletion of the log directory.
    logger_manager_global = LoggerManager() # Re-instantiate or ensure it can reconfigure
    if not target_log_directory:
        bootstrap_logger.warning(f"cfg.LOG_DIR was not set. Defaulting final log file to current script directory: {target_log_file_path}")
        os.makedirs(_current_script_dir, exist_ok=True)
    else:
        os.makedirs(target_log_directory, exist_ok=True)
    
    # Clear all handlers from the root logger before setting up new ones to avoid duplication
    # and ensure old file handlers are gone if log path changed or was deleted.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        handler.close()
    # Remove bootstrap handler from bootstrap_logger if we are done with it,
    # or ensure LoggerManager doesn't add another console handler if bootstrap's is sufficient.
    # For now, LoggerManager will re-add handlers to the root logger.
    bootstrap_logger.removeHandler(bootstrap_handler) # Remove original bootstrap console handler
    bootstrap_handler.close()


    root_logger = logger_manager_global.setup_logging(log_level_str=cfg.LOG_LEVEL, log_file=target_log_file_path)
    root_logger.info(f"Main application logging re-initialized by LoggerManager. Level: {cfg.LOG_LEVEL.upper()}. File: '{target_log_file_path}'")
    # Re-log critical info with the new logger
    root_logger.info(f"Using configuration from: Defaults='{cfg.DEFAULTS_MODULE_PATH}', User='{cfg.USER_CONFIG_FILE_PATH}'")
    root_logger.info(f"Effective APP_PACKAGE: {cfg.APP_PACKAGE}")
    root_logger.info(f"Effective APP_ACTIVITY: {cfg.APP_ACTIVITY}")
    root_logger.info(f"Shutdown flag file path set to: {cfg.SHUTDOWN_FLAG_PATH}")
    root_logger.info(f"Log directory for this run: {target_log_directory}")


    app_component_config = {
        key: getattr(cfg, key) for key in dir(cfg)
        if not key.startswith('_') and not key.isupper() and hasattr(cfg,key) and not callable(getattr(cfg, key))
           and key not in ['DEFAULTS_MODULE_PATH', 'USER_CONFIG_FILE_PATH', 'BASE_DIR']
    }
    for const_key in ['APP_PACKAGE', 'APP_ACTIVITY', 'LOG_LEVEL', 'OUTPUT_DATA_DIR', 'LOG_DIR',
                      'DB_NAME', 'GEMINI_API_KEY', 'ALLOWED_EXTERNAL_PACKAGES', 'SHUTDOWN_FLAG_PATH']:
        if hasattr(cfg, const_key):
             app_component_config[const_key] = getattr(cfg, const_key)
    
    root_logger.debug(f"Configuration dictionary for components (sample): \n{json.dumps(app_component_config, indent=2, default=str, ensure_ascii=False)}")

    app_exit_code = 0
    crawler_instance = None
    try:
        root_logger.info("Importing and initializing AppCrawler...")
        # Ensure current directory is in path for local 'crawler' import
        if _current_script_dir not in sys.path:
            sys.path.insert(0, _current_script_dir) 
        from crawler import AppCrawler 
        crawler_instance = AppCrawler(app_config=cfg)
        root_logger.info("AppCrawler initialized. Starting crawl...")
        crawler_instance.run() # This internally calls asyncio.run()
        root_logger.info("AppCrawler crawl process finished normally.")

    except KeyboardInterrupt:
        root_logger.warning("KeyboardInterrupt received in main.py. Signaling application shutdown.")
        app_exit_code = 130
    except SystemExit as se:
        root_logger.info(f"SystemExit caught in main.py with code: {se.code}. Assuming controlled application exit.")
        app_exit_code = int(se.code) if isinstance(se.code, int) else 0 # Use 0 if se.code is None
    except Exception as e_core_app:
        root_logger.critical(f"Unexpected error running application core: {e_core_app}", exc_info=True)
        app_exit_code = 1
    finally:
        if crawler_instance is not None and hasattr(crawler_instance, 'perform_full_cleanup'):
            root_logger.info("Main.py finally: Attempting to call crawler_instance.perform_full_cleanup().")
            try:
                # perform_full_cleanup is an async method
                asyncio.run(crawler_instance.perform_full_cleanup())
            except RuntimeError as re_err:
                root_logger.error(f"Main.py finally: RuntimeError during asyncio.run(perform_full_cleanup): {re_err}. This might indicate an issue with event loop management.", exc_info=True)
            except Exception as e_cleanup:
                root_logger.error(f"Main.py finally: Error during final cleanup via perform_full_cleanup: {e_cleanup}", exc_info=True)
        
        if cfg.SHUTDOWN_FLAG_PATH and os.path.exists(cfg.SHUTDOWN_FLAG_PATH):
            root_logger.warning(f"Main.py finally: Shutdown flag file ('{cfg.SHUTDOWN_FLAG_PATH}') still exists. Removing.")
            remove_with_retry(cfg.SHUTDOWN_FLAG_PATH)
        
        main_process_end_time = time.time()
        total_main_block_duration = main_process_end_time - main_process_start_time
        total_elapsed_from_script_start = main_process_end_time - SCRIPT_START_TIME
        
        root_logger.info(f"======== Script '{os.path.basename(__file__)}' __main__ block finished with exit_code: {app_exit_code} ========")
        root_logger.info(f"Total execution time for __main__ block: {time.strftime('%H:%M:%S', time.gmtime(total_main_block_duration))}.{int((total_main_block_duration % 1) * 1000):03d}")
        root_logger.info(f"Total elapsed time since script import (SCRIPT_START_TIME): {time.strftime('%H:%M:%S', time.gmtime(total_elapsed_from_script_start))}.{int((total_elapsed_from_script_start % 1) * 1000):03d}")
        
        # Final attempt to close any remaining log handlers
        close_file_handlers(logging.getLogger())


    sys.exit(app_exit_code)