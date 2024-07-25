import logging
import threading
import time
import os
import traceback

from appium import webdriver
from appium.options.common.base import AppiumOptions
from selenium.common import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from lxml import etree
from Gui import GUIApp
from elementlocator import ElementLocator
from screen import Screen
from tuple import Tuple
import tkinter as tk
import sql_db
from screen import getScreenWithElements, get_screen_by_screen_id

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

driver = None
screen_list = []
tuples_list = []

current_app = None  # Global variable to keep track of the current GUIApp instance
current_screen = None
last_visited_screen = None
last_executed_action = None
element_locator = None
result_text_list = []  # will include the text of every element in every screen to be used later for analyzing
start_time = None
similarity_factor= .9 # how much should 2 elements be similar to be identified as same item

max_retries = 10  # Maximum number of retries(after a crash) before the script ends itself

""""app under test and target device setup"""
expected_package = "de.jameda"  # the name of the package we want to traverse
expected_start_activity = "com.app.MainActivity"  # the name of start activity of the app we want to traverse
expected_target_device = "Android"  #change based on device to run script on -> my tablet: R52N40JSZKM  , my phone: 279cb9b1 , emulator:Android


#todo fix Gui not updating with lists' update
#todo draw the tuple list as node and edges
#todo strip useful text out of result_text_list
#todo  what if the text on screen is only given info and not actually info required from user

''''
param:unique_elements -> list of ElementLocator
'''
def get_only_input_action_elements(unique_elements):
    # This list contains only action,input locators
    filtered_unique_elements = []
    for element in unique_elements:
        if element.classification == 'input' or element.classification == 'action':
            filtered_unique_elements.append(element)
    return filtered_unique_elements

''''
param:unique_elements -> list of ElementLocator
'''
def get_only_elements_without_forbidden_words(unique_elements):
    #this list containts only elements without forbidden words
    filtered_unique_elements = []
    for element in unique_elements:
        if not element.has_forbidden_words():
            filtered_unique_elements.append(element)
    return filtered_unique_elements

''''
param:unique_elements -> list of ElementLocator
'''
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
        tree = etree.fromstring(source.encode('utf-8'))

        # This list includes all types on locators (action,input,layout,output, etc...)
        unique_elements = []

        # Function to check if an element has relevant attributes
        def has_relevant_attributes(element):
            for attr in ['text', 'hint', 'content-desc']:
                if attr in element.attrib and element.attrib[attr].strip():
                    return True
            return False

        # Recursively find all elements
        def find_elements(element):

            element_already_exist_in_element_locators_flag = False
            ''''for temp_element_locator in element_locators:
                if element.get_attribute('resourceId') == temp_element_locator.id \
                        and element.get_attribute('content-desc') == temp_element_locator.contentDesc \
                        and element.get_attribute('hint') == temp_element_locator.hint \
                        and str(element.get_attribute('bounds')) == str(temp_element_locator.bounds) \
                        and element.get_attribute('text') == temp_element_locator.text:
                    element_already_exist_in_element_locators_flag = True
                    break '''''

            if element_already_exist_in_element_locators_flag:
                pass

            elif has_relevant_attributes(element):
                element_locator_temp = ElementLocator.createElementLocatorFromElement(element)
                element_locator = set_element_locator_classification(element_locator_temp)
                unique_elements.append(element_locator)
            for child in element:
                find_elements(child)

        find_elements(tree)

        # save every type of element for analyzing later
        store_screen_elements(unique_elements)
        # only keep input and action elements to interact with later
        element_locators = get_only_input_action_elements(unique_elements)
        element_locators = get_only_elements_without_forbidden_words(element_locators)

        return element_locators


    except Exception as e:
        logging.info(f"Error waiting for page to load: {e}")


def set_element_locator_classification(element:ElementLocator):


    if is_input_type(element):
        element.classification = "input"

    elif is_action_element(element):
        element.classification = "action"

    elif is_layout_element(element):
        element.classification = "layout"

    elif is_output_element(element):
        element.classification = "output"

    elif 'View' in element.className:
        # view of type View will be ignored to speed up the code, since this usually don't containt useful info
        pass
    else:
        raise ValueError(
            f"Element type unknown:{element.className} - {element.id}")
    return element


# creates a new screen and returns it
def create_screen(element_locators):
    # add screen id to each locator for logging purposes
    created_screen = Screen.createScreen(element_locators)
    for locator in created_screen.elements_locators_list:
        locator.screenId = created_screen.id
    return created_screen


