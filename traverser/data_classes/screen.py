import difflib
import logging
import re
from typing import List

from tabulate import tabulate

from traverser.data_classes.element import UiElement




class Screen:
    screen_id = 1  # Class variable for the screen ID, shared across all instances

    def __init__(self, elements_list: List[UiElement]):
        self.id = Screen.screen_id  # Assign the current class-level screen_id to the instance
        self.elements_list: List[UiElement] = elements_list
        Screen.screen_id += 1  # Increment the class-level screen_id for the next instance

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


    # compares two screens to check if they are the same
    def is_same_screen_as(self, second_screen):
        return self.elements_list== second_screen.elements_list



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

