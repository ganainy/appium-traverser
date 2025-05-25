import logging
import os
import time # Added for _get_current_state
from typing import Optional, Dict, List, Tuple, Set, TYPE_CHECKING

from . import config # Assuming config.py and utils.py exist and are relevant
from . import utils
from .database import DatabaseManager

if TYPE_CHECKING:
    from .appium_driver import AppiumDriver # For type hinting

class ScreenRepresentation:
    """Minimal representation of a discovered screen state (in-memory structure)."""
    def __init__(self, screen_id: int, xml_hash: str, visual_hash: str, screenshot_path: str):
        self.id = screen_id
        self.xml_hash = xml_hash
        self.visual_hash = visual_hash
        self.screenshot_path = screenshot_path # Path to the original screenshot
        self.annotated_screenshot_path: Optional[str] = None # Path to the annotated screenshot

    def get_composite_hash(self) -> str:
        """Helper to get the standard composite hash."""
        return f"{self.xml_hash}_{self.visual_hash}"

    def __repr__(self):
        return f"Screen(id={self.id}, xml_hash=\'{self.xml_hash[:8]}...\', vhash=\'{self.visual_hash}\', path=\'{self.screenshot_path}\')"

class ScreenStateManager:
    """
    Manages the state of the crawling process, including visited screens,
    transitions, and visit counts for loop detection within the current run.
    Uses ScreenRepresentation for in-memory objects.
    Also handles fetching the current screen state (screenshot and XML).
    """

    def __init__(self, db_manager: DatabaseManager, driver: 'AppiumDriver', config_dict: dict):
        self.db_manager = db_manager
        self.driver = driver # Added driver instance
        
        # Validate config_dict
        if config_dict is None:
            raise ValueError("config_dict cannot be None. Expected a dictionary.")
        if not isinstance(config_dict, dict):
            raise ValueError(f"config_dict must be a dictionary. Got {type(config_dict)} instead.")
        
        self.config_dict = config_dict # Added config_dict instance

        # --- Run-specific Info ---
        self.start_activity: Optional[str] = None
        self.app_package: Optional[str] = None
        self.current_step_number: int = 0
        # --- Data Structures ---
        self.screens: Dict[str, ScreenRepresentation] = {}
        self.transitions_loaded: List[Tuple[str, str, Optional[str]]] = []
        self.action_history_per_screen: Dict[str, List[str]] = {}
        self.current_run_visit_counts: Dict[str, int] = {}
        self.visited_screen_hashes: Set[str] = set()
        self._next_screen_id = 1    
        
    def get_current_state(self) -> Optional[Tuple[bytes, str]]:
            
        """Gets the current screenshot bytes and page source."""
        # Add stability wait *before* getting state
        stability_wait = self.config_dict.get('STABILITY_WAIT')
        if stability_wait is None:
            logging.error("Configuration error: 'STABILITY_WAIT' not defined in config")
            return None
        try:
            stability_wait_float = float(stability_wait)
            time.sleep(stability_wait_float)
        except (ValueError, TypeError):
            logging.error(f"Invalid STABILITY_WAIT value in config: {stability_wait}")
            return None

        try:
            screenshot_bytes = self.driver.get_screenshot_bytes() # Use self.driver
            page_source = self.driver.get_page_source() # Use self.driver

            if screenshot_bytes is None or page_source is None:
                logging.error("Failed to get current screen state (screenshot or XML is None).")
                return None
            return screenshot_bytes, page_source
        except Exception as e:
            logging.error(f"Exception getting current state: {e}", exc_info=True)
            return None

    def initialize_run(self, start_activity: str, app_package: str):
        """Initializes state for a new crawling run."""
        self.start_activity = start_activity
        self.app_package = app_package
        self.current_step_number = 0
        self.screens.clear()
        self.transitions_loaded.clear()
        self.action_history_per_screen.clear()
        self.current_run_visit_counts.clear()
        self.visited_screen_hashes.clear()
        self._next_screen_id = 1
        logging.info(f"ScreenStateManager initialized for a new run. Start activity: {self.start_activity}, App: {self.app_package}")

    def _get_composite_hash(self, xml_hash: str, visual_hash: str) -> str:
         """Combines XML and visual hash for a screen identifier."""
         return f"{xml_hash}_{visual_hash}"

    def load_from_db(self) -> bool:
        """Loads existing screens and transitions from the database to populate internal state.
        Returns True if any screens were loaded, False otherwise.
        """
        if not self.db_manager:
            logging.warning("No database manager provided, cannot load state.")
            return False

        logging.info("Loading previous state from database for ScreenStateManager...")
        self.screens.clear()
        self.transitions_loaded.clear()
        self.action_history_per_screen.clear()
        self.visited_screen_hashes.clear()
        self.current_run_visit_counts.clear() 

        db_screens_data = self.db_manager.get_all_screens()
        max_id_loaded = 0
        loaded_screen_count = 0
        for screen_data_tuple in db_screens_data:
            if len(screen_data_tuple) == 4:
                db_id, xml_h, visual_h, path = screen_data_tuple
            else:
                logging.error(f"Unexpected data format from get_all_screens(): {screen_data_tuple}. Skipping.")
                continue

            screen_repr_obj = ScreenRepresentation(db_id, xml_h, visual_h, path)
            comp_hash = screen_repr_obj.get_composite_hash()

            self.screens[comp_hash] = screen_repr_obj
            self.visited_screen_hashes.add(comp_hash)
            loaded_screen_count += 1

            if db_id > max_id_loaded:
                max_id_loaded = db_id

        self._next_screen_id = max_id_loaded + 1
        logging.info(f"Loaded {loaded_screen_count} screens from DB. Next available Screen ID for *new* screens: {self._next_screen_id}")

        db_transitions_data = self.db_manager.get_all_transitions()
        loaded_transition_count = 0
        for trans_data_tuple in db_transitions_data:
             if len(trans_data_tuple) == 3:
                 src_h, act_desc, dest_h = trans_data_tuple
             else:
                 logging.error(f"Unexpected data format from get_all_transitions(): {trans_data_tuple}. Skipping.")
                 continue

             self.transitions_loaded.append((src_h, act_desc, dest_h))
             loaded_transition_count += 1

             if src_h in self.screens: 
                 if src_h not in self.action_history_per_screen:
                      self.action_history_per_screen[src_h] = []
                 if act_desc not in self.action_history_per_screen[src_h]:
                      self.action_history_per_screen[src_h].append(act_desc)
             else:
                  logging.warning(f"Transition loaded with source hash \'{src_h}\' which doesn\'t match any loaded screen. History for this transition ignored.")

        logging.info(f"Loaded {loaded_transition_count} transitions from DB and populated action history.")

        if loaded_screen_count > 0:
            self.current_step_number = max_id_loaded 
            logging.info(f"State loaded. Current step number estimated to: {self.current_step_number}")
            return True
        else:
            self.current_step_number = 0
            logging.info("No screens found in DB to load state from.")
            return False

    def add_or_get_screen_representation(self, xml_hash: str, visual_hash: str, screenshot_bytes: bytes) -> Tuple[Optional[ScreenRepresentation], bool]:
        """
        Adds a new screen if not seen (or visually similar), saves screenshot,
        increments current run visit count for the *actual* state being used,
        and returns the correct ScreenRepresentation and a boolean indicating if it was a new screen.
        Handles visual similarity checks properly.
        """       
        exact_composite_hash = self._get_composite_hash(xml_hash, visual_hash)
        target_composite_hash = exact_composite_hash
        screen_to_return: Optional[ScreenRepresentation] = None
        found_similar = False
        is_new_screen = False
        
        similarity_threshold = self.config_dict.get('VISUAL_SIMILARITY_THRESHOLD')
        try:
            similarity_threshold = int(similarity_threshold) if similarity_threshold is not None else None
        except (ValueError, TypeError):
            logging.error(f"Invalid VISUAL_SIMILARITY_THRESHOLD in config: {similarity_threshold}")
            similarity_threshold = None

        # Only check for visual similarity if we have a valid threshold
        if similarity_threshold is not None and similarity_threshold >= 0:
            for existing_hash, existing_screen_repr in self.screens.items():
                try:
                    if visual_hash and existing_screen_repr.visual_hash and \
                       "error" not in visual_hash and "error" not in existing_screen_repr.visual_hash and \
                       "no_image" not in visual_hash and "no_image" not in existing_screen_repr.visual_hash:

                        dist = utils.visual_hash_distance(visual_hash, existing_screen_repr.visual_hash)
                        if dist <= similarity_threshold:
                            logging.info(f"Screen visually similar (dist={dist} <= {similarity_threshold}) to existing Screen ID {existing_screen_repr.id} (Hash: {existing_hash}). Using existing state.")
                            target_composite_hash = existing_hash
                            screen_to_return = existing_screen_repr
                            found_similar = True
                            break
                except Exception as e:
                    logging.warning(f"Error during visual hash comparison for {visual_hash} and {existing_screen_repr.visual_hash}: {e}")

        # Increment visit count for the target state
        self.current_run_visit_counts[target_composite_hash] = self.current_run_visit_counts.get(target_composite_hash, 0) + 1
        logging.debug(f"Visit count for hash '{target_composite_hash}' updated to: {self.current_run_visit_counts[target_composite_hash]}")
        
        if screen_to_return:
            return screen_to_return, False
        elif exact_composite_hash in self.screens:
            return self.screens[exact_composite_hash], False
        else:
            # Create new screen
            is_new_screen = True
            new_id = self._next_screen_id
            self._next_screen_id += 1
              # Save screenshot
            screenshot_dir = self.config_dict.get('SCREENSHOTS_DIR')
            if screenshot_dir is None:
                logging.error("Configuration error: 'SCREENSHOTS_DIR' not defined in config")
                return None, False  # Cannot proceed without a valid screenshots directory

            os.makedirs(screenshot_dir, exist_ok=True)
            screenshot_filename = f"screen_{new_id}_{visual_hash}.png"
            screenshot_path = os.path.join(screenshot_dir, screenshot_filename)
            try:
                with open(screenshot_path, "wb") as f:
                    f.write(screenshot_bytes)
                logging.info(f"Saved new screen screenshot: {screenshot_path}")
            except Exception as e:
                logging.error(f"Failed to save screenshot {screenshot_path}: {e}", exc_info=True)
                screenshot_path = "save_error"

            new_screen_repr = ScreenRepresentation(new_id, xml_hash, visual_hash, screenshot_path)
            self.screens[exact_composite_hash] = new_screen_repr

            # Update tracking sets/dicts
            self.visited_screen_hashes.add(exact_composite_hash)
            if exact_composite_hash not in self.action_history_per_screen:
                self.action_history_per_screen[exact_composite_hash] = []

            # Save to DB if available
            if self.db_manager:
                try:
                    db_result_hash = self.db_manager.insert_screen(
                        screen_id=new_id,
                        xml_hash=xml_hash,
                        visual_hash=visual_hash,
                        screenshot_path=screenshot_path
                    )
                    if db_result_hash != exact_composite_hash:
                        logging.warning(f"DB insert/ignore hash '{db_result_hash}' differs from expected '{exact_composite_hash}'.")
                except Exception as db_err:
                    logging.error(f"Database error adding screen ID {new_id}: {db_err}", exc_info=True)

            logging.info(f"Added new screen state (ID: {new_id}, Hash: {exact_composite_hash}).")
            return new_screen_repr, is_new_screen

    def increment_step(self, 
                         action_description: str, 
                         action_type: str, 
                         target_identifier: Optional[str], 
                         target_element_id: Optional[str], 
                         target_center_x: Optional[int], 
                         target_center_y: Optional[int], 
                         input_text: Optional[str], 
                         ai_raw_output: Optional[str]):
        self.current_step_number += 1
        logging.info(f"Step: {self.current_step_number} | Action: {action_description} | Type: {action_type} | Target: {target_identifier or target_element_id or 'N/A'}")

    def add_transition(self, source_hash: str, action_desc: str, dest_hash: Optional[str]):
        if not source_hash:
             logging.warning("Attempted to add transition with no source_hash.")
             return

        dest_hash_str = dest_hash if dest_hash is not None else "UNKNOWN_DEST"

        if source_hash not in self.action_history_per_screen:
            self.action_history_per_screen[source_hash] = []
        
        if action_desc not in self.action_history_per_screen[source_hash]:
             self.action_history_per_screen[source_hash].append(action_desc)
             logging.debug(f"Added \'{action_desc}\' to action history for {source_hash}")
        
        if self.db_manager:
            try:
                 transition_id = self.db_manager.insert_transition(
                    source_hash=source_hash,
                    action_desc=action_desc,
                    dest_hash=dest_hash_str
                 )
                 if transition_id is not None:
                     logging.debug(f"Saved transition to DB (ID: {transition_id}): {source_hash} --[{action_desc}]--> {dest_hash_str}")
                 else:
                     logging.error(f"Database manager failed to add transition: {source_hash} -> {dest_hash_str}")
            except Exception as db_err:
                logging.error(f"Database error adding transition {source_hash} -> {dest_hash_str}: {db_err}", exc_info=True)

    def get_action_history(self, screen_hash: str) -> List[str]:
        return self.action_history_per_screen.get(screen_hash, [])

    def get_visit_count(self, screen_hash: str) -> int:
        return self.current_run_visit_counts.get(screen_hash, 0)

    def get_total_screens(self) -> int:
        return len(self.screens)    
    
    def get_total_transitions(self) -> int:
        """Gets the total number of transitions recorded in the database.
        
        Returns:
            int: The number of transitions, or -1 if there was an error, or 0 if no database.
        """
        if self.db_manager:
            try:
                # Ensure TRANSITIONS_TABLE is accessible
                sql = f"SELECT COUNT(*) FROM {getattr(self.db_manager, 'TRANSITIONS_TABLE', 'transitions')}"
                result = self.db_manager._execute_sql(sql, fetch_one=True)
                
                # Handle the various possible return types
                if result is None:
                    return 0
                if isinstance(result, tuple) and len(result) > 0:
                    count = result[0]
                    return count if isinstance(count, int) else 0
                if isinstance(result, list) and len(result) > 0:
                    count = result[0]
                    return count if isinstance(count, int) else 0
                if isinstance(result, int):
                    return result
                    
                logging.warning(f"Unexpected result type from database query: {type(result)}")
                return 0
            except Exception as e:
                logging.error(f"Failed to get total transitions count from DB: {e}")
                return -1 
        return 0

    def get_screen_by_hash(self, composite_hash: str) -> Optional[ScreenRepresentation]:
        return self.screens.get(composite_hash)

