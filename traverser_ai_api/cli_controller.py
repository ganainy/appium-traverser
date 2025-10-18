#!/usr/bin/env python3
"""
CLI Controller for Appium Crawler
Uses the centralized Config class.
"""

import sys
import os
from pathlib import Path

# Determine project root
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import json
import requests
import signal
import subprocess
import threading
import errno
import time
import argparse
import logging
import sqlite3
from typing import Optional, Dict, Any, List, Tuple
import textwrap
from typing import get_type_hints
import glob

import sys
import os
from pathlib import Path

# Determine project root and add to path
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from config import Config
except ImportError as e:
    sys.stderr.write(f"FATAL: Could not import 'Config' class from config.py: {e}\n")
    sys.stderr.write(
        "Ensure config.py exists and contains the Config class definition.\n"
    )
    sys.exit(1)

try:
    from utils import SCRIPT_START_TIME, LoggerManager
except ImportError as e:
    sys.stderr.write(f"FATAL: Could not import logging utilities from utils.py: {e}\n")
    sys.stderr.write(
        "Ensure utils.py exists and contains SCRIPT_START_TIME, LoggerManager.\n"
    )
    if "SCRIPT_START_TIME" not in globals():
        SCRIPT_START_TIME = time.time()
    sys.exit(1)

try:
    from analysis_viewer import RunAnalyzer, XHTML2PDF_AVAILABLE
except ImportError as e:
    sys.stderr.write(f"FATAL: Could not import from analysis_viewer.py: {e}\n")
    sys.stderr.write(
        "Ensure analysis_viewer.py is in the same directory or Python path and has no import errors.\n"
    )
    RunAnalyzer = None
    XHTML2PDF_AVAILABLE = False


