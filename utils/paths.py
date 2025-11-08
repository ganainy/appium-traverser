"""
Manages path resolution and generation for crawl sessions.
"""
import os
from pathlib import Path
from typing import Optional, Dict, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from config.config import Config


def find_project_root(start_path: Path) -> Path:
    """Find project root by looking for marker files (pyproject.toml, setup.py, etc.).
    
    Args:
        start_path: Starting path to search from (typically __file__ or current directory).
        
    Returns:
        Path to project root directory.
        
    Raises:
        FileNotFoundError: If project root cannot be determined (no marker files found).
    """
    start_path = Path(start_path).resolve()
    
    # Marker files that indicate project root
    markers = ["pyproject.toml", "setup.py", "setup.cfg", ".git", "README.md"]
    
    for parent in [start_path] + list(start_path.parents):
        # Check if any marker file exists
        if any((parent / marker).exists() for marker in markers):
            return parent
    
    # If no marker found, raise an error
    raise FileNotFoundError(
        f"Could not find project root. Searched from {start_path} "
        f"looking for markers: {markers}"
    )

# Constants for configuration keys
class SessionKeys:
    """Constants for configuration keys related to session paths."""
    OUTPUT_DATA_DIR_KEY = "OUTPUT_DATA_DIR"
    SESSION_DIR_TEMPLATE = "SESSION_DIR"
    DB_NAME_TEMPLATE = "DB_NAME"
    SCREENSHOTS_DIR_TEMPLATE = "SCREENSHOTS_DIR"
    LOG_DIR_TEMPLATE = "LOG_DIR"
    ANNOTATED_SCREENSHOTS_DIR_TEMPLATE = "ANNOTATED_SCREENSHOTS_DIR"
    TRAFFIC_CAPTURE_OUTPUT_DIR_TEMPLATE = "TRAFFIC_CAPTURE_OUTPUT_DIR"
    APP_PACKAGE = "APP_PACKAGE"
    TARGET_DEVICE_UDID = "TARGET_DEVICE_UDID"
    SESSION_TIMESTAMP = "SESSION_TIMESTAMP"
    DEVICE_ID_KEY = "device_id"
    APP_PACKAGE_KEY = "app_package"
    PACKAGE_KEY = "package"
    TIMESTAMP_KEY = "timestamp"
    SESSION_DIR_KEY = "session_dir"
    # Keys for parsed session data
    KEY_APP_PACKAGE = "app_package"
    KEY_APP_PACKAGE_SAFE = "app_package_safe"
    KEY_DB_PATH = "db_path"
    KEY_DB_FILENAME = "db_filename"
    KEY_SESSION_DIR = "session_dir"


