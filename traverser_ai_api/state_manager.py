import logging
import os
from typing import Optional, Dict, List, Tuple, Set

# Assuming config.py and utils.py exist and are relevant
from . import config
from . import utils
# Import only DatabaseManager from database.py
from .database import DatabaseManager

# *** Define ScreenRepresentation class here ***
class ScreenRepresentation:
    """Minimal representation of a discovered screen state (in-memory structure)."""
    def __init__(self, screen_id: int, xml_hash: str, visual_hash: str, screenshot_path: str):
        self.id = screen_id
        self.xml_hash = xml_hash
        self.visual_hash = visual_hash
        self.screenshot_path = screenshot_path
        # Composite hash can be derived when needed or stored if preferred,
        # but base attributes are essential.

    def get_composite_hash(self) -> str:
        """Helper to get the standard composite hash."""
        # Consistent with CrawlingState._get_composite_hash
        return f"{self.xml_hash}_{self.visual_hash}"

    def __repr__(self):
        # Provide a more informative representation
        return f"Screen(id={self.id}, xml_hash='{self.xml_hash[:8]}...', vhash='{self.visual_hash}', path='{self.screenshot_path}')"
# *********************************************


class CrawlingState:
    """
    Manages the state of the crawling process, including visited screens,
    transitions, and visit counts for loop detection within the current run.
    Uses ScreenRepresentation for in-memory objects.
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        # --- Data Structures ---
        # Stores ScreenRepresentation objects, keyed by composite_hash
        self.screens: Dict[str, ScreenRepresentation] = {}

        # List of transitions loaded from DB (source_hash, action_desc, dest_hash)
        # Primarily for context/debugging if needed after loading.
        self.transitions_loaded: List[Tuple[str, str, Optional[str]]] = []

        # History of actions performed *from* a specific screen state *during this run*.
        # Key: composite_hash, Value: List of action descriptions attempted.
        self.action_history_per_screen: Dict[str, List[str]] = {}

        # In-memory state for the current run (not saved to DB by default)
        self.current_run_visit_counts: Dict[str, int] = {} # Map composite_hash -> visit count *this session*
        self.visited_screen_hashes: Set[str] = set() # Set of composite_hashes seen (loaded from DB screens)

        # Internal state
        self._next_screen_id = 1 # Tracks the next available numeric ID for *new* screens

        # --- Initialization ---
        self._load_state_from_db() # Initialize persistent state from DB

    def _get_composite_hash(self, xml_hash: str, visual_hash: str) -> str:
         """Combines XML and visual hash for a screen identifier."""
         # Ensure consistency with ScreenRepresentation.get_composite_hash if used
         return f"{xml_hash}_{visual_hash}"

    def _load_state_from_db(self):
        """Loads existing screens and transitions from the database to populate internal state."""
        if not self.db_manager:
            logging.warning("No database manager provided, cannot load state.")
            return

        logging.info("Loading previous state from database...")
        self.screens.clear()
        self.transitions_loaded.clear()
        self.action_history_per_screen.clear()
        self.visited_screen_hashes.clear()
        self.current_run_visit_counts.clear() # Ensure visit counts reset on load

        # 1. Load Screens
        # Assumes db_manager.get_all_screens() returns list of tuples like (screen_id, xml_hash, visual_hash, path)
        # This matches the current DatabaseManager.get_all_screens() definition.
        db_screens_data = self.db_manager.get_all_screens()
        max_id_loaded = 0
        loaded_screen_count = 0
        for screen_data_tuple in db_screens_data:
            if len(screen_data_tuple) == 4:
                db_id, xml_h, visual_h, path = screen_data_tuple
            else:
                logging.error(f"Unexpected data format from get_all_screens(): {screen_data_tuple}. Skipping.")
                continue

            # Create the ScreenRepresentation object
            screen_repr_obj = ScreenRepresentation(db_id, xml_h, visual_h, path)
            comp_hash = screen_repr_obj.get_composite_hash() # Use method for consistency

            # Store the object in the dictionary
            self.screens[comp_hash] = screen_repr_obj
            self.visited_screen_hashes.add(comp_hash) # Add hash to the set of known hashes
            loaded_screen_count += 1

            if db_id > max_id_loaded:
                max_id_loaded = db_id

        # Set the next available ID based on loaded data
        self._next_screen_id = max_id_loaded + 1
        logging.info(f"Loaded {loaded_screen_count} screens from DB. Next available Screen ID for *new* screens: {self._next_screen_id}")

        # 2. Load Transitions (primarily to build action history for existing screens)
        # Assumes db_manager.get_all_transitions() returns list of tuples like (source_hash, action_desc, dest_hash)
        db_transitions_data = self.db_manager.get_all_transitions()
        loaded_transition_count = 0
        for trans_data_tuple in db_transitions_data:
             if len(trans_data_tuple) == 3:
                 src_h, act_desc, dest_h = trans_data_tuple
             else:
                 logging.error(f"Unexpected data format from get_all_transitions(): {trans_data_tuple}. Skipping.")
                 continue

             # Add to internal list (optional, for debugging/context)
             self.transitions_loaded.append((src_h, act_desc, dest_h))
             loaded_transition_count += 1

             # Populate action history for the source screen IF that screen was loaded
             if src_h in self.screens: # Check if the source hash exists in our loaded screens
                 if src_h not in self.action_history_per_screen:
                      self.action_history_per_screen[src_h] = []
                 # Avoid adding duplicate actions loaded from DB for the same screen history
                 if act_desc not in self.action_history_per_screen[src_h]:
                      self.action_history_per_screen[src_h].append(act_desc)
             else:
                  logging.warning(f"Transition loaded with source hash '{src_h}' which doesn't match any loaded screen. History for this transition ignored.")

        logging.info(f"Loaded {loaded_transition_count} transitions from DB and populated action history.")
        # Reminder: current_run_visit_counts remains empty after loading.

    def add_or_get_screen(self, xml_hash: str, visual_hash: str, screenshot_bytes: bytes) -> ScreenRepresentation:
        """
        Adds a new screen if not seen (or visually similar), saves screenshot,
        increments current run visit count for the *actual* state being used,
        and returns the correct ScreenRepresentation.
        Handles visual similarity checks properly.
        """
        exact_composite_hash = self._get_composite_hash(xml_hash, visual_hash)
        # Variables to hold the final screen representation and its hash
        target_composite_hash = exact_composite_hash
        screen_to_return = None
        found_similar = False

        # --- Visual Similarity Check ---
        similarity_threshold = getattr(config, 'VISUAL_SIMILARITY_THRESHOLD', 5)
        if similarity_threshold >= 0:
            for existing_hash, existing_screen_repr in self.screens.items(): # Rename loop var
                try:
                    # Perform comparison only if hashes are valid
                    if visual_hash and existing_screen_repr.visual_hash and \
                       "error" not in visual_hash and "error" not in existing_screen_repr.visual_hash and \
                       "no_image" not in visual_hash and "no_image" not in existing_screen_repr.visual_hash:

                        dist = utils.visual_hash_distance(visual_hash, existing_screen_repr.visual_hash)
                        if dist <= similarity_threshold:
                            logging.info(f"Screen visually similar (dist={dist} <= {similarity_threshold}) to existing Screen ID {existing_screen_repr.id} (Hash: {existing_hash}). Using existing state.")
                            # --- FIX: Use the MATCHED screen's info ---
                            target_composite_hash = existing_hash         # Use the hash of the matched screen
                            screen_to_return = existing_screen_repr     # Set the object to return
                            found_similar = True
                            # -----------------------------------------
                            break # Found a similar match, stop checking
                    # else: (Optional: log skipping invalid hash comparison)
                except Exception as e:
                    logging.warning(f"Error during visual hash comparison for {visual_hash} and {existing_screen_repr.visual_hash}: {e}")

        # --- Increment Visit Count (using the determined target_composite_hash) ---
        self.current_run_visit_counts[target_composite_hash] = self.current_run_visit_counts.get(target_composite_hash, 0) + 1
        # Log the visit count *for the hash being used* (either exact or similar)
        logging.debug(f"Visit count for hash '{target_composite_hash}' updated to: {self.current_run_visit_counts[target_composite_hash]}")

        # --- Return Existing or Create New ---
        if screen_to_return: # This is set if found_similar is True
            logging.debug(f"Returning existing (visually similar) Screen state ID: {screen_to_return.id}")
            return screen_to_return
        elif exact_composite_hash in self.screens: # Check if exact match exists (and wasn't visually similar)
            logging.debug(f"Screen state (exact hash) {exact_composite_hash} already known (ID: {self.screens[exact_composite_hash].id}). Returning existing.")
            # Increment visit count again? No, already done above using target_composite_hash which was exact_composite_hash in this case.
            return self.screens[exact_composite_hash]
        else:
            # --- Screen is genuinely new ---
            logging.info(f"Creating new screen state record for hash: {exact_composite_hash}")
            new_id = self._next_screen_id
            self._next_screen_id += 1

            # Save screenshot
            screenshot_dir = getattr(config, 'SCREENSHOTS_DIR', 'screenshots')
            os.makedirs(screenshot_dir, exist_ok=True)
            screenshot_filename = f"screen_{new_id}_{visual_hash}.png" # Use visual hash in name
            screenshot_path = os.path.join(screenshot_dir, screenshot_filename)
            try:
                with open(screenshot_path, "wb") as f: f.write(screenshot_bytes)
                logging.info(f"Saved new screen screenshot: {screenshot_path}")
            except Exception as e:
                logging.error(f"Failed to save screenshot {screenshot_path}: {e}", exc_info=True)
                screenshot_path = "save_error"

            # Create ScreenRepresentation object for the new screen
            new_screen_repr = ScreenRepresentation(new_id, xml_hash, visual_hash, screenshot_path)

            # Store using the EXACT composite hash
            self.screens[exact_composite_hash] = new_screen_repr
            self.visited_screen_hashes.add(exact_composite_hash)
            # Initialize action history and visit count (visit count already done above for this hash)
            if exact_composite_hash not in self.action_history_per_screen:
                self.action_history_per_screen[exact_composite_hash] = []

            # Save to database
            if self.db_manager:
                try:
                    db_result_hash = self.db_manager.insert_screen(
                        screen_id=new_id, xml_hash=xml_hash, visual_hash=visual_hash, screenshot_path=screenshot_path
                    )
                    # Optional: Check if db_result_hash matches exact_composite_hash for consistency
                    if db_result_hash != exact_composite_hash:
                        logging.warning(f"DB insert/ignore hash '{db_result_hash}' differs from expected '{exact_composite_hash}'.")
                except Exception as db_err:
                     logging.error(f"Database error adding screen ID {new_id}: {db_err}", exc_info=True)

            logging.info(f"Added new screen state (ID: {new_id}, Exact Hash: {exact_composite_hash}).")
            return new_screen_repr

    # --- Keep add_transition, get_action_history, get_visit_count, etc. as they were ---
    def add_transition(self, source_hash: str, action_desc: str, dest_hash: Optional[str]):
        # ... (Keep existing implementation) ...
        if not source_hash: logging.warning("Add transition missing source_hash."); return
        dest_hash_str = dest_hash if dest_hash is not None else "UNKNOWN_DEST"
        # Update Action History (for the current run)
        if source_hash in self.action_history_per_screen:
            if action_desc not in self.action_history_per_screen[source_hash]:
                 self.action_history_per_screen[source_hash].append(action_desc)
                 logging.debug(f"Added '{action_desc}' to history for {source_hash}")
        else: logging.warning(f"Source hash '{source_hash}' not found in history. Initializing."); self.action_history_per_screen[source_hash] = [action_desc]
        # Save to Database
        if self.db_manager:
            try: self.db_manager.insert_transition(source_hash=source_hash, action_desc=action_desc, dest_hash=dest_hash_str)
            except Exception as db_err: logging.error(f"DB error adding transition {source_hash} -> {dest_hash_str}: {db_err}", exc_info=True)

    def get_action_history(self, screen_hash: str) -> List[str]:
        return self.action_history_per_screen.get(screen_hash, [])



    def get_total_screens(self) -> int:
        return len(self.screens)

    def get_total_transitions(self) -> int:
        if self.db_manager:
            try: return self.db_manager.get_total_transitions()
            except Exception as e: logging.error(f"Failed get total transitions from DB: {e}"); return -1
        else: return 0

    def get_screen_by_hash(self, composite_hash: str) -> Optional[ScreenRepresentation]:
        return self.screens.get(composite_hash)

    def add_transition(self, source_hash: str, action_desc: str, dest_hash: Optional[str]):
        """Records a transition between screen states in memory (action history) and database."""
        if not source_hash:
             logging.warning("Attempted to add transition with no source_hash.")
             return

        dest_hash_str = dest_hash if dest_hash is not None else "UNKNOWN_DEST"

        # Update Action History (for the current run)
        if source_hash in self.action_history_per_screen:
            if action_desc not in self.action_history_per_screen[source_hash]:
                 self.action_history_per_screen[source_hash].append(action_desc)
                 logging.debug(f"Added '{action_desc}' to action history for {source_hash}")
            # else: # Log less verbosely if action already exists
            #      logging.debug(f"Action '{action_desc}' already in history for {source_hash} this run.")
        else:
            # Should ideally not happen if add_or_get_screen was called first, but handle defensively
            logging.warning(f"Source hash '{source_hash}' not found in action history when adding transition. Initializing history.")
            self.action_history_per_screen[source_hash] = [action_desc]

        # Save to Database
        if self.db_manager:
            try:
                 # Use the insert_transition method
                 transition_id = self.db_manager.insert_transition(
                    source_hash=source_hash,
                    action_desc=action_desc,
                    dest_hash=dest_hash_str
                 )
                 if transition_id is not None:
                     logging.debug(f"Saved transition to DB (ID: {transition_id}): {source_hash} --[{action_desc}]--> {dest_hash_str}")
                 else:
                     # insert_transition might return None on failure depending on implementation
                     logging.error(f"Database manager failed to add transition: {source_hash} -> {dest_hash_str}")
            except Exception as db_err:
                logging.error(f"Database error adding transition {source_hash} -> {dest_hash_str}: {db_err}", exc_info=True)


    def get_action_history(self, screen_hash: str) -> List[str]:
        """Gets the list of actions already attempted FROM a given screen state during this run."""
        return self.action_history_per_screen.get(screen_hash, [])

    def get_visit_count(self, screen_hash: str) -> int:
        """Gets the visit count for the given screen state *during the current run*."""
        return self.current_run_visit_counts.get(screen_hash, 0)



    def get_total_screens(self) -> int:
        """Gets the total number of unique screen states discovered (in memory)."""
        return len(self.screens)

    def get_total_transitions(self) -> int:
        """Gets the total number of transitions recorded *in the database*."""
        if self.db_manager:
            try:
                # Assuming DatabaseManager has a method to count transitions
                # If not, add one: e.g., SELECT COUNT(*) FROM transitions
                # For now, let's assume it exists or approximate with loaded count + new ones
                # return self.db_manager.get_total_transitions_count() # Ideal
                # Fallback: Return count loaded + count added this run (less accurate if multiple runs)
                sql = f"SELECT COUNT(*) FROM {self.db_manager.TRANSITIONS_TABLE}"
                result = self.db_manager._execute_sql(sql, fetch_one=True)
                return result[0] if result else 0

            except Exception as e:
                logging.error(f"Failed to get total transitions count from DB: {e}")
                return -1 # Indicate error
        else:
            return 0

    def get_screen_by_hash(self, composite_hash: str) -> Optional[ScreenRepresentation]:
        """Gets the ScreenRepresentation object by its composite hash."""
        return self.screens.get(composite_hash)