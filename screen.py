import logging

screen_id = 1  # initial id for the first screen

class Screen:

    def __init__(self, ):
        self.id = None
        self.elements_locators_list = []

    def printScreen(self):
        attributes = []

        # Add the ID attribute
        attributes.append(f"id: {self.id}")

        # Collect other attributes
        for attr, value in self.__dict__.items():
            if attr != "id" and attr != "elements_locators_list":
                attributes.append(f"{attr}: {value}")

        # Collect printLocator outputs from each element in elements
        for i, element in enumerate(self.elements_locators_list):
            locator_info = element.printLocator()
            attributes.append(f"element_{i}: {locator_info}")

        toPrint = ", ".join(attributes)
        logging.info(toPrint)

    def createScreen(elements_locators_list):
        global screen_id
        screen = Screen()

        screen.id = screen_id
        screen_id = screen_id + 1

        for element_locator in elements_locators_list:
            screen.elements_locators_list.append(element_locator)

        logging.info("created new screen:")
        screen.printScreen()
        return screen

    # compares two screens to check if they are the same
    def isSameScreenAs(self, secondScreen):
        # if only one item is same in both screen then its the same screen, since each item is unique (with a screenId)
        for first_screen_locator_element in self.elements_locators_list:
            for second_screen_locator_element in secondScreen.elements_locators_list:
                if first_screen_locator_element.isSameElementAs(second_screen_locator_element):
                    return True
        return False
        # return any(element in self.elements_locators_list for element in secondScreen.elements_locators_list)

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
                if first_screen_locator_element.isSameElementAs(second_screen_locator_element):
                    matching_elements_count += 1
                    break  # Move to the next element in the first screen

        # Check if all elements in second_screen_elements_locators were matched
        return matching_elements_count == len(second_screen_elements_locators)


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
        sum =0
        for locator in self.elements_locators_list:
            if locator.explored == False:
                sum +=1
        return sum

def getScreenWithElements(screens, element_locators):
    """
    This method identifies which screen from a list of screens contains a given list of element locators.

    :param screens: list of Screen objects
    :param element_locators: list of ElementLocator objects
    :return: Screen object that matches the given element locators
    """
    for screen in screens:
        if screen.hasSameLocatorsAs(element_locators):
            return screen
    return None

def getScreenWithElement(screens,element_locator):
    """
    This method identifies which screen from a element locator.

    :param screens: list of Screen objects
    :param element_locator: ElementLocator object
    :return: Screen object that matches the given element locator
    """
    for screen in screens:
        if screen.hasLocator(element_locator):
            return screen
    return None
