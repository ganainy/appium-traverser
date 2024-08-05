import difflib
import logging
import os
import pickle
import shutil
import time
import traceback

from appium import webdriver
from appium.options.common.base import AppiumOptions
from lxml import etree
from selenium.common import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import sql_db
from elementlocator import ElementLocator
from screen import Screen
from screen import get_screen_by_screen_id
from tuple import Tuple

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

driver = None
screen_list = []
tuples_list = []

current_app = None  # Global variable to keep track of the current GUIApp instance
current_screen = None
last_visited_screen = None
last_executed_action = None
element_locator = None
result_text_list = (
    []
)  # will include the text of every element in every screen to be used later for analyzing
start_time = None
similarity_factor = (
    0.9  # how much should 2 items be similar to be identified as same item
)
synthetic_delay_amount = 0.1  # amount of delay added to make space between actions

max_retries = (
    1  # Maximum number of retries(after a crash) before the script ends itself
)

expected_package = (
    "com.myfitnesspal.android"  # the name of the package we want to traverse
)
expected_start_activity = "com.myfitnesspal.android.splash.SplashActivity"
expected_target_device = "279cb9b1"

screenshots_path = os.path.join(os.getcwd(), f"{expected_package}_screenshots")

"""'
param:unique_elements -> list of ElementLocator
"""


def get_only_input_action_elements(unique_elements):
    # This list contains only action,input locators
    filtered_unique_elements = []
    for element in unique_elements:
        if element.classification == "input" or element.classification == "action":
            filtered_unique_elements.append(element)
    return filtered_unique_elements


"""'
param:unique_elements -> list of ElementLocator
"""


def get_only_elements_without_forbidden_words(unique_elements):
    # this list contains only elements without forbidden words
    filtered_unique_elements = []
    for element in unique_elements:
        if not element.has_forbidden_words():
            filtered_unique_elements.append(element)
    return filtered_unique_elements


"""'
param:unique_elements -> list of ElementLocator
"""


def store_screen_elements(unique_elements):
    for element in unique_elements:
        result_text_list.append(element)
    return 0


def identify_screen_through_locators():
    global driver
    global result_text_list
    # Find all elements on the screen
    logging.info("----------------------------------------------")
    logging.info("Classifying elements on the screen...")

    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//*"))
        )

        # Get the page source in XML format
        source = driver.page_source

        # Parse the XML
        tree = etree.fromstring(source.encode("utf-8"))

        screen_xml_to_string = source.encode("utf-8")

        # This list includes all types on locators (action,input,layout, etc...)
        unique_elements = []

        # Function to check if an element has relevant attributes
        def has_relevant_attributes(element):
            for attr in ["text", "hint", "content-desc"]:
                if attr in element.attrib and element.attrib[attr].strip():
                    return True
            return False

        # Recursively find all elements
        def find_elements(element):

            element_already_exist_in_element_locators_flag = False
            """'for temp_element_locator in element_locators:
                if element.get_attribute('resourceId') == temp_element_locator.id \
                        and element.get_attribute('content-desc') == temp_element_locator.contentDesc \
                        and element.get_attribute('hint') == temp_element_locator.hint \
                        and str(element.get_attribute('bounds')) == str(temp_element_locator.bounds) \
                        and element.get_attribute('text') == temp_element_locator.text:
                    element_already_exist_in_element_locators_flag = True
                    break """ ""

            if element_already_exist_in_element_locators_flag:
                pass

            elif has_relevant_attributes(element):
                element_locator_temp = (
                    ElementLocator.create_element_locator_from_xml_element(element)
                )
                element_locator = set_element_locator_classification(
                    element_locator_temp
                )
                unique_elements.append(element_locator)
            for child in element:
                find_elements(child)

        find_elements(tree)

        # save every type of element for analyzing later
        store_screen_elements(unique_elements)
        # only keep input and action elements to interact with later
        element_locators = get_only_input_action_elements(unique_elements)
        # reduce the given locators list to only unique elements based on their content
        element_locators = get_unique_elements(element_locators)
        # sometimes xml of current page contains elements of previous pages, filter them out
        # element_locators= filter_current_screen_elements(element_locators)
        # remove locators with words we don't want to interact with
        # todo uncomment
        # element_locators = get_only_elements_without_forbidden_words(element_locators)

        return element_locators, screen_xml_to_string

    except Exception as e:
        logging.info(f"Error waiting for page to load: {e}")


