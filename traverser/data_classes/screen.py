import difflib
import logging
import re

from tabulate import tabulate

screen_id = 1  # initial id for the first screen



class Screen:

    def __init__(
        self,
    ):

        self.id = None
        self.elements_list = []

    def print_screen(self):
        # List to store table rows
        table_data = []

        # Add the ID attribute
        table_data.append(["id", self.id])


        # Collect printLocator outputs from each element in elements
        for i, element in enumerate(self.elements_list):
            element = element.get_element()
            table_data.append([f"element_{i}", element])

        # Print the table using tabulate
        table_str = tabulate(
            table_data, headers=["Attribute", "Value"], tablefmt="grid"
        )
        logging.info("\n" + table_str)


    # todo
    # compares two screens to check if they are the same
    def is_same_screen_as(self, second_screen):
        return True



    def get_first_unexplored_element(self):
        for locator in self.elements_list:
            if not locator.explored:
                return locator
        return None

    def get_sum_unexplored_elements(self):
        sum = 0
        for locator in self.elements_list:
            if not locator.explored:
                sum += 1
        return sum




def get_screen_with_elements(screen_list, element_locators):
    """
    This method identifies which screen from a list of screens contains a given list of element locators.

    :param screen_list: list of Screen objects
    :param element_locators: list of ElementLocator objects
    :return: Screen object that matches the given element locators
    """
    for screen in screen_list:
        if screen.has_same_locators_as(element_locators):
            return screen

    logging.error("getScreenWithElements: failed to find screen")
    return None


def get_screen_by_screen_id(screens, screen_id):
    """
    This method identifies which screen from a element locator.

    :param screens: list of Screen objects
    :param screen_id: id of screen
    :return: Screen object that matches the given element locator
    """
    for screen in screens:
        if screen.id == screen_id:
            return screen
    return None

    #todo
def create_screen():
    global screen_id
    screen = Screen()

    return screen
