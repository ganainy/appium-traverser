import logging
import time
import sys
import os
import json
import shutil # For rmtree
from typing import Optional, Dict, Any

# --- Global Script Start Time (defined once at the very top) ---
SCRIPT_START_TIME = time.time()

# --- Custom Log Formatter ---
class ElapsedTimeFormatter(logging.Formatter):
    """Custom formatter to log elapsed time since script start."""
    def formatTime(self, record, datefmt=None):
        elapsed_seconds = record.created - SCRIPT_START_TIME
        h = int(elapsed_seconds // 3600)
        m = int((elapsed_seconds % 3600) // 60)
        s = int(elapsed_seconds % 60)
        ms = int((elapsed_seconds - (h * 3600 + m * 60 + s)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

# --- Logging Setup Function ---
def setup_logging(log_level_str: str = "INFO", log_file: Optional[str] = None):
    numeric_level = getattr(logging, log_level_str.upper(), logging.INFO)
    if not isinstance(numeric_level, int) or numeric_level == logging.INFO and log_level_str.upper() != "INFO":
        print(f"Warning: Invalid log level string: '{log_level_str}'. Defaulting to INFO.", file=sys.stderr)
        numeric_level = logging.INFO
        log_level_str = "INFO"

    log_formatter = ElapsedTimeFormatter("[%(levelname)s] (%(asctime)s) %(filename)s:%(lineno)d - %(message)s")
    logger = logging.getLogger()
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(numeric_level)

    console_handler_stdout = logging.StreamHandler(sys.stdout)
    console_handler_stdout.setFormatter(log_formatter)
    logger.addHandler(console_handler_stdout)

    if log_file:
        try:
            log_file_dir = os.path.dirname(os.path.abspath(log_file))
            if log_file_dir: os.makedirs(log_file_dir, exist_ok=True)
            file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
            file_handler.setFormatter(log_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logging.error(f"Error setting up file logger for {log_file}: {e}. Continuing with console logging.", exc_info=True)

    if numeric_level > logging.DEBUG:
        for lib_name in ["appium.webdriver.webdriver", "urllib3.connectionpool", "selenium.webdriver.remote.remote_connection"]:
            logging.getLogger(lib_name).setLevel(logging.WARNING)
    # Initial log message will be emitted by the caller of setup_logging

# --- Initial (Basic) Logging Setup ---
setup_logging("INFO") # Default to INFO, no file log initially

# --- Project Root and Configuration Paths ---
# Assuming this main.py is in traverser_ai_api, and config.py is in the same directory.
# The project root is one level up from traverser_ai_api.
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_DIR = os.path.abspath(os.path.join(CURRENT_SCRIPT_DIR, ".."))
USER_CONFIG_FILENAME = "user_config.json"
USER_CONFIG_FILE_PATH = os.path.join(PROJECT_ROOT_DIR, USER_CONFIG_FILENAME)

# --- Configuration Loading from config.py (defaults) ---
try:
    from . import config as cfg # cfg is the alias for the config.py module
    CONFIG_MODULE_PATH = os.path.abspath(cfg.__file__) # Path to the loaded config.py
    CONFIG_DIR = os.path.dirname(CONFIG_MODULE_PATH) # Directory of config.py
    logging.info(f"Successfully imported default config module from: {CONFIG_MODULE_PATH}")
except ImportError as e:
    logging.critical(f"CRITICAL: Failed to import 'config' module. Ensure 'config.py' exists. Error: {e}", exc_info=True)
    sys.exit(1)
except Exception as e:
    logging.critical(f"CRITICAL: Unexpected error during 'config' module import. Error: {e}", exc_info=True)
    sys.exit(1)

# --- Define Shutdown Flag (relative to config.py's location) ---
SHUTDOWN_FLAG_FILENAME = "crawler_shutdown.flag"
_shutdown_flag_file_path = os.path.join(CONFIG_DIR, SHUTDOWN_FLAG_FILENAME) # Usually PROJECT_ROOT/traverser_ai_api/crawler_shutdown.flag
logging.info(f"Shutdown flag file path set to: {_shutdown_flag_file_path}")

# --- Path Resolution Helper (relative to config.py's location for paths defined in config.py) ---
def resolve_config_path(path_template_or_direct: str, app_package_name: Optional[str] = None) -> str:
    path_to_resolve = path_template_or_direct
    if app_package_name and "{package}" in path_template_or_direct:
        path_to_resolve = path_template_or_direct.format(package=app_package_name)
    
    # Paths from config.py are relative to config.py's directory (CONFIG_DIR)
    # unless they are absolute
    if not os.path.isabs(path_to_resolve):
        resolved_path = os.path.abspath(os.path.join(CONFIG_DIR, path_to_resolve))
    else:
        resolved_path = path_to_resolve
    return resolved_path

# --- Override config.py defaults with user_config.json values ---
# This must happen BEFORE re-initializing logging with potentially overridden values
# and before resolving package-dependent paths.

# Store initial log settings from cfg before they are potentially overridden
_initial_cfg_log_level = str(getattr(cfg, 'LOG_LEVEL', 'INFO'))
_initial_cfg_log_file_name = str(getattr(cfg, 'LOG_FILE_NAME', 'main_traverser.log')) # Default if not in config.py

if os.path.exists(USER_CONFIG_FILE_PATH):
    try:
        with open(USER_CONFIG_FILE_PATH, 'r') as f:
            user_config_data = json.load(f)
        logging.info(f"Successfully loaded user configuration from: {USER_CONFIG_FILE_PATH}")
        
        for key, value in user_config_data.items():
            if hasattr(cfg, key):
                original_value = getattr(cfg, key)
                original_type = type(original_value)
                try:
                    # Attempt type conversion based on original type in config.py
                    converted_value = value
                    if original_type == bool and not isinstance(value, bool):
                        converted_value = str(value).lower() in ['true', '1', 'yes']
                    elif original_type == int and not isinstance(value, int):
                        converted_value = int(value)
                    elif original_type == float and not isinstance(value, float):
                        converted_value = float(value)
                    # Add more specific list handling if needed, e.g. for ALLOWED_EXTERNAL_PACKAGES
                    elif original_type == list and isinstance(value, str): # QTextEdit in UI saves as single string for lists
                         converted_value = [item.strip() for item in value.split('\n') if item.strip()]
                    elif original_type == list and isinstance(value, list): # If already a list in JSON
                         converted_value = value


                    setattr(cfg, key, converted_value)
                    if original_value != converted_value: # Log only if changed
                         logging.info(f"User config override: cfg.{key} = {converted_value} (was: {original_value})")

                except (ValueError, TypeError) as ve:
                    logging.warning(f"Type conversion error for user_config key '{key}' (value: '{value}', type: {type(value)}). Expected {original_type}. Using default. Error: {ve}")
            # else:
            #    logging.debug(f"Key '{key}' from user_config.json not found in config.py defaults.")
    except json.JSONDecodeError as e:
        logging.error(f"Error: Could not parse {USER_CONFIG_FILE_PATH}. Invalid JSON: {e}", exc_info=True)
    except Exception as e:
        logging.warning(f"Warning: Failed to load or apply user configuration from {USER_CONFIG_FILE_PATH}: {e}", exc_info=True)
else:
    logging.info(f"User configuration file ({USER_CONFIG_FILE_PATH}) not found. Using defaults from config.py.")


# --- Re-initialize logging with potentially overridden settings ---
# Paths in config.py are relative to config.py itself (CONFIG_DIR)
# LOG_FILE_NAME and LOG_LEVEL are now sourced from the (potentially updated) cfg object
_current_log_level = str(getattr(cfg, 'LOG_LEVEL', 'INFO'))
_current_log_file_name = str(getattr(cfg, 'LOG_FILE_NAME', 'main_traverser_final.log')) # Default name

# Construct log file path relative to project root's output_data/logs
_log_dir_final = os.path.join(PROJECT_ROOT_DIR, "output_data", "logs")
_log_file_path_final = os.path.join(_log_dir_final, _current_log_file_name)

# Re-setup logging only if level or file name changed from initial config.py defaults
if _current_log_level.upper() != _initial_cfg_log_level.upper() or _current_log_file_name != _initial_cfg_log_file_name:
    setup_logging(log_level_str=_current_log_level, log_file=_log_file_path_final)
    logging.info(f"Logging re-initialized. Level: {_current_log_level.upper()}. File: {_log_file_path_final}")
else:
    # If only user_config existed but didn't change log settings, still ensure logging uses the correct path
    # This handles the case where config.py might define a template for log file.
    # For now, we assume LOG_FILE_NAME from config.py or user_config.json is the final name.
    setup_logging(log_level_str=_initial_cfg_log_level, log_file=_log_file_path_final) # Use initial level, but potentially new path
    logging.info(f"Logging setup confirmed. Level: {_initial_cfg_log_level.upper()}. File: {_log_file_path_final}")


# --- Log final determined APP_PACKAGE and APP_ACTIVITY ---
# These are now the effective values after potential user_config.json override
logging.info(f"Effective APP_PACKAGE for crawl: {cfg.APP_PACKAGE}")
logging.info(f"Effective APP_ACTIVITY for crawl: {cfg.APP_ACTIVITY}")


# --- Resolve package-dependent paths AFTER APP_PACKAGE is finalized ---
# Ensure these attribute names match what's in your config.py
# Example: DB_NAME_TEMPLATE = "../output_data/database_output/{package}_crawl_data.db"
cfg.DB_NAME = resolve_config_path(getattr(cfg, 'DB_NAME', '../output_data/database_output/{package}_crawl_data.db').format(package=cfg.APP_PACKAGE))
cfg.SCREENSHOTS_DIR = resolve_config_path(getattr(cfg, 'SCREENSHOTS_DIR', '../output_data/screenshots/crawl_screenshots_{package}').format(package=cfg.APP_PACKAGE))
cfg.ANNOTATED_SCREENSHOTS_DIR = resolve_config_path(getattr(cfg, 'ANNOTATED_SCREENSHOTS_DIR', '../output_data/screenshots/annotated_crawl_screenshots_{package}').format(package=cfg.APP_PACKAGE))
cfg.TRAFFIC_CAPTURE_OUTPUT_DIR = resolve_config_path(getattr(cfg, 'TRAFFIC_CAPTURE_OUTPUT_DIR', '../output_data/traffic_captures/{package}').format(package=cfg.APP_PACKAGE))

# --- APP_INFO_OUTPUT_DIR (usually not package-dependent, but resolve it) ---
cfg.APP_INFO_OUTPUT_DIR = resolve_config_path(getattr(cfg, 'APP_INFO_OUTPUT_DIR', '../output_data/app_info'))
try:
    os.makedirs(cfg.APP_INFO_OUTPUT_DIR, exist_ok=True)
except OSError as e:
    logging.error(f"Could not create APP_INFO_OUTPUT_DIR: {cfg.APP_INFO_OUTPUT_DIR}. Error: {e}", exc_info=True)


# --- Import find_app_info and AppCrawler (late, after config is fully processed) ---
get_device_serial_func, generate_app_info_cache_func = None, None # Keep these for now, though not used in this revised flow
try:
    from .find_app_info import get_device_serial, generate_app_info_cache
    get_device_serial_func = get_device_serial
    generate_app_info_cache_func = generate_app_info_cache
    # logging.debug("Successfully imported app info functions from find_app_info.py.")
except ImportError:
    logging.warning("Could not import from 'find_app_info.py'. Some discovery features might be affected if used directly.")
except Exception as e:
    logging.error(f"Error importing from 'find_app_info.py': {e}", exc_info=True)

try:
    from .crawler import AppCrawler
    logging.info("Successfully imported AppCrawler.")
except ImportError as e:
    logging.critical(f"CRITICAL: Failed to import 'AppCrawler'. Error: {e}", exc_info=True)
    sys.exit(1)
except Exception as e:
    logging.critical(f"CRITICAL: Unexpected error importing 'AppCrawler'. Error: {e}", exc_info=True)
    sys.exit(1)


# --- Main Execution Block ---
if __name__ == "__main__":
    main_start_time = time.time()
    logging.info(f"======== Script '{os.path.basename(__file__)}' started. PID: {os.getpid()} ========")
    logging.info(f"Python: {sys.version.splitlines()[0]} on {sys.platform}")
    logging.info(f"Project Root: {PROJECT_ROOT_DIR}")
    logging.info(f"Default Config Module: {CONFIG_MODULE_PATH}")
    logging.info(f"User Config File (if used): {USER_CONFIG_FILE_PATH}")
    logging.info(f"Shutdown flag will be checked at: {_shutdown_flag_file_path}")

    if os.path.exists(_shutdown_flag_file_path):
        logging.warning(f"Found existing shutdown flag at startup: {_shutdown_flag_file_path}. Removing it.")
        try:
            os.remove(_shutdown_flag_file_path)
        except OSError as e_remove_flag:
            logging.error(f"Error removing stale shutdown flag at startup: {e_remove_flag}")

    # 1. Validate Essential Configurations from the merged cfg
    if not getattr(cfg, 'APP_PACKAGE', None):
        logging.critical("APP_PACKAGE is not defined. Cannot proceed. Exiting.")
        sys.exit(1)
    if not getattr(cfg, 'APP_ACTIVITY', None):
        logging.critical("APP_ACTIVITY is not defined. Cannot proceed. Exiting.")
        sys.exit(1)
    
    if not getattr(cfg, 'GEMINI_API_KEY', None):
        logging.critical("GEMINI_API_KEY is not set (needed for AI Assistant). Exiting.")
        sys.exit(1)
    else:
        logging.info("GEMINI_API_KEY is set.")

    # The app info cache handling for auto-discovery of APP_ACTIVITY might be less relevant now
    # since user_config.json directly provides APP_PACKAGE and APP_ACTIVITY from the UI.
    # If you still want auto-discovery as a fallback IF user_config.json is missing those fields,
    # that logic could be re-inserted here, but it complicates the "single source of truth" from UI.
    # For now, we assume APP_PACKAGE and APP_ACTIVITY from cfg (merged) are definitive.

    current_app_package = cfg.APP_PACKAGE
    current_app_activity = cfg.APP_ACTIVITY
    logging.info(f"Crawler will target: PACKAGE='{current_app_package}', ACTIVITY='{current_app_activity}'")


    # 2. Handle Existing Run Data
    if not getattr(cfg, 'CONTINUE_EXISTING_RUN', False):
        logging.info(f"CONTINUE_EXISTING_RUN is False. Clearing existing crawl data for '{current_app_package}'...")
        paths_to_clear = [cfg.DB_NAME, cfg.SCREENSHOTS_DIR, cfg.ANNOTATED_SCREENSHOTS_DIR, cfg.TRAFFIC_CAPTURE_OUTPUT_DIR]
        db_suffixes_to_clear = ['-shm', '-wal']
        for path_str in paths_to_clear:
            if not path_str: continue
            if os.path.exists(path_str):
                try:
                    if os.path.isfile(path_str):
                        os.remove(path_str)
                        logging.info(f"Removed file: {path_str}")
                        if path_str == cfg.DB_NAME:
                            for suffix in db_suffixes_to_clear:
                                aux_file = path_str + suffix
                                if os.path.exists(aux_file): os.remove(aux_file); logging.info(f"Removed: {aux_file}")
                    elif os.path.isdir(path_str):
                        shutil.rmtree(path_str)
                        logging.info(f"Removed directory: {path_str}")
                except OSError as e:
                    logging.error(f"Error removing '{path_str}': {e}", exc_info=True)
    else:
        logging.info(f"CONTINUE_EXISTING_RUN is True. Existing data for '{current_app_package}' will be used/appended.")

    # 3. Ensure Necessary Directories Exist
    dirs_to_ensure_exist = [
        os.path.dirname(cfg.DB_NAME), cfg.SCREENSHOTS_DIR,
        cfg.ANNOTATED_SCREENSHOTS_DIR, cfg.TRAFFIC_CAPTURE_OUTPUT_DIR
    ]
    for dir_path in dirs_to_ensure_exist:
        if not dir_path: continue
        try:
            os.makedirs(dir_path, exist_ok=True)
            # logging.debug(f"Ensured directory exists: {dir_path}") # Less verbose
        except OSError as e:
            logging.error(f"Could not create directory '{dir_path}': {e}. This might cause issues.", exc_info=True)

    # 4. Prepare Configuration Dictionary for AppCrawler
    current_config_dict = {
        key: getattr(cfg, key) for key in dir(cfg) 
        if not key.startswith('__') and not callable(getattr(cfg, key)) and not isinstance(getattr(cfg, key), type(sys))
    }
    current_config_dict["SHUTDOWN_FLAG_PATH"] = _shutdown_flag_file_path # Add shutdown flag path
    
    logging.debug(f"Final configuration for AppCrawler: \n{json.dumps(current_config_dict, indent=2, default=str)}")

    # 5. Initialize and Run the Crawler
    logging.info(f"Initializing AppCrawler for '{current_app_package}'...")
    crawler_instance = None
    exit_code = 0
    try:
        crawler_instance = AppCrawler(config_dict=current_config_dict)
        logging.info("AppCrawler initialized. Starting crawl...")
        crawler_instance.run() 
        logging.info("AppCrawler crawl process finished normally.")
    except KeyboardInterrupt:
        logging.warning("KeyboardInterrupt received in main.py. Signaling shutdown.")
        exit_code = 1
    except SystemExit as se:
        logging.info(f"SystemExit caught in main.py with code: {se.code}. Assuming crawler-initiated exit.")
        exit_code = int(se.code) if isinstance(se.code, int) else 0
    except Exception as e_crawler:
        logging.critical(f"Unexpected error running AppCrawler: {e_crawler}", exc_info=True)
        exit_code = 1
    finally:
        if crawler_instance and hasattr(crawler_instance, 'quit_driver') and callable(crawler_instance.quit_driver):
            logging.info("Main.py finally: Calling crawler_instance.quit_driver() as fallback.")
            try:
                crawler_instance.quit_driver()
            except Exception as e_quit:
                logging.error(f"Main.py finally: Error during fallback driver quit: {e_quit}", exc_info=True)
        
        if os.path.exists(_shutdown_flag_file_path):
            logging.warning(f"Main.py finally: Shutdown flag file still exists. Removing.")
            try:
                os.remove(_shutdown_flag_file_path)
            except OSError as e_remove_final:
                logging.error(f"Main.py finally: Error removing shutdown flag: {e_remove_final}")
        
        main_end_time = time.time()
        total_script_duration = main_end_time - main_start_time
        total_elapsed_from_start = main_end_time - SCRIPT_START_TIME
        
        logging.info(f"======== Script '{os.path.basename(__file__)}' finished with exit_code: {exit_code} ========")
        logging.info(f"Total execution time for __main__ block: {time.strftime('%H:%M:%S', time.gmtime(total_script_duration))}.{int((total_script_duration % 1) * 1000):03d}")
        logging.info(f"Total elapsed time since script start: {time.strftime('%H:%M:%S', time.gmtime(total_elapsed_from_start))}.{int((total_elapsed_from_start % 1) * 1000):03d}")

    sys.exit(exit_code)