import logging
import os
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

try:
    import utils.utils as utils
except ImportError:
    import utils
try:
    from infrastructure.database import DatabaseManager
except ImportError:
    from database import DatabaseManager

# Import your main Config class
from config.app_config import Config

if TYPE_CHECKING:
    from infrastructure.appium_driver import AppiumDriver

class ScreenRepresentation:
    """Minimal representation of a discovered screen state."""
    def __init__(self,
                 screen_id: int,
                 composite_hash: str,
                 xml_hash: str,
                 visual_hash: str,
                 screenshot_path: Optional[str],
                 activity_name: Optional[str] = None,
                 xml_content: Optional[str] = None,
                 screenshot_bytes: Optional[bytes] = None,
                 first_seen_run_id: Optional[int] = None,
                 first_seen_step_number: Optional[int] = None):
        self.id = screen_id
        self.composite_hash = composite_hash
        self.xml_hash = xml_hash
        self.visual_hash = visual_hash
        self.screenshot_path = screenshot_path
        self.annotated_screenshot_path: Optional[str] = None
        self.activity_name = activity_name
        self.xml_content = xml_content
        self.screenshot_bytes = screenshot_bytes
        self.first_seen_run_id = first_seen_run_id
        self.first_seen_step_number = first_seen_step_number
        self.xml_root_for_mapping: Optional[Any] = None

    def __repr__(self):
        return (f"Screen(id={self.id}, hash='{self.composite_hash[:12]}...', "
                f"activity='{self.activity_name}', path='{os.path.basename(self.screenshot_path) if self.screenshot_path else 'N/A'}')")

