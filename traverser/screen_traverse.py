import logging
import os
import pickle
import shutil
import time
import traceback
from typing import List
from appium import webdriver
from appium.options.common.base import AppiumOptions
from traverser.utils import sql_db
from data_classes.element import UiElement
from data_classes.screen import get_screen_by_screen_id
from data_classes.tuple import Tuple

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

global_driver = None
global_screen_list = []
global_tuples_list = []
#TODO all these variables to be controlled using an interface
global_current_app = None  # Global variable to keep track of the current GUIApp instance
global_current_screen = None
global_last_visited_screen = None
global_last_executed_action = None
global_ui_element = None

global_start_time = None

global_synthetic_delay_amount = 0.1  # amount of delay added to make space between actions

max_retries = (
    1  # Maximum number of retries(after a crash) before the script ends itself
)

expected_package = (
    "eu.smartpatient.mytherapy"  # the name of the package we want to traverse
)
expected_start_activity = (
    "eu.smartpatient.mytherapy.feature.account.presentation.onboarding.WelcomeActivity"
)
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



def identify_screen_through_locators():
    global global_driver
    # Find all elements on the screen
    logging.info("----------------------------------------------")
    logging.info("Classifying elements on the screen...")

    # This list includes all types on locators (action,input,layout, etc...)
    unique_elements = []
    #todo
    unique_elements.append(global_ui_element)

    # only keep input and action elements to interact with later
    element_locators = get_only_input_action_elements(unique_elements)

    return element_locators



def set_element_locator_classification(element: UiElement):
    if is_action_element(element):
        element.classification = "action"

    elif is_input_type(element):
        element.classification = "input"

    else:
        element.classification = "unknown"
        logging.warning(f"Element type unknown:{element.class_name} - {element.id}")
    return element


# creates a new screen and returns it
def create_screen(elements:List[UiElement]):
    # add screen id to each locator for logging purposes
    created_screen = create_screen(elements)
    for element in created_screen.elements_locators_list:
        element.screen_id = created_screen.id
    return created_screen


def is_input_type(element: UiElement) -> bool:
    """Check if the element is an input type."""
    return False


