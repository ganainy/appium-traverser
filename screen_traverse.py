import logging
import time

from appium import webdriver
from appium.options.common.base import AppiumOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from elementlocator import ElementLocator
from screen import Screen
from tuple import Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

driver = None
screen_list = []
tuples_list = []
explored_locators=[] # holds any locators that will be executed to prevent double execution of same locator


def identify_screen():
    global driver
    # Find all elements on the screen
    logging.info("Classifying elements on the screen...")
    elements = driver.find_elements(By.XPATH, "//*")
    element_locators = []

    for element in elements:

        if is_input_type(element):

            element_locators.append(ElementLocator.createElementLocatorFromElement(element, "input"))

        elif is_clickable(element):
            element_locators.append(ElementLocator.createElementLocatorFromElement(element, "action"))

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

    return Screen.createScreen(element_locators)


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
    element_locator=ElementLocator.createElementLocatorFromElement(element,"action")
    element_class = element.get_attribute('class')
    input_types = ['Button', 'ImageView', 'Image', 'ViewGroup']

    for input_type in input_types:
        if input_type in element_class and \
                element.is_displayed() and element.is_enabled() \
                and element.get_attribute('clickable') == 'true':
            if element_locator.hasAttr("id") or element_locator.hasAttr("text") \
                    or element_locator.hasAttr("hint")  or element_locator.hasAttr("contentDesc"):
                return True


    return False # contains_any_word(element_class, input_types)


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
        "appium:deviceName": "Android",
        "appium:appPackage": "de.jameda",
        "appium:appActivity": "com.app.MainActivity",
        "appium:noReset": True,
        "appium:autoGrantPermissions": True,
        "appium:newCommandTimeout": 1000,  #3600

    })

    global driver
    global screen_list
    global tuples_list
    global explored_locators
    try:
        driver = webdriver.Remote("http://127.0.0.1:4723", options=options)


        # loop forever
        while True:

            #check if the screen after doing the action is the same screen before the action
            current_screen = identify_screen()
            if not screen_list or current_screen.isSameScreenAs(screen_list[-1])  :
                # remove any elements that are in explored_locators (because were already executed)
                current_screen.elements_locators_list = [
                    element for element in current_screen.elements_locators_list
                    if not any(element.isSameElementAs(explored) for explored in explored_locators)
                ]

                if not current_screen.elements_locators_list:
                    # no more locators are left in this particular screen, go back to previous screen
                    # todo no more actions left press back button and identify again
                    pass
                else:
                    # go to the next locator and execute based on its classification
                    element_locator = current_screen.elements_locators_list.pop(0)
                    explored_locators.append(element_locator)

                    if element_locator.classification == "input":
                        fillInputElement(element_locator)
                    elif element_locator.classification == "action":
                        tapActionElement(element_locator)
            else:
                # the screen after the action is not the same as before the action
                # add screen to screen list if it wasn't there
                if current_screen not in screen_list:
                    screen_list.append(current_screen)

                tuple = Tuple.createTuple(screen_list[-1], current_screen.elements_locators_list[-1], current_screen)
                if tuple not in tuples_list:
                    #tuple not already in the tuple list, add it
                    tuples_list.append(tuple)

                # tuple already exist in the traverse list, continue with the next locator if there are locators left
                if not current_screen.elements_locators_list:
                    # no more locators are left in this particular screen, go back to previous screen
                    # todo no more actions left press back button and identify again
                    pass

    except Exception as e:
        logging.error(f"An error occurred: {e}")


# todo this function takes a field input and fills it based on its label/text
def fillInputElement(element_locator):
    return 0


# this function clicks an action element based on its location
def tapActionElement(element_locator):
    global driver

    try:

        x = element_locator.element.location.get('x') + 1
        y = element_locator.element.location.get('y') + 1
        driver.tap([(x, y)])
        time.sleep(2)

    except Exception as e:
        logging.error(f"tapActionElement: error while tapping element {e}")

    return 0


if __name__ == "__main__":
    main()
