import logging

class Tuple:
    tuple_id = 1  # Class-level variable for generating unique tuple IDs

    def __init__(self, source, action, destination):
        """
        Initialize a Tuple instance and automatically assign a unique ID.
        """
        self.id = Tuple.tuple_id
        Tuple.tuple_id += 1  # Increment for the next tuple

        self.source = source  # Screen object
        self.action = action  # UiElement object (or locator)
        self.destination = destination  # Screen object

        logging.info("Created new tuple:")
        self.print_tuple()

    def print_tuple(self):
        logging.info(f"Tuple id {self.id}: Screen[{self.source.id}] -> Action[{self.action}] -> Screen[{self.destination.id}]")

    def is_same_tuple_as(self, source, action, destination):
        """
        Compare the current tuple with another tuple's source, action, and destination.
        """
        if source is None or action is None or destination is None:
            return False  # Handle None case as needed

        return (self.source.id == source.id and
                self.action.is_same_element_as(action) and
                self.destination.id == destination.id)