def filter_current_screen_elements(current_elements):
    global screen_list

    def is_element_in_other_screen(element, screen_list):
        for screen in screen_list:
            for screen_element in screen.elements_locators_list:
                if element.isSameElementAs(screen_element):
                    return True
        return False

    filtered_elements = [
        element
        for element in current_elements
        if not is_element_in_other_screen(element, screen_list)
    ]

    return filtered_elements


def get_unique_elements(elements):
    unique_elements = {}
    for element in elements:
        # Create a tuple of all attributes except for 'location', 'bounds', 'screenId', and 'explored'
        key = tuple(
            (k, v)
            for k, v in element.__dict__.items()
            if k not in ["location", "bounds", "screenId", "explored"]
        )

        # If this key is not in unique_elements, add it
        if key not in unique_elements:
            unique_elements[key] = element

    # Return the list of unique ElementLocator objects
    return list(unique_elements.values())


def set_element_locator_classification(element: ElementLocator):
    if is_action_element(element):
        element.classification = "action"

    elif is_input_type(element):
        element.classification = "input"

    elif is_layout_element(element):
        element.classification = "layout"

    elif "View" in element.className:
        # view of type View will be ignored to speed up the code, since this usually don't contain useful info
        pass
    else:
        element.classification = "unknown"
        logging.warning(f"Element type unknown:{element.className} - {element.id}")
    return element


# creates a new screen and returns it
def create_screen(element_locators, screen_xml_to_string):
    # add screen id to each locator for logging purposes
    created_screen = Screen.createScreen(element_locators, screen_xml_to_string)
    for locator in created_screen.elements_locators_list:
        locator.screenId = created_screen.id
    return created_screen


def is_input_type(element: ElementLocator) -> bool:
    """Check if the element is an input type."""
    element_class = element.className
    input_types = [
        "android.widget.EditText",
        "android.widget.TextField",
    ]

    # Direct class name check
    if element_class in input_types:
        return True

    # Check for partial matches in class name
    for input_type in input_types:
        if input_type.lower() in element_class.lower():
            return True

    # Check attributes
    return contains_any_word(element_class, input_types)


# Takes an element and returns true if clickable
def is_action_element(element: ElementLocator) -> bool:
    """Check if the element is an action type."""
    element_class = element.className
    input_types = [
        "android.widget.Button",
        "android.widget.ImageView",
        "android.widget.Image",
        "android.view.ViewGroup",
        "android.widget.CheckBox",
        "android.widget.CheckedTextView",
        "android.widget.RadioButton",
        "android.widget.CheckBox",
        "android.widget.Switch",
        "android.widget.ToggleButton",
        "android.widget.Spinner",
        "android.widget.SeekBar",
        "android.widget.RatingBar",
        "android.widget.NumberPicker",
        "android.widget.TextView",
    ]

    for input_type in input_types:
        if input_type == element_class:
            return True
    return False


# Checks if element is a layout element
def is_layout_element(element: ElementLocator):
    # Define logic to check if element is a layout element
    layoutType = element.className
    layoutList = [
        "LinearLayout",
        "RelativeLayout",
        "FrameLayout",
        "ConstraintLayout",
        "AbsoluteLayout",
        "GridView",
        "ListView",
        "HwViewPager",
        "RecyclerView",
    ]
    return contains_any_word(layoutType, layoutList)


# Takes a word and a list to check if a word exists within the list
def contains_any_word(element_class, input_types):
    # Convert text to lowercase for case-insensitive comparison
    element_class = element_class.lower()

    # Convert each word in word_list to lowercase for case-insensitive comparison
    input_types = [word.lower() for word in input_types]

    for input_type in input_types:
        if input_type in element_class:
            return True

    return False


