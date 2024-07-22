import logging
import threading
import time

from appium import webdriver
from appium.options.common.base import AppiumOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from Gui import GUIApp
from elementlocator import ElementLocator
from screen import Screen
from tuple import Tuple
import tkinter as tk
from screen import getScreenWithElements,get_screen_by_screen_id

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

driver = None
screen_list = []
tuples_list = []

current_app = None  # Global variable to keep track of the current GUIApp instance
current_screen = None
last_visited_screen = None
last_executed_action = None
element_locator = None


#todo fix tuple not created,\
# fix Gui not updating with lists' update , text boxes are identified as action , what if the text on screen is only \
# given info and not actually info required from user
def identify_screen_through_locators():
    global driver
    # Find all elements on the screen
    logging.info("----------------------------------------------")
    logging.info("Classifying elements on the screen...")

    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//*"))
        )
        logging.info("Page has finished loading.")
        # todo use this instead elements = driver.find_elements(By.XPATH, "//*")
        elements = driver.find_elements(By.XPATH,
                                        "//*[contains(@class, 'EditText') or contains(@class, 'ImageView') or contains(@class, 'ImageImage') or contains(@class, 'TextField') or contains(@class, 'Button')  or contains(@class, 'ViewGroup')]")

        element_locators = []

        for element in elements:

            if is_input_type(element):

                element_locators.append(ElementLocator.createElementLocatorFromElement(element, "input"))

            elif is_clickable(element):
                element_locator= ElementLocator.createElementLocatorFromElement(element, "action")
                # ignore locators which include 'back' text to speed up screen exploration
                if not element_locator.contain_back_text():
                    element_locators.append(element_locator)

            elif is_layout_element(element):
                # a layout element will be ignored in the classification
                ElementLocator.createElementLocatorFromElement(element, "layout")

            elif is_output_element(element):
                # logging.info(f"output element : {element.get_attribute('class')} ")
                # todo save label to logs
                ElementLocator.createElementLocatorFromElement(element, "output")


            elif 'View' in element.get_attribute('class'):
                pass
            else:
                raise ValueError(
                    f"Element type unknown:{element.get_attribute('class')} - {element.get_attribute('resource-id')}")

        return element_locators


    except Exception as e:
        logging.info(f"Error waiting for page to load: {e}")




# creates a new screen and returns it
def create_screen(element_locators):
    # add screen id to each locator for logging purposes
    created_screen = Screen.createScreen(element_locators)
    for locator in created_screen.elements_locators_list:
        locator.screenId = created_screen.id
    return created_screen


def is_input_type(element: WebElement) -> bool:
    """Check if the element is an input type."""
    element_class = element.get_attribute('class')
    input_types = ['EditText', 'TextField', 'RadioButton']

    for input_type in input_types:
        if input_type in element_class:
            return True

    return contains_any_word(element_class, input_types)


# Takes an element and returns true if clickable
def is_clickable(element: WebElement) -> bool:
    """Check if the element is an input type."""
    element_locator = ElementLocator.createElementLocatorFromElement(element, "action")
    element_class = element.get_attribute('class')
    input_types = ['Button', 'ImageView', 'Image', 'ViewGroup']

    for input_type in input_types:
        if input_type in element_class and \
                element.is_displayed() and element.is_enabled() \
                and element.get_attribute('clickable') == 'true':
            if element_locator.hasAttr("id") or element_locator.hasAttr("text") \
                    or element_locator.hasAttr("hint") or element_locator.hasAttr("contentDesc"):
                return True

    return False  # contains_any_word(element_class, input_types)


# Checks if element is a layout element
def is_layout_element(element):
    # Define logic to check if element is a layout element
    #todo: handle viewpager, RecyclerView
    layoutType = element.get_attribute('class')
    layoutList = ['LinearLayout', 'RelativeLayout', 'FrameLayout', 'ConstraintLayout', 'AbsoluteLayout'
                                                                                       'GridView', 'ListView',
                  'HwViewPager', 'RecyclerView']
    return contains_any_word(layoutType, layoutList)


