import logging

tuple_id = 1  # initial id for the first tuple


class Tuple:

    def __init__(self, ):
        self.id = None
        self.source = None  # of type screen
        self.action = None  # of type element locator
        self.destination = None  # of type screen

    def printTuple(self):
        logging.info(f"Tuple id {self.id}: Screen[{self.source.id}] -> Action[{self.action}] -> Screen[{self.destination.id}]")

    def createTuple(source,action,destination):
        global tuple_id
        tuple = Tuple()

        tuple.id = tuple_id
        tuple_id = tuple_id + 1

        tuple.source=source
        tuple.action = action
        tuple.destination = destination

        logging.info("created new tuple:")
        tuple.printTuple()
        return tuple

    def isSameTupleAs(self,otherTuple):
        return self.source == otherTuple.source and self.action == otherTuple.action and self.destination == otherTuple.destination