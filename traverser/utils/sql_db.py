import logging
import sqlite3

from traverser.data_classes.element import UiElement
from traverser.data_classes.tuple import Tuple

conn = None
elements_table_name = None
tuple_table_name = None


def create_connection(db_file):
    """Create a database connection to the SQLite database specified by db_file."""
    global conn
    try:
        conn = sqlite3.connect(db_file)
    except sqlite3.Error as e:
        print(e)
    return conn


def create_ui_elements_table(given_table_name):
    global conn
    global elements_table_name
    elements_table_name = given_table_name

    try:
        # Check if the table already exists
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (elements_table_name,),
        )
        table_exists = cur.fetchone()

        if table_exists:
            return

        # Create table if it does not exist
        create_table_command = f"""
                 CREATE TABLE IF NOT EXISTS {elements_table_name} (
                     id TEXT,
                     x TEXT,
                     y TEXT,
                     width TEXT,
                     height TEXT,
                     confidence TEXT,
                     class_name TEXT,
                     detection_id TEXT
                 );
             """
        conn.execute(create_table_command)
    except sqlite3.Error as e:
        logging.error(f"An error occurred: {e}")


def create_tuples_table(given_table_name):
    global conn
    global tuple_table_name
    tuple_table_name = given_table_name

    try:
        # Check if the table already exists
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (given_table_name,),
        )
        table_exists = cur.fetchone()

        if table_exists:
            return

        # Create table if it does not exist
        create_table_command = f"""
              CREATE TABLE IF NOT EXISTS {given_table_name} (
                  source_screen_id TEXT,
                  action_id TEXT,
                  action_screen_id TEXT,
                  destination_screen_id TEXT
              );
          """
        conn.execute(create_table_command)

    except sqlite3.Error as e:
        logging.error(f"An error occurred: {e}")



def insert_element(element_locator):
    """Insert a element object into the ui_elements table."""
    global conn
    no_null_element_locator = replace_none_with_empty_string(element_locator)
    sql = f""" INSERT INTO {elements_table_name}(id, x, y, width, height, confidence, class_name, detection_id)
              VALUES(?,?,?,?,?,?,?,?) """
    cur = conn.cursor()
    cur.execute(
        sql,
        (
            no_null_element_locator.id,
            no_null_element_locator.classification,
            no_null_element_locator.class_name,
            no_null_element_locator.screen_id,
            no_null_element_locator.explored,
        ),
    )
    conn.commit()
    return cur.lastrowid


def insert_tuple(tuple: Tuple):
    global tuple_table_name
    """Insert a tuple object into the tuples table."""
    global conn
    no_null_action_element_locator = replace_none_with_empty_string(tuple.action)
    sql = f""" INSERT INTO {tuple_table_name}(source_screen_id, action_id,action_screen_id, destination_screen_id)
              VALUES(?,?,?,?) """
    cur = conn.cursor()
    cur.execute(
        sql,
        (
            str(tuple.source.id),
            no_null_action_element_locator.id,
            no_null_action_element_locator.screen_id,
            str(tuple.destination.id),
        ),
    )
    conn.commit()
    return cur.lastrowid


def print_attribute_types(element_locator: UiElement):
    """Print the class type of each attribute."""
    for attr, value in element_locator.__dict__.items():
        print(f"{attr}: {type(value)}")


def replace_none_with_empty_string(element_locator: UiElement) -> UiElement:
    """Replace None values with empty strings for all attributes and convert all values to strings."""
    for attr, value in element_locator.__dict__.items():
        if value is None:
            setattr(element_locator, attr, "")
        else:
            setattr(element_locator, attr, str(value))
    return element_locator
