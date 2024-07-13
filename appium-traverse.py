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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

driver=None
elementsStack=[]
popedStackElements=[]

def main():
    options = AppiumOptions()
    options.load_capabilities({
	"platformName": "Android",
	"appium:automationName": "uiautomator2",
	"appium:deviceName": "Android",
	"appium:appPackage": "com.huawei.health",
	"appium:appActivity": ".MainActivity",
	"appium:noReset": True,
	"appium:ensureWebviewsHavePages": True,
	"appium:nativeWebScreenshot": True,
	"appium:newCommandTimeout": 3600,
	"appium:connectHardwareKeyboard": True
    })

    global driver
    try:
        driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
        loop_screen()
    except Exception as e:
        logging.error(f"An error occurred: {e}")


def loop_screen():
    global elementsStack
    global popedStackElements
    try:
    
        
        

        # Log the input/action view of current screen
        #logging.info(f"Found {len(classified_elements)} input or action elements.")

        
         # Classify elements on the screen
        classified_elements = classify_elements(driver)
         # add only new elements to stack
        addUniqueElementsToStack(classified_elements)   

        while(len(elementsStack)>0):
            element=elementsStack.pop()
            popedStackElements.append(element)

            if(element.classification=="input"):
                fillInputElement(element)
                 # Classify elements on the screen
                classified_elements = classify_elements(driver)
                # add only new elements to stack
                addUniqueElementsToStack(classified_elements)
            elif(element.classification=="action"):
                tapActionElement(element)
                 # Classify elements on the screen
                classified_elements = classify_elements(driver)
                # add only new elements to stack
                addUniqueElementsToStack(classified_elements)
        
    except Exception as e:
        logging.error(f"An error occurred while classifying: {e}")

    #get_all_texts(driver)
    
    driver.quit()

def addUniqueElementsToStack(classified_elements):
        global elementsStack
        
        for element in classified_elements:
                if not elementsStack:
                    elementsStack.append(element)
                else:    
                    for stackElement in elementsStack:
                        #dont add element to stack if already was on it
                        if element.get_attribute('class') == stackElement.get_attribute('class') \
                            and element.get_attribute('resourceId') == stackElement.get_attribute('resourceId') :
                            pass
                        #element was already poped dont add it again to stack
                        elif element in popedStackElements:
                            pass
                        else:
                            #element was never on stack add it
                            elementsStack.append(element)
                            break
        logging.info(f"new Stack size: {len(elementsStack)}")
                     
                


#this function takes a field input and fills it based on its label
def fillInputElement(element):
    return 0

#this function clicks an action element
def tapActionElement(element):
    logging.info(f"Performing click on: {element.get_attribute('resourceId')} - {element.text} -{element.get_attribute('class')} - {element.classification} ") 
    element.click()
    time.sleep(1)
    return 0

#Method to return all the labels found on a specific screen
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

#This method add a flag isAction to mark an element if action or input type
def classify_elements(driver):
    # Find all elements on the screen
    logging.info("Classifying elements on the screen...")
    elements = driver.find_elements(By.XPATH, "//*")
    classified_elements=[]

   
    for element in elements:
        
        if is_input_type(element):
            element.classification="input"
            classified_elements.append(element)

        elif is_clickable(element):
            element.classification="action"
            classified_elements.append(element) 

        elif is_layout_element(element):
            #a layout element will be ignored in the classification 
            #logging.info(f"layout element ignored: {element.get_attribute('class')} ") 
             element.classification="layout"
             
        elif is_output_element(element):
            #logging.info(f"output element : {element.get_attribute('class')} ") 
            # todo save label to logs 
            element.classification="output"  
            
        elif('View' in element.get_attribute('class')):
            pass    
        else:
            raise ValueError(f"Element type unknown:{element.get_attribute('class')} - {element.get_attribute('resource-id')}")

    return classified_elements

#Takes an element and returns true if clickable
def is_clickable(element: WebElement) -> bool:
    """Check if the element is an input type."""
    element_class = element.get_attribute('class')
    input_types = ['Button', 'ImageView',]

    for input_type in input_types:
        if input_type in element_class and \
             element.is_displayed() and element.is_enabled() \
                  and element.get_attribute('clickable') == 'true' :
            return True

    return contains_any_word(element_class, input_types)
    

#Takes an element and returns true if it is of input type
from selenium.webdriver.remote.webelement import WebElement

#Checks if element is a input element that accept userinput
def is_input_type(element: WebElement) -> bool:
    """Check if the element is an input type."""
    element_class = element.get_attribute('class')
    input_types = ['EditText', 'TextField','RadioButton']

    for input_type in input_types:
        if input_type in element_class:
            return True

    return contains_any_word(element_class, input_types)

#Checks if element is a layout element
def is_layout_element(element):
    # Define logic to check if element is a layout element
    #todo: handle viewpager, RecyclerView
    layoutType = element.get_attribute('class')
    layoutList= ['LinearLayout', 'RelativeLayout', 'FrameLayout','ConstraintLayout','AbsoluteLayout'
                 'GridView','ListView','HwViewPager','RecyclerView'] 
    return contains_any_word(layoutType,layoutList)

def is_output_element(element):
    elementType=element.get_attribute('class')
    layoutList= ['TextView']
    return contains_any_word(elementType,layoutList)


#Takes a word and a list to check if a word exists within the list
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
