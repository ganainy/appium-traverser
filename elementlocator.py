
from selenium.webdriver.remote.webelement import WebElement
import re



def get_element_location_from_bounds(bounds):
    pattern = r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]'
    match = re.search(pattern, str(bounds))

    if match:
        start_x, start_y, end_x, end_y = map(int, match.groups())
        center_x = (start_x + end_x) // 2
        center_y = (start_y + end_y) // 2

        return {
            'start': (start_x, start_y),
            'end': (end_x, end_y),
            'center': (center_x, center_y)
        }
    else:
        return None



class ElementLocator:
    def __init__(self, ):
        self.id = None
        self.classification = None
        self.className = None
        self.text = None
        self.location = None # of type Dict, has start,end,center
        self.contentDesc = None
        self.hint = None
        self.bounds = None
        self.screenId = None
        self.explored = False # flag to determine if the locator was clicked before or not
        self.clickable= None
        self.enabled = None
        self.displayed = None


    def mark_element_locator_as_explored(self):
        self.explored = True

    def printLocator(self):
        attributes = []
        for attr, value in self.__dict__.items():
            if attr != 'element':  # Exclude 'element' attribute
                attributes.append(f"{attr}: {value}")
        toPrint = ", ".join(attributes)
        return toPrint

    def create_element_locator_from_xml_element(element):
        elementLocator = ElementLocator()

        elementLocator.id = element.attrib.get('resource-id')
        elementLocator.className = element.attrib.get('class')
        elementLocator.text = element.attrib.get('text')
        elementLocator.contentDesc = element.attrib.get('content-desc')
        elementLocator.hint = element.attrib.get('hint')
        elementLocator.bounds = element.attrib.get('bounds')
        elementLocator.clickable = element.attrib.get('clickable')
        elementLocator.enabled = element.attrib.get('enabled')
        elementLocator.displayed = element.attrib.get('displayed')
        elementLocator.location = get_element_location_from_bounds(elementLocator.bounds)
        
        elementLocator.explored = False

        return elementLocator

    def create_element_locator_from_web_element(element:WebElement):
        elementLocator = ElementLocator()

        elementLocator.id = element.get_attribute('resource-id')
        elementLocator.className = element.get_attribute('class')
        elementLocator.text = element.text  # Use text property directly
        elementLocator.contentDesc = element.get_attribute('content-desc')
        elementLocator.hint = element.get_attribute('hint')
        bounds = str(element.get_attribute('bounds'))
        elementLocator.bounds = bounds
        elementLocator.location = get_element_location_from_bounds(elementLocator.bounds)
        elementLocator.enabled = element.is_enabled()
        elementLocator.enabled = element.get_attribute('clickable')
        elementLocator.displayed = element.is_displayed()

        elementLocator.explored = False

        return elementLocator

    def isSameElementAs(self, secondElement):
        firstElementAttributes = []
        for attr, value in self.__dict__.items():
            if attr not in ['element', 'screenId', 'explored']:  # Exclude 'element' and 'screenId' attributes
                firstElementAttributes.append(f"{attr}: {value}")

        secondElementAttributes = []
        for attr, value in secondElement.__dict__.items():
            if attr not in ['element', 'screenId', 'explored']:  # Exclude 'element' and 'screenId' attributes
                secondElementAttributes.append(f"{attr}: {value}")

        return firstElementAttributes == secondElementAttributes

    def hasAttr(self, attr):
        return attr is not None and attr != 'null' and attr != ''

    def has_forbidden_words(self):
        """
        Checks if any attribute of the instance contains the words 'back' or 'login' or their variants (
        case-insensitive).

            :return: bool indicating if any attribute contains the forbidden words
            """
        forbidden_words = [
            # English words
            'back', 'return', 'login', 'log in', 'sign in', 'signin', 'sign-on', 'sign on',
            'authenticate', 'logon', 'log on', 'previous', 'home', 'exit', 'quit',
            'signout', 'sign out', 'logout', 'log out', 'go back', 'back to',

            # German words
            'zurück', 'rückkehr', 'einloggen', 'anmelden', 'anmeldung',
            'authentifizieren', 'abmelden', 'abmeldung', 'zurückkehren', 'vorherige',
            'startseite', 'verlassen', 'beenden', 'ausloggen', 'ausloggen',
            'gehe zurück', 'zurück zu'
        ]

        for attr, value in self.__dict__.items():
            if isinstance(value, str):  # Only check string attributes
                for word in forbidden_words:
                    if word.lower() in value.lower():
                        return True

        return False
