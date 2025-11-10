"""
Manages path resolution and generation for crawl sessions.
"""
import logging
import os
import re
from pathlib import Path
from typing import Optional, Dict, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from config.app_config import Config


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
    TARGET_DEVICE_NAME = "TARGET_DEVICE_NAME"
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
        # Store session-specific state as instance variables instead of in config
        # Check if a timestamp was passed from the orchestrator
        self._timestamp: str = os.environ.get("CRAWLER_SESSION_TIMESTAMP")
        if self._timestamp:
            logger = logging.getLogger(__name__)
            logger.debug(f"Using inherited session timestamp: {self._timestamp}")
        else:
            # If not, generate a new one (for standalone runs)
            self._timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            logger = logging.getLogger(__name__)
            logger.debug(f"Generated new session timestamp: {self._timestamp}")
        self._device_udid: Optional[str] = None
        self._device_name: Optional[str] = None
        # Try to detect device info early to avoid "unknown_device" paths
        self._try_detect_device_early()

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
    
    def _try_detect_device_early(self) -> None:
        """Try to detect device info early to avoid creating paths with 'unknown_device'.
        
        This is a best-effort attempt - if device detection fails, device info will be
        set later when AppiumDriver.initialize_session() is called.
        """
        try:
            # Check if device info is already set in config (e.g., from previous session)
            device_udid = self.config.get(SessionKeys.TARGET_DEVICE_UDID)
            device_name = self.config.get(SessionKeys.TARGET_DEVICE_NAME)
            
            if device_udid or device_name:
                self._device_udid = device_udid
                self._device_name = device_name
                logger = logging.getLogger(__name__)
                logger.debug(f"Using device info from config: UDID={device_udid}, Name={device_name}")
                return
            
            # Try to detect device early using device detection
            try:
                from infrastructure.device_detection import detect_all_devices, select_best_device
                all_devices = detect_all_devices()
                if all_devices:
                    selected_device = select_best_device(all_devices, 'android', None)
                    if selected_device:
                        self._device_udid = selected_device.id
                        self._device_name = selected_device.name
                        logger = logging.getLogger(__name__)
                        logger.debug(f"Early device detection successful: UDID={selected_device.id}, Name={selected_device.name}")
                        return
            except Exception as e:
                # Device detection failed - this is OK, device info will be set later
                logger = logging.getLogger(__name__)
                logger.debug(f"Early device detection failed (this is OK): {e}")
        except Exception as e:
            # Any error is OK - device info will be set later
            logger = logging.getLogger(__name__)
            logger.debug(f"Error in early device detection (this is OK): {e}")

    def set_device_info(self, udid: Optional[str] = None, name: Optional[str] = None) -> None:
        """Set device information and invalidate cached session path.
        
        Args:
            udid: Device UDID (optional)
            name: Device name (optional, preferred over UDID for readability)
        """
        # Check if session directory already exists - if so, don't allow device info changes
        # This prevents creating duplicate directories
        # Check the cached path first
        if self._session_path and self._session_path.exists():
            logger = logging.getLogger(__name__)
            logger.warning(f"Session directory already exists at {self._session_path}. Cannot change device info. Ignoring.")
            return
        
        # Also check if a directory exists for the CURRENT device/app/timestamp combination
        # This catches cases where directory was created but path wasn't cached
        # Use current device info (before updating) to check for existing directory
        try:
            base_dir = self.config.OUTPUT_DATA_DIR
            if base_dir:
                current_device_id = self._device_name or self._device_udid or "unknown_device"
                current_device_id = re.sub(r'[^\w.-]', '_', current_device_id)
                app_package_safe = self._get_app_package_safe()
                potential_path = Path(base_dir) / "sessions" / f"{current_device_id}_{app_package_safe}_{self._timestamp}"
                if potential_path.exists():
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Session directory already exists at {potential_path}. Cannot change device info. Ignoring.")
                    # Update cached path to the existing one
                    self._session_path = potential_path.resolve()
                    return
        except Exception:
            # If check fails, continue - better to allow device info update than block it
            pass
        
        if udid is not None:
            self._device_udid = udid
        if name is not None:
            self._device_name = name
        # Invalidate cached session path to force regeneration with new device info
        # Only if directory doesn't exist yet
        self._session_path = None

    def get_device_udid(self) -> Optional[str]:
        """Get the current device UDID."""
        return self._device_udid

    def get_device_name(self) -> Optional[str]:
        """Get the current device name."""
        return self._device_name

    def get_timestamp(self) -> str:
        """Get the session timestamp."""
        return self._timestamp

    def get_session_path(self, force_regenerate: bool = False) -> Optional[Path]:
        """Resolves and returns the absolute path to the session directory.
        
        Args:
            force_regenerate: If True, force regeneration of the path even if cached.
        """
        # Prefer device name over UDID for folder names (more readable)
        # Fallback: UDID -> unknown_device
        # Use instance variables instead of config.get()
        device_name = self._device_name
        device_udid = self._device_udid
        current_device_id = device_name or device_udid or "unknown_device"
        
        # Sanitize device ID for use in file paths (replace invalid characters)
        current_device_id = re.sub(r'[^\w.-]', '_', current_device_id)
        
        # Lazy path creation: Don't create paths with "unknown_device" - wait for device info
        # If we don't have device info yet, we can still return a path object, but it won't be used
        # to create directories until device info is available
        if current_device_id == "unknown_device" and not force_regenerate:
            # If path was already created, return it (but log a warning)
            if self._session_path:
                logger = logging.getLogger(__name__)
                logger.warning(f"Session path was created before device info was available: {self._session_path}")
                return self._session_path
            # Don't create a path yet - wait for device info to be set
            # This prevents directories from being created with "unknown_device"
            logger = logging.getLogger(__name__)
            logger.debug("Device info not available yet, deferring session path creation. Set device info first.")
            # Return None to indicate device info is not available yet
            # Components should check if device info is available before creating directories
            return None
        
        # If path was already created with "unknown_device" but we now have a real device ID, regenerate
        # BUT only if the directory doesn't exist yet
        if self._session_path and not force_regenerate:
            # Check if directory already exists - if so, don't regenerate
            if self._session_path.exists():
                logger = logging.getLogger(__name__)
                logger.debug(f"Session directory already exists at {self._session_path}, not regenerating path")
                return self._session_path
            
            # Extract device ID from existing path to check if it needs updating
            path_str = str(self._session_path)
            if "unknown_device" in path_str and current_device_id != "unknown_device":
                # Device ID was set after path creation, regenerate the path
                # But only if directory doesn't exist
                self._session_path = None
                logger = logging.getLogger(__name__)
                logger.info(f"Regenerating session path with device ID: {current_device_id} (was: unknown_device)")
        elif force_regenerate:
            # Force regeneration requested - but check if directory exists first
            if self._session_path and self._session_path.exists():
                logger = logging.getLogger(__name__)
                logger.warning(f"Session directory already exists at {self._session_path}, ignoring force_regenerate request")
                return self._session_path
            # Force regeneration requested
            self._session_path = None
            logger = logging.getLogger(__name__)
            logger.debug(f"Force regenerating session path with device ID: {current_device_id}")
        
        if self._session_path and not force_regenerate:
            return self._session_path

        template = self.config.get(SessionKeys.SESSION_DIR_TEMPLATE)
        base_dir = self.config.OUTPUT_DATA_DIR  # This property is already resolved
        assert base_dir is not None, "OUTPUT_DATA_DIR must be set"
        
        device_id = current_device_id
        app_package_safe = self._get_app_package_safe()
        assert self._timestamp is not None

        if not template:
            # Default: sessions/{device_id}_{app_package}_{timestamp}
            session_dir_str = str(Path(base_dir) / "sessions" / f"{device_id}_{app_package_safe}_{self._timestamp}")
        else:
            # Replace placeholders in the template
            # First replace OUTPUT_DATA_DIR placeholder
            template = template.replace(f"{{{SessionKeys.OUTPUT_DATA_DIR_KEY}}}", str(base_dir))
            # Then replace other placeholders
            session_dir_str = template
            session_dir_str = session_dir_str.replace(f"{{{SessionKeys.DEVICE_ID_KEY}}}", device_id)
            session_dir_str = session_dir_str.replace(f"{{{SessionKeys.APP_PACKAGE_KEY}}}", app_package_safe)
            session_dir_str = session_dir_str.replace(f"{{{SessionKeys.TIMESTAMP_KEY}}}", self._timestamp)
            
            # Ensure sessions/ subdirectory is present in the path
            # If the template was somehow stored without sessions/, add it
            base_dir_str = str(base_dir)
            if session_dir_str.startswith(base_dir_str):
                # Check if sessions/ is missing between base_dir and the session name
                remaining = session_dir_str[len(base_dir_str):].lstrip('/\\')
                # If remaining starts directly with device_id pattern (no sessions/), add it
                if remaining and not remaining.startswith('sessions'):
                    # Reconstruct with sessions/ subdirectory
                    session_dir_str = str(Path(base_dir) / "sessions" / f"{device_id}_{app_package_safe}_{self._timestamp}")

        self._session_path = Path(session_dir_str).resolve()
        # Only create parent directories (sessions/) if they don't exist
        # Only create if we have a real device ID (lazy creation - wait for device info)
        
        return self._session_path

    def _resolve_template(self, template_key: str, force_regenerate: bool = False) -> Path:
        """Helper to resolve a path template like DB_NAME, LOG_DIR, etc.
        
        Args:
            template_key: The config key for the template
            force_regenerate: If True, force regeneration of session path before resolving template
        """
        template = self.config.get(template_key)
        session_dir = self.get_session_path(force_regenerate=force_regenerate)  # Ensures session_path is resolved
        
        # If session_dir is None, device info is not available yet
        if session_dir is None:
            logger = logging.getLogger(__name__)
            logger.warning(f"Cannot resolve {template_key}: device info not available. Set device info first.")
            raise RuntimeError(f"Cannot resolve {template_key}: device info not available. Set device info first using set_device_info().")

        if not template:
            raise ValueError(f"Config key {template_key} is not defined.")

        # Replace placeholders
        template = template.replace(f"{{{SessionKeys.OUTPUT_DATA_DIR_KEY}}}", str(self.config.OUTPUT_DATA_DIR))
        template = template.replace(f"{{{SessionKeys.SESSION_DIR_KEY}}}", str(session_dir))
        template = template.replace(f"{{{SessionKeys.PACKAGE_KEY}}}", self._get_app_package_safe())

        return Path(template).resolve()

    # --- Public Path Getters ---
    def get_db_path(self, force_regenerate: bool = False) -> Path:
        return self._resolve_template(SessionKeys.DB_NAME_TEMPLATE, force_regenerate=force_regenerate)

    def get_screenshots_dir(self, force_regenerate: bool = False) -> Path:
        return self._resolve_template(SessionKeys.SCREENSHOTS_DIR_TEMPLATE, force_regenerate=force_regenerate)

    def get_log_dir(self, force_regenerate: bool = False) -> Path:
        return self._resolve_template(SessionKeys.LOG_DIR_TEMPLATE, force_regenerate=force_regenerate)

    def get_annotated_screenshots_dir(self, force_regenerate: bool = False) -> Path:
        return self._resolve_template(SessionKeys.ANNOTATED_SCREENSHOTS_DIR_TEMPLATE, force_regenerate=force_regenerate)

    def get_traffic_capture_dir(self, force_regenerate: bool = False) -> Path:
        return self._resolve_template(SessionKeys.TRAFFIC_CAPTURE_OUTPUT_DIR_TEMPLATE, force_regenerate=force_regenerate)

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