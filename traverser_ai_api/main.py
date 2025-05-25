import logging
import time
import sys
import os
import json
import shutil # For rmtree
import io # Added for TextIOWrapper
from typing import Optional, Dict, Any, List

# --- Global Script Start Time (defined once at the very top) ---
SCRIPT_START_TIME = time.time()

# --- Custom Log Formatter and Handler Manager ---
class ElapsedTimeFormatter(logging.Formatter):
    """Custom formatter to log elapsed time since script start."""
    def formatTime(self, record, datefmt=None):
        elapsed_seconds = record.created - SCRIPT_START_TIME
        h = int(elapsed_seconds // 3600)
        m = int((elapsed_seconds % 3600) // 60)
        s = int(elapsed_seconds % 60)
        ms = int((elapsed_seconds - (h * 3600 + m * 60 + s)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

class LoggerManager:
    """Manages logging setup and persistence of handlers"""
    def __init__(self):
        # Keep references to prevent garbage collection
        self.handlers = []
        self.stdout_wrapper = None

    def setup_logging(self, log_level_str: str, log_file: Optional[str] = None) -> logging.Logger:
        numeric_level = getattr(logging, log_level_str.upper())
        if not isinstance(numeric_level, int):
            raise ValueError(f"Invalid log level string: {log_level_str}")

        # Create root logger
        logger = logging.getLogger()
        logger.setLevel(numeric_level)
    
        # Remove existing handlers
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            if isinstance(handler, logging.FileHandler):
                try:
                    handler.close()
                except Exception:
                    pass

        # Create formatter
        log_formatter = ElapsedTimeFormatter("[%(levelname)s] (%(asctime)s) %(filename)s:%(lineno)d - %(message)s")
    
        # Console Handler - carefully handle UTF-8
        try:
            # Create a persistent wrapper
            if not self.stdout_wrapper:
                self.stdout_wrapper = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            console_handler = logging.StreamHandler(self.stdout_wrapper)
        except Exception:
            # Fallback to regular stdout
            console_handler = logging.StreamHandler(sys.stdout)
    
        console_handler.setFormatter(log_formatter)
        logger.addHandler(console_handler)
        self.handlers.append(console_handler)

        # File Handler
        if log_file:
            try:
                log_file_dir = os.path.dirname(os.path.abspath(log_file))
                if log_file_dir:
                    os.makedirs(log_file_dir, exist_ok=True)
                file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
                file_handler.setFormatter(log_formatter)
                logger.addHandler(file_handler)
                self.handlers.append(file_handler)
            except Exception as e:
                raise RuntimeError(f"Error setting up file logger for {log_file}: {e}")

        # Set levels for noisy libraries
        if numeric_level > logging.DEBUG:
            for lib_name in ["appium.webdriver.webdriver", "urllib3.connectionpool", "selenium.webdriver.remote.remote_connection"]:
                logging.getLogger(lib_name).setLevel(logging.WARNING)
        
        return logger

class Config:
    """Configuration class with type hints for IntelliSense support"""
    def __init__(self):
        # App settings
        self.APP_PACKAGE: str = ""
        self.APP_ACTIVITY: str = ""
        
        # Directory paths
        self.DB_NAME: str = ""
        self.SCREENSHOTS_DIR: str = ""
        self.ANNOTATED_SCREENSHOTS_DIR: str = ""
        self.TRAFFIC_CAPTURE_OUTPUT_DIR: str = ""
        self.APP_INFO_OUTPUT_DIR: str = ""
        
        # Logging settings
        self.LOG_LEVEL: Optional[str] = None
        self.LOG_FILE_NAME: Optional[str] = None

        # AI Settings
        self.DEFAULT_MODEL_TYPE: Optional[str] = None
        self.AI_SAFETY_SETTINGS: Optional[Dict[str, str]] = None

        # Other settings to be added as needed
        self.CONTINUE_EXISTING_RUN: Optional[bool] = None
        self.GEMINI_API_KEY: Optional[str] = None
        self.APPIUM_SERVER_URL: Optional[str] = None
        self.TARGET_DEVICE_UDID: Optional[str] = None
        self.NEW_COMMAND_TIMEOUT: Optional[int] = None
        self.APPIUM_IMPLICIT_WAIT: Optional[int] = None
        self.MAX_CONSECUTIVE_AI_FAILURES: Optional[int] = None
        self.MAX_CONSECUTIVE_MAP_FAILURES: Optional[int] = None
        self.MAX_CONSECUTIVE_EXEC_FAILURES: Optional[int] = None
        self.APP_LAUNCH_WAIT_TIME: Optional[int] = None
        self.WAIT_AFTER_ACTION: Optional[float] = None
        self.STABILITY_WAIT: Optional[float] = None
        self.ALLOWED_EXTERNAL_PACKAGES: Optional[List[str]] = None
        self.USE_COORDINATE_FALLBACK: Optional[bool] = None
        self.XML_SNIPPET_MAX_LEN: Optional[int] = None
        self.VISUAL_SIMILARITY_THRESHOLD: Optional[int] = None
        self.ENABLE_XML_CONTEXT: Optional[bool] = None
        self.CRAWL_MODE: Optional[str] = None
        self.MAX_CRAWL_STEPS: Optional[int] = None
        self.MAX_CRAWL_DURATION_SECONDS: Optional[int] = None
        self.ENABLE_TRAFFIC_CAPTURE: Optional[bool] = None
        self.PCAPDROID_PACKAGE: Optional[str] = None
        self.PCAPDROID_ACTIVITY: Optional[str] = None
        self.DEVICE_PCAP_DIR: Optional[str] = None
        self.CLEANUP_DEVICE_PCAP_FILE: Optional[bool] = None
        self.USE_CHAT_MEMORY: Optional[bool] = None
        self.MAX_CHAT_HISTORY: Optional[int] = None
        self.GEMINI_MODELS: Optional[Dict[str, Any]] = None # For AI Assistant, though it reads from global config
        self.AVAILABLE_ACTIONS: Optional[List[str]] = None # For AI Assistant prompt building

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update config from a dictionary, with type validation"""
        for key, value in data.items():
            if hasattr(self, key):
                current_value = getattr(self, key)
                try:
                    # Convert value to the same type as the current attribute
                    if isinstance(current_value, bool) and not isinstance(value, bool):
                        converted_value = str(value).lower() in ['true', '1', 'yes']
                    elif isinstance(current_value, int) and not isinstance(value, int):
                        converted_value = int(value)
                    elif isinstance(current_value, float) and not isinstance(value, float):
                        converted_value = float(value)
                    elif isinstance(current_value, list):
                        if isinstance(value, str):
                            converted_value = [item.strip() for item in value.split('\n') if item.strip()]
                        else:
                            converted_value = value
                    else:
                        converted_value = value

                    if current_value != converted_value:
                        setattr(self, key, converted_value)
                        logging.info(f"Config updated: {key} = {converted_value} (was: {current_value})")
                except (ValueError, TypeError) as e:
                    logging.warning(f"Type conversion error for config key '{key}': {e}")

    def load_from_file(self, path: str) -> None:
        """Load configuration from a Python file"""
        try:
            with open(path, 'r') as f:
                # Create a new dict with a clean global namespace
                global_dict = {}
                # Execute the file content in the new namespace
                exec(f.read(), global_dict)
                # Update config from the new namespace
                self.update_from_dict({k: v for k, v in global_dict.items() 
                                    if not k.startswith('__') and not callable(v)})
                logging.info(f"Successfully loaded config from: {path}")
        except Exception as e:
            logging.critical(f"Failed to load config from '{path}': {e}", exc_info=True)
            raise

# Create single instances of managers
logger_manager = LoggerManager()
cfg = Config()

# Load config file first
CONFIG_MODULE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.py')
try:
    cfg.load_from_file(CONFIG_MODULE_PATH)
except Exception as e:
    logging.critical(f"CRITICAL: Failed to load 'config.py'. Error: {e}", exc_info=True)
    sys.exit(1)

# --- Initial (Basic) Logging Setup ---
cfg_log_level = getattr(cfg, 'LOG_LEVEL')
if cfg_log_level is None:
    raise ValueError("LOG_LEVEL must be defined in config")
root_logger = logger_manager.setup_logging(cfg_log_level)
root_logger.info("Initial logging setup complete")

# --- Project Root and Configuration Paths ---
# Assuming this main.py is in traverser_ai_api, and config.py is in the same directory.
# The project root is one level up from traverser_ai_api.
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_DIR = os.path.abspath(os.path.join(CURRENT_SCRIPT_DIR, ".."))
# Changed: Use config from traverser_ai_api directory instead of root
USER_CONFIG_FILENAME = "user_config.json"
USER_CONFIG_FILE_PATH = os.path.join(CURRENT_SCRIPT_DIR, USER_CONFIG_FILENAME)  # Use CURRENT_SCRIPT_DIR instead of PROJECT_ROOT_DIR

CONFIG_DIR = CURRENT_SCRIPT_DIR

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

# Get required log settings from config
_initial_cfg_log_level = getattr(cfg, 'LOG_LEVEL')
if _initial_cfg_log_level is None:
    raise ValueError("LOG_LEVEL must be defined in config")
_initial_cfg_log_file_name = getattr(cfg, 'LOG_FILE_NAME')
if _initial_cfg_log_file_name is None:
    raise ValueError("LOG_FILE_NAME must be defined in config")

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
# Get required log settings from config with validation
_current_log_level = getattr(cfg, 'LOG_LEVEL')
if _current_log_level is None:
    raise ValueError("LOG_LEVEL must be defined in config")
_current_log_file_name = getattr(cfg, 'LOG_FILE_NAME')
if _current_log_file_name is None:
    raise ValueError("LOG_FILE_NAME must be defined in config")

# Construct log file path relative to project root's output_data/logs
_log_dir_final = os.path.join(PROJECT_ROOT_DIR, "output_data", "logs")
_log_file_path_final = os.path.join(_log_dir_final, _current_log_file_name)

# Always re-setup logging with the final configuration
root_logger = logger_manager.setup_logging(log_level_str=_current_log_level, log_file=_log_file_path_final)
root_logger.info(f"Logging re-initialized. Level: {_current_log_level.upper()}. File: {_log_file_path_final}")


# --- Log final determined APP_PACKAGE and APP_ACTIVITY ---
# These are now the effective values after potential user_config.json override
logging.info(f"Effective APP_PACKAGE for crawl: {cfg.APP_PACKAGE}")
logging.info(f"Effective APP_ACTIVITY for crawl: {cfg.APP_ACTIVITY}")


# --- Resolve package-dependent paths AFTER APP_PACKAGE is finalized ---
db_name_template = getattr(cfg, 'DB_NAME')
if db_name_template is None:
    raise ValueError("DB_NAME must be defined in config")
cfg.DB_NAME = resolve_config_path(db_name_template.format(package=cfg.APP_PACKAGE))

screenshots_dir_template = getattr(cfg, 'SCREENSHOTS_DIR')
if screenshots_dir_template is None:
    raise ValueError("SCREENSHOTS_DIR must be defined in config")
cfg.SCREENSHOTS_DIR = resolve_config_path(screenshots_dir_template.format(package=cfg.APP_PACKAGE))

annotated_screenshots_dir_template = getattr(cfg, 'ANNOTATED_SCREENSHOTS_DIR')
if annotated_screenshots_dir_template is None:
    raise ValueError("ANNOTATED_SCREENSHOTS_DIR must be defined in config")
cfg.ANNOTATED_SCREENSHOTS_DIR = resolve_config_path(annotated_screenshots_dir_template.format(package=cfg.APP_PACKAGE))

traffic_capture_dir_template = getattr(cfg, 'TRAFFIC_CAPTURE_OUTPUT_DIR')
if traffic_capture_dir_template is None:
    raise ValueError("TRAFFIC_CAPTURE_OUTPUT_DIR must be defined in config")
cfg.TRAFFIC_CAPTURE_OUTPUT_DIR = resolve_config_path(traffic_capture_dir_template.format(package=cfg.APP_PACKAGE))

# --- APP_INFO_OUTPUT_DIR (usually not package-dependent, but resolve it) ---
app_info_dir = getattr(cfg, 'APP_INFO_OUTPUT_DIR')
if app_info_dir is None:
    raise ValueError("APP_INFO_OUTPUT_DIR must be defined in config")
cfg.APP_INFO_OUTPUT_DIR = resolve_config_path(app_info_dir)

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
        if crawler_instance and hasattr(crawler_instance, 'perform_full_cleanup') and callable(crawler_instance.perform_full_cleanup):
            logging.info("Main.py finally: Calling crawler_instance.perform_full_cleanup() for final cleanup.")
            try:
                crawler_instance.perform_full_cleanup()
            except Exception as e_cleanup:
                logging.error(f"Main.py finally: Error during final cleanup: {e_cleanup}", exc_info=True)
        
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
        logging.info(f"======== Script '{os.path.basename(__file__)}' finished with exit_code: {exit_code} ========")
        logging.info(f"Total execution time for __main__ block: {time.strftime('%H:%M:%S', time.gmtime(total_script_duration))}.{int((total_script_duration % 1) * 1000):03d}")
        logging.info(f"Total elapsed time since script start: {time.strftime('%H:%M:%S', time.gmtime(total_elapsed_from_start))}.{int((total_elapsed_from_start % 1) * 1000):03d}")

    sys.exit(exit_code)