def main():
    global expected_package
    global expected_start_activity
    global expected_target_device
    options = AppiumOptions()
    options.load_capabilities(
        {
            "platformName": "Android",
            "appium:automationName": "uiautomator2",
            "appium:deviceName": expected_target_device,
            "appium:appPackage": expected_package,
            "appium:appActivity": expected_start_activity,
            "appium:noReset": True,
            "appium:autoGrantPermissions": True,
            "appium:newCommandTimeout": 3600,
        }
    )

    # File to store the checkpoint
    CHECKPOINT_FILE = "app_state_checkpoint.pkl"

    def save_checkpoint():
        state = {
            "screen_list": screen_list,
            "tuples_list": tuples_list,
            "current_screen": current_screen,
            "last_visited_screen": last_visited_screen,
            "last_executed_action": last_executed_action,
            "element_locator": element_locator,
        }
        with open(CHECKPOINT_FILE, "wb") as f:
            pickle.dump(state, f)

    def load_checkpoint():
        if os.path.exists(CHECKPOINT_FILE):
            with open(CHECKPOINT_FILE, "rb") as f:
                return pickle.load(f)
        return None

    def app_logic():
        global driver
        global screen_list
        global tuples_list
        global current_screen
        global last_visited_screen
        global last_executed_action
        global element_locator
        global start_time
        global max_retries

        # flag to check if app exited normally or crashed
        exception_occurred_flag = False
        # Retry mechanism configuration
        retries = 0  # Current retry count

        # load checkpoint if it exists (in case program crashed and ended unexpectedly)

        """ 
        checkpoint = load_checkpoint()

        if checkpoint:
            screen_list = checkpoint['screen_list']
            tuples_list = checkpoint['tuples_list']
            current_screen = checkpoint['current_screen']
            last_visited_screen = checkpoint['last_visited_screen']
            last_executed_action = checkpoint['last_executed_action']
            element_locator = checkpoint['element_locator']
            logging.info("Loaded checkpoint. Resuming from last saved state.")
        else:
            logging.info("No checkpoint found. Starting from the beginning.") """

        while retries < max_retries:  # Retry loop
            try:
                driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
                # Record the start time
                global start_time
                start_time = time.time()

                #  variable to track if all screens are explored to end the script
                all_screens_explored = False

                # Loop forever
                while not all_screens_explored:

                    # Save checkpoint periodically with each loop start to be used in case of program crash
                    save_checkpoint()

                    # This method checks if we left the app under test and returns to it if this happens
                    ensure_in_app()

                    # Check if the screen after doing the action is the same screen before the action
                    # Get the page source in XML format and turn it into a string
                    elements_locators, screen_xml_to_string = (
                        identify_screen_through_locators()
                    )

                    # Add screen to screen list if it wasn't there
                    is_unique_screen_flag = is_unique_screen(
                        screen_xml_to_string, screen_list
                    )

                    current_screen = get_screen_by_locators(
                        elements_locators, screen_list
                    )
                    if current_screen is not None:
                        # The screen after the action is the same as before the action
                        logging.info(
                            f"old screen  {current_screen.id} with {current_screen.get_sum_unexplored_locators()}/{len(current_screen.elements_locators_list)} unexplored locators already in screen_list , length is still: {len(screen_list)}"
                        )
                    else:
                        # the screen after doing the action is not the same screen before the action

                        current_screen = create_screen(
                            elements_locators, screen_xml_to_string
                        )
                        screen_list.append(current_screen)
                        take_screenshot(current_screen.id)
                        logging.info(
                            f"new screen {current_screen.id} with {current_screen.get_sum_unexplored_locators()} unexplored locators was added to screen_list , new length is: {len(screen_list)}"
                        )
                    """" 
                    if is_unique_screen_flag:
                        # the screen after doing the action is not the same screen before the action

                        current_screen = create_screen(
                            elements_locators, screen_xml_to_string
                        )
                        screen_list.append(current_screen)
                        take_screenshot(current_screen.id)
                        logging.info(
                            f"new screen {current_screen.id} with {current_screen.get_sum_unexplored_locators()} unexplored locators was added to screen_list , new length is: {len(screen_list)}"
                        )

                    else:
                        # The screen after the action is the same as before the action
                        current_screen = get_screen_by_locators(
                            elements_locators, screen_list
                        )
                        logging.info(
                            f"old screen  {current_screen.id} with {current_screen.get_sum_unexplored_locators()} unexplored locators already in screen_list , length is still: {len(screen_list)}"
                        )
                    """ """

                    """ " This code will be executed in both cases unique screen or not " ""

                    # the last visited screen is the one containing the locator element action that was executed
                    if element_locator is not None:
                        last_visited_screen = get_screen_by_screen_id(
                            screen_list, element_locator.screenId
                        )
                        last_executed_action = element_locator

                        is_unique_tuple_flag = is_unique_tuple(
                            last_visited_screen,
                            last_executed_action,
                            current_screen,
                            tuples_list,
                        )
                        is_valid_tuple_flag = is_valid_tuple(
                            last_visited_screen, last_executed_action, current_screen
                        )
                        if (
                            last_visited_screen
                            and is_valid_tuple_flag
                            and is_unique_tuple_flag
                        ):
                            # Tuple not already in the tuple list, add it
                            tuple = Tuple.createTuple(
                                last_visited_screen,
                                last_executed_action,
                                current_screen,
                            )
                            tuples_list.append(tuple)
                            logging.info(
                                f"tuple was added to tuples_list , new length is: {len(tuples_list)}"
                            )
                        else:
                            logging.info(
                                f"tuple already in tuples_list , length is still: {len(tuples_list)}"
                            )

                    if current_screen.get_sum_unexplored_locators() <= 0:
                        # No more locators are left in this particular screen, go back to the previous screen
                        press_device_back_button(driver)
                    else:
                        # Go to the next locator and execute based on its classification + set as explored to \
                        # not execute it again
                        element_locator = current_screen.get_first_unexplored_locator()

                        if element_locator is not None:
                            element_locator.mark_element_locator_as_explored()

                            if element_locator.classification == "input":
                                fillInputElement(element_locator)
                            elif element_locator.classification != "input":
                                tapActionElement(element_locator)

                    # Check if all screens are explored
                    all_screens_explored = all(
                        screen.get_sum_unexplored_locators() == 0
                        for screen in screen_list
                    )

                    if all_screens_explored:
                        logging.info(
                            "All screens and their elements have been explored. Ending the program."
                        )
                        return

            except Exception as e:
                exception_occurred_flag = True
                # Get the full traceback
                tb = traceback.extract_tb(e.__traceback__)

                # Get the name of the last function in the traceback (where the exception occurred)
                last_func = tb[-1].name if tb else "Unknown"

                logging.error(f"An error occurred in method '{last_func}': {e}")
                logging.error("Full traceback:")
                for frame in tb:
                    logging.error(
                        f"  File {frame.filename}, line {frame.lineno}, in {frame.name}"
                    )
                    if frame.line:
                        logging.error(f"    {frame.line}")
                # Press the back button
                press_device_back_button(driver)
                retries += 1  # Increment the retry counter

            finally:
                # Record the end time
                end_time = time.time()
                duration = end_time - start_time
                logging.info(f"Total execution time: {duration:.2f} seconds")
                # Clean up the checkpoint file after successful completion
                if exception_occurred_flag and os.path.exists(CHECKPOINT_FILE):
                    os.remove(CHECKPOINT_FILE)
                # Store all found element locators to db
                for element_locator in result_text_list:
                    sql_db.insert_element_locator(element_locator)
                # Store all found tuples locators to db
                for tuple in tuples_list:
                    tuple_id = sql_db.insert_tuple(tuple)
                    print(f"tuple with id {tuple_id} inserted.")
                if driver:
                    driver.quit()

        if retries == max_retries:
            logging.error("Max retries reached, exiting the test.")
            return
        else:
            logging.info("Test succeeded after retrying.")

    # Function to check if the current screen belongs to the specified app
    def ensure_in_app(allow_external_webviews=False):
        global driver
        global expected_package
        global expected_start_activity

        current_package = driver.current_package
        current_activity = driver.current_activity

        # List of known external packages that are part of the app flow
        allowed_external_packages = [
            "com.google.android.gms",  # Google Sign-In
            "com.facebook.katana",  # Facebook sign in
        ]

        # Add external WebView packages of famous browsers if allowed
        if allow_external_webviews:
            allowed_external_packages.extend(
                [
                    "com.android.chrome",  # Chrome for WebView
                    "com.brave.browser",  # Brave Browser
                ]
            )

        if (
            current_package != expected_package
            and current_package not in allowed_external_packages
        ):
            return_to_app(allowed_external_packages)
        else:
            logging.info(
                f"Current package: {current_package}, Current activity: {current_activity}"
            )
            if current_package == expected_package:
                logging.info(f"Already in the expected app ({expected_package}).")
            else:
                if allow_external_webviews:
                    logging.info(f"In an allowed external package ({current_package}).")
                else:
                    logging.warning(
                        f"In an external package ({current_package}), but WebViews are not allowed. Returning to main app."
                    )
                    # Construct the intent string
                    intent = f"{expected_package}/{expected_start_activity}"
                    # Use the execute_script method to start the activity
                    driver.execute_script("mobile: startActivity", {"intent": intent})

    def return_to_app(allowed_external_packages):
        # First, try pressing back button
        press_device_back_button(driver)
        time.sleep(2)  # Wait for the screen to change

        current_package = driver.current_package
        if (
            current_package != expected_package
            and current_package not in allowed_external_packages
        ):
            logging.info(
                f"Still not in the expected app or allowed external package. Relaunching the app. {current_package}"
            )
            # Construct the intent string
            intent = f"{expected_package}/{expected_start_activity}"
            # Use the execute_script method to start the activity
            driver.execute_script("mobile: startActivity", {"intent": intent})
        else:
            logging.info(
                f"Successfully navigated back to the app or an allowed external package."
            )

    def press_device_back_button(driver):
        driver.press_keycode(4)  # 4 is the Android keycode for the back button

    # this method takes a screenshot of the device
    def take_screenshot(screen_id):
        global screenshots_path
        logging.info(f"Taking a screenshot of screen {screen_id} ...")
        global driver

        # Create the tmp-screenshots directory if it doesn't exist
        if not os.path.exists(screenshots_path):
            os.makedirs(screenshots_path)

        # Define the full path for the screenshot, including the expected_package at the start
        screenshot_path = os.path.join(screenshots_path, f"screen{screen_id}.png")

        # Save the screenshot
        driver.save_screenshot(screenshot_path)
        logging.info(f"Screenshot saved: {screenshot_path}")

    def is_unique_tuple(src_screen, element_locator, dest_screen, tuples_list):
        # Check for None values
        if src_screen is None:
            logging.warning("src_screen is None in is_unique_tuple")
            return False
        if element_locator is None:
            logging.warning("element_locator is None in is_unique_tuple")
            return False
        if dest_screen is None:
            logging.warning("dest_screen is None in is_unique_tuple")
            return False
        if tuples_list is None:
            logging.warning("tuples_list is None in is_unique_tuple")
            return False

        is_unique = True

        if not tuples_list:
            return is_unique

        for tuple in tuples_list:
            if tuple is None:
                logging.warning("Encountered None tuple in tuples_list")
                continue
            if not hasattr(tuple, "isSameTupleAs"):
                logging.warning(f"Tuple {tuple} does not have isSameTupleAs method")
                continue
            if tuple.isSameTupleAs(src_screen, element_locator, dest_screen):
                is_unique = False
                break

        return is_unique

    # checks if a tuple is valid, tuple is invalid if action dosn't exist or src_screen is same as dest_screen
    def is_valid_tuple(src_screen, action, dest_screen):
        if src_screen is None or dest_screen is None:
            return False
        return action is not None and not src_screen.isSameScreenAs(dest_screen)

    def get_screen_by_locators(elements_locators, screen_list):
        similarity_factor = 0.9

        if not elements_locators:
            logging.warning("get_screen_by_locators: elements_locators is empty")
            return None

        best_match_screen = None
        best_match_count = 0
        total_elements = len(elements_locators)

        for screen in screen_list:
            matching_elements_count = screen.get_sum_matching_locators(
                elements_locators
            )

            # Check for 100% match
            if matching_elements_count == total_elements:
                logging.info(
                    f"get_screen_by_locators: Found 100% match with {matching_elements_count} elements"
                )
                return screen

            # Update best match if this screen has more matching elements
            if matching_elements_count > best_match_count:
                best_match_count = matching_elements_count
                best_match_screen = screen

        # If no 100% match found, check if the best match meets the similarity threshold
        if best_match_screen:
            similarity_score = best_match_count / total_elements
            if similarity_score >= similarity_factor:
                logging.info(
                    f"get_screen_by_locators: Found best match with similarity {similarity_score:.2f} "
                    f"({best_match_count}/{total_elements} elements)"
                )
                return best_match_screen
            else:
                logging.warning(
                    f"get_screen_by_locators: Best match similarity {similarity_score:.2f} "
                    f"({best_match_count}/{total_elements} elements) below threshold {similarity_factor}"
                )
        else:
            logging.error("get_screen_by_locators: No matching screen found")

        return None

    def is_unique_screen(screen_xml_to_string, screen_list, similarity_factor=0.9):
        if not screen_list:
            return True

        for screen in screen_list:
            # Get the XML representation of the screen from the list
            existing_screen_xml = screen.screen_xml_to_string

            # Calculate the similarity ratio between the two XML strings
            similarity_ratio = difflib.SequenceMatcher(
                None, screen_xml_to_string, existing_screen_xml
            ).ratio()

            # Check if the similarity ratio is at least 90%
            if similarity_ratio >= similarity_factor:
                return False  # Screen is not unique

        return True  # Screen is unique

    def press_device_back_button(driver):
        logging.info("pressed back button.")
        driver.press_keycode(4)

    app_logic()