def is_input_type(element: ElementLocator) -> bool:
    """Check if the element is an input type."""
    element_class = element.className
    input_types = ['EditText', 'TextField', 'RadioButton']

    for input_type in input_types:
        if input_type in element_class:
            return True

    return contains_any_word(element_class, input_types)


# Takes an element and returns true if clickable
def is_action_element(element: ElementLocator) -> bool:
    """Check if the element is an input type."""
    element_class = element.className
    input_types = ['Button', 'ImageView', 'Image', 'ViewGroup', 'CheckBox','CheckedTextView']

    for input_type in input_types:
        if input_type in element_class and \
                element.displayed == 'true' and element.enabled == 'true' and element.clickable == 'true':
            return True
    return False


# Checks if element is a layout element
def is_layout_element(element: ElementLocator):
    # Define logic to check if element is a layout element
    #todo: handle viewpager, RecyclerView
    layoutType = element.className
    layoutList = ['LinearLayout', 'RelativeLayout', 'FrameLayout', 'ConstraintLayout', 'AbsoluteLayout'
                                                                                       'GridView', 'ListView',
                  'HwViewPager', 'RecyclerView']
    return contains_any_word(layoutType, layoutList)


def is_output_element(element: ElementLocator):
    elementType = element.className
    layoutList = ['TextView']
    return contains_any_word(elementType, layoutList)


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
    options.load_capabilities({
        "platformName": "Android",
        "appium:automationName": "uiautomator2",
        "appium:deviceName": expected_target_device,
        "appium:appPackage": expected_package,
        "appium:appActivity": expected_start_activity,
        "appium:noReset": True,
        "appium:autoGrantPermissions": True,
        "appium:newCommandTimeout": 3600,
    })

    from PIL import Image
    import numpy as np

    def is_same_screenshot(image1_path, image2_path, similarity_threshold=0.90):
        # Open the images
        img1 = Image.open(image1_path)
        img2 = Image.open(image2_path)

        # Ensure the images are the same size
        if img1.size != img2.size:
            raise ValueError("Images must be the same size")

        # Convert images to grayscale
        img1 = img1.convert('L')
        img2 = img2.convert('L')

        # Convert images to numpy arrays
        arr1 = np.array(img1)
        arr2 = np.array(img2)

        # Calculate the difference
        diff = np.abs(arr1 - arr2)

        # Calculate similarity
        similarity = 1 - (np.sum(diff) / (255.0 * arr1.size))

        print(f"Similarity: {similarity:.2%}")

        # Check if similarity is above the threshold
        return similarity >= similarity_threshold


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

        # Retry mechanism configuration
        retries = 0  # Current retry count

        while retries < max_retries:  # Retry loop
            try:
                driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
                # Record the start time
                global start_time
                start_time = time.time()

                # Loop forever
                while True:

                    # This method checks if we left the app under test and returns to it if this happens
                    ensure_in_app()

                    # Check if the screen after doing the action is the same screen before the action
                    elements_locators = identify_screen_through_locators()

                    # Add screen to screen list if it wasn't there
                    is_unique_screen_flag = is_unique_screen(elements_locators, screen_list)

                    if is_unique_screen_flag:
                        # the screen after doing the action is not the same screen before the action
                        current_screen = create_screen(elements_locators)
                        screen_list.append(current_screen)
                        take_screenshot(current_screen.id)
                        logging.info(
                            f"screen {current_screen.id} with {current_screen.get_sum_unexplored_locators()} unexplored locators was added to screen_list , new length is: {len(screen_list)}")

                    else:
                        # The screen after the action is the same as before the action
                        current_screen = get_screen_by_locators( elements_locators,screen_list)
                        logging.info(
                            f"screen  {current_screen.id} with {current_screen.get_sum_unexplored_locators()} unexplored locators already in screen_list , length is still: {len(screen_list)}")

                    """" This code will be executed in both cases unique screen or not """

                    # the last visited screen is the one containing the locator element action that was executed
                    if element_locator is not None:
                        last_visited_screen = get_screen_by_screen_id(screen_list, element_locator.screenId)
                        last_executed_action = element_locator

                        is_unique_tuple_flag = is_unique_tuple(last_visited_screen, last_executed_action,
                                                               current_screen, tuples_list)
                        is_valid_tuple_flag = is_valid_tuple(last_visited_screen, last_executed_action,
                                                             current_screen)
                        if last_visited_screen and is_valid_tuple_flag and is_unique_tuple_flag:
                            # Tuple not already in the tuple list, add it
                            tuple = Tuple.createTuple(last_visited_screen, last_executed_action,
                                                      current_screen)
                            tuples_list.append(tuple)
                            logging.info(f"tuple was added to tuples_list , new length is: {len(tuples_list)}")
                        else:
                            logging.info(f"tuple already in tuples_list , length is still: {len(tuples_list)}")

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
                            elif element_locator.classification == "action":
                                tapActionElement(element_locator)




            except Exception as e:
                # Get the full traceback
                tb = traceback.extract_tb(e.__traceback__)

                # Get the name of the last function in the traceback (where the exception occurred)
                last_func = tb[-1].name if tb else "Unknown"

                logging.error(f"An error occurred in method '{last_func}': {e}")
                logging.error("Full traceback:")
                for frame in tb:
                    logging.error(f"  File {frame.filename}, line {frame.lineno}, in {frame.name}")
                    if frame.line:
                        logging.error(f"    {frame.line}")
                # Press the back button
                press_device_back_button(driver)
                retries += 1  # Increment the retry counter
                time.sleep(1)  # Optional: wait before retrying

            finally:
                # Record the end time
                end_time = time.time()
                duration = end_time - start_time
                logging.info(f"Total execution time: {duration:.2f} seconds")
                # Store all found element locators to db
                for element_locator in result_text_list:
                    obj_id = sql_db.insert_element_locator(element_locator)
                # Store all found tuples locators to db
                for tuple in tuples_list:
                    tuple_id = sql_db.insert_tuple(tuple)
                    print(f"tuple with id {tuple_id} inserted.")

        if retries == max_retries:
            logging.error("Max retries reached, exiting the test.")
        else:
            logging.info("Test succeeded after retrying.")

    # Function to check if the current screen belongs to the specified app
    def ensure_in_app():
        global driver
        global expected_package
        global expected_start_activity

        current_package = driver.current_package
        if current_package != expected_package:
            logging.info(
                f"Current package ({current_package}) is not the expected package ({expected_package}). Navigating back to the app.")
            press_device_back_button(driver)  # Press the back button
            time.sleep(2)  # Wait for the screen to change
            current_package = driver.current_package
            if current_package != expected_package:
                logging.info(f"Still not in the expected app ({expected_package}). Relaunching the app.")
                # Construct the intent string
                intent = f"{expected_package}/{expected_start_activity}"
                # Use the execute_script method to start the activity
                driver.execute_script("mobile: startActivity", {"intent": intent})
            else:
                logging.info(f"Successfully navigated back to the app ({expected_package}).")
        else:
            logging.info(f"Already in the expected app ({expected_package}).")

    #this method takes a screenshot of the device
    def take_screenshot(screen_id):
        logging.info(f"taking a screenshot of screen {screen_id} ...")
        global driver
        screenshot_path = os.path.join(os.getcwd(), f'screen{screen_id}.png')
        driver.save_screenshot(screenshot_path)

    def is_unique_tuple(src_screen, element_locator, dest_screen, tuples_list):
        is_unique = True

        if not tuples_list:
            return is_unique

        for tuple in tuples_list:
            if tuple.isSameTupleAs(src_screen, element_locator, dest_screen):
                is_unique = False
                break

        return is_unique

    # checks if a tuple is valid, tuple is invalid if action dosn't exist or src_screen is same as dest_screen
    def is_valid_tuple(src_screen, action, dest_screen):
        return action is not None and not src_screen.isSameScreenAs(dest_screen)


    def get_screen_by_locators(elements_locators, screen_list):
        global similarity_factor

        for screen in screen_list:
            # Check if {similarity factor} or more elements match
            matching_elements_count = screen.get_sum_matching_locators(elements_locators)
            # print(f"matching_elements_count {matching_elements_count} out of {len(elements_locators)}")
            if matching_elements_count >= similarity_factor * len(elements_locators):
                return screen

        logging.error(f"get_screen_by_locators: failed to find screen, matching_elements_count {matching_elements_count}")
        return None
    def is_unique_screen(elements_locators, screen_list):
        global similarity_factor
        is_unique = True

        if not screen_list:
            return is_unique

        for screen in screen_list:
            # Check if 90% or more elements match
            matching_elements_count=screen.get_sum_matching_locators(elements_locators)
            #print(f"matching_elements_count {matching_elements_count} out of {len(elements_locators)}")
            if matching_elements_count >= similarity_factor * len(elements_locators) :
                is_unique = False
                break

        return is_unique

    def remove_explored_elements(current_screen, explored_locators):
        # Iterate over a copy of the list to avoid modifying the list while iterating
        for element in current_screen.elements_locators_list[:]:
            if any(element.isSameElementAs(explored) for explored in explored_locators):
                current_screen.elements_locators_list.remove(element)

    def press_device_back_button(driver):
        logging.info("pressed back button.")
        driver.press_keycode(4)

    app_logic()


