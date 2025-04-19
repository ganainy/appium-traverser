import logging
import os
from typing import Optional, Dict, List, Tuple, Set

import config # Import config module
import utils # Import utils module

class ScreenRepresentation:
    """Minimal representation of a discovered screen state."""
    def __init__(self, screen_id: int, xml_hash: str, visual_hash: str, screenshot_path: str):
        self.id = screen_id
        self.xml_hash = xml_hash
        self.visual_hash = visual_hash
        self.screenshot_path = screenshot_path

    def __repr__(self):
        return f"Screen(id={self.id}, vhash={self.visual_hash})"

class CrawlingState:
    """Manages the state of the crawling process."""

    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.screens: Dict[str, ScreenRepresentation] = {} # Map composite_hash -> ScreenRepresentation
        self.transitions: List[Tuple[str, str, Optional[str]]] = [] # List of (source_hash, action_desc, dest_hash)
        # Track actions attempted on each unique screen state to guide AI
        self.action_history_per_screen: Dict[str, List[str]] = {} # Map composite_hash -> List[action_description]
        self.visited_screen_hashes: Set[str] = set() # For faster checking if screen was seen
        self._next_screen_id = 1
        self._load_state_from_db() # Initialize state from DB if exists

    def _get_composite_hash(self, xml_hash: str, visual_hash: str) -> str:
         """Combines XML and visual hash for a more unique screen identifier."""
         # Simple concatenation, could be more complex
         return f"{xml_hash}_{visual_hash}"

    def _load_state_from_db(self):
        """Loads existing screens and transitions from the database."""
        if not self.db_manager: return
        logging.info("Loading previous state from database...")
        # Load Screens
        db_screens = self.db_manager.get_all_screens()
        max_id = 0
        for db_id, xml_h, visual_h, path in db_screens:
             comp_hash = self._get_composite_hash(xml_h, visual_h)
             self.screens[comp_hash] = ScreenRepresentation(db_id, xml_h, visual_h, path)
             self.visited_screen_hashes.add(comp_hash)
             if db_id > max_id:
                 max_id = db_id
        self._next_screen_id = max_id + 1
        logging.info(f"Loaded {len(self.screens)} screens from DB. Next ID: {self._next_screen_id}")

        # Load Transitions (and populate action history)
        db_transitions = self.db_manager.get_all_transitions()
        for src_h, act_desc, dest_h in db_transitions:
            self.transitions.append((src_h, act_desc, dest_h))
            # Populate history (if source hash exists)
            if src_h in self.action_history_per_screen:
                # Avoid adding duplicates if DB somehow has them
                if act_desc not in self.action_history_per_screen[src_h]:
                     self.action_history_per_screen[src_h].append(act_desc)
            else:
                 # Check if src_h corresponds to a known screen hash before initializing
                 # This check might be redundant if DB integrity is maintained
                 is_known_source = any(s.xml_hash + "_" + s.visual_hash == src_h for s in self.screens.values())
                 if is_known_source:
                     self.action_history_per_screen[src_h] = [act_desc]
                 else:
                     logging.warning(f"Transition loaded with unknown source hash: {src_h}. Skipping history population for this entry.")

        logging.info(f"Loaded {len(self.transitions)} transitions from DB.")


    def add_or_get_screen(self, xml_hash: str, visual_hash: str, screenshot_bytes: bytes) -> ScreenRepresentation:
        """Adds a new screen if not seen, or returns existing one. Saves screenshot."""
        composite_hash = self._get_composite_hash(xml_hash, visual_hash)

        # Check for visually similar screens first
        # This helps consolidate minor XML changes that don't affect appearance significantly
        for existing_hash, screen_repr in self.screens.items():
             dist = utils.visual_hash_distance(visual_hash, screen_repr.visual_hash)
             if dist <= config.VISUAL_SIMILARITY_THRESHOLD:
                 logging.info(f"Screen visually similar (dist={dist}) to existing Screen {screen_repr.id}. Using existing.")
                 # Should we update the XML hash if it changed slightly? Maybe not, keep original.
                 # Make sure the composite hash used matches the *found* similar screen
                 composite_hash = existing_hash # Use the hash of the similar screen
                 break # Use the first visually similar screen found
        else: # If no break occurred (no visually similar screen found)
             pass # Proceed to check exact composite hash


        if composite_hash in self.screens:
            logging.debug(f"Screen state {composite_hash} already known (ID: {self.screens[composite_hash].id}).")
            return self.screens[composite_hash]
        else:
            # Screen is new (or not similar enough to existing ones)
            new_id = self._next_screen_id
            self._next_screen_id += 1

            # Save screenshot
            screenshot_dir = config.SCREENSHOTS_DIR
            os.makedirs(screenshot_dir, exist_ok=True)
            screenshot_path = os.path.join(screenshot_dir, f"screen_{new_id}_{visual_hash}.png")
            try:
                with open(screenshot_path, "wb") as f:
                    f.write(screenshot_bytes)
                logging.info(f"Saved new screen screenshot: {screenshot_path}")
            except Exception as e:
                logging.error(f"Failed to save screenshot {screenshot_path}: {e}")
                screenshot_path = "save_error" # Mark as error

            # Create representation
            screen_repr = ScreenRepresentation(new_id, xml_hash, visual_hash, screenshot_path)
            self.screens[composite_hash] = screen_repr
            self.visited_screen_hashes.add(composite_hash) # Add exact hash to visited set
            self.action_history_per_screen[composite_hash] = [] # Initialize action history

            # Save to database
            if self.db_manager:
                self.db_manager.insert_screen(
                    screen_id=new_id,
                    xml_hash=xml_hash,
                    visual_hash=visual_hash,
                    screenshot_path=screenshot_path
                )
            logging.info(f"Added new screen state (ID: {new_id}, Hash: {composite_hash}).")
            return screen_repr

    def add_transition(self, source_hash: str, action_desc: str, dest_hash: Optional[str]):
        """Records a transition between screen states."""
        if not source_hash:
             logging.warning("Attempted to add transition with no source hash.")
             return

        transition = (source_hash, action_desc, dest_hash or "UNKNOWN_DEST")
        self.transitions.append(transition)
        logging.debug(f"Recorded transition: {source_hash} --[{action_desc}]--> {dest_hash}")

        # Update action history for the source screen
        if source_hash in self.action_history_per_screen:
            # Avoid adding exact same description multiple times for this instance
            if action_desc not in self.action_history_per_screen[source_hash]:
                 self.action_history_per_screen[source_hash].append(action_desc)
        else:
            # This case might happen if state wasn't perfectly loaded from DB, initialize anyway
             self.action_history_per_screen[source_hash] = [action_desc]


        # Save to database
        if self.db_manager:
            self.db_manager.insert_transition(
                source_hash=source_hash,
                action_desc=action_desc,
                dest_hash=dest_hash or "UNKNOWN_DEST" # Store unknown if destination couldn't be determined
            )

    def get_action_history(self, screen_hash: str) -> List[str]:
        """Gets the list of actions already attempted on a given screen state."""
        return self.action_history_per_screen.get(screen_hash, [])

    def get_total_screens(self) -> int:
        return len(self.screens)

    def get_total_transitions(self) -> int:
        return len(self.transitions)