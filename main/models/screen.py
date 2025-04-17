import difflib
import logging
import re

from tabulate import tabulate

screen_id = 1  # initial id for the first screen


class Screen:

    def __init__(
        self,
    ):
        self.screen_xml_to_string = (
            None  # this is a string representation of the screen XML
        )
        self.id = None
        self.elements_locators_list = []

    def printScreen(self):
        # List to store table rows
        table_data = []

        # Add the ID attribute
        table_data.append(["id", self.id])

        # Collect other attributes
        for attr, value in self.__dict__.items():
            if (
                attr == "contentDesc"
                or attr == "hint"
                or attr == "text"
                or attr == "screenId"
                or attr == "className"
            ):
                table_data.append([attr, value])

        # Collect printLocator outputs from each element in elements
        for i, element in enumerate(self.elements_locators_list):
            locator_info = element.printLocator()
            table_data.append([f"element_{i}", locator_info])

        # Print the table using tabulate
        table_str = tabulate(
            table_data, headers=["Attribute", "Value"], tablefmt="grid"
        )
        logging.info("\n" + table_str)

    def createScreen(elements_locators_list, screen_xml_to_string):
        global screen_id
        screen = Screen()
        screen.screen_xml_to_string = screen_xml_to_string
        screen.id = screen_id
        screen_id = screen_id + 1

        for element_locator in elements_locators_list:
            screen.elements_locators_list.append(element_locator)

        logging.info("created new screen:")
        screen.printScreen()
        return screen

    # compares two screens to check if they are the same
    def isSameScreenAs(self, secondScreen):
        # Get the XML representation of both screens
        first_screen_xml = self.screen_xml_to_string
        second_screen_xml = secondScreen.screen_xml_to_string

        # Calculate the similarity ratio between the two XML strings
        similarity_ratio = difflib.SequenceMatcher(
            None, first_screen_xml, second_screen_xml
        ).ratio()

        # Check if the similarity ratio is at least 90%
        if similarity_ratio >= 0.9:
            return True
        else:
            return False

    # similar to isSameScreenAs but compares through the second screen locators
    def hasSameLocatorsAs(self, second_screen_elements_locators):
        """
        Checks if the screen has the same locators as the given list of element locators.
        This version requires all elements to match.

        :param second_screen_elements_locators: list of ElementLocator objects
        :return: bool indicating if this screen has the same locators
        """
        matching_elements_count = 0
        for first_screen_locator_element in self.elements_locators_list:
            for second_screen_locator_element in second_screen_elements_locators:
                if first_screen_locator_element.isSameElementAs(
                    second_screen_locator_element
                ):
                    matching_elements_count += 1
                    break  # Move to the next element in the first screen

        # Check if all elements in second_screen_elements_locators were matched
        return matching_elements_count == len(second_screen_elements_locators)

    def get_sum_matching_locators(self, second_screen_elements_locators):
        """
        Checks if the screen has the same locators as the given list of element locators.
        This version requires all elements to match.

        :param second_screen_elements_locators: list of ElementLocator objects
        :return: bool indicating if this screen has the same locators
        """
        matching_elements_count = 0
        for first_screen_locator_element in self.elements_locators_list:
            for second_screen_locator_element in second_screen_elements_locators:
                if first_screen_locator_element.isSameElementAs(
                    second_screen_locator_element
                ):
                    matching_elements_count += 1
                    break  # Move to the next element in the first screen

        return matching_elements_count

    def hasLocator(self, element_locator):
        # return a screen if it has a certain locator
        for current_screen_element_locator in self.elements_locators_list:
            if current_screen_element_locator.isSameElementAs(element_locator):
                return True
        return False

    def get_first_unexplored_locator(self):
        for locator in self.elements_locators_list:
            if not locator.explored:
                return locator
        return None

    def get_sum_unexplored_locators(self):
        sum = 0
        for locator in self.elements_locators_list:
            if not locator.explored:
                sum += 1
        return sum

    def has_matching_element(self, locator):
        for element in self.elements_locators_list:
            if self._is_element_match(element, locator):
                return True
        return False

    def _is_element_match(self, element, locator):
        # Check for matching attributes
        attributes_to_check = ["id", "className", "text", "contentDesc"]
        match_score = 0
        total_checks = 0

        for attr in attributes_to_check:
            if getattr(element, attr) and getattr(locator, attr):
                total_checks += 1
                if getattr(element, attr) == getattr(locator, attr):
                    match_score += 1

        # Check location (if available)
        if element.location and locator.location:
            total_checks += 1
            if self._is_location_similar(element.location, locator.location):
                match_score += 1

        # Calculate similarity
        if total_checks > 0:
            similarity = match_score / total_checks
            return similarity >= 0.8  # 80% similarity threshold
        return False

    def _is_location_similar(self, loc1, loc2, tolerance=50):
        # Helper function to extract center from bounds string
        def get_center_from_bounds(bounds):
            pattern = r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]"
            match = re.search(pattern, str(bounds))
            if match:
                start_x, start_y, end_x, end_y = map(int, match.groups())
                return (start_x + end_x) // 2, (start_y + end_y) // 2
            return None

        # Extract centers based on the type of loc1 and loc2
        center1 = (
            loc1["center"] if isinstance(loc1, dict) else get_center_from_bounds(loc1)
        )
        center2 = (
            loc2["center"] if isinstance(loc2, dict) else get_center_from_bounds(loc2)
        )

        # If we couldn't extract centers, return False
        if center1 is None or center2 is None:
            return False

        # Check if the center points are within the tolerance
        return (
            abs(center1[0] - center2[0]) <= tolerance
            and abs(center1[1] - center2[1]) <= tolerance
        )

    def compare_element_attributes(self, elements_locators):
        if len(self.elements_locators_list) != len(elements_locators):
            return False

        for element, locator in zip(self.elements_locators_list, elements_locators):
            if not self._compare_detailed_attributes(element, locator):
                return False
        return True

    def _compare_detailed_attributes(self, element, locator):
        attributes_to_compare = [
            "id",
            "className",
            "text",
            "contentDesc",
            "hint",
            "clickable",
            "enabled",
            "displayed",
        ]

        for attr in attributes_to_compare:
            if getattr(element, attr) != getattr(locator, attr):
                return False

        # Compare location
        if element.location and locator.location:
            if not self._is_location_similar(
                element.location, locator.location, tolerance=10
            ):
                return False

        return True


def getScreenWithElements(screen_list, element_locators):
    """
    This method identifies which screen from a list of screens contains a given list of element locators.

    :param screen_list: list of Screen objects
    :param element_locators: list of ElementLocator objects
    :return: Screen object that matches the given element locators
    """
    for screen in screen_list:
        if screen.hasSameLocatorsAs(element_locators):
            return screen

    logging.error("getScreenWithElements: failed to find screen")
    return None


def get_screen_by_screen_id(screens, screenId):
    """
    This method identifies which screen from a element locator.

    :param screens: list of Screen objects
    :param screenId: id of screen
    :return: Screen object that matches the given element locator
    """
    for screen in screens:
        if screen.id == screenId:
            return screen
    return None