def is_output_element(element):
    elementType = element.get_attribute('class')
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
    options = AppiumOptions()
    options.load_capabilities({
        "platformName": "Android",
        "appium:automationName": "uiautomator2",
        "appium:deviceName": "R52N40JSZKM",  # todo change based on device to run script on -> my tablet: R52N40JSZKM  , emulator:Android
        "appium:appPackage": "de.jameda", # todo change based on app to run script on
        "appium:appActivity": "com.app.MainActivity", # todo change based on start activity of the app to run script on
        "appium:noReset": True,
        "appium:autoGrantPermissions": True,
        "appium:newCommandTimeout": 3600,
    })

    def app_logic():
        global driver
        global screen_list
        global tuples_list
        global current_screen
        global last_visited_screen
        global last_executed_action
        global element_locator

        # Retry mechanism configuration
        max_retries = 5  # Maximum number of retries
        retries = 0  # Current retry count

        while retries < max_retries:  # Retry loop
            try:
                driver = webdriver.Remote("http://127.0.0.1:4723", options=options)

                # Loop forever
                while True:

                    # Check if the screen after doing the action is the same screen before the action
                    elements_locators = identify_screen_through_locators()

                    # Add screen to screen list if it wasn't there
                    is_unique_screen_flag = is_unique_screen(elements_locators, screen_list)

                    if is_unique_screen_flag:
                        # the screen after doing the action is not the same screen before the action
                        current_screen = create_screen(elements_locators)
                        screen_list.append(current_screen)
                        logging.info(f"screen {current_screen.id} with {current_screen.get_sum_unexplored_locators()} unexplored locators was added to screen_list , new length is: {len(screen_list)}")

                    else:
                        # The screen after the action is the same as before the action
                        current_screen=getScreenWithElements(screen_list,elements_locators)
                        logging.info(f"screen  {current_screen.id} with {current_screen.get_sum_unexplored_locators()} unexplored locators already in screen_list , length is still: {len(screen_list)}")

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

                    if not current_screen.elements_locators_list:
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
                logging.error(f"An error occurred: {e}")
                # Press the back button
                press_device_back_button(driver)
                retries += 1  # Increment the retry counter
                time.sleep(1)  # Optional: wait before retrying

            else:
                # If the try block succeeds, break out of the retry loop
                break

        if retries == max_retries:
            logging.error("Max retries reached, exiting the test.")
        else:
            logging.info("Test succeeded after retrying.")

    def is_unique_tuple(src_screen,element_locator,dest_screen,tuples_list):
        is_unique = True

        if not tuples_list:
            return is_unique

        for tuple in tuples_list:
            if tuple.isSameTupleAs(src_screen,element_locator,dest_screen):
                is_unique = False
                break

        return is_unique

    # checks if a tuple is valid, tuple is invalid if action dosn't exist or src_screen is same as dest_screen
    def is_valid_tuple(src_screen,action,dest_screen):
        return action is not None and not src_screen.isSameScreenAs(dest_screen)


    def is_unique_screen(elements_locators, screen_list):
        is_unique = True

        if not screen_list:
            return is_unique

        for screen in screen_list:
            if screen.hasSameLocatorsAs(elements_locators):
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

    # GUI
    def start_gui(screen_list, tuples_list):
        global current_app

        if current_app is not None:
            current_app.close()  # Close the existing GUI app

        root = tk.Tk()
        current_app = GUIApp(root, screen_list, tuples_list)
        root.mainloop()

    # Build tables Gui if tables aren't empty
    global screen_list
    global tuples_list
    if screen_list or tuples_list:
        #start the GUI on different thread not to block the traverser
        gui_thread = threading.Thread(target=start_gui)
        gui_thread.daemon = True  # This allows the program to exit even if the thread is running
        gui_thread.start()

    app_logic()


# todo this function takes a field input and fills it based on its label/text
def fillInputElement(element_locator):
    element=find_element(element_locator)
    if element:
        print("fillInputElement: Element found!")
        element.send_keys("test")
    else:
        print("fillInputElement: Element not found.")
    return 0


# this function clicks an action element based on its location
def tapActionElement(element_locator):
    global driver
    global last_visited_screen
    global last_executed_action

    try:
        logging.info(
            f"tapping Element: {element_locator.id} | {element_locator.location} | {element_locator.classification} | {element_locator.text} | {element_locator.contentDesc} ")
        x = element_locator.location.get('x') + 1
        y = element_locator.location.get('y') + 1
        driver.tap([(x, y)])
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
            return driver.find_element_by_id(locator.id)
        except:
            pass

    if locator.text:
        try:
            return driver.find_element_by_xpath(f"//*[contains(text(), '{locator.text}')]")
        except:
            pass

    if locator.contentDesc:
        try:
            return driver.find_element_by_accessibility_id(locator.contentDesc)
        except:
            pass

    if locator.hint:
        try:
            return driver.find_element_by_xpath(f"//*[@hint='{locator.hint}']")
        except:
            pass

    if locator.bounds:
        # Assuming bounds are provided in the format "[left,top][right,bottom]"
        # This is a more complex locator and typically requires custom logic to handle
        try:
            bounds = locator.bounds
            left, top = bounds.split('[')[1].split(']')[0].split(',')
            right, bottom = bounds.split('[')[2].split(']')[0].split(',')
            elements = driver.find_elements_by_xpath("//*")
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
            elements = driver.find_elements_by_xpath("//*")
            for elem in elements:
                if elem.location == locator.location:
                    return elem
        except:
            pass

    if locator.className:
        try:
            return driver.find_element_by_class_name(locator.className)
        except:
            pass

    return None




if __name__ == "__main__":
    main()