class SessionPathManager:
    """
    Manages all path generation and parsing for a single crawl session.
    This is the single source of truth for all session-related paths.
    """

    def __init__(self, config: "Config"):
        self.config = config
        self._session_path: Optional[Path] = None
        self._app_package: Optional[str] = None
        self._app_package_safe: Optional[str] = None
        self._timestamp: Optional[str] = self.config.get(SessionKeys.SESSION_TIMESTAMP) or \
                                       datetime.now().strftime("%Y%m%d_%H%M%S")
        # Cache timestamp
        self.config.set(SessionKeys.SESSION_TIMESTAMP, self._timestamp, persist=False)

    def _get_app_package(self) -> str:
        if not self._app_package:
            self._app_package = self.config.get(SessionKeys.APP_PACKAGE) or "unknown.app"
        assert self._app_package is not None
        return self._app_package

    def _get_app_package_safe(self) -> str:
        """Gets the app package name formatted for use in file paths."""
        if not self._app_package_safe:
            self._app_package_safe = self._get_app_package().replace(".", "_")
        return self._app_package_safe

    def get_session_path(self) -> Path:
        """Resolves and returns the absolute path to the session directory."""
        if self._session_path:
            return self._session_path

        template = self.config.get(SessionKeys.SESSION_DIR_TEMPLATE)
        base_dir = self.config.OUTPUT_DATA_DIR  # This property is already resolved
        assert base_dir is not None, "OUTPUT_DATA_DIR must be set"
        
        device_id = self.config.get(SessionKeys.TARGET_DEVICE_UDID) or "unknown_device"
        app_package_safe = self._get_app_package_safe()
        assert self._timestamp is not None

        if not template:
            session_dir_str = str(Path(base_dir) / f"{device_id}_{app_package_safe}_{self._timestamp}")
        else:
            template = template.replace(f"{{{SessionKeys.OUTPUT_DATA_DIR_KEY}}}", str(base_dir))
            session_dir_str = template
            session_dir_str = session_dir_str.replace(f"{{{SessionKeys.DEVICE_ID_KEY}}}", device_id)
            session_dir_str = session_dir_str.replace(f"{{{SessionKeys.APP_PACKAGE_KEY}}}", app_package_safe)
            session_dir_str = session_dir_str.replace(f"{{{SessionKeys.TIMESTAMP_KEY}}}", self._timestamp)

        self._session_path = Path(session_dir_str).resolve()
        return self._session_path

    def _resolve_template(self, template_key: str) -> Path:
        """Helper to resolve a path template like DB_NAME, LOG_DIR, etc."""
        template = self.config.get(template_key)
        session_dir = self.get_session_path()  # Ensures session_path is resolved

        if not template:
            raise ValueError(f"Config key {template_key} is not defined.")

        # Replace placeholders
        template = template.replace(f"{{{SessionKeys.OUTPUT_DATA_DIR_KEY}}}", str(self.config.OUTPUT_DATA_DIR))
        template = template.replace(f"{{{SessionKeys.SESSION_DIR_KEY}}}", str(session_dir))
        template = template.replace(f"{{{SessionKeys.PACKAGE_KEY}}}", self._get_app_package_safe())

        return Path(template).resolve()

    # --- Public Path Getters ---
    def get_db_path(self) -> Path:
        return self._resolve_template(SessionKeys.DB_NAME_TEMPLATE)

    def get_screenshots_dir(self) -> Path:
        return self._resolve_template(SessionKeys.SCREENSHOTS_DIR_TEMPLATE)

    def get_log_dir(self) -> Path:
        return self._resolve_template(SessionKeys.LOG_DIR_TEMPLATE)

    def get_annotated_screenshots_dir(self) -> Path:
        return self._resolve_template(SessionKeys.ANNOTATED_SCREENSHOTS_DIR_TEMPLATE)

    def get_traffic_capture_dir(self) -> Path:
        return self._resolve_template(SessionKeys.TRAFFIC_CAPTURE_OUTPUT_DIR_TEMPLATE)

    @staticmethod
    def get_reports_dir(session_dir: str) -> Path:
        """Get the reports directory for a session.
        
        Args:
            session_dir: Path to the session directory
            
        Returns:
            Path to the reports directory
        """
        from cli.constants import keys as CKeys
        return Path(session_dir) / CKeys.DIR_REPORTS

    @staticmethod
    def get_pdf_report_path(reports_dir: Path, app_package: str, pdf_output_name: Optional[str]) -> Path:
        """Generate the full path for a PDF report.
        
        Args:
            reports_dir: Path to the reports directory
            app_package: App package name
            pdf_output_name: Optional custom PDF filename
            
        Returns:
            Full path to the PDF report
        """
        pdf_filename_suffix = (
            Path(pdf_output_name).name if pdf_output_name else "analysis.pdf"
        )
        final_pdf_filename = f"{app_package}_{pdf_filename_suffix}"
        return reports_dir / final_pdf_filename

    @staticmethod
    def parse_session_dir(session_dir: Path, config: "Config") -> Optional[Dict[str, str]]:
        """
        Robustly parses a session directory to find its database and metadata.
        This is the new 'Reader' logic for AnalysisService.
        """
        try:
            # 1. Get the DB template and extract the subdirectory and suffix
            db_template = config.get(SessionKeys.DB_NAME_TEMPLATE, "")  # e.g., "{session_dir}/database/{package}_crawl_data.db"
            db_template_relative = db_template.replace(f"{{{SessionKeys.SESSION_DIR_KEY}}}/", "")  # "database/{package}_crawl_data.db"

            if SessionKeys.PACKAGE_KEY not in db_template_relative:
                # Cannot reliably parse if the package isn't in the DB name
                return None

            db_subdir = Path(db_template_relative).parent  # "database"
            db_suffix = db_template_relative.split(f"{{{SessionKeys.PACKAGE_KEY}}}")[1]  # "_crawl_data.db"

            # 2. Find the database file
            db_dir_path = session_dir / db_subdir
            if not db_dir_path.is_dir():
                return None

            db_files = list(db_dir_path.glob(f"*{db_suffix}"))
            if not db_files:
                return None

            db_file = db_files[0]  # Take the first match

            # 3. Extract the app package from the db file name
            app_package_safe = db_file.name.replace(db_suffix, "")
            return {
                SessionKeys.KEY_APP_PACKAGE: app_package_safe.replace("_", "."),  # De-sanitize
                SessionKeys.KEY_APP_PACKAGE_SAFE: app_package_safe,
                SessionKeys.KEY_DB_PATH: str(db_file.resolve()),
                SessionKeys.KEY_DB_FILENAME: db_file.name,
                SessionKeys.KEY_SESSION_DIR: str(session_dir.resolve()),
            }
        except Exception:
            return None  # Failed to parse