# Takes an element and returns true if clickable
def is_action_element(element: UiElement) -> bool:
    """Check if the element is an action type."""
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
            "screen_list": global_screen_list,
            "tuples_list": global_tuples_list,
            "current_screen": global_current_screen,
            "last_visited_screen": global_last_visited_screen,
            "last_executed_action": global_last_executed_action,
            "element_locator": global_ui_element,
        }
        with open(CHECKPOINT_FILE, "wb") as f:
            pickle.dump(state, f)

    def load_checkpoint():
        if os.path.exists(CHECKPOINT_FILE):
            with open(CHECKPOINT_FILE, "rb") as f:
                return pickle.load(f)
        return None

    def app_logic():
        global global_driver
        global global_screen_list
        global global_tuples_list
        global global_current_screen
        global global_last_visited_screen
        global global_last_executed_action
        global global_ui_element
        global global_start_time
        global max_retries

        # flag to check if app exited normally or crashed
        exception_occurred_flag = False
        # Retry mechanism configuration
        retries = 0  # Current retry count

        # load checkpoint if it exists (in case program crashed and ended unexpectedly)

        checkpoint = load_checkpoint()

        if checkpoint:
            global_screen_list = checkpoint['screen_list']
            global_tuples_list = checkpoint['tuples_list']
            global_current_screen = checkpoint['current_screen']
            global_last_visited_screen = checkpoint['last_visited_screen']
            global_last_executed_action = checkpoint['last_executed_action']
            global_ui_element = checkpoint['element_locator']
            logging.info("Loaded checkpoint. Resuming from last saved state.")
        else:
            logging.info("No checkpoint found. Starting from the beginning.")

        while retries < max_retries:  # Retry loop
            try:
                global_driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
                # Record the start time
                global global_start_time
                global_start_time = time.time()

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
                    ui_elements= (
                        identify_screen_through_locators()
                    )

                    # Add screen to screen list if it wasn't there
                    is_unique_screen_flag = is_unique_screen(
                    global_screen_list
                    )

                    global_current_screen = get_screen_by_elements(
                        ui_elements, global_screen_list
                    )
                    if global_current_screen is not None:
                        # The screen after the action is the same as before the action
                        logging.info(
                            f"old screen  {global_current_screen.id} with {global_current_screen.get_sum_unexplored_locators()}/{len(global_current_screen.elements_locators_list)} unexplored locators already in screen_list , length is still: {len(global_screen_list)}"
                        )
                    else:
                        # the screen after doing the action is not the same screen before the action

                        global_current_screen = create_screen(
                            ui_elements
                        )
                        global_screen_list.append(global_current_screen)
                        take_screenshot(global_current_screen.id)
                        logging.info(
                            f"new screen {global_current_screen.id} with {global_current_screen.get_sum_unexplored_locators()} "
                            f"unexplored elements was added to screen_list , new length is: {len(global_screen_list)}")


                    " This code will be executed in both cases unique screen or not "

                    # the last visited screen is the one containing the  element action that was executed
                    if global_ui_element is not None:
                        global_last_visited_screen = get_screen_by_screen_id(
                            global_screen_list, global_ui_element.screen_id
                        )
                        global_last_executed_action = global_ui_element

                        is_unique_tuple_flag = is_unique_tuple(
                            global_last_visited_screen,
                            global_last_executed_action,
                            global_current_screen,
                            global_tuples_list,
                        )
                        is_valid_tuple_flag = is_valid_tuple(
                            global_last_visited_screen, global_last_executed_action, global_current_screen
                        )
                        if (
                            global_last_visited_screen
                            and is_valid_tuple_flag
                            and is_unique_tuple_flag
                        ):
                            # Tuple not already in the tuple list, add it
                            tuple = Tuple.create_tuple(
                                global_last_visited_screen,
                                global_last_executed_action,
                                global_current_screen,
                            )
                            global_tuples_list.append(tuple)
                            logging.info(
                                f"tuple was added to tuples_list , new length is: {len(global_tuples_list)}"
                            )
                        else:
                            logging.info(
                                f"tuple already in tuples_list , length is still: {len(global_tuples_list)}"
                            )

                    if global_current_screen.get_sum_unexplored_locators() <= 0:
                        # No more locators are left in this particular screen, go back to the previous screen
                        press_device_back_button(global_driver)
                    else:
                        # Go to the next locator and execute based on its classification + set as explored to \
                        # not execute it again
                        global_ui_element = global_current_screen.get_first_unexplored_locator()

                        if global_ui_element is not None:
                            global_ui_element.mark_element_as_explored()

                            if global_ui_element.classification == "input":
                                fillInputElement(global_ui_element)
                            elif global_ui_element.classification != "input":
                                tap_action_element(global_ui_element)

                    # Check if all screens are explored
                    all_screens_explored = all(
                        screen.get_sum_unexplored_elements() == 0
                        for screen in global_screen_list
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
                press_device_back_button(global_driver)
                retries += 1  # Increment the retry counter

            finally:
                # Record the end time
                end_time = time.time()
                duration = end_time - global_start_time
                logging.info(f"Total execution time: {duration:.2f} seconds")
                # Clean up the checkpoint file after successful completion
                if exception_occurred_flag and os.path.exists(CHECKPOINT_FILE):
                    os.remove(CHECKPOINT_FILE)
                # Store all found tuples locators to db
                for tuple in global_tuples_list:
                    tuple_id = sql_db.insert_tuple(tuple)
                    print(f"tuple with id {tuple_id} inserted.")
                if global_driver:
                    global_driver.quit()

        if retries == max_retries:
            logging.error("Max retries reached, exiting the test.")
            return
        else:
            logging.info("Test succeeded after retrying.")

    # Function to check if the current screen belongs to the specified app
    def ensure_in_app(allow_external_webviews=False):
        global global_driver
        global expected_package
        global expected_start_activity

        current_package = global_driver.current_package
        current_activity = global_driver.current_activity

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
                    "com.miui.security",  # allow permission dialogs on xiaomi
                    "com.miui.securitycenter",
                    "com.android.permissioncontroller",  # allow permission dialogs
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
                    global_driver.execute_script("mobile: startActivity", {"intent": intent})

    def return_to_app(allowed_external_packages):
        # First, try pressing back button
        press_device_back_button(global_driver)
        time.sleep(2)  # Wait for the screen to change

        current_package = global_driver.current_package
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
            global_driver.execute_script("mobile: startActivity", {"intent": intent})
            time.sleep(2)
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
        global global_driver

        # Create the tmp-screenshots directory if it doesn't exist
        if not os.path.exists(screenshots_path):
            os.makedirs(screenshots_path)

        # Define the full path for the screenshot, including the expected_package at the start
        screenshot_path = os.path.join(screenshots_path, f"screen{screen_id}.png")

        # Save the screenshot
        global_driver.save_screenshot(screenshot_path)
        logging.info(f"Screenshot saved: {screenshot_path}")

    def is_unique_tuple(src_screen, element, dest_screen, tuples_list):
        # Check for None values
        if src_screen is None:
            logging.warning("src_screen is None in is_unique_tuple")
            return False
        if element is None:
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
            if tuple.is_same_tuple_as(src_screen, element, dest_screen):
                is_unique = False
                break

        return is_unique

    # checks if a tuple is valid, tuple is invalid if action dosn't exist or src_screen is same as dest_screen
    def is_valid_tuple(src_screen, action, dest_screen):
        if src_screen is None or dest_screen is None:
            return False
        return action is not None and not src_screen.isSameScreenAs(dest_screen)

    #todo
    def get_screen_by_elements(elements_locators, screen_list):
        return None

    # todo
    def is_unique_screen(screen_list):
        return True  # Screen is unique

    def press_device_back_button(driver):
        logging.info("pressed back button.")
        driver.press_keycode(4)

    app_logic()


# TODO
#  this function takes a field input and fills it based on its label/text
def fillInputElement(element_locator):
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

    # element.clear()  # Clear any existing text
    # element.send_keys(input_value_for_field)
    time.sleep(global_synthetic_delay_amount)






# this function clicks an action element based on its location
def tap_action_element(element:UiElement):
    global global_driver
    global global_synthetic_delay_amount

    try:
        logging.info(
            f"tapping Element: {element.id} | {element.x},{element.y} | {element.classification} | {element.confidence} | {element.class_name} "
        )
        global_driver.tap([(element.x, element.y)])
        time.sleep(global_synthetic_delay_amount)

    except Exception as e:
        logging.error(f"tapActionElement: error while tapping element {e}")

    return 0


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