class ScreenStateManager:
    """
    Manages screen states, visit counts, and action history for the current crawl run.
    Interacts with DatabaseManager for persistence and AppiumDriver for state capture.
    Uses the centralized Config object for settings.
    """
    def __init__(self, db_manager: DatabaseManager, driver: 'AppiumDriver', app_config: Config):
        self.db_manager = db_manager
        self.driver = driver
        self.cfg = app_config

        required_cfg_attrs = [
            'STABILITY_WAIT', 'VISUAL_SIMILARITY_THRESHOLD',
            'SCREENSHOTS_DIR', 'ANNOTATED_SCREENSHOTS_DIR',
            'APP_PACKAGE', 'APP_ACTIVITY'
        ]
        for attr in required_cfg_attrs:
            val = self.cfg.get(attr, None)
            if val is None:
                if attr == 'VISUAL_SIMILARITY_THRESHOLD' and val == 0: continue # 0 is valid
                if attr == 'ALLOWED_EXTERNAL_PACKAGES' and isinstance(val, list): continue # Empty list is fine
                raise ValueError(f"ScreenStateManager: Config missing or '{attr}' is None.")

        self.current_run_id: Optional[int] = None
        self.current_app_package: str = str(self.cfg.get('APP_PACKAGE'))
        self.current_start_activity: str = str(self.cfg.get('APP_ACTIVITY'))
        self.current_run_latest_step_number: int = 0 # Added attribute

        self.known_screens_cache: Dict[str, ScreenRepresentation] = {}
        self.current_run_visit_counts: Dict[str, int] = {}
        self.current_run_action_history: Dict[str, List[str]] = {}
        self._next_screen_db_id_counter: int = 1
        logging.debug("ScreenStateManager initialized.")

    def initialize_for_run(self, run_id: int, app_package: str, start_activity: str, is_continuation: bool):
        self.current_run_id = run_id
        self.current_app_package = app_package
        self.current_start_activity = start_activity
        self.current_run_visit_counts.clear()
        self.current_run_action_history.clear()
        self.current_run_latest_step_number = 0 # Reset for the run

        self._load_all_known_screens_from_db()
        if is_continuation:
            self._populate_run_specific_history(run_id) # This will set current_run_latest_step_number
            logging.debug(f"ScreenStateManager initialized for CONTINUED Run ID: {run_id}. Known screens: {len(self.known_screens_cache)}. Latest step from history: {self.current_run_latest_step_number}. History for this run populated.")
        else:
            logging.debug(f"ScreenStateManager initialized for NEW Run ID: {run_id}. Known screens: {len(self.known_screens_cache)}. Visit counts/history reset for this run. Latest step set to 0.")

    def _load_all_known_screens_from_db(self):
        self.known_screens_cache.clear()
        max_db_id = 0
        db_screen_rows = self.db_manager.get_all_screens()
        for row_index, row_data in enumerate(db_screen_rows):
            try:
                # Expected: (screen_id, composite_hash, xml_hash, visual_hash, screenshot_path,
                # activity_name, xml_content, first_seen_run_id, first_seen_step_number)
                if len(row_data) < 9:
                    logging.warning(f"Skipping DB screen row due to insufficient columns: {row_data}")
                    continue

                screen_id = int(row_data[0]) if row_data[0] is not None else -1 # Should always be int
                composite_hash = str(row_data[1]) if row_data[1] is not None else ""
                xml_hash = str(row_data[2]) if row_data[2] is not None else ""
                visual_hash = str(row_data[3]) if row_data[3] is not None else ""
                screenshot_path = str(row_data[4]) if row_data[4] is not None else None
                activity_name = str(row_data[5]) if row_data[5] is not None else None
                xml_content = str(row_data[6]) if row_data[6] is not None else None
                first_seen_run_id = int(row_data[7]) if row_data[7] is not None else None
                first_seen_step_number = int(row_data[8]) if row_data[8] is not None else None

                if not composite_hash or screen_id == -1:
                    logging.warning(f"Skipping DB screen row due to missing critical data (ID or composite_hash): {row_data}")
                    continue

                screen = ScreenRepresentation(
                    screen_id=screen_id, composite_hash=composite_hash, xml_hash=xml_hash,
                    visual_hash=visual_hash, screenshot_path=screenshot_path,
                    activity_name=activity_name, xml_content=xml_content,
                    first_seen_run_id=first_seen_run_id,
                    first_seen_step_number=first_seen_step_number
                )
                self.known_screens_cache[screen.composite_hash] = screen
                if screen.id > max_db_id:
                    max_db_id = screen.id
            except (IndexError, ValueError, TypeError) as e:
                logging.error(f"Error processing screen row {row_index} from DB: {row_data}. Error: {e}", exc_info=True)

        self._next_screen_db_id_counter = max_db_id + 1
        logging.debug(f"Loaded {len(self.known_screens_cache)} known screens. Next screen DB ID: {self._next_screen_db_id_counter}")

    def _populate_run_specific_history(self, run_id: int):
        self.current_run_visit_counts.clear()
        self.current_run_action_history.clear()
        steps = self.db_manager.get_steps_for_run(run_id) # Assumes get_steps_for_run exists
        
        max_step_num_for_run = 0
        for step_data in steps:
            # Assuming step_data format from DatabaseManager includes:
            # (step_log_id, run_id, step_number, from_screen_id, to_screen_id, action_description, ...)
            try:
                current_step_number_from_db = step_data[2] if len(step_data) > 2 and step_data[2] is not None else 0
                if current_step_number_from_db > max_step_num_for_run:
                    max_step_num_for_run = current_step_number_from_db

                from_screen_id = step_data[3] if len(step_data) > 3 and step_data[3] is not None else None
                action_desc = step_data[5] if len(step_data) > 5 and step_data[5] is not None else None

                if from_screen_id is not None:
                    from_screen_repr = self.get_screen_by_db_id(from_screen_id)
                    if from_screen_repr and from_screen_repr.composite_hash:
                        from_hash = from_screen_repr.composite_hash
                        self.current_run_visit_counts[from_hash] = self.current_run_visit_counts.get(from_hash, 0) + 1
                        if action_desc:
                            if from_hash not in self.current_run_action_history:
                                self.current_run_action_history[from_hash] = []
                            if action_desc not in self.current_run_action_history[from_hash]:
                                self.current_run_action_history[from_hash].append(action_desc)
            except IndexError as e:
                logging.warning(f"Error processing step data for run history (IndexError): {step_data}. Error: {e}")
            except Exception as e:
                logging.warning(f"Unexpected error processing step data for run history: {step_data}. Error: {e}", exc_info=True)
        
        self.current_run_latest_step_number = max_step_num_for_run # Set the latest step number
        logging.debug(f"Populated visit counts ({len(self.current_run_visit_counts)}) and action history ({len(self.current_run_action_history)}) for Run ID {run_id}. Max step number found: {max_step_num_for_run}.")


    def _get_current_raw_state_from_driver(self) -> Optional[Tuple[bytes, str, str, str]]:
        stability_wait = float(self.cfg.STABILITY_WAIT) # type: ignore
        if stability_wait > 0: time.sleep(stability_wait)
        try:
            screenshot_bytes = self.driver.get_screenshot_bytes()
            page_source = self.driver.get_page_source() or ""
            current_package = self.driver.get_current_package() or "UnknownPackage"
            current_activity = self.driver.get_current_activity() or "UnknownActivity"
            if not screenshot_bytes: logging.error("Failed to get screenshot (None)."); return None
            return screenshot_bytes, page_source, current_package, current_activity
        except Exception as e:
            logging.error(f"Exception getting current raw state from driver: {e}", exc_info=True)
            return None

    def _get_composite_hash(self, xml_hash: str, visual_hash: str) -> str:
        return f"{xml_hash}_{visual_hash}"

    def get_current_screen_representation(self, run_id: int, step_number: int) -> Optional[ScreenRepresentation]:
        raw_state = self._get_current_raw_state_from_driver()
        if not raw_state: return None

        screenshot_bytes, xml_str, pkg, act = raw_state
        xml_hash = utils.calculate_xml_hash(xml_str)
        visual_hash = utils.calculate_visual_hash(screenshot_bytes)
        composite_hash = self._get_composite_hash(xml_hash, visual_hash)

        temp_id = -step_number
        ss_filename = f"screen_run{run_id}_step{step_number}_{visual_hash[:8]}.png"
        ss_path = os.path.join(str(self.cfg.SCREENSHOTS_DIR), ss_filename)

        os.makedirs(str(self.cfg.SCREENSHOTS_DIR), exist_ok=True)

        return ScreenRepresentation(
            screen_id=temp_id, composite_hash=composite_hash, xml_hash=xml_hash, visual_hash=visual_hash,
            screenshot_path=ss_path, activity_name=act, xml_content=xml_str,
            screenshot_bytes=screenshot_bytes, first_seen_run_id=run_id, first_seen_step_number=step_number
        )

    def process_and_record_state(self, candidate_screen: ScreenRepresentation, run_id: int, step_number: int, increment_visit_count: bool = True) -> Tuple[ScreenRepresentation, Dict[str, Any]]:
        final_screen_to_use: Optional[ScreenRepresentation] = None
        is_new_discovery_for_system = False

        if candidate_screen.composite_hash in self.known_screens_cache:
            final_screen_to_use = self.known_screens_cache[candidate_screen.composite_hash]
            logging.debug(f"Exact screen match found in cache: ID {final_screen_to_use.id} (Hash: {final_screen_to_use.composite_hash})")
        else:
            found_similar_screen = None
            similarity_threshold = int(self.cfg.get('VISUAL_SIMILARITY_THRESHOLD')) # type: ignore
            if similarity_threshold >= 0:
                for existing_screen in self.known_screens_cache.values():
                    if candidate_screen.visual_hash not in ["no_image", "hash_error"] and existing_screen.visual_hash not in ["no_image", "hash_error"]:
                        dist = utils.visual_hash_distance(candidate_screen.visual_hash, existing_screen.visual_hash)
                        if dist <= similarity_threshold:
                            logging.debug(f"Screen visually similar (dist={dist}<={similarity_threshold}) to existing Screen ID {existing_screen.id}. Using existing state.")
                            found_similar_screen = existing_screen
                            break

            if found_similar_screen:
                final_screen_to_use = found_similar_screen
            else:
                is_new_discovery_for_system = True
                candidate_screen.id = self._next_screen_db_id_counter

                ss_filename = f"screen_{candidate_screen.id}_{candidate_screen.visual_hash[:8]}.png"
                screenshots_dir = str(self.cfg.SCREENSHOTS_DIR)
                candidate_screen.screenshot_path = os.path.join(screenshots_dir, ss_filename)

                try:
                    if candidate_screen.screenshot_bytes:
                        # Ensure the screenshots directory exists
                        os.makedirs(screenshots_dir, exist_ok=True)
                        with open(candidate_screen.screenshot_path, "wb") as f: f.write(candidate_screen.screenshot_bytes)
                        logging.debug(f"Saved new screen screenshot: {candidate_screen.screenshot_path}")
                    else: raise IOError("Screenshot bytes missing for new screen.")
                except Exception as e:
                    logging.error(f"Failed to save screenshot {candidate_screen.screenshot_path}: {e}", exc_info=True)
                    candidate_screen.screenshot_path = None

                db_id = self.db_manager.insert_screen(
                    composite_hash=candidate_screen.composite_hash, xml_hash=candidate_screen.xml_hash,
                    visual_hash=candidate_screen.visual_hash, screenshot_path=candidate_screen.screenshot_path,
                    activity_name=candidate_screen.activity_name, xml_content=candidate_screen.xml_content,
                    run_id=run_id, step_number=step_number # This step_number is first_seen_step_number
                )
                if db_id is None or db_id != candidate_screen.id :
                    logging.error(f"Failed to insert new screen into DB or ID mismatch. Expected: {candidate_screen.id}, Got from DB: {db_id}")
                    if db_id is not None: candidate_screen.id = db_id
                else: # Success
                    candidate_screen.id = db_id

                self.known_screens_cache[candidate_screen.composite_hash] = candidate_screen
                self._next_screen_db_id_counter = max(self._next_screen_db_id_counter, candidate_screen.id + 1)
                logging.debug(f"Recorded new screen to DB & cache: ID {candidate_screen.id} (Hash: {candidate_screen.composite_hash})")
                final_screen_to_use = candidate_screen

        if not final_screen_to_use:
            logging.critical("CRITICAL: final_screen_to_use was not set. Using candidate as fallback. This indicates a logic flaw.")
            final_screen_to_use = candidate_screen
            if final_screen_to_use.id < 0: # If it's still the temporary ID
                final_screen_to_use.id = self._next_screen_db_id_counter
                self._next_screen_db_id_counter += 1
                logging.warning(f"Assigned emergency ID {final_screen_to_use.id} to fallback screen.")


        hash_for_visit_count = final_screen_to_use.composite_hash
        # Get current visit count before potentially incrementing
        current_visit_count = self.current_run_visit_counts.get(hash_for_visit_count, 0)
        
        # Only increment visit count if requested (to avoid double-counting when called multiple times per step)
        if increment_visit_count:
            self.current_run_visit_counts[hash_for_visit_count] = current_visit_count + 1
            # Use the incremented count for visit_info
            visit_count_for_info = current_visit_count + 1
        else:
            # Use the current count (before incrementing) for visit_info
            visit_count_for_info = current_visit_count

        historical_actions = self.db_manager.get_action_history_for_screen(final_screen_to_use.id)

        visit_info = {
            "screen_representation": final_screen_to_use,
            "is_new_discovery": is_new_discovery_for_system,
            "visit_count_this_run": visit_count_for_info,
            "previous_actions_on_this_state": historical_actions
        }
        logging.debug(f"Processed state for hash {hash_for_visit_count}: ID {final_screen_to_use.id}, NewSystemDiscovery={is_new_discovery_for_system}, RunVisits={visit_info['visit_count_this_run']}")
        return final_screen_to_use, visit_info

    def record_action_taken_from_screen(self, from_screen_composite_hash: str, action_description: str):
        if from_screen_composite_hash not in self.current_run_action_history:
            self.current_run_action_history[from_screen_composite_hash] = []
        if action_description not in self.current_run_action_history[from_screen_composite_hash]:
            self.current_run_action_history[from_screen_composite_hash].append(action_description)
        logging.debug(f"Recorded action '{action_description}' for screen hash '{from_screen_composite_hash}' in current run history.")

    def get_action_history_for_run(self, screen_composite_hash: str) -> List[str]:
        return self.current_run_action_history.get(screen_composite_hash, [])

    def get_visit_count_for_run(self, screen_composite_hash: str) -> int:
        return self.current_run_visit_counts.get(screen_composite_hash, 0)
        
    def get_visit_count(self, screen_composite_hash: str) -> int:
        """Get the total visit count for a screen across all runs."""
        if not self.db_manager:
            return self.get_visit_count_for_run(screen_composite_hash)
            
        try:
            # Get the total visit count from the database
            total_count = self.db_manager.get_screen_visit_count(screen_composite_hash)
            # Add the current run's visit count
            run_count = self.get_visit_count_for_run(screen_composite_hash)
            return total_count + run_count
        except Exception as e:
            logging.error(f"Error getting visit count from database: {e}")
            return self.get_visit_count_for_run(screen_composite_hash)

    def get_total_unique_screens_in_cache(self) -> int:
        return len(self.known_screens_cache)

    def get_screen_by_composite_hash(self, composite_hash: str) -> Optional[ScreenRepresentation]:
        return self.known_screens_cache.get(composite_hash)

    def get_screen_by_db_id(self, screen_id: Optional[int]) -> Optional[ScreenRepresentation]:
        if screen_id is None: return None
        for screen in self.known_screens_cache.values():
            if screen.id == screen_id:
                return screen
        logging.warning(f"Screen with DB ID {screen_id} not found in current cache. Consider reloading cache or checking data integrity.")
        return None
