import asyncio
import json
import logging
import os
import shutil
import sys
import time
from typing import Optional

try:
    from config.config import Config
except ImportError:
    from config.config import Config

try:
    try:
        from utils.utils import SCRIPT_START_TIME, ElapsedTimeFormatter, LoggerManager
    except ImportError:
        from utils.utils import SCRIPT_START_TIME, ElapsedTimeFormatter, LoggerManager
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
    cfg = Config(user_config_json_path=USER_CONFIG_JSON_PATH)
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

    if cfg.get('SHUTDOWN_FLAG_PATH') and os.path.exists(cfg.get('SHUTDOWN_FLAG_PATH')):
        bootstrap_logger.warning(f"Found existing shutdown flag at startup: {cfg.get('SHUTDOWN_FLAG_PATH')}. Removing it.")
        remove_with_retry(cfg.get('SHUTDOWN_FLAG_PATH'))
    if not cfg.get('APP_PACKAGE'):
        bootstrap_logger.critical("APP_PACKAGE is not defined in configuration. Cannot proceed. Exiting.")
        sys.exit(1)
    if not cfg.get('APP_ACTIVITY'):
        bootstrap_logger.critical("APP_ACTIVITY is not defined in configuration. Cannot proceed. Exiting.")
        sys.exit(1)
    # These checks can remain with bootstrap_logger
    if cfg.get('ENABLE_TRAFFIC_CAPTURE') and not cfg.get('PCAPDROID_API_KEY') and cfg.get('PCAPDROID_PACKAGE') == "com.emanuelef.remote_capture":
        bootstrap_logger.warning("PCAPDROID_API_KEY is not set, but traffic capture is enabled for PCAPdroid. Capture might fail if API key is required.")
    # Provider-agnostic credential check
    ai_provider = str(getattr(cfg, 'AI_PROVIDER', 'gemini')).lower()
    if ai_provider == 'gemini':
        if not getattr(cfg, 'GEMINI_API_KEY', None):
            bootstrap_logger.warning("GEMINI_API_KEY is not set. AI-dependent features may fail when using provider 'gemini'.")
        else:
            bootstrap_logger.info("Gemini API key detected.")
    elif ai_provider == 'openrouter':
        if not getattr(cfg, 'OPENROUTER_API_KEY', None):
            bootstrap_logger.warning("OPENROUTER_API_KEY is not set. AI-dependent features may fail when using provider 'openrouter'.")
        else:
            bootstrap_logger.info("OpenRouter API key detected.")
    elif ai_provider == 'ollama':
        if not getattr(cfg, 'OLLAMA_BASE_URL', None) and not os.getenv('OLLAMA_HOST', None):
            bootstrap_logger.warning("OLLAMA_BASE_URL/OLLAMA_HOST is not set. AI-dependent features may fail when using provider 'ollama'.")
        else:
            bootstrap_logger.info("Ollama base URL detected.")

    current_app_package = cfg.get('APP_PACKAGE')
    current_app_activity = cfg.get('APP_ACTIVITY')
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
    # Removed preparation of legacy JSONL AI interactions log (ai_interactions.log)
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
                      'DB_NAME', 'ALLOWED_EXTERNAL_PACKAGES', 'SHUTDOWN_FLAG_PATH',
                      'GEMINI_API_KEY', 'OPENROUTER_API_KEY', 'OLLAMA_BASE_URL']:
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
        try:
            from legacy_code.crawler import AppCrawler  
        except ImportError:
            from legacy_code.crawler import AppCrawler 
        crawler_instance = AppCrawler(app_config=cfg)
        root_logger.info("AppCrawler initialized. Starting crawl...")
        crawler_instance.run() # This internally calls asyncio.run()
        root_logger.info("AppCrawler crawl process finished normally.")

        # --- Auto-run UI Element Annotation after each crawl (provider-agnostic) ---
        try:
            screenshots_dir = getattr(cfg, 'SCREENSHOTS_DIR', None)
            app_identifier = getattr(cfg, 'APP_PACKAGE', None)

            if not screenshots_dir or not os.path.isdir(screenshots_dir):
                root_logger.debug("UI Annotation: No screenshots directory found; skipping auto-annotation.")
            elif not app_identifier:
                root_logger.debug("UI Annotation: APP_PACKAGE not set; skipping auto-annotation.")
            else:
                # Resolve provider, model, and API key/base URL from config
                provider = str(getattr(cfg, 'AI_PROVIDER', 'gemini')).lower()
                model_name = str(getattr(cfg, 'DEFAULT_MODEL_TYPE', '')).strip()
                api_key_or_base = None
                if provider == 'gemini':
                    api_key_or_base = getattr(cfg, 'GEMINI_API_KEY', None)
                elif provider == 'openrouter':
                    api_key_or_base = getattr(cfg, 'OPENROUTER_API_KEY', None)
                elif provider == 'ollama':
                    # For Ollama, we pass base URL as the "api_key" param to the adapter
                    api_key_or_base = getattr(cfg, 'OLLAMA_BASE_URL', None) or os.getenv('OLLAMA_HOST', None)

                if not api_key_or_base:
                    root_logger.debug(f"UI Annotation: Missing credentials/base for provider '{provider}'; skipping auto-annotation.")
                elif not model_name:
                    root_logger.debug("UI Annotation: DEFAULT_MODEL_TYPE not set; skipping auto-annotation.")
                else:
                    # Prepare output directory and file
                    output_base_dir = os.path.join(getattr(cfg, 'OUTPUT_DATA_DIR', 'output_data'), 'annotations')
                    os.makedirs(output_base_dir, exist_ok=True)
                    output_file_path = os.path.join(output_base_dir, f"{app_identifier}_annotations.json")

                    # Import model adapters and PIL
                    try:
                        try:
                            from domain.model_adapters import create_model_adapter
                        except ImportError:
                            from domain.model_adapters import create_model_adapter
                        import glob
                        import re

                        from PIL import Image
                    except Exception as imp_err:
                        root_logger.error(f"UI Annotation: Failed to import dependencies: {imp_err}", exc_info=True)
                        raise

                    # Initialize adapter
                    try:
                        adapter = create_model_adapter(provider, api_key_or_base, model_name)
                        generation_cfg = {
                            'generation_config': {
                                'temperature': 0.3,
                                'top_p': 0.8,
                                'top_k': 20,
                                'max_output_tokens': 2048
                            }
                        }
                        adapter.initialize(generation_cfg, safety_settings=getattr(cfg, 'AI_SAFETY_SETTINGS', {}))
                    except Exception as init_err:
                        root_logger.error(f"UI Annotation: Failed to initialize model adapter for provider '{provider}': {init_err}", exc_info=True)
                        raise

                    # Helper to clean JSON-like responses
                    def _clean_json_response(text: str) -> str:
                        try:
                            text = re.sub(r"```(?:json)?\s*|\s*```", "", text or "")
                            text = re.sub(r",(\s*[\]}])", r"\1", text)
                            text = text.strip()
                            if not text.startswith('['):
                                si = text.find('[')
                                if si != -1:
                                    text = text[si:]
                            if not text.endswith(']'):
                                ei = text.rfind(']')
                                if ei != -1:
                                    text = text[:ei+1]
                            return text
                        except Exception:
                            return text or "[]"

                    # Build prompt (provider-agnostic)
                    prompt = (
                        "Analyze this screenshot and identify ALL UI elements visible in the image. "
                        "For each element, return JSON with: type (button, editText, textView, etc.), "
                        "description (optional), resource_id (optional), and normalized bounding_box coordinates "
                        "with top_left [y1, x1] and bottom_right [y2, x2] where values are 0.0-1.0. "
                        "IMPORTANT: Respond ONLY with a JSON array; no extra text."
                    )

                    # Collect screenshots (*.png, *.jpg, *.jpeg, *.webp)
                    patterns = ["*.png", "*.jpg", "*.jpeg", "*.webp"]
                    image_files = []
                    for pat in patterns:
                        image_files.extend(glob.glob(os.path.join(screenshots_dir, pat)))

                    if not image_files:
                        root_logger.debug("UI Annotation: No images found to annotate; skipping.")
                    else:
                        results = {}
                        failed = []
                        root_logger.info(f"UI Annotation: Starting automatic UI element annotation using provider '{provider}' and model '{model_name}'.")
                        for img_path in sorted(image_files):
                            try:
                                with Image.open(img_path) as img:
                                    response_text, meta = adapter.generate_response(
                                        prompt=prompt,
                                        image=img,
                                        image_format=getattr(cfg, 'IMAGE_FORMAT', 'JPEG'),
                                        image_quality=getattr(cfg, 'IMAGE_QUALITY', 70)
                                    )
                                cleaned = _clean_json_response(response_text)
                                try:
                                    data = json.loads(cleaned)
                                    if isinstance(data, list):
                                        results[os.path.basename(img_path)] = data
                                    else:
                                        root_logger.warning(f"UI Annotation: Non-list JSON for {os.path.basename(img_path)}; marking as failed.")
                                        failed.append(os.path.basename(img_path))
                                except json.JSONDecodeError:
                                    root_logger.warning(f"UI Annotation: JSON decode failed for {os.path.basename(img_path)}; marking as failed.")
                                    failed.append(os.path.basename(img_path))
                            except Exception as per_img_err:
                                root_logger.warning(f"UI Annotation: Error annotating {os.path.basename(img_path)}: {per_img_err}")
                                failed.append(os.path.basename(img_path))

                        # Save results
                        if results:
                            try:
                                with open(output_file_path, 'w', encoding='utf-8') as f:
                                    json.dump(results, f, indent=2, ensure_ascii=False)
                                root_logger.info(f"UI Annotation: Completed. Results saved to: {output_file_path}")
                            except Exception as save_err:
                                root_logger.error(f"UI Annotation: Failed to save results: {save_err}", exc_info=True)
                        # Save failed list if any
                        if failed:
                            try:
                                failed_list_file = os.path.join(output_base_dir, f"{app_identifier}_annotations_failed.txt")
                                with open(failed_list_file, 'w', encoding='utf-8') as f:
                                    f.write('\n'.join(failed))
                                root_logger.info(f"UI Annotation: Failed to process {len(failed)} images. List saved to: {failed_list_file}")
                            except Exception as fail_save_err:
                                root_logger.error(f"UI Annotation: Failed to save failed image list: {fail_save_err}", exc_info=True)
        except Exception as outer_ann_err:
            root_logger.error(f"UI Annotation: Unexpected error in auto-annotation block: {outer_ann_err}", exc_info=True)

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
                if asyncio.iscoroutinefunction(crawler_instance.perform_full_cleanup):
                    asyncio.run(crawler_instance.perform_full_cleanup())
                else:
                    crawler_instance.perform_full_cleanup()
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
