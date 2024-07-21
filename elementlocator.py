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
        self.element = None

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

        if not element or not classification:
            raise ValueError("ElementLocator: Both 'element' and 'classification' must be provided in details.")

        return elementLocator


    def isSameElementAs(self, secondElement):

        firstElementAttributes = []
        for attr, value in self.__dict__.items():
            if attr != 'element':  # Exclude 'element' attribute
                firstElementAttributes.append(f"{attr}: {value}")

        secondElementAttributes = []
        for attr, value in secondElement.__dict__.items():
            if attr != 'element':  # Exclude 'element' attribute
                secondElementAttributes.append(f"{attr}: {value}")

        return firstElementAttributes == secondElementAttributes

    def hasAttr(self,attr):
        return attr is not None and attr != 'null' and attr != ''
