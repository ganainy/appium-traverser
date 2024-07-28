import logging
import sqlite3

from elementlocator import ElementLocator
from tuple import Tuple
conn = None
element_locators_table_name = None
tuple_table_name = None


def create_connection(db_file):
    """Create a database connection to the SQLite database specified by db_file."""
    global conn
    try:
        conn = sqlite3.connect(db_file)
        logging.info(f"Connected to database: {db_file}")
    except sqlite3.Error as e:
        print(e)
    return conn


def create_elements_locators_table(given_table_name):
    global conn
    global element_locators_table_name
    element_locators_table_name = given_table_name

    try:
        # Check if the table already exists
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (element_locators_table_name,))
        table_exists = cur.fetchone()

        if table_exists:
            logging.info(f"Table {element_locators_table_name} already exists. No action needed.")
            return

        # Create table if it does not exist
        create_table_command = f"""
              CREATE TABLE IF NOT EXISTS {element_locators_table_name} (
                  id TEXT,
                  classification TEXT,
                  className TEXT,
                  text TEXT,
                  location TEXT,
                  contentDesc TEXT,
                  hint TEXT,
                  bounds TEXT,
                  screenId TEXT,
                  explored TEXT
              );
          """
        conn.execute(create_table_command)
        logging.info(f"Table {element_locators_table_name} created successfully")

    except sqlite3.Error as e:
        logging.error(f"An error occurred: {e}")


def create_tuples_table(given_table_name):
    global conn
    global tuple_table_name
    tuple_table_name = given_table_name

    try:
        # Check if the table already exists
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (given_table_name,))
        table_exists = cur.fetchone()

        if table_exists:
            logging.info(f"Table {given_table_name} already exists. No action needed.")
            return

        # Create table if it does not exist
        create_table_command = f"""
              CREATE TABLE IF NOT EXISTS {given_table_name} (
                  source_screen_id TEXT,
                  action_id TEXT,
                  action_text TEXT,
                  action_hint TEXT,
                  action_contentDesc TEXT,
                  action_screenId TEXT,
                  destination_screen_id TEXT
              );
          """
        conn.execute(create_table_command)
        logging.info(f"Table {given_table_name} created successfully")

    except sqlite3.Error as e:
        logging.error(f"An error occurred: {e}")


def insert_element_locator(element_locator):
    """Insert a element_locator object into the elements_locators table."""
    global conn
    no_null_element_locator = replace_none_with_empty_string(element_locator)
    sql = f''' INSERT INTO {element_locators_table_name}(id, classification, className, text, location, contentDesc, hint, bounds, screenId, explored)
              VALUES(?,?,?,?,?,?,?,?,?,?) '''
    cur = conn.cursor()
    cur.execute(sql, (
        no_null_element_locator.id,
        no_null_element_locator.classification,
        no_null_element_locator.className,
        no_null_element_locator.text,
        no_null_element_locator.location,
        no_null_element_locator.contentDesc,
        no_null_element_locator.hint,
        no_null_element_locator.bounds,
        no_null_element_locator.screenId,
        no_null_element_locator.explored
    ))
    conn.commit()
    return cur.lastrowid


def insert_tuple(tuple: Tuple):
    global tuple_table_name
    """Insert a tuple object into the tuples table."""
    global conn
    no_null_action_element_locator = replace_none_with_empty_string(tuple.action)
    sql = f''' INSERT INTO {tuple_table_name}(source_screen_id, action_id, action_text, action_hint, action_contentDesc, action_screenId, destination_screen_id)
              VALUES(?,?,?,?,?,?,?) '''
    cur = conn.cursor()
    cur.execute(sql, (
        str(tuple.source.id),
        no_null_action_element_locator.id,
        no_null_action_element_locator.text,
        no_null_action_element_locator.hint,
        no_null_action_element_locator.contentDesc,
        no_null_action_element_locator.screenId,
        str(tuple.destination.id)
    ))
    conn.commit()
    return cur.lastrowid


def delete_table(table_name):
    global conn
    """Delete a table from the SQLite database."""
    try:
        cur = conn.cursor()

        # SQL command to delete the table
        sql = f"DROP TABLE IF EXISTS {table_name};"

        # Execute the SQL command
        cur.execute(sql)
        conn.commit()
        print(f"Table '{table_name}' deleted successfully.")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")



def print_attribute_types(element_locator: ElementLocator):
    """Print the class type of each attribute."""
    for attr, value in element_locator.__dict__.items():
        print(f"{attr}: {type(value)}")


def replace_none_with_empty_string(element_locator: ElementLocator) -> ElementLocator:
    """Replace None values with empty strings for all attributes and convert all values to strings."""
    for attr, value in element_locator.__dict__.items():
        if value is None:
            setattr(element_locator, attr, "")
        else:
            setattr(element_locator, attr, str(value))
    return element_locator
