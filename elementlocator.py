import logging
from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement


class ElementLocator:
    def __init__(self, ):
        self.id = None
        self.classification = None
        self.className = None
        self.text = None
        self.location = None
        self.contentDesc = None
        self.hint = None
        self.bounds = None
        self.screenId = None
        self.explored = False
        self.element = None

    def mark_element_locator_as_explored(self):
        self.explored = True

    def printLocator(self):
        attributes = []
        for attr, value in self.__dict__.items():
            if attr != 'element':  # Exclude 'element' attribute
                attributes.append(f"{attr}: {value}")
        toPrint = ", ".join(attributes)
        return toPrint

    def createElementLocatorFromElement(element, classification):
        elementLocator = ElementLocator()

        elementLocator.id = element.get_attribute('resourceId')  #resourceId
        elementLocator.className = element.get_attribute('class')
        elementLocator.classification = classification
        elementLocator.text = element.text
        elementLocator.location = element.location
        elementLocator.element = element
        elementLocator.contentDesc = element.get_attribute('content-desc')
        elementLocator.hint = element.get_attribute('hint')
        elementLocator.bounds = element.get_attribute('bounds')
        elementLocator.explored = False

        if not element or not classification:
            raise ValueError("ElementLocator: Both 'element' and 'classification' must be provided in details.")

        return elementLocator

    def isSameElementAs(self, secondElement):
        firstElementAttributes = []
        for attr, value in self.__dict__.items():
            if attr not in ['element', 'screenId','explored']:  # Exclude 'element' and 'screenId' attributes
                firstElementAttributes.append(f"{attr}: {value}")

        secondElementAttributes = []
        for attr, value in secondElement.__dict__.items():
            if attr not in ['element', 'screenId','explored']:  # Exclude 'element' and 'screenId' attributes
                secondElementAttributes.append(f"{attr}: {value}")

        return firstElementAttributes == secondElementAttributes

    def hasAttr(self, attr):
        return attr is not None and attr != 'null' and attr != ''

    def ignore_forbidden_words(self):
        """
            Checks if any attribute of the instance contains the words 'back' or 'login' or their variants (case insensitive).

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
