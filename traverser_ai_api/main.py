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
        # Format as H:MM:SS.milliseconds
        h = int(elapsed_seconds // 3600)
        m = int((elapsed_seconds % 3600) // 60)
        s = int(elapsed_seconds % 60)
        ms = int((elapsed_seconds - (h * 3600 + m * 60 + s)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

# --- Logging Setup Function ---
def setup_logging(log_level_str: str = "INFO", log_file: Optional[str] = None):
    """Sets up logging with ElapsedTimeFormatter for console (stdout) and optionally a file."""
    numeric_level = getattr(logging, log_level_str.upper(), None)
    if not isinstance(numeric_level, int):
        # Use print for this very early warning as logging might not be fully set up.
        print(f"Warning: Invalid log level string: '{log_level_str}'. Defaulting to INFO.", file=sys.stderr)
        numeric_level = logging.INFO
        log_level_str = "INFO" # Correct the string for consistency if used later

    log_formatter = ElapsedTimeFormatter("[%(levelname)s] (%(asctime)s) %(filename)s:%(lineno)d - %(message)s")
    
    logger = logging.getLogger() # Get the root logger
    
    # Remove any existing handlers to prevent duplicate messages or formatting conflicts
    # This is important if setup_logging is called multiple times (e.g., after config load)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close() # Close handler before removing
    
    logger.setLevel(numeric_level) # Set level on the logger itself

    # Console Handler (always to sys.stdout for QProcess capture)
    console_handler_stdout = logging.StreamHandler(sys.stdout)
    console_handler_stdout.setFormatter(log_formatter)
    logger.addHandler(console_handler_stdout)

    # File Handler (Optional)
    if log_file:
        try:
            log_file_dir = os.path.dirname(os.path.abspath(log_file))
            if log_file_dir: # Ensure directory exists if log_file includes a path
                os.makedirs(log_file_dir, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
            file_handler.setFormatter(log_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # If file logging setup fails, log to console (which should be set up by now)
            logging.error(f"Error setting up file logger for {log_file}: {e}. Continuing with console logging.", exc_info=True)

    # Reduce verbosity of noisy libraries if main log level is not DEBUG
    if numeric_level > logging.DEBUG:
        for lib_name in ["appium.webdriver.webdriver", "urllib3.connectionpool", "selenium.webdriver.remote.remote_connection"]:
            logging.getLogger(lib_name).setLevel(logging.WARNING)
    
    # logging.info(f"Logging initialized. Level: {log_level_str.upper()}. File: {log_file if log_file else 'None'}")


# --- Initial (Basic) Logging Setup ---
# This ensures logging is available for early config loading issues.
# It will be re-configured after config.py and user_config.json are loaded.
setup_logging("INFO") # Default to INFO, no file log initially

# --- Configuration Loading ---
try:
    from . import config as cfg # cfg is the alias for the config module
    CONFIG_MODULE_PATH = os.path.abspath(cfg.__file__)
    CONFIG_DIR = os.path.dirname(CONFIG_MODULE_PATH)
    logging.info(f"Successfully imported config module from: {CONFIG_MODULE_PATH}")
except ImportError as e:
    logging.critical(f"CRITICAL: Failed to import 'config' module. Ensure 'config.py' exists and is in the correct path. Error: {e}", exc_info=True)
    sys.exit(1)
except Exception as e: # Catch any other exception during import or path resolution
    logging.critical(f"CRITICAL: Unexpected error during 'config' module import or path setup. Error: {e}", exc_info=True)
    sys.exit(1)

# Re-initialize logging with values from config.py
_log_level = getattr(cfg, 'LOG_LEVEL', 'INFO')
_log_file_template = getattr(cfg, 'LOG_FILE_TEMPLATE', None) # e.g., "../output_data/logs/{package}_main.log"
_log_file_name: Optional[str] = "app_traverser_default.log" # Initialized to a default string
_log_file_path: Optional[str] = None
_current_log_level = logging.INFO # Assuming this and similar globals are already here
_initial_config_log_level_str: Optional[str] = None # Assuming this and similar globals are already here
if _log_file_template:
    # At this stage, APP_PACKAGE might not be finalized. Use a generic log name or make it part of config.
    # For now, let's assume a generic log file name if {package} is in template before APP_PACKAGE is known
    # Or, better, make LOG_FILE_TEMPLATE not require {package} or handle it later.
    # Let's assume LOG_FILE in config.py is a direct path or relative path for a general log.
    # If it needs {package}, it should be handled after APP_PACKAGE is set.
    # For simplicity, let's assume LOG_FILE is a simple path for now.
    _log_file_name = getattr(cfg, 'LOG_FILE_NAME', 'main_script.log') # Ensure this is defined
    _log_dir = os.path.abspath(os.path.join(CONFIG_DIR, "..", "output_data", "logs"))
    _log_file_path = os.path.join(_log_dir, _log_file_name)

setup_logging(log_level_str=_log_level, log_file=_log_file_path)
logging.info(f"Logging re-initialized with settings from config.py. Level: {_log_level}")

# Load user_config.json and override defaults from cfg (config.py)
# user_config.json is expected to be in the same directory as config.py
user_config_path = os.path.join(CONFIG_DIR, "user_config.json")
if os.path.exists(user_config_path):
    try:
        with open(user_config_path, 'r') as f:
            user_config_data = json.load(f)
        logging.info(f"Successfully loaded user configuration from: {user_config_path}")
        
        # Hold the initial log settings before user overrides, in case they are needed for re-initialization
        initial_log_level = _log_level
        initial_log_file_name = _log_file_name # Capture the name defined from config.py or hardcoded default
        initial_log_file_path = _log_file_path

        for key, value in user_config_data.items():
            if hasattr(cfg, key):
                original_type = type(getattr(cfg, key))
                try:
                    if original_type == bool: value = str(value).lower() in ['true', '1', 'yes']
                    elif original_type == int: value = int(value)
                    elif original_type == float: value = float(value)
                    elif original_type == list and isinstance(value, str): # Example: handle comma or newline separated strings for lists
                        value = [item.strip() for item in value.replace('\\n', ',').split(',') if item.strip()]
                    
                    setattr(cfg, key, value)
                    logging.info(f"User config override: cfg.{key} = {value}")
                except ValueError as ve:
                    logging.warning(f"Type conversion error for user_config key '{key}' (value: '{value}'). Expected {original_type}. Error: {ve}")
            else:
                logging.warning(f"Key '{key}' from user_config.json not found in config.py defaults.")

        # Check if logging settings were changed by user_config and re-initialize if so
        user_log_level = user_config_data.get('LOG_LEVEL', initial_log_level)
        # Use initial_log_file_name as the default if LOG_FILE_NAME is not in user_config.json
        user_log_file_name_override = user_config_data.get('LOG_FILE_NAME', initial_log_file_name) 
        
        user_log_file_path_override = initial_log_file_path # Default to previous path
        
        # If user specified a LOG_FILE_NAME (even if same as default), reconstruct path
        # Or if they specified a LOG_FILE_TEMPLATE (which implies custom naming)
        if user_config_data.get('LOG_FILE_NAME') is not None or user_config_data.get('LOG_FILE_TEMPLATE') is not None:
             user_log_dir_for_override = os.path.abspath(os.path.join(CONFIG_DIR, "..", "output_data", "logs")) 
             user_log_file_path_override = os.path.join(user_log_dir_for_override, user_log_file_name_override)

        if user_log_level != initial_log_level or user_log_file_path_override != initial_log_file_path:
            _log_level = user_log_level  # Update module-level _log_level
            _log_file_path = user_log_file_path_override # Update module-level _log_file_path
            
            setup_logging(log_level_str=_log_level, log_file=_log_file_path)
            logging.info(f"Logging re-initialized with settings from user_config.json. Level: {_log_level}, File: {_log_file_path}")
        else:
            logging.info("User configuration loaded, but no changes to active logging settings (level/file).")

    except json.JSONDecodeError as e:
        logging.error(f"Error: Could not parse {user_config_path}. Invalid JSON: {e}", exc_info=True)
    except Exception as e:
        logging.warning(f"Warning: Failed to load or apply user configuration from {user_config_path}: {e}", exc_info=True)
else:
    logging.info(f"User configuration file not found at {user_config_path}. Using defaults from config.py.")


# --- Path Resolution Helper ---
def resolve_config_path(path_template_or_direct: str, app_package_name: Optional[str] = None) -> str:
    """
    Resolves a path string from config. It can be a template needing an app_package_name,
    or a direct relative/absolute path. Relative paths are resolved from CONFIG_DIR.
    """
    path_to_resolve = path_template_or_direct
    if app_package_name and "{package}" in path_template_or_direct:
        path_to_resolve = path_template_or_direct.format(package=app_package_name)
    
    if not os.path.isabs(path_to_resolve):
        resolved_path = os.path.abspath(os.path.join(CONFIG_DIR, path_to_resolve))
    else:
        resolved_path = path_to_resolve
    return resolved_path

# --- Early Path Setups (those not dependent on final APP_PACKAGE) ---
cfg.APP_INFO_OUTPUT_DIR = resolve_config_path(getattr(cfg, 'APP_INFO_OUTPUT_DIR', '../output_data/app_info/'))
try:
    os.makedirs(cfg.APP_INFO_OUTPUT_DIR, exist_ok=True)
    logging.info(f"Ensured APP_INFO_OUTPUT_DIR exists: {cfg.APP_INFO_OUTPUT_DIR}")
except OSError as e:
    logging.error(f"Could not create APP_INFO_OUTPUT_DIR: {cfg.APP_INFO_OUTPUT_DIR}. Error: {e}", exc_info=True)
    # This might be critical depending on subsequent logic.

# --- Import find_app_info functions (optional, for app discovery) ---
get_device_serial_func, generate_app_info_cache_func = None, None
try:
    from .find_app_info import get_device_serial, generate_app_info_cache
    get_device_serial_func = get_device_serial
    generate_app_info_cache_func = generate_app_info_cache
    logging.info("Successfully imported app info functions from find_app_info.py.")
except ImportError:
    logging.warning("Could not import from 'find_app_info.py'. App info cache/discovery features will be disabled. Ensure APP_PACKAGE and APP_ACTIVITY are correctly set in config.")
except Exception as e:
    logging.error(f"Error importing from 'find_app_info.py': {e}", exc_info=True)


# --- Import AppCrawler (late, after config is set) ---
try:
    from .crawler import AppCrawler
    logging.info("Successfully imported AppCrawler.")
except ImportError as e:
    logging.critical(f"CRITICAL: Failed to import 'AppCrawler'. Ensure 'crawler.py' exists and its dependencies are met. Error: {e}", exc_info=True)
    sys.exit(1)
except Exception as e:
    logging.critical(f"CRITICAL: Unexpected error importing 'AppCrawler'. Error: {e}", exc_info=True)
    sys.exit(1)


# --- Main Execution Block ---
if __name__ == "__main__":
    main_start_time = time.time()
    logging.info(f"======== Script '{os.path.basename(__file__)}' started. PID: {os.getpid()} ========")
    logging.info(f"Python: {sys.version.splitlines()[0]} on {sys.platform}")
    logging.info(f"Initial CWD: {os.getcwd()}")
    logging.info(f"Config module location: {CONFIG_MODULE_PATH}")

    # 1. Validate Essential Configurations from cfg
    if not getattr(cfg, 'APP_PACKAGE', None):
        logging.critical("APP_PACKAGE is not defined in configuration (config.py or user_config.json). Cannot proceed. Exiting.")
        sys.exit(1)
    
    # GEMINI_API_KEY check (can be optional if AI features are toggleable)
    if getattr(cfg, 'USE_AI_IMAGE_ANALYSIS', False) or getattr(cfg, 'USE_AI_TEXT_ANALYSIS', False):
        if not getattr(cfg, 'GEMINI_API_KEY', None):
            logging.critical("AI features are enabled in config, but GEMINI_API_KEY is not set. Exiting.")
            sys.exit(1)
        else:
            logging.info("GEMINI_API_KEY is set.")
    else:
        logging.info("AI features are not enabled or GEMINI_API_KEY not required by current config.")

    # 2. App Info Cache Handling & Finalize APP_PACKAGE/APP_ACTIVITY
    app_info_successfully_configured = False
    initial_target_package = cfg.APP_PACKAGE # Store initial package from config
    
    if get_device_serial_func and generate_app_info_cache_func and getattr(cfg, 'AUTO_DISCOVER_APP_ACTIVITY', False):
        logging.info(f"Attempting to auto-discover/verify app info for: {initial_target_package}")
        for attempt in range(2): # Try to load; if fail, try to generate then load again.
            try:
                device_udid = getattr(cfg, 'TARGET_DEVICE_UDID', None)
                device_serial = get_device_serial_func(device_udid) # Returns None if error or no device
                
                if not device_serial:
                    logging.warning(f"Could not get device serial (UDID: {device_udid}). Cannot use device-specific app info cache.")
                    # Fallback to generic cache name or skip caching for this run if serial is essential
                    # For now, let's assume we can proceed without serial for cache name, or it's handled in find_app_info
                    cache_filename_suffix = "_app_info.json" # Generic if no serial
                else:
                    cache_filename_suffix = f"_{device_serial}_app_info.json"

                # Use AI filtering for discovery if configured
                ai_filter_for_discovery = getattr(cfg, 'USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY', False)
                cache_prefix = "filtered" if ai_filter_for_discovery else "all"
                cache_filename = f"{initial_target_package}_{cache_prefix}{cache_filename_suffix}"
                cache_filepath = os.path.join(cfg.APP_INFO_OUTPUT_DIR, cache_filename)
                logging.info(f"App info cache lookup (Attempt {attempt + 1}): {cache_filepath}")

                if os.path.exists(cache_filepath):
                    with open(cache_filepath, 'r', encoding='utf-8') as f:
                        cached_app_info = json.load(f)
                    
                    # find_app_info.py might store a list or a single dict. Adapt as needed.
                    # Assuming it's a dict with 'package_name' and 'activity_name' for the target app.
                    if isinstance(cached_app_info, dict) and cached_app_info.get('package_name') == initial_target_package and cached_app_info.get('activity_name'):
                        cfg.APP_PACKAGE = cached_app_info['package_name'] # Should be same as initial_target_package
                        cfg.APP_ACTIVITY = cached_app_info['activity_name']
                        logging.info(f"Successfully loaded app info from cache: PACKAGE='{cfg.APP_PACKAGE}', ACTIVITY='{cfg.APP_ACTIVITY}'")
                        app_info_successfully_configured = True
                        break # Exit loop on success
                    else:
                        logging.warning(f"Cache file {cache_filepath} exists but data is not in expected format or doesn't match target package.")
                
                if attempt == 0 and not app_info_successfully_configured: # Only try to generate on the first failed load attempt
                    logging.info(f"App info cache not found or invalid. Attempting to (re)generate for '{initial_target_package}'...")
                    # generate_app_info_cache should save to the correct project-level dir (cfg.APP_INFO_OUTPUT_DIR)
                    # It might return the path to the generated file or True/False
                    generation_success = generate_app_info_cache_func(
                        target_package=initial_target_package,
                        device_udid=device_udid,
                        output_dir=cfg.APP_INFO_OUTPUT_DIR, # Pass the resolved output directory
                        use_ai_filtering=ai_filter_for_discovery
                    )
                    if not generation_success:
                        logging.error("App info cache generation failed. Check logs from find_app_info.py.")
                        # Decide if to break or let the loop try loading again (if generation created a partial file)
                elif attempt == 1 and not app_info_successfully_configured:
                    logging.warning(f"Failed to load app info from cache even after generation attempt.")

            except Exception as e_cache:
                logging.error(f"Error during app info cache handling (Attempt {attempt + 1}): {e_cache}", exc_info=True)
        
        if not app_info_successfully_configured:
            logging.warning(f"Could not auto-discover/verify app info for '{initial_target_package}'. Will proceed with values from config (ACTIVITY='{getattr(cfg, 'APP_ACTIVITY', None)}') if available.")
            if not getattr(cfg, 'APP_ACTIVITY', None): # If activity is crucial and not found
                logging.critical(f"APP_ACTIVITY for '{cfg.APP_PACKAGE}' could not be determined and is not set in config. Exiting.")
                sys.exit(1)
            # If here, APP_PACKAGE is set, APP_ACTIVITY might be from config.
            app_info_successfully_configured = True # Mark as configured to proceed with config values
    else:
        logging.info("App info auto-discovery/cache check skipped (either disabled in config or find_app_info.py functions unavailable).")
        if not getattr(cfg, 'APP_ACTIVITY', None):
            logging.critical(f"APP_ACTIVITY for '{cfg.APP_PACKAGE}' is not set in config, and auto-discovery is disabled/unavailable. Exiting.")
            sys.exit(1)
        logging.info(f"Proceeding with manually configured: PACKAGE='{cfg.APP_PACKAGE}', ACTIVITY='{cfg.APP_ACTIVITY}'")
        app_info_successfully_configured = True

    if not app_info_successfully_configured: # Should be caught above, but as a final check
        logging.critical(f"CRITICAL: App info (package/activity) could not be finalized for target '{initial_target_package}'. Exiting.")
        sys.exit(1)
    
    # Final APP_PACKAGE and APP_ACTIVITY to be used
    current_app_package = cfg.APP_PACKAGE
    current_app_activity = cfg.APP_ACTIVITY
    logging.info(f"Final app configuration: PACKAGE='{current_app_package}', ACTIVITY='{current_app_activity}'")

    # 3. Finalize Dynamic Paths (Screenshots, DB) using the determined APP_PACKAGE
    # These templates are from config.py, e.g., "../output_data/db/{package}_crawl_data.db"
    cfg.DB_NAME = resolve_config_path(getattr(cfg, 'DB_NAME_TEMPLATE', '../output_data/db/{package}_crawl_data.db'), current_app_package)
    cfg.SCREENSHOTS_DIR = resolve_config_path(getattr(cfg, 'SCREENSHOTS_DIR_TEMPLATE', '../output_data/screenshots/crawl_screenshots_{package}/'), current_app_package)
    cfg.ANNOTATED_SCREENSHOTS_DIR = resolve_config_path(getattr(cfg, 'ANNOTATED_SCREENSHOTS_DIR_TEMPLATE', '../output_data/screenshots/annotated_crawl_screenshots_{package}/'), current_app_package)
    # TRAFFIC_CAPTURE_OUTPUT_DIR might also be a template
    cfg.TRAFFIC_CAPTURE_OUTPUT_DIR = resolve_config_path(getattr(cfg, 'TRAFFIC_CAPTURE_OUTPUT_DIR_TEMPLATE', '../output_data/traffic/{package}/'), current_app_package)


    # 4. Handle Existing Run Data (Clearing directories if not continuing)
    if not getattr(cfg, 'CONTINUE_EXISTING_RUN', False):
        logging.info(f"CONTINUE_EXISTING_RUN is False. Clearing existing crawl data for '{current_app_package}'...")
        
        paths_to_clear = [cfg.DB_NAME, cfg.SCREENSHOTS_DIR, cfg.ANNOTATED_SCREENSHOTS_DIR, cfg.TRAFFIC_CAPTURE_OUTPUT_DIR]
        db_suffixes_to_clear = ['-shm', '-wal'] # For SQLite auxiliary files

        for path_str in paths_to_clear:
            if not path_str: continue # Skip if path string is empty
            if os.path.exists(path_str):
                try:
                    if os.path.isfile(path_str):
                        os.remove(path_str)
                        logging.info(f"Removed existing file: {path_str}")
                        if path_str == cfg.DB_NAME: # Check for SQLite auxiliary files
                            for suffix in db_suffixes_to_clear:
                                aux_file = path_str + suffix
                                if os.path.exists(aux_file):
                                    os.remove(aux_file)
                                    logging.info(f"Removed existing DB auxiliary file: {aux_file}")
                    elif os.path.isdir(path_str):
                        shutil.rmtree(path_str)
                        logging.info(f"Removed existing directory: {path_str}")
                except OSError as e:
                    logging.error(f"Error removing '{path_str}': {e}", exc_info=True)
            # else: logging.debug(f"Path to clear not found (normal if first run): {path_str}")
    else:
        logging.info(f"CONTINUE_EXISTING_RUN is True. Existing data for '{current_app_package}' will be used/appended if present.")

    # 5. Ensure Necessary Directories Exist (after potential clearing)
    dirs_to_ensure_exist = [
        os.path.dirname(cfg.DB_NAME), # Parent directory for the database file
        cfg.SCREENSHOTS_DIR,
        cfg.ANNOTATED_SCREENSHOTS_DIR,
        cfg.TRAFFIC_CAPTURE_OUTPUT_DIR
    ]
    for dir_path in dirs_to_ensure_exist:
        if not dir_path: continue # Skip if path string is empty (e.g. dirname of a root file)
        try:
            os.makedirs(dir_path, exist_ok=True)
            logging.info(f"Ensured directory exists: {dir_path}")
        except OSError as e:
            # Log error but script might continue if directory is not critical or created later
            logging.error(f"Could not create directory '{dir_path}': {e}. This might cause issues.", exc_info=True)


    # 6. Prepare Configuration Dictionary for AppCrawler
    # This uses the cfg object, which has been updated by user_config.json and app info cache.
    # Create a dictionary of all non-private, non-callable attributes from cfg
    current_config_dict = {
        key: getattr(cfg, key) for key in dir(cfg) 
        if not key.startswith('__') and \
           not callable(getattr(cfg, key)) and \
           not isinstance(getattr(cfg, key), type(sys)) # Exclude modules like 'os', 'sys' if they are in cfg
    }
    # Ensure critical, potentially resolved/updated paths are correctly in the dict for the crawler
    # Most of these are already updated in cfg directly, so they will be included.
    # Explicitly ensure APP_PACKAGE and APP_ACTIVITY are the finalized ones.
    current_config_dict["APP_PACKAGE"] = current_app_package
    current_config_dict["APP_ACTIVITY"] = current_app_activity
    
    logging.debug(f"Final configuration being passed to AppCrawler: \n{json.dumps(current_config_dict, indent=2, default=str)}")

    # 7. Initialize and Run the Crawler
    logging.info(f"Initializing AppCrawler for '{current_app_package}'...")
    crawler_instance = None
    try:
        crawler_instance = AppCrawler(config_dict=current_config_dict)
        logging.info("AppCrawler initialized. Starting crawl...")
        crawler_instance.run() # Changed start_crawl() to run()
        logging.info("AppCrawler crawl process finished.")

    except KeyboardInterrupt:
        logging.warning("KeyboardInterrupt received. Attempting to shut down crawler gracefully...")
        # Graceful shutdown logic might be in crawler's __del__ or a specific stop method
    except SystemExit as se:
        logging.warning(f"SystemExit called: {se}. This might be due to a critical error handled elsewhere.")
        # Re-raise if necessary, or handle as a specific termination cause
        # For now, assume it's handled and proceed to finally block.
    except Exception as e_crawler:
        logging.critical(f"An unexpected error occurred while initializing or running the AppCrawler: {e_crawler}", exc_info=True)
        # Depending on the error, you might want to sys.exit(1) here or let finally block handle cleanup.
    finally:
        if crawler_instance and hasattr(crawler_instance, 'quit_driver') and callable(crawler_instance.quit_driver):
            logging.info("Attempting to quit Appium driver...")
            try:
                crawler_instance.quit_driver()
                logging.info("Appium driver quit successfully.")
            except Exception as e_quit:
                logging.error(f"Error encountered while quitting Appium driver: {e_quit}", exc_info=True)
        else:
            logging.info("No active Appium driver to quit or quit_driver method not found.")
        
        main_end_time = time.time()
        total_script_duration = main_end_time - main_start_time
        # Use SCRIPT_START_TIME for total elapsed since script file execution began
        total_elapsed_from_start = main_end_time - SCRIPT_START_TIME
        
        logging.info(f"======== Script '{os.path.basename(__file__)}' finished. ========")
        logging.info(f"Total execution time for __main__ block: {time.strftime('%H:%M:%S', time.gmtime(total_script_duration))}.{int((total_script_duration % 1) * 1000):03d}")
        logging.info(f"Total elapsed time since script start: {time.strftime('%H:%M:%S', time.gmtime(total_elapsed_from_start))}.{int((total_elapsed_from_start % 1) * 1000):03d}")

    # sys.exit(0) # Explicitly exit with 0 if successful, though it's default