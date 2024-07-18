# This sample code supports Appium Python client >=2.3.0
# pip install Appium-Python-Client
# Then you can paste this into a file and simply run with Python
import logging
import time
from appium import webdriver
from appium.options.common.base import AppiumOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.by import By

# For W3C actions
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions import interaction
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import NoSuchElementException

from elementlocator import ElementLocator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

driver = None
locatorsStack = []
popedStackLocators = []


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
    try:
        driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
        loop_screen()
    except Exception as e:
        logging.error(f"An error occurred: {e}")


def loop_screen():
    global locatorsStack
    global popedStackLocators
    try:
        # Classify elements on the screen
        classified_locators = classify_elements(driver)
        # add only new elements to stack
        addUniqueElementsToStack(classified_locators)

        while len(locatorsStack) > 0:
            locator = locatorsStack.pop()
            popedStackLocators.append(locator)

            if locator.classification == "input":
                fillInputElement(locator)
                # Classify elements on the screen
                classified_elements = classify_elements(driver)
                # add only new elements to stack
                addUniqueElementsToStack(classified_elements)
            elif locator.classification == "action":
                tapActionElement(locator)
                # Classify elements on the screen
                classified_elements = classify_elements(driver)
                # add only new elements to stack
                addUniqueElementsToStack(classified_elements)

    except Exception as e:
        logging.error(f"An error occurred while classifying: {e}")

    driver.quit()


def addUniqueElementsToStack(screenLocators):
    global locatorsStack
    global popedStackLocators

    for screenLocator in screenLocators:
        # Flag to check if the screenLocator is already in the stack or popedStackLocators
        is_in_stack = False
        is_in_poped = False

        # Check if the screenLocator is already in the stack
        for stackLocator in locatorsStack:
            if screenLocator.isSameElementAs(stackLocator):
                is_in_stack = True
                break

        # Check if the screenLocator is in the popedStackLocators
        is_in_poped = isPoped(screenLocator)

        # If the screenLocator is not in the stack and wasn't popped before, add it
        if not is_in_stack and not is_in_poped:
            locatorsStack.append(screenLocator)
            logging.info("new element added to stack:")
            screenLocator.printLocator()

    logging.info(f"new Stack size: {len(locatorsStack)}")
    return locatorsStack

   # Check if a screenLocator is in the popedStackLocators
def isPoped(screenLocator):
    global popedStackLocators
    for popedLocator in popedStackLocators:
        if screenLocator.isSameElementAs(popedLocator):
            return True
    return False

#this function takes a field input and fills it based on its label
def fillInputElement(locator):
    return 0


#this function clicks an action element
def tapActionElement(locator):
    global locatorsStack
    global driver
    #WebDriverWait wait = new WebDriverWait(driver, Duration.ofSeconds(10));
    try:
        # Attempt to find the element and click it
        if locator.hasAttr(locator.id):
            element = driver.find_element(By.ID, locator.id)
            element.click()

        elif  locator.hasAttr(locator.text):
            element = driver.find_element(By.NAME, locator.text)
            element.click()

        elif  locator.hasAttr(locator.className):
            elements = driver.find_elements(By.CLASS_NAME, locator.className)
            for element in elements:
                elementLocator=ElementLocator.createElementLocatorFromElement(element,"action")
                if isPoped(elementLocator):
                    pass
                else:
                    element.click()
                    break

        else:
            logging.info(f"tapActionElement: cant find element by id, class or name ")
            locatorsStack.pop()
            popedStackLocators.append(locator)


    except Exception as e:
        logging.error(f"tapActionElement: error while tapping element {e}")

    return 0


# Method to return all the labels found on a specific screen
def get_all_texts(driver):
    # Find all elements on the screen
    elements = driver.find_elements(By.XPATH, "//*")

    # Extract text from each element
    texts = [element.text for element in elements if element.text]

    try:
        # Get all texts from the current screen
        logging.info("Getting all texts from the screen...")

        # Log the retrieved texts
        for text in texts:
            logging.info(f"Element text: {text}")

    except Exception as e:
        logging.error(f"An error occurred: {e}")

    return texts


# This method add a flag isAction to mark an element if action or input type
def classify_elements(driver):
    # Find all elements on the screen
    logging.info("Classifying elements on the screen...")
    elements = driver.find_elements(By.XPATH, "//*")
    classified_locators = []

    for element in elements:

        if is_input_type(element):

            classified_locators.append(ElementLocator.createElementLocatorFromElement(element, "input"))

        elif is_clickable(element):
            classified_locators.append(ElementLocator.createElementLocatorFromElement(element, "action"))

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

    return classified_locators


# Takes an element and returns true if clickable
def is_clickable(element: WebElement) -> bool:
    """Check if the element is an input type."""
    element_class = element.get_attribute('class')
    input_types = ['Button', 'ImageView', 'Image', 'ViewGroup']

    for input_type in input_types:
        if input_type in element_class and \
                element.is_displayed() and element.is_enabled() \
                and element.get_attribute('clickable') == 'true':
            return True

    return contains_any_word(element_class, input_types)


# Checks if element is a input element that accept userinput
def is_input_type(element: WebElement) -> bool:
    """Check if the element is an input type."""
    element_class = element.get_attribute('class')
    input_types = ['EditText', 'TextField', 'RadioButton']

    for input_type in input_types:
        if input_type in element_class:
            return True

    return contains_any_word(element_class, input_types)


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


if __name__ == "__main__":
    main()