# this function locates the input type element on the screen
def fillInputElement(element_locator):
    element = find_element(element_locator)
    if element:
        logging.info("fillInputElement: Element found!")
        fill_edit_text(
            ElementLocator.create_element_locator_from_web_element(element), element
        )

    else:
        logging.info("fillInputElement: Element not found.")
    return 0


#  this function takes a field input and fills it based on its label/text


def fill_edit_text(element_locator: ElementLocator, element: WebElement):
    max_retries = 3
    # Define dummy data for different classifications
    signup_data = {
        "email": "afoda500@gmail.com",
        "name": "John Doe",
        "password": "P@mr9601206!",
        "birthdate": "01/01/1990",
        "username": "testuser159753",
        "address": "123 Test St, Test City, Test Country",
        "phone": "123-456-7890",
    }

    keyword_variants = {
        "email": [
            "email",
            "e-mail",
            "mail",
            "Email",
            "E-Mail",
            "Mail",
            "E-Mail-Adresse",
            "eMail",
        ],
        "name": [
            "name",
            "full name",
            "full_name",
            "fullname",
            "Name",
            "Vorname",
            "Nachname",
            "vollständiger Name",
        ],
        "password": ["password", "pass", "pwd", "Password", "Passwort", "Kennwort"],
        "birthdate": [
            "birthdate",
            "birthday",
            "dob",
            "date of birth",
            "Geburtsdatum",
            "Geburtstag",
            "Geb-Datum",
        ],
        "username": [
            "username",
            "user name",
            "user_name",
            "Benutzername",
            "Nutzername",
            "Anmeldename",
        ],
        "address": [
            "address",
            "Address",
            "Adresse",
            "Wohnadresse",
            "Postanschrift",
            "Anschrift",
        ],
        "phone": [
            "phone",
            "phone number",
            "telephone",
            "Telefonnummer",
            "Telefon",
            "Handynummer",
            "Mobilnummer",
        ],
    }

    input_value_for_field = None
    for key, variants in keyword_variants.items():
        for variant in variants:
            variant_lower = variant.lower()
            if (
                variant_lower in element_locator.contentDesc.lower()
                or variant_lower in element_locator.text.lower()
                or variant_lower in element_locator.hint.lower()
            ):
                input_value_for_field = signup_data[key]
                break
        if input_value_for_field is not None:
            break

    if input_value_for_field is None:
        logging.info(
            "No matching variant found in element locator attributes. Skipping this field."
        )
        return  # Skip filling this field instead of using "unknown"

    for attempt in range(max_retries):
        try:
            element.clear()  # Clear any existing text
            element.send_keys(input_value_for_field)
            time.sleep(synthetic_delay_amount)

            # Verify if the text was actually input
            actual_value = element.get_attribute("value") or element.text
            if actual_value != input_value_for_field:
                logging.warning(
                    f"Input verification failed. Expected: {input_value_for_field}, Actual: {actual_value}"
                )
                if attempt == max_retries - 1:
                    logging.error(
                        f"Failed to input correct value after {max_retries} attempts"
                    )
                    return
                continue  # Try again if this wasn't the last attempt

            logging.info(
                f"Successfully filled edit text with value: {input_value_for_field}"
            )
            return  # Exit the function if successful
        except WebDriverException as e:
            if "socket hang up" in str(e):
                logging.warning(
                    f"WebDriverException occurred (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(synthetic_delay_amount * 10)  # Wait before retrying
                else:
                    logging.error(
                        f"Failed to fill edit text after {max_retries} attempts: {e}"
                    )
            else:
                logging.error(f"Unexpected WebDriverException: {e}")
                raise  # Re-raise the exception if it's not a "socket hang up" error
        except Exception as e:
            logging.error(f"Unexpected error while filling edit text: {e}")
            raise

    logging.error("Failed to fill edit text after all retry attempts")


# this function clicks an action element based on its location
def tapActionElement(element_locator):
    global driver
    global last_visited_screen
    global last_executed_action
    global synthetic_delay_amount

    try:
        logging.info(
            f"tapping Element: {element_locator.id} | {element_locator.location} | {element_locator.classification} | {element_locator.text} | {element_locator.contentDesc} "
        )
        center_x, center_y = element_locator.location["center"]
        driver.tap([(center_x, center_y)])
        time.sleep(synthetic_delay_amount)

    except Exception as e:
        logging.error(f"tapActionElement: error while tapping element {e}")

    return 0


def find_element(locator):
    global driver
    """
    Tries to find an element using all available locators in the given locator object.

    :param driver: The Appium webdriver instance.
    :param locator: An instance of ElementLocator containing possible attributes.
    :return: The found element or None if no element is found.
    """
    if locator.id:
        try:
            return driver.find_element(By.ID, locator.id)
        except:
            pass

    if locator.text:
        try:
            return driver.find_element(By.NAME, locator.text)
        except:
            pass

    if locator.contentDesc:
        try:
            return driver.find_element(By.NAME, locator.contentDesc)
        except:
            pass

    if locator.hint:
        try:
            return driver.find_element(By.NAME, locator.hint)
        except:
            pass

    if locator.bounds:
        # Assuming bounds are provided in the format "[left,top][right,bottom]"
        # This is a more complex locator and typically requires custom logic to handle
        try:
            bounds = locator.bounds
            left, top = bounds.split("[")[1].split("]")[0].split(",")
            right, bottom = bounds.split("[")[2].split("]")[0].split(",")
            elements = driver.find_elements(By.XPATH, "//*")
            for elem in elements:
                loc = elem.location
                size = elem.size
                if (
                    loc["x"] == int(left)
                    and loc["y"] == int(top)
                    and loc["x"] + size["width"] == int(right)
                    and loc["y"] + size["height"] == int(bottom)
                ):
                    return elem
        except:
            pass

    if locator.location:
        # This is usually not used directly for finding elements
        try:
            elements = driver.find_elements(By.XPATH, "//*")
            # logging.info(f"looking for element in this location: {locator.location}")
            for elem in elements:
                # logging.info(f"element location: {elem.location}")
                if elem.location == locator.location:
                    return elem
        except:
            pass

    if locator.className:
        try:
            return driver.find_element(By.CLASS_NAME, locator.className)
        except:
            pass

    return None


def delete_screenshots():
    global screenshots_path

    # Check if the folder exists
    if os.path.exists(screenshots_path):
        try:
            # Remove the entire folder and its contents
            shutil.rmtree(screenshots_path)
            print(f"Successfully deleted the folder: {screenshots_path}")
        except Exception as e:
            print(f"Error deleting the folder: {e}")
    else:
        print(f"The folder {screenshots_path} does not exist.")


if __name__ == "__main__":
    conn = sql_db.create_connection(f"{expected_package}.db")
    if conn is not None:
        # Drop existing tables if they exist
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS element_locators_v1")
        cursor.execute("DROP TABLE IF EXISTS tuples_table_v1")
        conn.commit()

        delete_screenshots()
        sql_db.create_elements_locators_table("element_locators_v1")
        sql_db.create_tuples_table("tuples_table_v1")
    main()