# this function locates the input type element on the screen
def fillInputElement(element_locator):
    element = find_element(element_locator)
    if element:
        logging.info("fillInputElement: Element found!")
        fill_edit_text(ElementLocator.createElementLocatorFromElement(element))

    else:
        logging.info("fillInputElement: Element not found.")
    return 0


#  this function takes a field input and fills it based on its label/text
def fill_edit_text(element_locator: ElementLocator, max_retries=3):
    # Define dummy data for different classifications
    signup_data = {
        'email': 'afoda500@gmail.com',
        'name': 'John Doe',
        'password': 'Password123!',
        'birthdate': '01/01/1990',
        'username': 'testuser159753',
        'address': '123 Test St, Test City, Test Country',
        'phone': '123-456-7890'
    }

    keyword_variants = {
        'email': ['email', 'e-mail', 'mail', 'Email', 'E-Mail', 'Mail', 'E-Mail-Adresse', 'eMail'],
        'name': ['name', 'full name', 'full_name', 'fullname', 'Name', 'Vorname', 'Nachname', 'vollständiger Name'],
        'password': ['password', 'pass', 'pwd', 'Password', 'Passwort', 'Kennwort'],
        'birthdate': ['birthdate', 'birthday', 'dob', 'date of birth', 'Geburtsdatum', 'Geburtstag', 'Geb-Datum'],
        'username': ['username', 'user name', 'user_name', 'Benutzername', 'Nutzername', 'Anmeldename'],
        'address': ['address', 'Address', 'Adresse', 'Wohnadresse', 'Postanschrift', 'Anschrift'],
        'phone': ['phone', 'phone number', 'telephone', 'Telefonnummer', 'Telefon', 'Handynummer', 'Mobilnummer']
    }

    input_value_for_field = None
    for key, variants in keyword_variants.items():
        for variant in variants:
            variant_lower = variant.lower()
            if (variant_lower in element_locator.contentDesc.lower() or
                    variant_lower in element_locator.text.lower() or
                    variant_lower in element_locator.hint.lower()):
                input_value_for_field = signup_data[key]
                break
        if input_value_for_field is not None:
            break

    if input_value_for_field is None:
        input_value_for_field = 'unknown'
        logging.info("fill_edit_text: No matching variant found in element locator attributes.")

    for attempt in range(max_retries):
        try:
            element_locator.element.send_keys(input_value_for_field)
            logging.info(f"Successfully filled edit text with value: {input_value_for_field}")
            return  # Exit the function if successful
        except WebDriverException as e:
            if "socket hang up" in str(e):
                logging.warning(f"WebDriverException occurred (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait for 2 seconds before retrying
                else:
                    logging.error(f"Failed to fill edit text after {max_retries} attempts: {e}")
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

    try:
        logging.info(
            f"tapping Element: {element_locator.id} | {element_locator.location} | {element_locator.classification} | {element_locator.text} | {element_locator.contentDesc} ")
        center_x, center_y = element_locator.location['center']
        driver.tap([(center_x, center_y)])
        time.sleep(2)

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
            left, top = bounds.split('[')[1].split(']')[0].split(',')
            right, bottom = bounds.split('[')[2].split(']')[0].split(',')
            elements = driver.find_elements(By.XPATH, "//*")
            for elem in elements:
                loc = elem.location
                size = elem.size
                if (loc['x'] == int(left) and loc['y'] == int(top) and
                        loc['x'] + size['width'] == int(right) and
                        loc['y'] + size['height'] == int(bottom)):
                    return elem
        except:
            pass

    if locator.location:
        # This is usually not used directly for finding elements
        try:
            elements = driver.find_elements(By.XPATH, "//*")
            #logging.info(f"looking for element in this location: {locator.location}")
            for elem in elements:
                #logging.info(f"element location: {elem.location}")
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


if __name__ == "__main__":
    conn = sql_db.create_connection(sql_db.database)
    if conn is not None:
        sql_db.create_elements_locators_table('element_locators_v1')
        sql_db.create_tuples_table('tuples_table_v1')
    main()
