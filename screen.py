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

    def isSameScreenAs(self, secondScreen):
        for first_screen_locator_element in self.elements_locators_list:
            for second_screen_locator_element in secondScreen.elements_locators_list:
                if first_screen_locator_element.isSameElementAs(second_screen_locator_element):
                    return True
        return False

        #return any(element in self.elements_locators_list for element in secondScreen.elements_locators_list)
