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

try:
    from config import Config
except ImportError as e:
    sys.stderr.write(f"FATAL: Could not import 'Config' class from config.py: {e}\n")
    sys.stderr.write("Ensure config.py exists and contains the Config class definition.\n")
    sys.exit(1)

try:
    from utils import SCRIPT_START_TIME, LoggerManager
except ImportError as e:
    sys.stderr.write(f"FATAL: Could not import logging utilities from utils.py: {e}\n")
    sys.stderr.write("Ensure utils.py exists and contains SCRIPT_START_TIME, LoggerManager.\n")
    if 'SCRIPT_START_TIME' not in globals():
        SCRIPT_START_TIME = time.time()
    sys.exit(1)

try:
    from analysis_viewer import RunAnalyzer, XHTML2PDF_AVAILABLE
except ImportError as e:
    sys.stderr.write(f"FATAL: Could not import from analysis_viewer.py: {e}\n")
    sys.stderr.write("Ensure analysis_viewer.py is in the same directory or Python path and has no import errors.\n")
    RunAnalyzer = None
    XHTML2PDF_AVAILABLE = False


class CLIController:
    """Command-line controller for the Appium Crawler."""

    def __init__(self, app_config_instance: Config):
        self.cfg = app_config_instance
        self.api_dir = os.path.dirname(os.path.abspath(__file__))
        self.find_app_info_script_path = os.path.join(self.api_dir, "find_app_info.py")
        self.health_apps_data: List[Dict[str, Any]] = []
        self.pid_file_path = os.path.join(self.cfg.BASE_DIR or self.api_dir, "crawler.pid")
        self.crawler_process: Optional[subprocess.Popen] = None
        self.discovered_analysis_targets: List[Dict[str, Any]] = []

        logging.debug(f"PID file will be managed at: {self.pid_file_path}")

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        if self.cfg.CURRENT_HEALTH_APP_LIST_FILE and os.path.exists(self.cfg.CURRENT_HEALTH_APP_LIST_FILE):
            logging.info(f"Attempting to auto-load health apps from: {self.cfg.CURRENT_HEALTH_APP_LIST_FILE}")
            self._load_health_apps_from_file(self.cfg.CURRENT_HEALTH_APP_LIST_FILE)
        else:
            logging.info("No pre-existing health app list file found or file does not exist.")

    def _signal_handler(self, signum, frame):
        logging.warning(f"\nSignal {signal.Signals(signum).name} received. Initiating crawler shutdown...")
        self.stop_crawler()
        logging.info("CLI shutdown signal handled.")
        sys.exit(0)

    def _is_process_running(self, pid: int) -> bool:
        if pid <= 0: return False
        try:
            os.kill(pid, 0)
        except OSError as err:
            return err.errno == errno.EPERM
        return True

    def save_all_changes(self) -> bool:
        logging.info("Attempting to save all current configuration settings...")
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
        logging.info(f"Attempting to set config: {key} = '{value_str}'")
        try:
            self.cfg.update_setting_and_save(key, value_str)
            return True
        except Exception as e:
            logging.error(f"Failed to set config for {key}: {e}", exc_info=True)
            return False

    def scan_apps(self, force_rescan: bool = False) -> bool:
        if not force_rescan and self.cfg.CURRENT_HEALTH_APP_LIST_FILE and \
           os.path.exists(self.cfg.CURRENT_HEALTH_APP_LIST_FILE):
            logging.info(f"Using cached health app list: {self.cfg.CURRENT_HEALTH_APP_LIST_FILE}")
            return self._load_health_apps_from_file(self.cfg.CURRENT_HEALTH_APP_LIST_FILE)

        if not os.path.exists(self.find_app_info_script_path):
            logging.error(f"find_app_info.py script not found at {self.find_app_info_script_path}")
            return False
        logging.info("Starting health app scan...")
        try:
            result = subprocess.run(
                [sys.executable, '-u', self.find_app_info_script_path, '--mode', 'discover'],
                cwd=self.api_dir, capture_output=True, text=True, timeout=300, check=False
            )
            if result.returncode != 0:
                logging.error(f"App scan script failed. Stderr: {result.stderr}")
                return False
            cache_file_line = next((line for line in result.stdout.splitlines() if "Cache file generated at:" in line), None)
            if not cache_file_line:
                logging.error("Could not find cache file path in scan output.")
                return False
            cache_file_path = cache_file_line.split("Cache file generated at:", 1)[1].strip()
            resolved_cache_path = Path(self.api_dir) / cache_file_path if not Path(cache_file_path).is_absolute() else Path(cache_file_path)
            if not resolved_cache_path.exists():
                 logging.error(f"Cache file reported by script not found: {resolved_cache_path}")
                 return False
            self.cfg.update_setting_and_save('CURRENT_HEALTH_APP_LIST_FILE', str(resolved_cache_path))
            return self._load_health_apps_from_file(str(resolved_cache_path))
        except Exception as e:
            logging.error(f"Error during app scan: {e}", exc_info=True)
            return False

    def _load_health_apps_from_file(self, file_path: str) -> bool:
        logging.debug(f"Loading health apps from: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.health_apps_data = data.get('apps', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            logging.info(f"Loaded {len(self.health_apps_data)} health apps from {file_path}")
            return True
        except Exception as e:
            logging.error(f"Error loading health apps from {file_path}: {e}", exc_info=True)
            self.health_apps_data = []
            return False

    def list_apps(self):
        if not self.health_apps_data:
            logging.info("No health apps loaded. Run 'scan-apps'.")
            return
        print(f"\n=== Available Health Apps ({len(self.health_apps_data)}) ===")
        for i, app in enumerate(self.health_apps_data):
            print(f"{i+1:2d}. App: {app.get('app_name', 'N/A')}\n     Pkg: {app.get('package_name', 'N/A')}\n     Act: {app.get('activity_name', 'N/A')}\n")
        print("===================================")

    def select_app(self, app_identifier: str) -> bool:
        if not self.health_apps_data: logging.error("No health apps loaded. Run 'scan-apps'."); return False
        selected_app = None
        try:
            index = int(app_identifier) - 1
            if 0 <= index < len(self.health_apps_data): selected_app = self.health_apps_data[index]
        except ValueError:
            app_identifier_lower = app_identifier.lower()
            for app in self.health_apps_data:
                if app_identifier_lower in app.get('app_name', '').lower() or \
                   app_identifier_lower == app.get('package_name', '').lower():
                    selected_app = app; break
        if not selected_app: logging.error(f"App '{app_identifier}' not found."); return False
        pkg, act, name = selected_app.get('package_name'), selected_app.get('activity_name'), selected_app.get('app_name', 'Unknown')
        if not pkg or not act: logging.error(f"Selected app '{name}' missing package/activity."); return False
        logging.info(f"Selecting app: '{name}' (Package: {pkg})")
        self.cfg.update_setting_and_save('APP_PACKAGE', pkg)
        self.cfg.update_setting_and_save('APP_ACTIVITY', act)
        self.cfg.update_setting_and_save('LAST_SELECTED_APP', {'package_name': pkg, 'activity_name': act, 'app_name': name})
        return True

    def start_crawler(self) -> bool:
        if not self.cfg.SHUTDOWN_FLAG_PATH: logging.error("Shutdown flag path not configured."); return False
        if Path(self.cfg.SHUTDOWN_FLAG_PATH).exists():
            logging.warning(f"Removing existing shutdown flag: {self.cfg.SHUTDOWN_FLAG_PATH}")
            try: Path(self.cfg.SHUTDOWN_FLAG_PATH).unlink()
            except OSError as e: logging.error(f"Could not remove flag: {e}"); return False

        main_script = Path(self.api_dir) / 'main.py'
        if Path(self.pid_file_path).exists():
            try:
                pid = int(Path(self.pid_file_path).read_text().strip())
                if self._is_process_running(pid):
                    logging.warning(f"Crawler already running (PID {pid})."); return False
                Path(self.pid_file_path).unlink()
            except (ValueError, OSError) as e: logging.warning(f"Error with PID file: {e}")

        if self.crawler_process and self.crawler_process.poll() is None:
            logging.warning(f"CLI-managed crawler (PID {self.crawler_process.pid}) already running."); return False
        if not self.cfg.APP_PACKAGE or not self.cfg.APP_ACTIVITY:
            logging.error("APP_PACKAGE and APP_ACTIVITY must be set."); return False

        logging.info("Starting crawler process...")
        try:
            env = os.environ.copy()
            env['PYTHONPATH'] = str(_project_root) + os.pathsep + env.get('PYTHONPATH', '')
            self.crawler_process = subprocess.Popen(
                [sys.executable, '-u', str(main_script)], cwd=str(_project_root),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                bufsize=1, universal_newlines=True, encoding='utf-8', errors='replace', env=env
            )
            Path(self.pid_file_path).write_text(str(self.crawler_process.pid))
            logging.info(f"Crawler started (PID {self.crawler_process.pid}). PID written to {self.pid_file_path}.")
            threading.Thread(target=self._monitor_crawler_output, daemon=True).start()
            return True
        except Exception as e:
            logging.error(f"Failed to start crawler: {e}", exc_info=True)
            return False

    def _monitor_crawler_output(self):
        if not self.crawler_process or not self.crawler_process.stdout: return
        pid = self.crawler_process.pid
        try:
            for line in iter(self.crawler_process.stdout.readline, ''): print(line, end='')
            rc = self.crawler_process.wait()
            logging.info(f"Crawler (PID {pid}) exited with code {rc}.")
        except Exception as e: logging.error(f"Error monitoring crawler (PID {pid}): {e}", exc_info=True)
        finally:
            self._cleanup_pid_file_if_matches(pid)
            if self.crawler_process and self.crawler_process.pid == pid: self.crawler_process = None

    def stop_crawler(self) -> bool:
        logging.info("Signaling crawler to stop...")
        if not self.cfg.SHUTDOWN_FLAG_PATH: logging.error("SHUTDOWN_FLAG_PATH not configured."); return False

        pid_to_signal = None
        if self.crawler_process and self.crawler_process.poll() is None: pid_to_signal = self.crawler_process.pid
        elif Path(self.pid_file_path).exists():
            try:
                pid_from_file = int(Path(self.pid_file_path).read_text().strip())
                if self._is_process_running(pid_from_file): pid_to_signal = pid_from_file
            except (ValueError, OSError): pass

        try:
            Path(self.cfg.SHUTDOWN_FLAG_PATH).write_text("stop")
            logging.info(f"Shutdown flag created: {self.cfg.SHUTDOWN_FLAG_PATH}.")
            if pid_to_signal: logging.info(f"Crawler (PID {pid_to_signal}) should detect flag.")
            else: logging.info("No active crawler PID identified by CLI. Flag set for any running instance.")
            return True
        except Exception as e:
            logging.error(f"Failed to create shutdown flag: {e}", exc_info=True)
            return False

    def _cleanup_pid_file_if_matches(self, pid_to_check: Optional[int]):
        pid_file = Path(self.pid_file_path)
        if pid_file.exists():
            try:
                pid_in_file = int(pid_file.read_text().strip())
                if (pid_to_check is not None and pid_in_file == pid_to_check and not self._is_process_running(pid_in_file)) or \
                   (pid_to_check is None and not self._is_process_running(pid_in_file)):
                    pid_file.unlink()
                    logging.info(f"Removed PID file: {pid_file} (contained PID: {pid_in_file})")
            except (ValueError, OSError, Exception) as e:
                logging.warning(f"Error during PID file cleanup for {pid_file}: {e}. Removing if invalid.")
                try: pid_file.unlink()
                except OSError: pass


    def status(self):
        print("\n=== CLI Crawler Status ===")
        pid_file = Path(self.pid_file_path)
        status_msg = "  Crawler Process: Unknown"
        if self.crawler_process and self.crawler_process.poll() is None:
            status_msg = f"  Crawler Process: Running (PID {self.crawler_process.pid}, CLI-managed)"
        elif pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                if self._is_process_running(pid): status_msg = f"  Crawler Process: Running (PID {pid} from PID file)"
                else: status_msg = f"  Crawler Process: Stale PID file (PID {pid} not running)"
            except (ValueError, OSError): status_msg = "  Crawler Process: Invalid PID file"
        else: status_msg = "  Crawler Process: Stopped (no PID file)"
        print(status_msg)
        print(f"  Target App:      '{self.cfg.LAST_SELECTED_APP.get('app_name', self.cfg.APP_PACKAGE) if self.cfg.LAST_SELECTED_APP else self.cfg.APP_PACKAGE}' ({self.cfg.APP_PACKAGE or 'Not Set'})")
        print(f"  Output Data Dir: {self.cfg.OUTPUT_DATA_DIR or 'Not Set'}")
        print("========================")

    def _ensure_analysis_targets_discovered(self, quiet: bool = False) -> bool:
        if not self.discovered_analysis_targets:
            if not quiet:
                logging.info("Analysis targets not yet discovered in this session. Running discovery...")
            if not self._discover_analysis_targets_internal(quiet_discovery=quiet):
                if not quiet:
                    logging.error("Failed to discover analysis targets.")
                return False
        return True

    def _discover_analysis_targets_internal(self, quiet_discovery: bool = True) -> bool:
        if not self.cfg.OUTPUT_DATA_DIR:
            if not quiet_discovery: logging.error("OUTPUT_DATA_DIR is not configured.")
            return False

        db_output_root = Path(self.cfg.OUTPUT_DATA_DIR) / "database_output"
        if not db_output_root.is_dir():
            if not quiet_discovery: logging.error(f"Database output directory not found: {db_output_root}")
            return False

        self.discovered_analysis_targets = []
        target_idx = 1
        db_filename_template = Path(self.cfg._DB_NAME_TEMPLATE.split('/')[-1]).name

        for app_package_dir in db_output_root.iterdir():
            if app_package_dir.is_dir():
                app_package_name = app_package_dir.name
                expected_db_filename = db_filename_template.replace("{package}", app_package_name)
                db_file_path = app_package_dir / expected_db_filename

                if not db_file_path.exists():
                    found_dbs = list(app_package_dir.glob("*.db"))
                    if found_dbs:
                        db_file_path = found_dbs[0]
                        expected_db_filename = db_file_path.name
                    else:
                        continue

                self.discovered_analysis_targets.append({
                    "index": target_idx,
                    "app_package": app_package_name,
                    "db_path": str(db_file_path.resolve()),
                    "db_filename": expected_db_filename
                })
                target_idx += 1
        return True


    def list_analysis_targets(self) -> bool:
        if not self._discover_analysis_targets_internal(quiet_discovery=True):
            print("Error: Could not discover analysis targets. Check OUTPUT_DATA_DIR and database_output structure.")
            return False

        if not self.cfg.OUTPUT_DATA_DIR :
             print("Error: OUTPUT_DATA_DIR is not set in the configuration.")
             return False
        db_output_root = Path(self.cfg.OUTPUT_DATA_DIR) / "database_output"

        print(f"\nAvailable analysis targets in {db_output_root}:")
        if not self.discovered_analysis_targets:
            print("No app packages with database files found.")
        else:
            for target in self.discovered_analysis_targets:
                print(f"{target['index']}. App Package: {target['app_package']}, DB File: {target['db_filename']}")
            print(f"\nUse '--list-runs-for-target --target-index <NUMBER>' or '--list-runs-for-target --target-app-package <PKG_NAME>' to see runs.")
            print(f"Use '--generate-analysis-pdf --target-index <NUMBER> OR --target-app-package <PKG_NAME> [--pdf-output-name <name.pdf>]' to create PDF for the (latest) run.")
        return True


    def list_runs_for_target(self, target_identifier: str, is_index: bool) -> bool:
        if not self._ensure_analysis_targets_discovered(quiet=True):
            print("Error: Could not ensure analysis targets were discovered. Aborting.")
            return False

        selected_target: Optional[Dict[str, Any]] = None
        if is_index:
            try:
                target_index_val = int(target_identifier)
                selected_target = next((t for t in self.discovered_analysis_targets if t["index"] == target_index_val), None)
            except ValueError:
                logging.error(f"Invalid target index: '{target_identifier}'. Must be a number.")
                print(f"Error: Invalid target index '{target_identifier}'. Please provide a number from the list.")
                return False
            if not selected_target:
                logging.error(f"Target index {target_identifier} not found in the discovered list.")
                print(f"Error: Target index {target_identifier} not found. Run '--list-analysis-targets' to see available targets.")
                return False
        else: # Identifier is an app package name
            selected_target = next((t for t in self.discovered_analysis_targets if t["app_package"] == target_identifier), None)
            if not selected_target:
                logging.error(f"Target app package '{target_identifier}' not found in the discovered list.")
                print(f"Error: Target app package '{target_identifier}' not found. Run '--list-analysis-targets' to see available targets.")
                return False


        if RunAnalyzer is None: logging.error("RunAnalyzer module not available."); return False
        if self.cfg.OUTPUT_DATA_DIR is None: logging.error("OUTPUT_DATA_DIR is not configured."); return False

        print(f"\n--- Runs for Target {selected_target['index']}: {selected_target['app_package']} (DB: {selected_target['db_filename']}) ---")
        try:
            analyzer = RunAnalyzer(
                db_path=selected_target["db_path"],
                output_data_dir=self.cfg.OUTPUT_DATA_DIR,
                app_package_for_run=selected_target["app_package"]
            )
            analyzer.list_runs()
            return True
        except FileNotFoundError:
            logging.error(f"Database file not found for target {selected_target['app_package']}: {selected_target['db_path']}")
            print(f"Error: Database file not found: {selected_target['db_path']}")
            return False
        except Exception as e:
            logging.error(f"Error listing runs for target {selected_target['app_package']}: {e}", exc_info=True)
            print(f"Error listing runs: {e}")
            return False

    def generate_analysis_pdf_for_target(self, target_identifier: str, is_index: bool, pdf_output_name: Optional[str] = None) -> bool:
        # Removed run_id_str from parameters
        if not self._ensure_analysis_targets_discovered(quiet=True):
            print("Error: Could not ensure analysis targets were discovered. Aborting PDF generation.")
            return False

        if not RunAnalyzer or not XHTML2PDF_AVAILABLE:
            logging.error("RunAnalyzer or PDF library (xhtml2pdf) not available.")
            print("Error: Analysis module or PDF library not available. PDF generation aborted.")
            return False
        if self.cfg.OUTPUT_DATA_DIR is None: logging.error("OUTPUT_DATA_DIR is not configured."); return False

        selected_target: Optional[Dict[str, Any]] = None
        if is_index:
            try:
                target_index_val = int(target_identifier)
                selected_target = next((t for t in self.discovered_analysis_targets if t["index"] == target_index_val), None)
            except ValueError:
                logging.error(f"Invalid target index: '{target_identifier}'. Must be a number.")
                print(f"Error: Invalid target index '{target_identifier}'.")
                return False
            if not selected_target:
                logging.error(f"Target index {target_identifier} not found.")
                print(f"Error: Target index {target_identifier} not found.")
                return False
        else: # Identifier is an app package name
            selected_target = next((t for t in self.discovered_analysis_targets if t["app_package"] == target_identifier), None)
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
                logging.info(f"Using Run ID: {actual_run_id} (latest/only) for target {selected_target['app_package']}.")
            else: # Fallback if no runs or if query fails to return a run_id
                 # If there are runs but ORDER BY DESC LIMIT 1 fails, try to get any run_id
                cursor_temp.execute("SELECT run_id FROM runs LIMIT 1")
                any_run_row = cursor_temp.fetchone()
                if any_run_row and any_run_row[0] is not None:
                    actual_run_id = any_run_row[0]
                    logging.warning(f"Could not determine latest run, using first available Run ID: {actual_run_id} for target {selected_target['app_package']}.")
                else:
                    logging.error(f"No runs found in the database for target {selected_target['app_package']}. Cannot determine a run ID.")
                    print(f"Error: No runs found for {selected_target['app_package']}. Cannot generate PDF.")
                    conn_temp.close()
                    return False
            conn_temp.close()
        except sqlite3.Error as e:
            logging.error(f"Database error determining run ID for {selected_target['app_package']}: {e}")
            print(f"Error: Database error determining run ID for {selected_target['app_package']}.")
            return False
        
        if actual_run_id is None: # Should be caught by logic above, but as a safeguard
            logging.error(f"Failed to determine a run_id for PDF generation for target {selected_target['app_package']}.")
            return False

        analysis_reports_dir = Path(self.cfg.OUTPUT_DATA_DIR) / "analysis_reports"
        analysis_reports_dir.mkdir(parents=True, exist_ok=True)

        pdf_filename_suffix = Path(pdf_output_name).name if pdf_output_name else "analysis.pdf"
        # Use the determined actual_run_id in the filename
        final_pdf_filename = f"{selected_target['app_package']}_{pdf_filename_suffix}"
        final_pdf_path = str(analysis_reports_dir / final_pdf_filename)

        logging.info(f"Generating PDF for Target: {selected_target['app_package']}, Run ID: {actual_run_id}, Output: {final_pdf_path}")
        try:
            analyzer = RunAnalyzer(
                db_path=selected_target["db_path"],
                output_data_dir=self.cfg.OUTPUT_DATA_DIR,
                app_package_for_run=selected_target["app_package"]
            )
            analyzer.analyze_run_to_pdf(actual_run_id, final_pdf_path)
            return True
        except FileNotFoundError:
            logging.error(f"Database file not found for PDF generation: {selected_target['db_path']}")
            print(f"Error: Database file not found: {selected_target['db_path']}")
            return False
        except Exception as e:
            logging.error(f"Error generating PDF for target {selected_target['app_package']}, run {actual_run_id}: {e}", exc_info=True)
            print(f"Error generating PDF: {e}")
            return False


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI Controller for Appium Crawler.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
Examples:
  %(prog)s status
  %(prog)s scan-apps
  %(prog)s list-apps
  %(prog)s --select-app "Your App Name"  # Or use index: %(prog)s --select-app 1
  %(prog)s show-config
  %(prog)s set-config MAX_CRAWL_STEPS=50
  %(prog)s start
  %(prog)s stop

  # New Analysis Commands:
  %(prog)s --list-analysis-targets
  %(prog)s --list-runs-for-target --target-index 1
  %(prog)s --list-runs-for-target --target-app-package com.example.app

  %(prog)s --generate-analysis-pdf --target-index 1 
  %(prog)s --generate-analysis-pdf --target-app-package com.example.app
  %(prog)s --generate-analysis-pdf --target-app-package com.example.app --pdf-output-name "custom_report.pdf"
        """)
    )
    app_group = parser.add_argument_group('App Management')
    app_group.add_argument('--scan-apps', action='store_true', help='Scan device for health-related apps.')
    app_group.add_argument('--list-apps', action='store_true', help='List available health apps from last scan.')
    app_group.add_argument('--select-app', metavar='ID_OR_NAME', help='Select app by name or 1-based index.')

    crawler_group = parser.add_argument_group('Crawler Control')
    crawler_group.add_argument('--start', action='store_true', help='Start the crawler.')
    crawler_group.add_argument('--stop', action='store_true', help='Signal the crawler to stop.')
    crawler_group.add_argument('--status', action='store_true', help='Show crawler status.')

    config_group = parser.add_argument_group('Configuration Management')
    config_group.add_argument('--show-config', metavar='FILTER', nargs='?', const='', help='Show config (optionally filter by key).')
    config_group.add_argument('--set-config', metavar='K=V', action='append', help='Set config value (e.g., MAX_CRAWL_STEPS=100).')
    config_group.add_argument('--save-config', action='store_true', help='Save current config settings.')

    analysis_group = parser.add_argument_group('Analysis (New Workflow)')
    analysis_group.add_argument('--list-analysis-targets', action='store_true',
                                help='List all app packages with database files available for analysis.')
    analysis_group.add_argument('--list-runs-for-target', action='store_true',
                                help='List runs for a specific analysis target. Requires --target-index OR --target-app-package.')
    analysis_group.add_argument('--generate-analysis-pdf', action='store_true',
                                help='Generate PDF report for the (latest/only) run of an analysis target. Requires --target-index OR --target-app-package. Optionally takes --pdf-output-name.')

    analysis_target_group = analysis_group.add_mutually_exclusive_group(required=False)
    analysis_target_group.add_argument('--target-index', metavar='NUMBER', type=str,
                                help='Index number of the analysis target (from --list-analysis-targets).')
    analysis_target_group.add_argument('--target-app-package', metavar='PKG_NAME', type=str,
                                help='Full package name of the target application for analysis.')

    # --run-id is removed for generate-analysis-pdf as per user request to simplify
    analysis_group.add_argument('--pdf-output-name', metavar='FILENAME.pdf', type=str, default=None,
                                help='Optional: Base filename for the PDF. If not given, a default name is used.')

    parser.add_argument('--force-rescan', action='store_true', help='Force app rescan.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable DEBUG logging.')
    return parser

def main_cli():
    parser = create_parser()
    args = parser.parse_args()

    log_level = 'DEBUG' if args.verbose else 'INFO'
    logging.basicConfig(
        level=log_level,
        format='[%(levelname)s] %(asctime)s %(module)s: %(message)s',
        datefmt='%H:%M:%S',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logging.info("CLI Bootstrap logging initialized.")

    _cli_script_dir = Path(__file__).resolve().parent
    DEFAULT_CONFIG_MODULE_PATH_CLI = str(_cli_script_dir / 'config.py')
    USER_CONFIG_JSON_PATH_CLI = str(_cli_script_dir / "user_config.json")
    try:
        cli_cfg = Config(
            defaults_module_path=DEFAULT_CONFIG_MODULE_PATH_CLI,
            user_config_json_path=USER_CONFIG_JSON_PATH_CLI
        )
        if not cli_cfg.SHUTDOWN_FLAG_PATH:
             cli_cfg.SHUTDOWN_FLAG_PATH = str(Path(cli_cfg.BASE_DIR or _cli_script_dir) / "crawler_shutdown.flag")

        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        logger_manager_cli = LoggerManager()
        log_file_base = Path(cli_cfg.OUTPUT_DATA_DIR or _cli_script_dir)
        log_file_path = log_file_base / "logs" / "cli" / f"cli_{cli_cfg.LOG_FILE_NAME}"
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        logger_manager_cli.setup_logging(log_level_str=log_level, log_file=str(log_file_path))
        logging.info(f"CLI Application Logging Initialized. Level: {log_level}. File: '{log_file_path}'")

    except Exception as e:
        logging.critical(f"Failed to initialize Config or Logger: {e}", exc_info=True)
        sys.exit(100)

    controller = CLIController(app_config_instance=cli_cfg)
    action_taken = False
    exit_code = 0

    try:
        if args.scan_apps: action_taken = True; controller.scan_apps(force_rescan=args.force_rescan)
        elif args.list_apps: action_taken = True; controller.list_apps()
        elif args.select_app: action_taken = True; controller.select_app(args.select_app)
        elif args.show_config is not None: action_taken = True; controller.show_config(args.show_config)
        elif args.set_config:
            action_taken = True
            for item in args.set_config:
                if '=' not in item: logging.error(f"Invalid config format: {item}"); exit_code=1; break
                key, val = item.split('=', 1)
                if not controller.set_config_value(key, val): exit_code=1; break
        elif args.save_config: action_taken = True; controller.save_all_changes()
        elif args.status: action_taken = True; controller.status()
        elif args.start:
            action_taken = True
            if controller.start_crawler() and controller.crawler_process:
                try: controller.crawler_process.wait()
                except KeyboardInterrupt: logging.info("Crawler wait interrupted."); controller.stop_crawler()
            else: exit_code = 1
        elif args.stop: action_taken = True; controller.stop_crawler()

        elif args.list_analysis_targets:
            action_taken = True
            if not controller.list_analysis_targets(): exit_code = 1
        elif args.list_runs_for_target:
            action_taken = True
            if args.target_index:
                if not controller.list_runs_for_target(args.target_index, is_index=True): exit_code = 1
            elif args.target_app_package:
                if not controller.list_runs_for_target(args.target_app_package, is_index=False): exit_code = 1
            else:
                logging.error("--target-index OR --target-app-package is required with --list-runs-for-target.")
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
                logging.error("--target-index OR --target-app-package is required with --generate-analysis-pdf.")
                parser.print_help()
                exit_code = 1

            if target_identifier_val:
                # Pass None for run_id_str as it's no longer a direct CLI arg for this command
                if not controller.generate_analysis_pdf_for_target(
                    target_identifier_val,
                    is_index_val,
                    # args.run_id, # This argument is removed for this command
                    pdf_output_name=args.pdf_output_name
                ): exit_code = 1
            # else: error already handled and exit_code set

        elif not action_taken:
            parser.print_help()

    except KeyboardInterrupt:
        logging.info("CLI operation interrupted by user.")
        if hasattr(controller, 'crawler_process') and controller.crawler_process and controller.crawler_process.poll() is None:
            controller.stop_crawler()
        exit_code = 130
    except Exception as e:
        logging.critical(f"Unexpected CLI error: {e}", exc_info=True)
        exit_code = 1
    finally:
        if exit_code != 0 and exit_code != 130 and \
           hasattr(controller, 'crawler_process') and controller.crawler_process and controller.crawler_process.poll() is None:
            logging.info("CLI exiting with error; ensuring managed crawler is stopped.")
            controller.stop_crawler()
        logging.info(f"CLI session finished with exit_code: {exit_code}")
        sys.exit(exit_code)

if __name__ == '__main__':
    main_cli()