class CLIController:
    """Command-line controller for the Appium Crawler."""

    def __init__(self, app_config_instance: Config):
        self.cfg = app_config_instance
        self.api_dir = os.path.dirname(os.path.abspath(__file__))
        self.find_app_info_script_path = os.path.join(self.api_dir, "find_app_info.py")
        self.health_apps_data: List[Dict[str, Any]] = []
        self.pid_file_path = os.path.join(
            self.cfg.BASE_DIR or self.api_dir, "crawler.pid"
        )
        self.crawler_process: Optional[subprocess.Popen] = None
        self.discovered_analysis_targets: List[Dict[str, Any]] = []

        logging.debug(f"PID file will be managed at: {self.pid_file_path}")

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Attempt to auto-load cached health apps on startup
        cached_path = self.cfg.CURRENT_HEALTH_APP_LIST_FILE
        if cached_path:
            # Normalize relative path to absolute based on api_dir
            if not os.path.isabs(cached_path):
                cached_path = os.path.join(self.api_dir, cached_path)

            if os.path.exists(cached_path):
                logging.debug(
                    f"Attempting to auto-load health apps from: {cached_path}"
                )
                self._load_health_apps_from_file(cached_path)
            else:
                logging.debug(
                    f"Configured health app file not found: {cached_path}"
                )
                # Fallback: try resolving the latest device-specific 'health_filtered' cache
                fallback = self._resolve_latest_cache_file_by_suffix(
                    "health_filtered"
                )
                if fallback and os.path.exists(fallback):
                    logging.debug(
                        f"Falling back to resolved cache: {fallback}"
                    )
                    self._load_health_apps_from_file(fallback)
                else:
                    logging.debug(
                        "No pre-existing health app list file found or file does not exist."
                    )
        else:
            logging.debug(
                "No pre-existing health app list file found or file does not exist."
            )

    def _signal_handler(self, signum, frame):
        logging.warning(
            f"\nSignal {signal.Signals(signum).name} received. Initiating crawler shutdown..."
        )
        self.stop_crawler()
        logging.debug("CLI shutdown signal handled.")
        sys.exit(0)

    def _is_process_running(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except OSError as err:
            return err.errno == errno.EPERM
        return True

    def save_all_changes(self) -> bool:
        logging.debug("Attempting to save all current configuration settings...")
        try:
            self.cfg.save_user_config()
            return True
        except Exception as e:
            logging.error(f"Failed to save configuration: {e}", exc_info=True)
            return False

    def show_config(self, filter_key: Optional[str] = None):
        config_to_display = self.cfg._get_user_savable_config()
        print("\n=== Current Configuration ===")
        for key, value in sorted(config_to_display.items()):
            if filter_key and filter_key.lower() not in key.lower():
                continue
            print(f"  {key}: {value}")
        print("============================")

    def set_config_value(self, key: str, value_str: str) -> bool:
        logging.debug(f"Attempting to set config: {key} = '{value_str}'")
        try:
            # Try smarter parsing for complex types to improve CLI/UI parity
            parsed_value: Any = value_str
            type_hints = get_type_hints(Config)
            target_hint = type_hints.get(key)
            origin_type = (
                getattr(target_hint, "__origin__", None) if target_hint else None
            )

            # If value looks like JSON or target expects list/dict, attempt JSON parse
            looks_like_json = value_str.strip().startswith(("[", "{", '"'))
            if looks_like_json or origin_type in (list, dict):
                try:
                    parsed_value = json.loads(value_str)
                    logging.debug(f"Parsed JSON for {key}: type={type(parsed_value)}")
                except Exception:
                    # Fall back to raw string if JSON parsing fails
                    parsed_value = value_str

            self.cfg.update_setting_and_save(key, parsed_value)
            return True
        except Exception as e:
            logging.error(f"Failed to set config for {key}: {e}", exc_info=True)
            return False

    def scan_apps(self, force_rescan: bool = False) -> bool:
        if (
            not force_rescan
            and self.cfg.CURRENT_HEALTH_APP_LIST_FILE
            and os.path.exists(self.cfg.CURRENT_HEALTH_APP_LIST_FILE)
        ):
            logging.debug(
                f"Using cached health app list: {self.cfg.CURRENT_HEALTH_APP_LIST_FILE}"
            )
            return self._load_health_apps_from_file(
                self.cfg.CURRENT_HEALTH_APP_LIST_FILE
            )

        if not os.path.exists(self.find_app_info_script_path):
            logging.error(
                f"find_app_info.py script not found at {self.find_app_info_script_path}"
            )
            return False
        logging.debug("Starting health app scan...")
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-u",
                    self.find_app_info_script_path,
                    "--mode",
                    "discover",
                ],
                cwd=self.api_dir,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if result.returncode != 0:
                logging.error(f"App scan script failed. Stderr: {result.stderr}")
                return False
            cache_file_line = next(
                (
                    line
                    for line in result.stdout.splitlines()
                    if "Cache file generated at:" in line
                ),
                None,
            )
            if not cache_file_line:
                logging.error("Could not find cache file path in scan output.")
                return False
            cache_file_path = cache_file_line.split("Cache file generated at:", 1)[
                1
            ].strip()
            resolved_cache_path = (
                Path(self.api_dir) / cache_file_path
                if not Path(cache_file_path).is_absolute()
                else Path(cache_file_path)
            )
            if not resolved_cache_path.exists():
                logging.error(
                    f"Cache file reported by script not found: {resolved_cache_path}"
                )
                return False
            self.cfg.update_setting_and_save(
                "CURRENT_HEALTH_APP_LIST_FILE", str(resolved_cache_path)
            )
            return self._load_health_apps_from_file(str(resolved_cache_path))
        except Exception as e:
            logging.error(f"Error during app scan: {e}", exc_info=True)
            return False

    def scan_all_apps(self, force_rescan: bool = False) -> bool:
        """Deterministically scan and cache ALL apps (no AI filtering)."""
        logging.debug("Starting ALL apps scan (no AI filter)...")
        try:
            import find_app_info as fai
        except Exception as e:
            logging.error(f"Failed to import find_app_info for all-apps scan: {e}")
            return False
        try:
            output_path, result_data = fai.generate_app_info_cache(
                perform_ai_filtering_on_this_call=False
            )
            if not output_path:
                logging.error("All-apps scan did not produce a cache file.")
                return False
            logging.info(f"Cache file generated at: {output_path}")
            return self._load_health_apps_from_file(str(output_path))
        except Exception as e:
            logging.error(f"Error during all-apps scan: {e}", exc_info=True)
            return False

    def scan_health_apps(self, force_rescan: bool = False) -> bool:
        """Deterministically scan and cache AI-filtered health apps."""
        logging.debug("Starting HEALTH apps scan (AI filter)...")
        try:
            import find_app_info as fai
        except Exception as e:
            logging.error(f"Failed to import find_app_info for health-apps scan: {e}")
            return False
        try:
            output_path, result_data = fai.generate_app_info_cache(
                perform_ai_filtering_on_this_call=True
            )
            if not output_path:
                logging.error("Health-apps scan did not produce a cache file.")
                return False
            logging.info(f"Cache file generated at: {output_path}")
            self.cfg.update_setting_and_save(
                "CURRENT_HEALTH_APP_LIST_FILE", str(output_path)
            )
            return self._load_health_apps_from_file(str(output_path))
        except Exception as e:
            logging.error(f"Error during health-apps scan: {e}", exc_info=True)
            return False

    def _load_health_apps_from_file(self, file_path: str) -> bool:
        logging.debug(f"Loading health apps from: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Unified schema: require 'health_apps'; accept raw list format if provided
            if isinstance(data, dict):
                if isinstance(data.get("health_apps"), list):
                    self.health_apps_data = data.get("health_apps", [])
                else:
                    self.health_apps_data = []
            elif isinstance(data, list):
                # Raw list format
                self.health_apps_data = data
            else:
                self.health_apps_data = []
            logging.debug(
                f"Loaded {len(self.health_apps_data)} health apps from {file_path}"
            )
            return True
        except Exception as e:
            logging.error(
                f"Error loading health apps from {file_path}: {e}", exc_info=True
            )
            self.health_apps_data = []
            return False

    def _resolve_latest_cache_file_by_suffix(self, suffix: str) -> Optional[str]:
        """Find the most recent device-specific app info cache for the given suffix ('all' or 'health_filtered')."""
        try:
            out_dir = getattr(self.cfg, "APP_INFO_OUTPUT_DIR", None) or os.path.join(
                self.api_dir, "app_info"
            )
            if suffix == "all":
                pattern = os.path.join(out_dir, "device_*_all_apps.json")
            elif suffix == "health_filtered":
                pattern = os.path.join(out_dir, "device_*_filtered_health_apps.json")
            else:
                logging.debug(f"Unsupported suffix '{suffix}' for cache resolution")
                return None
            candidates = glob.glob(pattern)
            if not candidates:
                logging.debug(f"No cache files found for pattern: {pattern}")
                return None
            latest = max(candidates, key=lambda p: os.path.getmtime(p))
            logging.debug(f"Resolved latest cache file for '{suffix}': {latest}")
            return latest
        except Exception as e:
            logging.error(
                f"Failed to resolve latest cache file for '{suffix}': {e}",
                exc_info=True,
            )
            return None

    def list_apps(self):
        # Backward-compatible alias to list health apps (command retained, output unified)
        self.list_health_apps()

    def list_health_apps(self):
        # Try using the configured path first; otherwise resolve latest health_filtered cache
        source_path = None
        if self.cfg.CURRENT_HEALTH_APP_LIST_FILE and os.path.exists(
            self.cfg.CURRENT_HEALTH_APP_LIST_FILE
        ):
            source_path = self.cfg.CURRENT_HEALTH_APP_LIST_FILE
        else:
            source_path = self._resolve_latest_cache_file_by_suffix("health_filtered")

        if not source_path or not self._load_health_apps_from_file(source_path):
            logging.debug("No health apps loaded. Run 'scan-health-apps'.")
            return
        print(f"\n=== Available Health Apps ({len(self.health_apps_data)}) ===")
        for i, app in enumerate(self.health_apps_data):
            print(
                f"{i+1:2d}. App: {app.get('app_name', 'N/A')}\n     Pkg: {app.get('package_name', 'N/A')}\n     Act: {app.get('activity_name', 'N/A')}\n"
            )
        print("===================================")

    def list_all_apps(self):
        source_path = self._resolve_latest_cache_file_by_suffix("all")
        if not source_path or not self._load_health_apps_from_file(source_path):
            logging.debug("No all-apps cache loaded. Run 'scan-all-apps'.")
            return
        print(f"\n=== Available Apps (All) ({len(self.health_apps_data)}) ===")
        for i, app in enumerate(self.health_apps_data):
            print(
                f"{i+1:2d}. App: {app.get('app_name', 'N/A')}\n     Pkg: {app.get('package_name', 'N/A')}\n     Act: {app.get('activity_name', 'N/A')}\n"
            )
        print("===================================")

    def select_app(self, app_identifier: str) -> bool:
        if not self.health_apps_data:
            logging.error("No health apps loaded. Run 'scan-apps'.")
            return False
        selected_app = None
        try:
            index = int(app_identifier) - 1
            if 0 <= index < len(self.health_apps_data):
                selected_app = self.health_apps_data[index]
        except ValueError:
            app_identifier_lower = app_identifier.lower()
            for app in self.health_apps_data:
                if (
                    app_identifier_lower in app.get("app_name", "").lower()
                    or app_identifier_lower == app.get("package_name", "").lower()
                ):
                    selected_app = app
                    break
        if not selected_app:
            logging.error(f"App '{app_identifier}' not found.")
            return False
        pkg, act, name = (
            selected_app.get("package_name"),
            selected_app.get("activity_name"),
            selected_app.get("app_name", "Unknown"),
        )
        if not pkg or not act:
            logging.error(f"Selected app '{name}' missing package/activity.")
            return False
        self.cfg.update_setting_and_save("APP_PACKAGE", pkg)
        self.cfg.update_setting_and_save("APP_ACTIVITY", act)
        self.cfg.update_setting_and_save(
            "LAST_SELECTED_APP",
            {"package_name": pkg, "activity_name": act, "app_name": name},
        )
        
        # Display confirmation of selection
        print(f"\n✅ Successfully selected app:")
        print(f"   App Name:    {name}")
        print(f"   Package:     {pkg}")
        print(f"   Activity:    {act}")
        print(f"   Use 'python run_cli.py --show-selected-app' to view this information again.")
        
        return True

    def show_selected_app(self):
        """Display the currently selected app information."""
        print("\n=== Currently Selected App ===")
        
        # Try to get app info from LAST_SELECTED_APP first
        selected_app = self.cfg.LAST_SELECTED_APP
        
        if selected_app:
            app_name = selected_app.get("app_name", "Unknown")
            package_name = selected_app.get("package_name", "Unknown")
            activity_name = selected_app.get("activity_name", "Unknown")
        else:
            # Fallback to individual config values
            app_name = "Unknown"
            package_name = self.cfg.APP_PACKAGE or "Not Set"
            activity_name = self.cfg.APP_ACTIVITY or "Not Set"
        
        print(f"  App Name:    {app_name}")
        print(f"  Package:     {package_name}")
        print(f"  Activity:    {activity_name}")
        
        if package_name == "Not Set" and activity_name == "Not Set":
            print("\n  No app is currently selected.")
            print("  Use 'python run_cli.py --list-health-apps' to see available apps")
            print("  and 'python run_cli.py --select-app <index>' to select one.")
        
        print("==============================")

    def pause_crawler(self) -> bool:
        logging.debug("Signaling crawler to pause...")
        if not self.cfg.PAUSE_FLAG_PATH:
            logging.error("PAUSE_FLAG_PATH not configured.")
            return False
        try:
            Path(self.cfg.PAUSE_FLAG_PATH).write_text("pause")
            logging.debug(f"Pause flag created: {self.cfg.PAUSE_FLAG_PATH}.")
            return True
        except Exception as e:
            logging.error(f"Failed to create pause flag: {e}", exc_info=True)
            return False

    def resume_crawler(self) -> bool:
        logging.debug("Signaling crawler to resume...")
        if not self.cfg.PAUSE_FLAG_PATH:
            logging.error("PAUSE_FLAG_PATH not configured.")
            return False
        try:
            if Path(self.cfg.PAUSE_FLAG_PATH).exists():
                Path(self.cfg.PAUSE_FLAG_PATH).unlink()
                logging.debug(f"Pause flag removed: {self.cfg.PAUSE_FLAG_PATH}.")
            else:
                logging.debug("Pause flag not found, crawler is likely not paused.")
            return True
        except Exception as e:
            logging.error(f"Failed to remove pause flag: {e}", exc_info=True)
            return False

    def start_crawler(self) -> bool:
        if not self.cfg.SHUTDOWN_FLAG_PATH:
            logging.error("Shutdown flag path not configured.")
            return False
        if Path(self.cfg.SHUTDOWN_FLAG_PATH).exists():
            logging.warning(
                f"Removing existing shutdown flag: {self.cfg.SHUTDOWN_FLAG_PATH}"
            )
            try:
                Path(self.cfg.SHUTDOWN_FLAG_PATH).unlink()
            except OSError as e:
                logging.error(f"Could not remove flag: {e}")
                return False

        main_script = Path(self.api_dir) / "main.py"
        if Path(self.pid_file_path).exists():
            try:
                pid = int(Path(self.pid_file_path).read_text().strip())
                if self._is_process_running(pid):
                    logging.warning(f"Crawler already running (PID {pid}).")
                    return False
                Path(self.pid_file_path).unlink()
            except (ValueError, OSError) as e:
                logging.warning(f"Error with PID file: {e}")

        if self.crawler_process and self.crawler_process.poll() is None:
            logging.warning(
                f"CLI-managed crawler (PID {self.crawler_process.pid}) already running."
            )
            return False
        if not self.cfg.APP_PACKAGE or not self.cfg.APP_ACTIVITY:
            logging.error("APP_PACKAGE and APP_ACTIVITY must be set.")
            return False

        # Log the selected app and key info before starting
        try:
            selected_name = (
                self.cfg.LAST_SELECTED_APP.get("app_name", self.cfg.APP_PACKAGE)
                if self.cfg.LAST_SELECTED_APP
                else self.cfg.APP_PACKAGE
            )
        except Exception:
            selected_name = self.cfg.APP_PACKAGE
        logging.warning(
            f"Selected app: '{selected_name}' ({self.cfg.APP_PACKAGE or 'Not Set'})"
        )
        logging.warning(
            f"App info: package='{self.cfg.APP_PACKAGE or 'Not Set'}', activity='{self.cfg.APP_ACTIVITY or 'Not Set'}'"
        )

        logging.debug("Starting crawler process...")
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = (
                str(_project_root) + os.pathsep + env.get("PYTHONPATH", "")
            )
            self.crawler_process = subprocess.Popen(
                [sys.executable, "-u", str(main_script)],
                cwd=str(_project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            Path(self.pid_file_path).write_text(str(self.crawler_process.pid))
            logging.debug(
                f"Crawler started (PID {self.crawler_process.pid}). PID written to {self.pid_file_path}."
            )
            threading.Thread(target=self._monitor_crawler_output, daemon=True).start()
            return True
        except Exception as e:
            logging.error(f"Failed to start crawler: {e}", exc_info=True)
            return False

    # === Service Pre-checks (parity with UI "Pre-Check Services") ===
    def _check_appium_server(self) -> bool:
        try:
            appium_url = getattr(self.cfg, "APPIUM_SERVER_URL", "http://127.0.0.1:4723")
            response = requests.get(f"{appium_url}/status", timeout=3)
            if response.status_code == 200:
                status_data = response.json()
                return bool(
                    status_data.get("ready", False)
                    or status_data.get("value", {}).get("ready", False)
                )
        except Exception as e:
            logging.debug(f"Appium server check failed: {e}")
        return False

    def _check_mobsf_server(self) -> bool:
        try:
            mobsf_url = getattr(
                self.cfg, "MOBSF_API_URL", "http://localhost:8000/api/v1"
            )
            response = requests.get(f"{mobsf_url}/server_status", timeout=3)
            return response.status_code == 200
        except Exception as e:
            logging.debug(f"MobSF server check failed: {e}")
            return False

    def _check_ollama_service(self) -> bool:
        ollama_url = getattr(self.cfg, "OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            response = requests.get(f"{ollama_url}/api/tags", timeout=1.5)
            if response.status_code == 200:
                logging.debug("Ollama service detected via HTTP API")
                return True
        except Exception as e:
            logging.debug(f"Ollama HTTP API check failed: {e}")
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=2,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                    if hasattr(subprocess, "CREATE_NO_WINDOW")
                    else 0
                ),
            )
            return result.returncode == 0
        except Exception as e:
            logging.debug(f"Ollama subprocess check failed: {e}")
            return False

    def _check_api_keys_and_env(self) -> Tuple[List[str], List[str]]:
        issues: List[str] = []
        warnings: List[str] = []
        ai_provider = getattr(self.cfg, "AI_PROVIDER", "gemini").lower()
        if ai_provider == "gemini":
            if not getattr(self.cfg, "GEMINI_API_KEY", None):
                issues.append(
                    "❌ Gemini API key is not set (check GEMINI_API_KEY in .env file)"
                )
        elif ai_provider == "openrouter":
            if not getattr(self.cfg, "OPENROUTER_API_KEY", None):
                issues.append(
                    "❌ OpenRouter API key is not set (check OPENROUTER_API_KEY in .env file)"
                )
        elif ai_provider == "ollama":
            if not getattr(self.cfg, "OLLAMA_BASE_URL", None):
                warnings.append(
                    "⚠️ Ollama base URL not set (using default localhost:11434)"
                )

        if getattr(self.cfg, "ENABLE_TRAFFIC_CAPTURE", False):
            if not getattr(self.cfg, "PCAPDROID_API_KEY", None):
                issues.append(
                    "❌ PCAPDroid API key is not set (check PCAPDROID_API_KEY in .env file)"
                )

        if getattr(self.cfg, "ENABLE_MOBSF_ANALYSIS", False):
            if not getattr(self.cfg, "MOBSF_API_KEY", None):
                issues.append(
                    "❌ MobSF API key is not set (check MOBSF_API_KEY in .env file)"
                )
        return issues, warnings

    def precheck_services(self) -> bool:
        print("\n🔍 Pre-Crawl Validation Details:")
        print("=" * 50)
        issues: List[str] = []
        warnings: List[str] = []

        # Appium
        appium_running = self._check_appium_server()
        appium_url = getattr(self.cfg, "APPIUM_SERVER_URL", "http://127.0.0.1:4723")
        print(
            ("✅" if appium_running else "❌")
            + f" Appium server at {appium_url}"
            + (" is running" if appium_running else " is not accessible")
        )
        if not appium_running:
            issues.append("❌ Appium server is not running or not accessible")

        # MobSF (optional)
        mobsf_running = self._check_mobsf_server()
        mobsf_url = getattr(self.cfg, "MOBSF_API_URL", "http://localhost:8000/api/v1")
        print(
            ("✅" if mobsf_running else "⚠️")
            + f" MobSF server at {mobsf_url}"
            + (" is running" if mobsf_running else " is not accessible")
        )

        # Ollama depending on provider
        ai_provider = getattr(self.cfg, "AI_PROVIDER", "gemini").lower()
        if ai_provider == "ollama":
            ollama_running = self._check_ollama_service()
            print(
                ("✅" if ollama_running else "❌")
                + " Ollama service"
                + (" is running" if ollama_running else " is not running")
            )
            if not ollama_running:
                issues.append("❌ Ollama service is not running")

        # API keys and env
        api_issues, api_warnings = self._check_api_keys_and_env()
        for msg in api_issues:
            print(msg)
        for msg in api_warnings:
            print(msg)
        issues.extend(api_issues)
        warnings.extend(api_warnings)

        # Target app
        app_pkg = getattr(self.cfg, "APP_PACKAGE", None)
        print(
            ("✅" if app_pkg else "❌")
            + f" Target app: {app_pkg if app_pkg else 'Not selected'}"
        )
        if not app_pkg:
            issues.append("❌ No target app selected")

        # Summary
        print(
            "\n"
            + (
                "✅ All pre-crawl checks passed!"
                if not issues and not warnings
                else (
                    "⚠️ Pre-crawl validation completed with warnings:"
                    if not issues
                    else "❌ Pre-crawl validation failed:"
                )
            )
        )
        for msg in issues:
            print(f"   {msg}")
        for msg in warnings:
            print(f"   {msg}")
        if issues:
            print(
                "\n⚠️ Some requirements are not met. You can still start the crawler, but it may fail if services are not available."
            )
        return len(issues) == 0

    # === MobSF Parity Commands ===
    def test_mobsf_connection(self) -> bool:
        api_url = getattr(self.cfg, "MOBSF_API_URL", "").strip() or getattr(
            self.cfg, "MOBSF_API_URL", "http://localhost:8000/api/v1"
        )
        api_key = getattr(self.cfg, "MOBSF_API_KEY", "").strip()
        if not getattr(self.cfg, "ENABLE_MOBSF_ANALYSIS", False):
            logging.error(
                "MobSF Analysis is not enabled. Enable via set-config ENABLE_MOBSF_ANALYSIS=true"
            )
            return False
        if not api_url or not api_key:
            logging.error("MobSF API URL and API Key are required.")
            return False
        headers = {"Authorization": api_key}
        test_url = f"{api_url.rstrip('/')}/scans"
        try:
            resp = requests.get(test_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                print("MobSF connection successful!")
                try:
                    print(f"Server response: {resp.json()}")
                except Exception:
                    print(f"Response: {resp.text}")
                print(f"API URL used: {test_url}")
                return True
            else:
                logging.error(
                    f"MobSF connection failed with status code: {resp.status_code}"
                )
                logging.error(f"Response: {resp.text}")
                print(f"API URL used: {test_url}")
                return False
        except requests.RequestException as e:
            logging.error(f"MobSF connection error: {e}")
            print(f"API URL used: {test_url}")
            return False

    def run_mobsf_analysis(self) -> bool:
        try:
            from mobsf_manager import MobSFManager
        except ImportError as e:
            logging.error(f"Failed to import MobSFManager: {e}")
            return False
        if not getattr(self.cfg, "ENABLE_MOBSF_ANALYSIS", False):
            logging.error(
                "MobSF Analysis is not enabled. Enable via set-config ENABLE_MOBSF_ANALYSIS=true"
            )
            return False
        app_package = getattr(self.cfg, "APP_PACKAGE", None)
        if not app_package:
            logging.error(
                "No app selected. Please select an app first (scan-apps, list-apps, --select-app)."
            )
            return False
        api_url = getattr(self.cfg, "MOBSF_API_URL", None)
        api_key = getattr(self.cfg, "MOBSF_API_KEY", None)
        if not api_url or not api_key:
            logging.error("MobSF API URL and API Key are required.")
            return False
        mobsf = MobSFManager(self.cfg)
        print(f"Starting MobSF analysis for package: {app_package}")
        success, result = mobsf.perform_complete_scan(app_package)
        if success:
            print("MobSF analysis completed successfully!")
            print(f"PDF Report: {result.get('pdf_report', 'Not available')}")
            print(f"JSON Report: {result.get('json_report', 'Not available')}")
            security_score = result.get("security_score", {})
            if isinstance(security_score, dict):
                print(f"Security Score: {security_score.get('score', 'Not available')}")
            else:
                print(f"Security Score: {security_score}")
            return True
        else:
            logging.error(
                f"MobSF analysis failed: {result.get('error', 'Unknown error')}"
            )
            return False

    # === Focus Areas Parity Commands ===
    def list_focus_areas(self) -> bool:
        areas = getattr(self.cfg, "FOCUS_AREAS", []) or []
        if not areas:
            print("No focus areas configured.")
            return True
        print("\n=== Focus Areas ===")
        for i, area in enumerate(areas):
            name = area.get("title") or area.get("name") or f"Area {i+1}"
            enabled = area.get("enabled", True)
            priority = area.get("priority", i)
            print(f"{i+1:2d}. {name} | enabled={enabled} | priority={priority}")
        print("===================")
        return True

    def _find_focus_area_index(self, id_or_name: str) -> Optional[int]:
        areas = getattr(self.cfg, "FOCUS_AREAS", []) or []
        try:
            idx = int(id_or_name) - 1
            if 0 <= idx < len(areas):
                return idx
        except ValueError:
            name_lower = id_or_name.strip().lower()
            for i, area in enumerate(areas):
                if name_lower in (
                    str(area.get("title", "")).lower()
                    or str(area.get("name", "")).lower()
                ):
                    return i
        return None

    def set_focus_area_enabled(self, id_or_name: str, enabled: bool) -> bool:
        areas = getattr(self.cfg, "FOCUS_AREAS", []) or []
        idx = self._find_focus_area_index(id_or_name)
        if idx is None:
            logging.error(f"Focus area '{id_or_name}' not found.")
            return False
        areas[idx]["enabled"] = enabled
        try:
            self.cfg.update_setting_and_save("FOCUS_AREAS", areas)
            print(
                f"Focus area '{areas[idx].get('title', areas[idx].get('name', id_or_name))}' set enabled={enabled}"
            )
            return True
        except Exception as e:
            logging.error(f"Failed to update focus areas: {e}")
            return False

    def move_focus_area(self, from_index_str: str, to_index_str: str) -> bool:
        areas = getattr(self.cfg, "FOCUS_AREAS", []) or []
        try:
            from_idx = int(from_index_str) - 1
            to_idx = int(to_index_str) - 1
        except ValueError:
            logging.error("--from-index and --to-index must be integers (1-based)")
            return False
        if not (0 <= from_idx < len(areas)) or not (0 <= to_idx < len(areas)):
            logging.error("Index out of range for focus areas list")
            return False
        item = areas.pop(from_idx)
        areas.insert(to_idx, item)
        try:
            self.cfg.update_setting_and_save("FOCUS_AREAS", areas)
            print(f"Moved focus area to position {to_idx+1}")
            return True
        except Exception as e:
            logging.error(f"Failed to reorder focus areas: {e}")
            return False

    def add_focus_area(self, title: str, description: str = "", priority: int = 999, enabled: bool = True) -> bool:
        """Add a new focus area."""
        areas = getattr(self.cfg, "FOCUS_AREAS", []) or []
        
        # Check for duplicate title
        for area in areas:
            if area.get("title", "").lower() == title.lower():
                print(f"Error: Focus area with title '{title}' already exists.")
                return False
        
        # Create new focus area
        new_area = {
            "title": title,
            "description": description,
            "priority": priority,
            "enabled": enabled
        }
        
        areas.append(new_area)
        try:
            self.cfg.update_setting_and_save("FOCUS_AREAS", areas)
            print(f"✅ Successfully added focus area: {title}")
            return True
        except Exception as e:
            print(f"Error adding focus area: {e}")
            return False

    def edit_focus_area(self, id_or_name: str, title: Optional[str] = None, description: Optional[str] = None, priority: Optional[int] = None, enabled: Optional[bool] = None) -> bool:
        """Edit an existing focus area."""
        areas = getattr(self.cfg, "FOCUS_AREAS", []) or []
        idx = self._find_focus_area_index(id_or_name)
        if idx is None:
            print(f"Error: Focus area '{id_or_name}' not found.")
            return False
        
        area = areas[idx]
        
        # Update fields if provided
        if title is not None:
            area["title"] = title
        if description is not None:
            area["description"] = description
        if priority is not None:
            area["priority"] = priority
        if enabled is not None:
            area["enabled"] = enabled
        
        try:
            self.cfg.update_setting_and_save("FOCUS_AREAS", areas)
            print(f"✅ Successfully updated focus area: {area.get('title', 'Unknown')}")
            return True
        except Exception as e:
            print(f"Error updating focus area: {e}")
            return False

    def remove_focus_area(self, id_or_name: str) -> bool:
        """Remove a focus area."""
        areas = getattr(self.cfg, "FOCUS_AREAS", []) or []
        idx = self._find_focus_area_index(id_or_name)
        if idx is None:
            print(f"Error: Focus area '{id_or_name}' not found.")
            return False
        
        removed_area = areas.pop(idx)
        try:
            self.cfg.update_setting_and_save("FOCUS_AREAS", areas)
            print(f"✅ Successfully removed focus area: {removed_area.get('title', 'Unknown')}")
            return True
        except Exception as e:
            print(f"Error removing focus area: {e}")
            return False

    def import_focus_areas(self, file_path: str) -> bool:
        """Import focus areas from a JSON file."""
        if not os.path.exists(file_path):
            print(f"Error: File '{file_path}' not found.")
            return False
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                imported_areas = json.load(f)
            
            if not isinstance(imported_areas, list):
                print("Error: Import file must contain a JSON array of focus areas.")
                return False
            
            # Validate structure
            for i, area in enumerate(imported_areas):
                if not isinstance(area, dict):
                    print(f"Error: Item {i+1} is not a valid focus area object.")
                    return False
                if "title" not in area:
                    print(f"Error: Item {i+1} missing required 'title' field.")
                    return False
            
            # Get current areas and merge
            current_areas = getattr(self.cfg, "FOCUS_AREAS", []) or []
            
            # Add imported areas with priority adjustment to avoid conflicts
            max_priority = max([area.get("priority", 0) for area in current_areas], default=0)
            for area in imported_areas:
                # Adjust priority to be after existing areas
                area["priority"] = max_priority + area.get("priority", 0)
                # Ensure enabled field exists
                if "enabled" not in area:
                    area["enabled"] = True
            
            merged_areas = current_areas + imported_areas
            
            self.cfg.update_setting_and_save("FOCUS_AREAS", merged_areas)
            print(f"✅ Successfully imported {len(imported_areas)} focus areas from '{file_path}'")
            return True
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON file: {e}")
            return False
        except Exception as e:
            print(f"Error importing focus areas: {e}")
            return False

    def export_focus_areas(self, file_path: str) -> bool:
        """Export focus areas to a JSON file."""
        areas = getattr(self.cfg, "FOCUS_AREAS", []) or []
        
        if not areas:
            print("No focus areas to export.")
            return False
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(areas, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Successfully exported {len(areas)} focus areas to '{file_path}'")
            return True
        except Exception as e:
            print(f"Error exporting focus areas: {e}")
            return False

    def _monitor_crawler_output(self):
        if not self.crawler_process or not self.crawler_process.stdout:
            return
        pid = self.crawler_process.pid
        try:
            for line in iter(self.crawler_process.stdout.readline, ""):
                print(line, end="")
            rc = self.crawler_process.wait()
            logging.debug(f"Crawler (PID {pid}) exited with code {rc}.")
        except Exception as e:
            logging.error(f"Error monitoring crawler (PID {pid}): {e}", exc_info=True)
        finally:
            self._cleanup_pid_file_if_matches(pid)
            if self.crawler_process and self.crawler_process.pid == pid:
                self.crawler_process = None

    def stop_crawler(self) -> bool:
        logging.debug("Signaling crawler to stop...")
        if not self.cfg.SHUTDOWN_FLAG_PATH:
            logging.error("SHUTDOWN_FLAG_PATH not configured.")
            return False

        pid_to_signal = None
        if self.crawler_process and self.crawler_process.poll() is None:
            pid_to_signal = self.crawler_process.pid
        elif Path(self.pid_file_path).exists():
            try:
                pid_from_file = int(Path(self.pid_file_path).read_text().strip())
                if self._is_process_running(pid_from_file):
                    pid_to_signal = pid_from_file
            except (ValueError, OSError):
                pass

        try:
            Path(self.cfg.SHUTDOWN_FLAG_PATH).write_text("stop")
            logging.debug(f"Shutdown flag created: {self.cfg.SHUTDOWN_FLAG_PATH}.")
            if pid_to_signal:
                logging.debug(f"Crawler (PID {pid_to_signal}) should detect flag.")
            else:
                logging.debug(
                    "No active crawler PID identified by CLI. Flag set for any running instance."
                )
            return True
        except Exception as e:
            logging.error(f"Failed to create shutdown flag: {e}", exc_info=True)
            return False

    def _cleanup_pid_file_if_matches(self, pid_to_check: Optional[int]):
        pid_file = Path(self.pid_file_path)
        if pid_file.exists():
            try:
                pid_in_file = int(pid_file.read_text().strip())
                if (
                    pid_to_check is not None
                    and pid_in_file == pid_to_check
                    and not self._is_process_running(pid_in_file)
                ) or (
                    pid_to_check is None and not self._is_process_running(pid_in_file)
                ):
                    pid_file.unlink()
                    logging.debug(
                        f"Removed PID file: {pid_file} (contained PID: {pid_in_file})"
                    )
            except (ValueError, OSError, Exception) as e:
                logging.warning(
                    f"Error during PID file cleanup for {pid_file}: {e}. Removing if invalid."
                )
                try:
                    pid_file.unlink()
                except OSError:
                    pass

    def status(self):
        print("\n=== CLI Crawler Status ===")
        pid_file = Path(self.pid_file_path)
        status_msg = "  Crawler Process: Unknown"
        if self.crawler_process and self.crawler_process.poll() is None:
            status_msg = f"  Crawler Process: Running (PID {self.crawler_process.pid}, CLI-managed)"
        elif pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                if self._is_process_running(pid):
                    status_msg = f"  Crawler Process: Running (PID {pid} from PID file)"
                else:
                    status_msg = (
                        f"  Crawler Process: Stale PID file (PID {pid} not running)"
                    )
            except (ValueError, OSError):
                status_msg = "  Crawler Process: Invalid PID file"
        else:
            status_msg = "  Crawler Process: Stopped (no PID file)"
        print(status_msg)

        if self.cfg.PAUSE_FLAG_PATH and Path(self.cfg.PAUSE_FLAG_PATH).exists():
            print("  Execution State: Paused (pause flag is present)")
        else:
            print("  Execution State: Running")

        print(
            f"  Target App:      '{self.cfg.LAST_SELECTED_APP.get('app_name', self.cfg.APP_PACKAGE) if self.cfg.LAST_SELECTED_APP else self.cfg.APP_PACKAGE}' ({self.cfg.APP_PACKAGE or 'Not Set'})"
        )
        print(f"  Output Data Dir: {self.cfg.OUTPUT_DATA_DIR or 'Not Set'}")
        print("========================")

    def _ensure_analysis_targets_discovered(self, quiet: bool = False) -> bool:
        if not self.discovered_analysis_targets:
            if not quiet:
                logging.debug(
                    "Analysis targets not yet discovered in this session. Running discovery..."
                )
            if not self._discover_analysis_targets_internal(quiet_discovery=quiet):
                if not quiet:
                    logging.error("Failed to discover analysis targets.")
                return False
        return True

    def _discover_analysis_targets_internal(self, quiet_discovery: bool = True) -> bool:
        if not self.cfg.OUTPUT_DATA_DIR:
            if not quiet_discovery:
                logging.error("OUTPUT_DATA_DIR is not configured.")
            return False

        db_output_root = Path(self.cfg.OUTPUT_DATA_DIR)
        if not db_output_root.is_dir():
            if not quiet_discovery:
                logging.error(f"Output directory not found: {db_output_root}")
            return False

        self.discovered_analysis_targets = []
        target_idx = 1

        # Look for database files in session directories
        for session_dir in db_output_root.iterdir():
            if (
                session_dir.is_dir() and "_" in session_dir.name
            ):  # Session dirs have format device_package_timestamp
                db_dir = session_dir / "database"
                if db_dir.exists():
                    for db_file in db_dir.glob("*_crawl_data.db"):
                        # Extract app package from session directory name
                        session_parts = session_dir.name.split("_")
                        if len(session_parts) >= 2:
                            app_package_name = session_parts[
                                1
                            ]  # Second part is the app package

                            self.discovered_analysis_targets.append(
                                {
                                    "index": target_idx,
                                    "app_package": app_package_name,
                                    "db_path": str(db_file.resolve()),
                                    "db_filename": db_file.name,
                                    "session_dir": str(session_dir),
                                }
                            )
                            target_idx += 1
        return True

    def list_analysis_targets(self) -> bool:
        if not self._discover_analysis_targets_internal(quiet_discovery=True):
            print(
                "Error: Could not discover analysis targets. Check OUTPUT_DATA_DIR and database_output structure."
            )
            return False

        if not self.cfg.OUTPUT_DATA_DIR:
            print("Error: OUTPUT_DATA_DIR is not set in the configuration.")
            return False
        db_output_root = Path(self.cfg.OUTPUT_DATA_DIR)

        print(f"\nAvailable analysis targets in {db_output_root}:")
        if not self.discovered_analysis_targets:
            print("No app packages with database files found.")
        else:
            for target in self.discovered_analysis_targets:
                session_info = target.get("session_dir", "Unknown session")
                print(
                    f"{target['index']}. App Package: {target['app_package']}, DB File: {target['db_filename']} (Session: {Path(session_info).name})"
                )
            print(
                f"\nUse '--list-runs-for-target --target-index <NUMBER>' or '--list-runs-for-target --target-app-package <PKG_NAME>' to see runs."
            )
            print(
                f"Use '--generate-analysis-pdf --target-index <NUMBER> OR --target-app-package <PKG_NAME> [--pdf-output-name <name.pdf>]' to create PDF for the (latest) run."
            )
        return True

    def list_runs_for_target(self, target_identifier: str, is_index: bool) -> bool:
        if not self._ensure_analysis_targets_discovered(quiet=True):
            print("Error: Could not ensure analysis targets were discovered. Aborting.")
            return False

        selected_target: Optional[Dict[str, Any]] = None
        if is_index:
            try:
                target_index_val = int(target_identifier)
                selected_target = next(
                    (
                        t
                        for t in self.discovered_analysis_targets
                        if t["index"] == target_index_val
                    ),
                    None,
                )
            except ValueError:
                logging.error(
                    f"Invalid target index: '{target_identifier}'. Must be a number."
                )
                print(
                    f"Error: Invalid target index '{target_identifier}'. Please provide a number from the list."
                )
                return False
            if not selected_target:
                logging.error(
                    f"Target index {target_identifier} not found in the discovered list."
                )
                print(
                    f"Error: Target index {target_identifier} not found. Run '--list-analysis-targets' to see available targets."
                )
                return False
        else:  # Identifier is an app package name
            selected_target = next(
                (
                    t
                    for t in self.discovered_analysis_targets
                    if t["app_package"] == target_identifier
                ),
                None,
            )
            if not selected_target:
                logging.error(
                    f"Target app package '{target_identifier}' not found in the discovered list."
                )
                print(
                    f"Error: Target app package '{target_identifier}' not found. Run '--list-analysis-targets' to see available targets."
                )
                return False

        if RunAnalyzer is None:
            logging.error("RunAnalyzer module not available.")
            return False
        if self.cfg.OUTPUT_DATA_DIR is None:
            logging.error("OUTPUT_DATA_DIR is not configured.")
            return False

        print(
            f"\n--- Runs for Target {selected_target['index']}: {selected_target['app_package']} (DB: {selected_target['db_filename']}) ---"
        )
        try:
            analyzer = RunAnalyzer(
                db_path=selected_target["db_path"],
                output_data_dir=self.cfg.OUTPUT_DATA_DIR,
                app_package_for_run=selected_target["app_package"],
            )
            analyzer.list_runs()
            return True
        except FileNotFoundError:
            logging.error(
                f"Database file not found for target {selected_target['app_package']}: {selected_target['db_path']}"
            )
            print(f"Error: Database file not found: {selected_target['db_path']}")
            return False
        except Exception as e:
            logging.error(
                f"Error listing runs for target {selected_target['app_package']}: {e}",
                exc_info=True,
            )
            print(f"Error listing runs: {e}")
            return False

    def generate_analysis_pdf_for_target(
        self,
        target_identifier: str,
        is_index: bool,
        pdf_output_name: Optional[str] = None,
    ) -> bool:
        # Removed run_id_str from parameters
        if not self._ensure_analysis_targets_discovered(quiet=True):
            print(
                "Error: Could not ensure analysis targets were discovered. Aborting PDF generation."
            )
            return False

        if not RunAnalyzer or not XHTML2PDF_AVAILABLE:
            logging.error("RunAnalyzer or PDF library (xhtml2pdf) not available.")
            print(
                "Error: Analysis module or PDF library not available. PDF generation aborted."
            )
            return False
        if self.cfg.OUTPUT_DATA_DIR is None:
            logging.error("OUTPUT_DATA_DIR is not configured.")
            return False

        selected_target: Optional[Dict[str, Any]] = None
        if is_index:
            try:
                target_index_val = int(target_identifier)
                selected_target = next(
                    (
                        t
                        for t in self.discovered_analysis_targets
                        if t["index"] == target_index_val
                    ),
                    None,
                )
            except ValueError:
                logging.error(
                    f"Invalid target index: '{target_identifier}'. Must be a number."
                )
                print(f"Error: Invalid target index '{target_identifier}'.")
                return False
            if not selected_target:
                logging.error(f"Target index {target_identifier} not found.")
                print(f"Error: Target index {target_identifier} not found.")
                return False
        else:  # Identifier is an app package name
            selected_target = next(
                (
                    t
                    for t in self.discovered_analysis_targets
                    if t["app_package"] == target_identifier
                ),
                None,
            )
            if not selected_target:
                logging.error(f"Target app package '{target_identifier}' not found.")
                print(f"Error: Target app package '{target_identifier}' not found.")
                return False

        # Automatically determine the run_id (e.g., latest or only one)
        actual_run_id: Optional[int] = None
        try:
            conn_temp = sqlite3.connect(selected_target["db_path"])
            cursor_temp = conn_temp.cursor()
            # Attempt to get the highest run_id (latest)
            cursor_temp.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1")
            latest_run_row = cursor_temp.fetchone()
            if latest_run_row and latest_run_row[0] is not None:
                actual_run_id = latest_run_row[0]
                logging.debug(
                    f"Using Run ID: {actual_run_id} (latest/only) for target {selected_target['app_package']}."
                )
            else:  # Fallback if no runs or if query fails to return a run_id
                # If there are runs but ORDER BY DESC LIMIT 1 fails, try to get any run_id
                cursor_temp.execute("SELECT run_id FROM runs LIMIT 1")
                any_run_row = cursor_temp.fetchone()
                if any_run_row and any_run_row[0] is not None:
                    actual_run_id = any_run_row[0]
                    logging.warning(
                        f"Could not determine latest run, using first available Run ID: {actual_run_id} for target {selected_target['app_package']}."
                    )
                else:
                    logging.error(
                        f"No runs found in the database for target {selected_target['app_package']}. Cannot determine a run ID."
                    )
                    print(
                        f"Error: No runs found for {selected_target['app_package']}. Cannot generate PDF."
                    )
                    conn_temp.close()
                    return False
            conn_temp.close()
        except sqlite3.Error as e:
            logging.error(
                f"Database error determining run ID for {selected_target['app_package']}: {e}"
            )
            print(
                f"Error: Database error determining run ID for {selected_target['app_package']}."
            )
            return False

        if actual_run_id is None:  # Should be caught by logic above, but as a safeguard
            logging.error(
                f"Failed to determine a run_id for PDF generation for target {selected_target['app_package']}."
            )
            return False

        analysis_reports_dir = Path(selected_target["session_dir"]) / "reports"
        analysis_reports_dir.mkdir(parents=True, exist_ok=True)

        pdf_filename_suffix = (
            Path(pdf_output_name).name if pdf_output_name else "analysis.pdf"
        )
        # Use the determined actual_run_id in the filename
        final_pdf_filename = f"{selected_target['app_package']}_{pdf_filename_suffix}"
        final_pdf_path = str(analysis_reports_dir / final_pdf_filename)

        logging.debug(
            f"Generating PDF for Target: {selected_target['app_package']}, Run ID: {actual_run_id}, Output: {final_pdf_path}"
        )
        try:
            analyzer = RunAnalyzer(
                db_path=selected_target["db_path"],
                output_data_dir=self.cfg.OUTPUT_DATA_DIR,
                app_package_for_run=selected_target["app_package"],
            )
            analyzer.analyze_run_to_pdf(actual_run_id, final_pdf_path)
            return True
        except FileNotFoundError:
            logging.error(
                f"Database file not found for PDF generation: {selected_target['db_path']}"
            )
            print(f"Error: Database file not found: {selected_target['db_path']}")
            return False
        except Exception as e:
            logging.error(
                f"Error generating PDF for target {selected_target['app_package']}, run {actual_run_id}: {e}",
                exc_info=True,
            )
            print(f"Error generating PDF: {e}")
            return False

    def print_analysis_summary_for_target(
        self, target_identifier: str, is_index: bool
    ) -> bool:
        """Select target and print summary metrics for its latest/only run."""
        if not self._ensure_analysis_targets_discovered(quiet=True):
            print(
                "Error: Could not ensure analysis targets were discovered. Aborting summary printing."
            )
            return False

        if RunAnalyzer is None:
            logging.error("RunAnalyzer module not available.")
            print("Error: Analysis module not available.")
            return False
        if self.cfg.OUTPUT_DATA_DIR is None:
            logging.error("OUTPUT_DATA_DIR is not configured.")
            print("Error: OUTPUT_DATA_DIR is not configured.")
            return False

        selected_target: Optional[Dict[str, Any]] = None
        if is_index:
            try:
                target_index_val = int(target_identifier)
                selected_target = next(
                    (
                        t
                        for t in self.discovered_analysis_targets
                        if t["index"] == target_index_val
                    ),
                    None,
                )
            except ValueError:
                logging.error(
                    f"Invalid target index: '{target_identifier}'. Must be a number."
                )
                print(f"Error: Invalid target index '{target_identifier}'.")
                return False
            if not selected_target:
                logging.error(f"Target index {target_identifier} not found.")
                print(
                    f"Error: Target index {target_identifier} not found. Run '--list-analysis-targets' to see available targets."
                )
                return False
        else:
            selected_target = next(
                (
                    t
                    for t in self.discovered_analysis_targets
                    if t["app_package"] == target_identifier
                ),
                None,
            )
            if not selected_target:
                logging.error(f"Target app package '{target_identifier}' not found.")
                print(
                    f"Error: Target app package '{target_identifier}' not found. Run '--list-analysis-targets' to see available targets."
                )
                return False

        # Determine latest/only run_id
        actual_run_id: Optional[int] = None
        try:
            conn_temp = sqlite3.connect(selected_target["db_path"])
            cursor_temp = conn_temp.cursor()
            cursor_temp.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1")
            latest_run_row = cursor_temp.fetchone()
            if latest_run_row and latest_run_row[0] is not None:
                actual_run_id = latest_run_row[0]
            else:
                cursor_temp.execute("SELECT run_id FROM runs LIMIT 1")
                any_run_row = cursor_temp.fetchone()
                if any_run_row and any_run_row[0] is not None:
                    actual_run_id = any_run_row[0]
                else:
                    logging.error(
                        f"No runs found in the database for target {selected_target['app_package']}. Cannot determine a run ID."
                    )
                    print(f"Error: No runs found for {selected_target['app_package']}.")
                    conn_temp.close()
                    return False
            conn_temp.close()
        except sqlite3.Error as e:
            logging.error(
                f"Database error determining run ID for {selected_target['app_package']}: {e}"
            )
            print(
                f"Error: Database error determining run ID for {selected_target['app_package']}."
            )
            return False

        if actual_run_id is None:
            logging.error(
                f"Failed to determine a run_id for summary printing for target {selected_target['app_package']}."
            )
            return False

        try:
            analyzer = RunAnalyzer(
                db_path=selected_target["db_path"],
                output_data_dir=self.cfg.OUTPUT_DATA_DIR,
                app_package_for_run=selected_target["app_package"],
            )
            analyzer.print_run_summary(actual_run_id)
            return True
        except FileNotFoundError:
            logging.error(
                f"Database file not found for summary printing: {selected_target['db_path']}"
            )
            print(f"Error: Database file not found: {selected_target['db_path']}")
            return False
        except Exception as e:
            logging.error(
                f"Error printing summary for target {selected_target['app_package']}, run {actual_run_id}: {e}",
                exc_info=True,
            )
            print(f"Error printing summary: {e}")
            return False

    # === Device Management ===
    def list_devices(self) -> bool:
        """List all connected ADB devices."""
        try:
            result = subprocess.run(
                ["adb", "devices"], capture_output=True, text=True, check=True
            )
            devices = []
            for line in result.stdout.strip().split("\n")[1:]:
                if "\tdevice" in line:
                    devices.append(line.split("\t")[0])
            
            if not devices:
                print("No connected devices found.")
                return True
                
            print("\n=== Connected Devices ===")
            for i, device in enumerate(devices):
                print(f"{i+1}. {device}")
            print("==========================")
            return True
        except FileNotFoundError:
            print("ERROR: 'adb' command not found. Is Android SDK platform-tools in your PATH?")
            return False
        except Exception as e:
            print(f"Error getting connected devices: {e}")
            return False

    def select_device(self, device_udid: str, force: bool = False) -> bool:
        """Select a device by UDID and save it to configuration."""
        # First verify the device exists
        try:
            result = subprocess.run(
                ["adb", "devices"], capture_output=True, text=True, check=True
            )
            devices = []
            for line in result.stdout.strip().split("\n")[1:]:
                if "\tdevice" in line:
                    devices.append(line.split("\t")[0])
            
            if device_udid not in devices:
                print(f"Device '{device_udid}' not found in connected devices.")
                return False
        except FileNotFoundError:
            print("ERROR: 'adb' command not found. Is Android SDK platform-tools in your PATH?")
            return False
        except Exception as e:
            print(f"Error verifying device: {e}")
            return False
        
        # Save to configuration
        try:
            self.cfg.update_setting_and_save("DEVICE_UDID", device_udid)
            print(f"✅ Successfully selected device: {device_udid}")
            return True
        except Exception as e:
            print(f"Error saving device selection: {e}")
            return False

    def auto_select_device(self) -> bool:
        """Automatically select the first available device."""
        try:
            result = subprocess.run(
                ["adb", "devices"], capture_output=True, text=True, check=True
            )
            devices = []
            for line in result.stdout.strip().split("\n")[1:]:
                if "\tdevice" in line:
                    devices.append(line.split("\t")[0])
            
            if not devices:
                print("No connected devices found.")
                return False
            
            # Select the first device
            first_device = devices[0]
            return self.select_device(first_device)
        except FileNotFoundError:
            print("ERROR: 'adb' command not found. Is Android SDK platform-tools in your PATH?")
            return False
        except Exception as e:
            print(f"Error auto-selecting device: {e}")
            return False

    # === OpenRouter Model Management ===
    def list_openrouter_models(self, free_only: Optional[bool] = None) -> bool:
        """List available OpenRouter models from the local cache.
        
        Args:
            free_only: If True, only show free models. If False, show all models.
                      If None, use the OPENROUTER_SHOW_FREE_ONLY config setting.
        """
        try:
            from openrouter_models import load_openrouter_models_cache, is_openrouter_model_free
        except ImportError:
            from .openrouter_models import load_openrouter_models_cache, is_openrouter_model_free
        
        models = load_openrouter_models_cache()
        
        if not models:
            print("OpenRouter models cache not found. Run '--refresh-openrouter-models' first.")
            return False
        
        # Determine if we should filter to free-only models
        if free_only is None:
            free_only = getattr(self.cfg, "OPENROUTER_SHOW_FREE_ONLY", False)
        
        # Filter models if free_only is True
        if free_only:
            filtered_models = [m for m in models if is_openrouter_model_free(m)]
            if not filtered_models:
                print("No free models found in cache. Run '--refresh-openrouter-models' to update.")
                return False
            display_models = filtered_models
            filter_msg = " (Free Only)"
        else:
            display_models = models
            filter_msg = ""
        
        print(f"\n=== Available OpenRouter Models{filter_msg} ({len(display_models)}) ===")
        for i, model in enumerate(display_models):
            model_id = model.get("id", "N/A")
            model_name = model.get("name", "N/A")
            context_length = model.get("context_length", "N/A")
            pricing = model.get("pricing", {})
            prompt_price = pricing.get("prompt", "N/A")
            completion_price = pricing.get("completion", "N/A")
            
            # Check if model is free for display
            free_indicator = " [FREE]" if is_openrouter_model_free(model) else ""
            
            print(f"{i+1:2d}. ID: {model_id}{free_indicator}")
            print(f"    Name: {model_name}")
            print(f"    Context: {context_length}")
            print(f"    Pricing: Prompt {prompt_price} | Completion {completion_price}\n")
        print("=====================================")
        print("Use '--select-openrouter-model <index_or_name>' to select a model.")
        if free_only:
            print("Showing free models only. Use '--list-openrouter-models --all' to see all models.")
        return True
    
    def select_openrouter_model(self, model_identifier: str) -> bool:
        """Select an OpenRouter model by index or name/ID fragment."""
        try:
            from openrouter_models import load_openrouter_models_cache, is_openrouter_model_free
        except ImportError:
            from .openrouter_models import load_openrouter_models_cache, is_openrouter_model_free
        
        models = load_openrouter_models_cache()
        
        if not models:
            print("OpenRouter models cache not found. Run '--refresh-openrouter-models' first.")
            return False
        
        try:
            selected_model = None
            
            # Try to find by index first
            try:
                index = int(model_identifier) - 1
                if 0 <= index < len(models):
                    selected_model = models[index]
            except ValueError:
                # Not an index, search by name or ID
                model_identifier_lower = model_identifier.lower()
                for model in models:
                    model_id = model.get("id", "").lower()
                    model_name = model.get("name", "").lower()
                    if model_identifier_lower in model_id or model_identifier_lower in model_name:
                        selected_model = model
                        break
            
            if not selected_model:
                print(f"Model '{model_identifier}' not found.")
                return False
            
            model_id = selected_model.get("id")
            model_name = selected_model.get("name")
            
            # Check if this is a paid model and show warning if needed
            pricing = selected_model.get("pricing", {})
            prompt_price = pricing.get("prompt", "0")
            completion_price = pricing.get("completion", "0")
            
            # Show warning if this is a paid model and warnings are enabled
            show_warning = getattr(self.cfg, "OPENROUTER_NON_FREE_WARNING", False)
            is_free = is_openrouter_model_free(selected_model)
            
            if not is_free and show_warning:
                print("\n⚠️  WARNING: You've selected a PAID model!")
                print(f"   Prompt price: {prompt_price} | Completion price: {completion_price}")
                print("   This model will incur costs for each API call.")
                print("   To disable this warning, set OPENROUTER_NON_FREE_WARNING=false in config.")
                print("   To see only free models, use --list-openrouter-models --free-only")
                print()
            
            # Set AI provider to OpenRouter and update the model
            self.cfg.update_setting_and_save("AI_PROVIDER", "openrouter")
            self.cfg.update_setting_and_save("DEFAULT_MODEL_TYPE", model_id)
            
            print(f"✅ Successfully selected OpenRouter model:")
            print(f"   Model ID: {model_id}")
            print(f"   Model Name: {model_name}")
            print(f"   Pricing: Prompt {prompt_price} | Completion {completion_price}")
            
            if not is_free:
                print(f"   💰 This is a PAID model. Costs will be incurred for usage.")
            else:
                print(f"   🆓 This is a FREE model.")
                 
            print(f"   Use '--show-openrouter-selection' to view this information again.")
            
            return True
        except Exception as e:
            logging.error(f"Failed to select OpenRouter model: {e}", exc_info=True)
            print(f"Error selecting model: {e}")
            return False
    
    def show_selected_openrouter_model(self) -> bool:
        """Show the currently selected OpenRouter model."""
        print("\n=== Currently Selected OpenRouter Model ===")
        
        current_provider = getattr(self.cfg, "AI_PROVIDER", "")
        current_model = getattr(self.cfg, "DEFAULT_MODEL_TYPE", "")
        
        if current_provider.lower() != "openrouter":
            print(f"  Current provider: {current_provider}")
            print("  OpenRouter is not currently selected as the AI provider.")
            print("  Use '--select-openrouter-model <model>' to select an OpenRouter model.")
        else:
            print(f"  Provider: {current_provider}")
            print(f"  Model ID: {current_model}")
            
            # Try to get more details from cache
            try:
                from openrouter_models import get_openrouter_model_meta
            except ImportError:
                from .openrouter_models import get_openrouter_model_meta
            
            model_meta = get_openrouter_model_meta(current_model)
            
            if model_meta:
                model_name = model_meta.get("name", "N/A")
                context_length = model_meta.get("context_length", "N/A")
                pricing = model_meta.get("pricing", {})
                prompt_price = pricing.get("prompt", "N/A")
                completion_price = pricing.get("completion", "N/A")
                
                print(f"  Model Name: {model_name}")
                print(f"  Context Length: {context_length}")
                print(f"  Pricing: Prompt {prompt_price} | Completion {completion_price}")
            else:
                print("  Model details not found in cache. Run '--refresh-openrouter-models' to update.")
        
        print("========================================")
        return True

    def configure_openrouter_image_context(self, model_identifier: Optional[str] = None, enabled: Optional[bool] = None) -> bool:
        """Configure image context settings for OpenRouter models with tri-state handling."""
        current_provider = getattr(self.cfg, "AI_PROVIDER", "").lower()
        if current_provider != "openrouter":
            print("Error: This command is only available when OpenRouter is selected as the AI provider.")
            print("Use '--select-openrouter-model <model>' to select an OpenRouter model first.")
            return False
        
        # Get the current model if none specified
        if not model_identifier:
            model_identifier = getattr(self.cfg, "DEFAULT_MODEL_TYPE", "")
            if not model_identifier or model_identifier == "No model selected":
                print("Error: No OpenRouter model selected. Use '--select-openrouter-model <model>' first.")
                return False
        
        # Get model metadata
        try:
            from openrouter_models import get_openrouter_model_meta, is_openrouter_model_vision
        except ImportError:
            from .openrouter_models import get_openrouter_model_meta, is_openrouter_model_vision
        
        selected_model = get_openrouter_model_meta(model_identifier)
        
        if not selected_model:
            print(f"Error: Model '{model_identifier}' not found in cache.")
            return False
        
        # Check image support
        supports_image = selected_model.get("supports_image")
        model_name = selected_model.get("name", "Unknown")
        
        print(f"\n=== OpenRouter Image Context Configuration ===")
        print(f"Model: {model_name} ({model_identifier})")
        print(f"Image Support: {'Yes' if supports_image else 'No'}")
        
        if supports_image is True:
            # Model supports images - allow user to choose
            if enabled is None:
                current_setting = getattr(self.cfg, "ENABLE_IMAGE_CONTEXT", False)
                print(f"Current image context setting: {'Enabled' if current_setting else 'Disabled'}")
                print("This model supports image inputs.")
                return True
            else:
                self.cfg.update_setting_and_save("ENABLE_IMAGE_CONTEXT", enabled)
                print(f"✅ Image context {'enabled' if enabled else 'disabled'} for model {model_name}")
                return True
        elif supports_image is False:
            # Model doesn't support images - force disable
            if enabled is True:
                print("⚠️ Warning: This model does not support image inputs. Cannot enable image context.")
            self.cfg.update_setting_and_save("ENABLE_IMAGE_CONTEXT", False)
            print("✅ Image context disabled (model does not support images)")
            return True
        else:
            # Unknown capability - use heuristic
            heuristic = is_openrouter_model_vision(model_identifier)
            if heuristic:
                if enabled is None:
                    current_setting = getattr(self.cfg, "ENABLE_IMAGE_CONTEXT", False)
                    print(f"Current image context setting: {'Enabled' if current_setting else 'Disabled'}")
                    print("Model capability unknown; heuristic suggests it supports images.")
                    return True
                else:
                    self.cfg.update_setting_and_save("ENABLE_IMAGE_CONTEXT", enabled)
                    print(f"✅ Image context {'enabled' if enabled else 'disabled'} (heuristic-based)")
                    return True
            else:
                if enabled is True:
                    print("⚠️ Warning: Model capability unknown; heuristic suggests it does not support images.")
                self.cfg.update_setting_and_save("ENABLE_IMAGE_CONTEXT", False)
                print("✅ Image context disabled (heuristic-based)")
                return True

    def show_openrouter_model_details(self, model_identifier: Optional[str] = None) -> bool:
        """Show detailed information about an OpenRouter model including pricing and capabilities."""
        current_provider = getattr(self.cfg, "AI_PROVIDER", "").lower()
        if current_provider != "openrouter":
            print("Error: This command is only available when OpenRouter is selected as the AI provider.")
            return False
        
        # Get the current model if none specified
        if not model_identifier:
            model_identifier = getattr(self.cfg, "DEFAULT_MODEL_TYPE", "")
            if not model_identifier or model_identifier == "No model selected":
                print("Error: No OpenRouter model selected. Use '--select-openrouter-model <model>' first.")
                return False
        
        # Get model metadata
        try:
            from openrouter_models import get_openrouter_model_meta, is_openrouter_model_free
        except ImportError:
            from .openrouter_models import get_openrouter_model_meta, is_openrouter_model_free
        
        selected_model = get_openrouter_model_meta(model_identifier)
        
        if not selected_model:
            print(f"Error: Model '{model_identifier}' not found in cache.")
            return False
        
        # Display detailed information
        print(f"\n=== OpenRouter Model Details ===")
        print(f"ID: {selected_model.get('id', 'N/A')}")
        print(f"Name: {selected_model.get('name', 'N/A')}")
        print(f"Description: {selected_model.get('description', 'N/A')}")
        print(f"Context Length: {selected_model.get('context_length', 'N/A')}")
        
        # Pricing information
        pricing = selected_model.get('pricing', {})
        if pricing:
            print(f"\nPricing:")
            print(f"  Prompt: {pricing.get('prompt', 'N/A')}")
            print(f"  Completion: {pricing.get('completion', 'N/A')}")
            print(f"  Image: {pricing.get('image', 'N/A')}")
            
            # Free status
            is_free = is_openrouter_model_free(selected_model)
            print(f"  Free Model: {'Yes' if is_free else 'No'}")
        else:
            print(f"\nPricing: Not available")
        
        # Capabilities
        architecture = selected_model.get('architecture', {})
        if architecture:
            print(f"\nCapabilities:")
            input_modalities = architecture.get('input_modalities', [])
            output_modalities = architecture.get('output_modalities', [])
            print(f"  Input Modalities: {', '.join(input_modalities) if input_modalities else 'N/A'}")
            print(f"  Output Modalities: {', '.join(output_modalities) if output_modalities else 'N/A'}")
            
            supports_image = selected_model.get('supports_image')
            print(f"  Image Support: {'Yes' if supports_image else 'No'}")
            
            supported_parameters = architecture.get('supported_parameters', [])
            if supported_parameters:
                print(f"  Supported Parameters: {', '.join(supported_parameters)}")
        
        # Provider information
        top_provider = selected_model.get('top_provider', {})
        if top_provider:
            print(f"\nProvider Information:")
            print(f"  Provider Name: {top_provider.get('provider_name', 'N/A')}")
            print(f"  Model Format: {top_provider.get('model_format', 'N/A')}")
        
        # Current configuration
        current_image_context = getattr(self.cfg, "ENABLE_IMAGE_CONTEXT", False)
        print(f"\nCurrent Configuration:")
        print(f"  Image Context: {'Enabled' if current_image_context else 'Disabled'}")
        
        print("=================================")
        return True


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI Controller for Appium Crawler.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
Examples:
 %(prog)s status
 %(prog)s --list-devices
 %(prog)s --select-device emulator-5554
 %(prog)s --auto-select-device
 %(prog)s --scan-health-apps
 %(prog)s --scan-all-apps
 %(prog)s --list-health-apps
 %(prog)s --list-all-apps
 %(prog)s --select-app "Your App Name"  # Or use index: %(prog)s --select-app 1
 %(prog)s --show-selected-app
 %(prog)s show-config
 %(prog)s set-config MAX_CRAWL_STEPS=50
 %(prog)s start
 %(prog)s stop
 %(prog)s pause
 %(prog)s resume
                               
  # New Analysis Commands:
  %(prog)s --list-analysis-targets
  %(prog)s --list-runs-for-target --target-index 1
  %(prog)s --list-runs-for-target --target-app-package com.example.app

  %(prog)s --generate-analysis-pdf --target-index 1
  %(prog)s --generate-analysis-pdf --target-app-package com.example.app
  %(prog)s --generate-analysis-pdf --target-app-package com.example.app --pdf-output-name "custom_report.pdf"
  %(prog)s --print-analysis-summary --target-index 1
  %(prog)s --print-analysis-summary --target-app-package com.example.app

  # Focus Areas Management:
  %(prog)s --list-focus-areas
  %(prog)s --add-focus-area "Privacy Settings" --focus-description "Areas related to privacy" --focus-priority 1
  %(prog)s --edit-focus-area "Privacy Settings" --focus-description "Updated description"
  %(prog)s --remove-focus-area "Privacy Settings"
  %(prog)s --import-focus-areas focus_areas.json
  %(prog)s --export-focus-areas my_focus_areas.json

  # OpenRouter Model Management:
  %(prog)s --refresh-openrouter-models
  %(prog)s --list-openrouter-models
  %(prog)s --select-openrouter-model "gpt-4"  # Or use index: %(prog)s --select-openrouter-model 1
  %(prog)s --show-openrouter-selection
  %(prog)s --show-openrouter-model-details "gpt-4"
  %(prog)s --configure-openrouter-image-context
  %(prog)s --enable-image-context
  %(prog)s --disable-image-context
        """
        ),
    )
    
    device_group = parser.add_argument_group("Device Management")
    device_group.add_argument(
        "--list-devices",
        action="store_true",
        help="List all connected ADB devices.",
    )
    device_group.add_argument(
        "--select-device",
        metavar="UDID",
        help="Select a device by UDID for Appium operations.",
    )
    device_group.add_argument(
        "--auto-select-device",
        action="store_true",
        help="Automatically select the first available device.",
    )
    
    app_group = parser.add_argument_group("App Management")
    app_group.add_argument(
        "--scan-all-apps",
        action="store_true",
        help="Scan device and cache ALL installed apps (deterministic, no AI filtering).",
    )
    app_group.add_argument(
        "--scan-health-apps",
        action="store_true",
        help="Scan device and cache AI-filtered HEALTH apps (deterministic).",
    )
    app_group.add_argument(
        "--list-all-apps",
        action="store_true",
        help="List ALL apps from the latest cache.",
    )
    app_group.add_argument(
        "--list-health-apps",
        action="store_true",
        help="List HEALTH apps from the latest cache.",
    )
    app_group.add_argument(
        "--select-app",
        metavar="ID_OR_NAME",
        help="Select app by name or 1-based index.",
    )
    app_group.add_argument(
        "--show-selected-app",
        action="store_true",
        help="Show the currently selected app information.",
    )

    crawler_group = parser.add_argument_group("Crawler Control")
    crawler_group.add_argument(
        "--start", action="store_true", help="Start the crawler."
    )
    crawler_group.add_argument(
        "--pause",
        action="store_true",
        help="Signal the running crawler to pause execution.",
    )
    crawler_group.add_argument(
        "--resume",
        action="store_true",
        help="Signal a paused crawler to resume execution.",
    )
    crawler_group.add_argument(
        "--stop", action="store_true", help="Signal the crawler to stop."
    )
    crawler_group.add_argument(
        "--status", action="store_true", help="Show crawler status."
    )
    crawler_group.add_argument(
        "--precheck-services",
        action="store_true",
        help="Run pre-crawl validation checks for services and configuration.",
    )
    crawler_group.add_argument(
        "--annotate-offline-after-run",
        action="store_true",
        help="After crawler exits, run offline UI annotator to overlay bounding boxes and generate a gallery.",
    )

    config_group = parser.add_argument_group("Configuration Management")
    config_group.add_argument(
        "--show-config",
        metavar="FILTER",
        nargs="?",
        const="",
        help="Show config (optionally filter by key).",
    )
    config_group.add_argument(
        "--set-config",
        metavar="K=V",
        action="append",
        help="Set config value (e.g., MAX_CRAWL_STEPS=100).",
    )

    analysis_group = parser.add_argument_group("Analysis (New Workflow)")
    analysis_group.add_argument(
        "--list-analysis-targets",
        action="store_true",
        help="List all app packages with database files available for analysis.",
    )
    analysis_group.add_argument(
        "--list-runs-for-target",
        action="store_true",
        help="List runs for a specific analysis target. Requires --target-index OR --target-app-package.",
    )
    analysis_group.add_argument(
        "--generate-analysis-pdf",
        action="store_true",
        help="Generate PDF report for the (latest/only) run of an analysis target. Requires --target-index OR --target-app-package. Optionally takes --pdf-output-name.",
    )
    analysis_group.add_argument(
        "--print-analysis-summary",
        action="store_true",
        help="Compute and print summary metrics for the (latest/only) run of an analysis target. Requires --target-index OR --target-app-package.",
    )

    analysis_target_group = analysis_group.add_mutually_exclusive_group(required=False)
    analysis_target_group.add_argument(
        "--target-index",
        metavar="NUMBER",
        type=str,
        help="Index number of the analysis target (from --list-analysis-targets).",
    )
    analysis_target_group.add_argument(
        "--target-app-package",
        metavar="PKG_NAME",
        type=str,
        help="Full package name of the target application for analysis.",
    )

    # --run-id is removed for generate-analysis-pdf as per user request to simplify
    analysis_group.add_argument(
        "--pdf-output-name",
        metavar="FILENAME.pdf",
        type=str,
        default=None,
        help="Optional: Base filename for the PDF. If not given, a default name is used.",
    )

    mobsf_group = parser.add_argument_group("MobSF Integration")
    mobsf_group.add_argument(
        "--test-mobsf-connection",
        action="store_true",
        help="Test connection to MobSF server using current config (MOBSF_API_URL, MOBSF_API_KEY).",
    )
    mobsf_group.add_argument(
        "--run-mobsf-analysis",
        action="store_true",
        help="Run MobSF analysis for the currently selected app (APP_PACKAGE).",
    )

    focus_group = parser.add_argument_group("Focus Areas")
    focus_group.add_argument(
        "--list-focus-areas",
        action="store_true",
        help="List configured privacy focus areas.",
    )
    focus_group.add_argument(
        "--enable-focus-area",
        metavar="ID_OR_NAME",
        type=str,
        help="Enable a focus area by 1-based index or name substring.",
    )
    focus_group.add_argument(
        "--disable-focus-area",
        metavar="ID_OR_NAME",
        type=str,
        help="Disable a focus area by 1-based index or name substring.",
    )
    focus_group.add_argument(
        "--move-focus-area",
        action="store_true",
        help="Reorder focus areas using --from-index and --to-index (1-based).",
    )
    focus_group.add_argument(
        "--from-index",
        metavar="NUMBER",
        type=str,
        help="Source index for --move-focus-area (1-based).",
    )
    focus_group.add_argument(
        "--to-index",
        metavar="NUMBER",
        type=str,
        help="Target index for --move-focus-area (1-based).",
    )
    focus_group.add_argument(
        "--add-focus-area",
        metavar="TITLE",
        type=str,
        help="Add a new focus area with the given title.",
    )
    focus_group.add_argument(
        "--focus-description",
        metavar="TEXT",
        type=str,
        help="Description for the focus area (used with --add-focus-area or --edit-focus-area).",
    )
    focus_group.add_argument(
        "--focus-priority",
        metavar="NUMBER",
        type=int,
        help="Priority for the focus area (used with --add-focus-area or --edit-focus-area).",
    )
    focus_group.add_argument(
        "--edit-focus-area",
        metavar="ID_OR_NAME",
        type=str,
        help="Edit an existing focus area by index or name.",
    )
    focus_group.add_argument(
        "--remove-focus-area",
        metavar="ID_OR_NAME",
        type=str,
        help="Remove a focus area by index or name.",
    )
    focus_group.add_argument(
        "--import-focus-areas",
        metavar="FILE_PATH",
        type=str,
        help="Import focus areas from a JSON file.",
    )
    focus_group.add_argument(
        "--export-focus-areas",
        metavar="FILE_PATH",
        type=str,
        help="Export focus areas to a JSON file.",
    )

    parser.add_argument("--force-rescan", action="store_true", help="Force app rescan.")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable DEBUG logging."
    )

    # OpenRouter models cache management
    ai_group = parser.add_argument_group("AI Providers")
    ai_group.add_argument(
        "--refresh-openrouter-models",
        action="store_true",
        help=(
            "Fetch latest OpenRouter models and refresh the local cache (background). "
            "Requires OPENROUTER_API_KEY in .env; writes to output_data/cache/openrouter_models.json."
        ),
    )
    ai_group.add_argument(
        "--list-openrouter-models",
        action="store_true",
        help="List available OpenRouter models from the local cache.",
    )
    ai_group.add_argument(
        "--free-only",
        action="store_true",
        help="Show only free models when listing OpenRouter models (overrides OPENROUTER_SHOW_FREE_ONLY config).",
    )
    ai_group.add_argument(
        "--all",
        action="store_true",
        help="Show all models when listing OpenRouter models (overrides OPENROUTER_SHOW_FREE_ONLY config).",
    )
    ai_group.add_argument(
        "--select-openrouter-model",
        metavar="ID_OR_NAME",
        help="Select an OpenRouter model by index or name/ID fragment.",
    )
    ai_group.add_argument(
        "--show-openrouter-selection",
        action="store_true",
        help="Show the currently selected OpenRouter model.",
    )
    ai_group.add_argument(
        "--configure-openrouter-image-context",
        nargs="?",
        const=None,
        metavar="MODEL_ID",
        help="Configure image context settings for OpenRouter models with tri-state handling.",
    )
    ai_group.add_argument(
        "--enable-image-context",
        action="store_true",
        help="Enable image context for the current OpenRouter model.",
    )
    ai_group.add_argument(
        "--disable-image-context",
        action="store_true",
        help="Disable image context for the current OpenRouter model.",
    )
    ai_group.add_argument(
        "--show-openrouter-model-details",
        nargs="?",
        const=None,
        metavar="MODEL_ID",
        help="Show detailed information about an OpenRouter model including pricing and capabilities.",
    )
    return parser


def _find_latest_session_for_app(cfg: Config) -> Optional[Tuple[str, str]]:
    """Find the latest OUTPUT_DATA_DIR session for the configured APP_PACKAGE with an existing DB file."""
    base = getattr(cfg, "OUTPUT_DATA_DIR", None) or "output_data"
    app_pkg = getattr(cfg, "APP_PACKAGE", None)
    if not os.path.isdir(base) or not app_pkg:
        return None
    candidates: List[Tuple[float, str, str]] = []
    try:
        for name in os.listdir(base):
            path = os.path.join(base, name)
            if not os.path.isdir(path):
                continue
            if app_pkg in name:
                db_dir = os.path.join(path, "database")
                if os.path.isdir(db_dir):
                    for f in os.listdir(db_dir):
                        if f.endswith("_crawl_data.db"):
                            db_path = os.path.join(db_dir, f)
                            try:
                                mtime = os.path.getmtime(db_path)
                            except Exception:
                                mtime = 0.0
                            candidates.append((mtime, path, db_path))
    except Exception:
        return None
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, session_dir, db_path = candidates[0]
    return session_dir, db_path


def _run_offline_ui_annotator(session_dir: str, db_path: str) -> bool:
    """Invoke tools/ui_element_annotator.py to perform offline annotation for a completed run."""
    try:
        project_root = str(Path(__file__).resolve().parent.parent)
        script_path = str(Path(project_root) / "tools" / "ui_element_annotator.py")
        screenshots_dir = str(Path(session_dir) / "screenshots")
        out_dir = str(Path(session_dir) / "annotated_screenshots")
        cmd = [
            sys.executable,
            "-u",
            script_path,
            "--db-path",
            db_path,
            "--screens-dir",
            screenshots_dir,
            "--out-dir",
            out_dir,
        ]
        logging.debug(f"Running offline UI annotator: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)
        if result.returncode == 0:
            logging.info("Offline UI annotation completed successfully.")
            logging.debug(result.stdout)
            if result.stderr:
                logging.debug(result.stderr)
            return True
        else:
            logging.error(
                f"Offline UI annotation failed (code {result.returncode}). Output:\n{result.stdout}\n{result.stderr}"
            )
            return False
    except Exception as e:
        logging.error(f"Failed to run offline UI annotator: {e}", exc_info=True)
        return False


def main_cli():
    # Initially set logging to WARNING to suppress verbose initialization messages
    logging.basicConfig(
        level=logging.WARNING,
        format="[%(levelname)s] %(asctime)s %(module)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    parser = create_parser()
    args = parser.parse_args()

    # Now set the actual desired log level based on verbose flag
    log_level = "DEBUG" if args.verbose else "WARNING"
    
    # Re-configure logging with the correct level
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    logging.basicConfig(
        level=log_level,
        format="[%(levelname)s] %(asctime)s %(module)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logging.debug("CLI Bootstrap logging initialized.")

    _cli_script_dir = Path(__file__).resolve().parent
    DEFAULT_CONFIG_MODULE_PATH_CLI = str(_cli_script_dir / "config.py")
    USER_CONFIG_JSON_PATH_CLI = str(_cli_script_dir / "user_config.json")
    try:
        cli_cfg = Config(
            defaults_module_path=DEFAULT_CONFIG_MODULE_PATH_CLI,
            user_config_json_path=USER_CONFIG_JSON_PATH_CLI,
        )
        if not cli_cfg.SHUTDOWN_FLAG_PATH:
            cli_cfg.SHUTDOWN_FLAG_PATH = str(
                Path(cli_cfg.BASE_DIR or _cli_script_dir) / "crawler_shutdown.flag"
            )

        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        logger_manager_cli = LoggerManager()
        log_file_base = Path(cli_cfg.OUTPUT_DATA_DIR or _cli_script_dir)
        log_file_path = log_file_base / "logs" / "cli" / f"cli_{cli_cfg.LOG_FILE_NAME}"
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        logger_manager_cli.setup_logging(
            log_level_str=log_level, log_file=str(log_file_path)
        )
        logging.debug(
            f"CLI Application Logging Initialized. Level: {log_level}. File: '{log_file_path}'"
        )

    except Exception as e:
        logging.critical(f"Failed to initialize Config or Logger: {e}", exc_info=True)
        sys.exit(100)

    controller = CLIController(app_config_instance=cli_cfg)
    action_taken = False
    exit_code = 0

    try:
        # Device Management commands
        if getattr(args, "list_devices", False):
            action_taken = True
            if not controller.list_devices():
                exit_code = 1
        elif args.select_device:
            action_taken = True
            if not controller.select_device(args.select_device):
                exit_code = 1
        elif getattr(args, "auto_select_device", False):
            action_taken = True
            if not controller.auto_select_device():
                exit_code = 1
                
        # New explicit scan commands
        if getattr(args, "scan_all_apps", False):
            action_taken = True
            controller.scan_all_apps(force_rescan=args.force_rescan)
        elif getattr(args, "scan_health_apps", False):
            action_taken = True
            controller.scan_health_apps(force_rescan=args.force_rescan)
        # New explicit list commands
        elif getattr(args, "list_all_apps", False):
            action_taken = True
            controller.list_all_apps()
        elif getattr(args, "list_health_apps", False):
            action_taken = True
            controller.list_health_apps()
        elif args.select_app:
            action_taken = True
            controller.select_app(args.select_app)
        elif getattr(args, "show_selected_app", False):
            action_taken = True
            controller.show_selected_app()
        elif args.show_config is not None:
            action_taken = True
            controller.show_config(args.show_config)
        elif args.set_config:
            action_taken = True
            set_ok = True
            for item in args.set_config:
                if "=" not in item:
                    logging.error(f"Invalid config format: {item}")
                    exit_code = 1
                    set_ok = False
                    break
                key, val = item.split("=", 1)
                if not controller.set_config_value(key, val):
                    exit_code = 1
                    set_ok = False
                    break
            # Automatically persist changes when configuration is successfully updated
            if set_ok:
                if controller.save_all_changes():
                    logging.debug(
                        "Configuration updated via --set-config and saved to user_config.json."
                    )
                else:
                    logging.error(
                        "Configuration was updated but failed to save to user_config.json."
                    )
        elif args.status:
            action_taken = True
            controller.status()
        elif args.precheck_services:
            action_taken = True
            controller.precheck_services()
        elif args.start:
            action_taken = True
            if controller.start_crawler() and controller.crawler_process:
                try:
                    controller.crawler_process.wait()
                except KeyboardInterrupt:
                    logging.debug("Crawler wait interrupted.")
                    controller.stop_crawler()
                # Post-run offline annotation (no AI calls)
                if args.annotate_offline_after_run:
                    try:
                        latest = _find_latest_session_for_app(cfg=cli_cfg)
                        if latest:
                            session_dir, db_path = latest
                            _run_offline_ui_annotator(
                                session_dir=session_dir, db_path=db_path
                            )
                        else:
                            logging.warning(
                                "No latest session found for selected APP_PACKAGE. Skipping offline annotation."
                            )
                    except Exception as e:
                        logging.error(f"Offline annotator failed: {e}", exc_info=True)
            else:
                exit_code = 1
        elif args.stop:
            action_taken = True
            controller.stop_crawler()
        elif args.pause:
            action_taken = True
            controller.pause_crawler()
        elif args.resume:
            action_taken = True
            controller.resume_crawler()

        elif args.test_mobsf_connection:
            action_taken = True
            if not controller.test_mobsf_connection():
                exit_code = 1
        elif args.run_mobsf_analysis:
            action_taken = True
            if not controller.run_mobsf_analysis():
                exit_code = 1

        # OpenRouter models cache refresh
        elif args.refresh_openrouter_models:
            action_taken = True
            try:
                from .openrouter_models import background_refresh_openrouter_models
            except ImportError:
                from openrouter_models import background_refresh_openrouter_models

            # Use synchronous refresh for CLI to provide immediate feedback
            success = background_refresh_openrouter_models(wait_for_completion=True)
            if success:
                logging.info(
                    "OpenRouter models cache refreshed successfully; saved to traverser_ai_api/output_data/cache/openrouter_models.json"
                )
            else:
                logging.error("Failed to refresh OpenRouter models cache")
                exit_code = 1
        
        # OpenRouter model management
        elif args.list_openrouter_models:
            action_taken = True
            # Determine free_only flag based on arguments
            free_only = None
            if args.free_only:
                free_only = True
            elif args.all:
                free_only = False
            # If neither flag is specified, use None to respect config setting
            
            if not controller.list_openrouter_models(free_only=free_only):
                exit_code = 1
        
        elif args.select_openrouter_model:
            action_taken = True
            if not controller.select_openrouter_model(args.select_openrouter_model):
                exit_code = 1
        
        elif args.show_openrouter_selection:
            action_taken = True
            if not controller.show_selected_openrouter_model():
                exit_code = 1
        
        # OpenRouter parity features
        elif args.configure_openrouter_image_context is not None:
            action_taken = True
            model_id = args.configure_openrouter_image_context
            if not controller.configure_openrouter_image_context(model_id):
                exit_code = 1
        elif args.enable_image_context:
            action_taken = True
            if not controller.configure_openrouter_image_context(enabled=True):
                exit_code = 1
        elif args.disable_image_context:
            action_taken = True
            if not controller.configure_openrouter_image_context(enabled=False):
                exit_code = 1
        elif args.show_openrouter_model_details is not None:
            action_taken = True
            model_id = args.show_openrouter_model_details
            if not controller.show_openrouter_model_details(model_id):
                exit_code = 1

        elif args.list_analysis_targets:
            action_taken = True
            if not controller.list_analysis_targets():
                exit_code = 1
        elif args.list_runs_for_target:
            action_taken = True
            if args.target_index:
                if not controller.list_runs_for_target(
                    args.target_index, is_index=True
                ):
                    exit_code = 1
            elif args.target_app_package:
                if not controller.list_runs_for_target(
                    args.target_app_package, is_index=False
                ):
                    exit_code = 1
            else:
                logging.error(
                    "--target-index OR --target-app-package is required with --list-runs-for-target."
                )
                parser.print_help()
                exit_code = 1
        elif args.generate_analysis_pdf:
            action_taken = True
            target_identifier_val = None
            is_index_val = False
            if args.target_index:
                target_identifier_val = args.target_index
                is_index_val = True
            elif args.target_app_package:
                target_identifier_val = args.target_app_package
                is_index_val = False
            else:
                logging.error(
                    "--target-index OR --target-app-package is required with --generate-analysis-pdf."
                )
                parser.print_help()
                exit_code = 1

            if target_identifier_val:
                # Pass None for run_id_str as it's no longer a direct CLI arg for this command
                if not controller.generate_analysis_pdf_for_target(
                    target_identifier_val,
                    is_index_val,
                    # args.run_id, # This argument is removed for this command
                    pdf_output_name=args.pdf_output_name,
                ):
                    exit_code = 1
            # else: error already handled and exit_code set

        elif args.print_analysis_summary:
            action_taken = True
            target_identifier_val = None
            is_index_val = False
            if args.target_index:
                target_identifier_val = args.target_index
                is_index_val = True
            elif args.target_app_package:
                target_identifier_val = args.target_app_package
                is_index_val = False
            else:
                logging.error(
                    "--target-index OR --target-app-package is required with --print-analysis-summary."
                )
                parser.print_help()
                exit_code = 1

            if target_identifier_val:
                if not controller.print_analysis_summary_for_target(
                    target_identifier_val, is_index_val
                ):
                    exit_code = 1

        # Focus Areas commands
        elif args.list_focus_areas:
            action_taken = True
            if not controller.list_focus_areas():
                exit_code = 1
        elif args.enable_focus_area:
            action_taken = True
            if not controller.set_focus_area_enabled(args.enable_focus_area, True):
                exit_code = 1
        elif args.disable_focus_area:
            action_taken = True
            if not controller.set_focus_area_enabled(args.disable_focus_area, False):
                exit_code = 1
        elif args.move_focus_area:
            action_taken = True
            if not args.from_index or not args.to_index:
                logging.error("--move-focus-area requires --from-index and --to-index")
                exit_code = 1
            else:
                if not controller.move_focus_area(args.from_index, args.to_index):
                    exit_code = 1

        # Focus Areas CRUD operations
        elif args.add_focus_area:
            action_taken = True
            description = getattr(args, "focus_description", "") or ""
            priority = getattr(args, "focus_priority", 999)
            if not controller.add_focus_area(args.add_focus_area, description, priority):
                exit_code = 1
        elif args.edit_focus_area:
            action_taken = True
            title = None
            description = getattr(args, "focus_description", None)
            priority = getattr(args, "focus_priority", None)
            if not controller.edit_focus_area(args.edit_focus_area, title, description, priority):
                exit_code = 1
        elif args.remove_focus_area:
            action_taken = True
            if not controller.remove_focus_area(args.remove_focus_area):
                exit_code = 1
        elif args.import_focus_areas:
            action_taken = True
            if not controller.import_focus_areas(args.import_focus_areas):
                exit_code = 1
        elif args.export_focus_areas:
            action_taken = True
            if not controller.export_focus_areas(args.export_focus_areas):
                exit_code = 1

        elif not action_taken:
            parser.print_help()

    except KeyboardInterrupt:
        logging.debug("CLI operation interrupted by user.")
        if (
            hasattr(controller, "crawler_process")
            and controller.crawler_process
            and controller.crawler_process.poll() is None
        ):
            controller.stop_crawler()
        exit_code = 130
    except Exception as e:
        logging.critical(f"Unexpected CLI error: {e}", exc_info=True)
        exit_code = 1
    finally:
        if (
            exit_code != 0
            and exit_code != 130
            and hasattr(controller, "crawler_process")
            and controller.crawler_process
            and controller.crawler_process.poll() is None
        ):
            logging.debug(
                "CLI exiting with error; ensuring managed crawler is stopped."
            )
            controller.stop_crawler()
        logging.debug(f"CLI session finished with exit_code: {exit_code}")
        sys.exit(exit_code)


if __name__ == "__main__":
    main_cli()