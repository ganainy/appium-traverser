
from selenium.webdriver.remote.webelement import WebElement
import re




class UiElement:
    def __init__(self, ):
        self.id = None
        self.x = None
        self.y = None
        self.width = None
        self.height = None
        self.classification = None
        self.confidence = None
        self.class_name = None
        self.class_id = None
        self.detection_id = None

        self.screen_id = None
        self.explored = False # flag to determine if the element was clicked before or not


    def mark_element_as_explored(self):
        self.explored = True

    def get_element(self):
        attributes = []
        for attr, value in self.__dict__.items():
            attributes.append(f"{attr}: {value}")
        to_print = ", ".join(attributes)
        return to_print




    #todo
    def is_same_element_as(self, second_element):
        return True

