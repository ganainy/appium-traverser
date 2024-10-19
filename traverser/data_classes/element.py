class UiElement:
    def __init__(self,prediction):
        self.id = None
        self.classification = None
        self.screen_id = None
        self.explored = False  # flag to determine if the element was clicked before or not

        self.x = prediction["x"]
        self.y = prediction["y"]
        self.width = prediction["width"]
        self.height = prediction["height"]
        self.confidence = prediction["confidence"]
        self.class_name = prediction["class"]
        self.class_id = prediction["class_id"]
        self.detection_id = prediction["detection_id"]



    def mark_element_as_explored(self):
        """Mark the element as explored by setting the flag to True."""
        self.explored = True

    def get_element(self):
        """Return a string representation of all attributes of the element."""
        attributes = []
        for attr, value in self.__dict__.items():
            attributes.append(f"{attr}: {value}")
        return ", ".join(attributes)

    def is_same_element_as(self, second_element):
        """
        Compare the current element with another element.

        Two elements are considered the same if their key attributes match.
        Modify the comparison logic based on what defines uniqueness in your context.
        """
        return self == second_element

    def __eq__(self, other):
        """
        Override the default equality method to compare key attributes.
        Two UiElement instances are considered equal if their key properties match.
        """
        if isinstance(other, UiElement):
            return (
                self.id == other.id and
                self.x == other.x and
                self.y == other.y and
                self.width == other.width and
                self.height == other.height and
                self.class_name == other.class_name and
                self.class_id == other.class_id
            )
        return False

    def __hash__(self):
        """
        Override the default hash method to make UiElement hashable.
        The hash is based on the key attributes that define the element.
        """
        return hash((self.id, self.x, self.y, self.width, self.height, self.class_name, self.class_id))
