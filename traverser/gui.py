import logging
import tkinter as tk
from tkinter import ttk

class GUIApp:
    def __init__(self, root, screen_list, tuples_list):
        self.root = root
        self.root.title("Real-Time Data Display")
        self.screen_list = screen_list
        self.tuples_list = tuples_list

        # Tuple Table Label
        self.tuple_label = tk.Label(root, text="Tuple Table")
        self.tuple_label.pack()

        # Tuple Table
        self.tuple_tree = ttk.Treeview(root, columns=('ID', 'Source', 'Action', 'Destination'), show='headings')
        self.tuple_tree.heading('ID', text='ID')
        self.tuple_tree.heading('Source', text='Source')
        self.tuple_tree.heading('Action', text='Action')
        self.tuple_tree.heading('Destination', text='Destination')

        for col in self.tuple_tree['columns']:
            self.tuple_tree.column(col, anchor='center', stretch=tk.NO)  # Center text and adjust width based on content

        self.tuple_tree.pack(fill=tk.BOTH, expand=True)

        # Screen Table Label
        self.screen_label = tk.Label(root, text="Screen Table")
        self.screen_label.pack()

        # Screen Table
        self.screen_tree = ttk.Treeview(root, columns=('ID',), show='headings')
        self.screen_tree.heading('ID', text='screen ID')

        for col in self.screen_tree['columns']:
            self.screen_tree.column(col, anchor='center', stretch=tk.NO)  # Center text and adjust width based on content

        self.screen_tree.pack(fill=tk.BOTH, expand=True)

        # ElementLocator Table Label
        self.element_locator_label = tk.Label(root, text="Element Locator Table")
        self.element_locator_label.pack()

        # ElementLocator Table
        self.element_locator_tree = ttk.Treeview(root, columns=(
            'screenId', 'ID', 'Classification', 'ClassName', 'Text', 'Location', 'ContentDesc', 'Hint', 'Bounds'),
                                                 show='headings')
        self.element_locator_tree.heading('screenId', text='screenId')
        self.element_locator_tree.heading('ID', text='ID')
        self.element_locator_tree.heading('Classification', text='Classification')
        self.element_locator_tree.heading('ClassName', text='ClassName')
        self.element_locator_tree.heading('Text', text='Text')
        self.element_locator_tree.heading('Location', text='Location')
        self.element_locator_tree.heading('ContentDesc', text='ContentDesc')
        self.element_locator_tree.heading('Hint', text='Hint')
        self.element_locator_tree.heading('Bounds', text='Bounds')

        for col in self.element_locator_tree['columns']:
            self.element_locator_tree.column(col, anchor='center', stretch=tk.NO)  # Center text and adjust width based on content

        self.element_locator_tree.pack(fill=tk.BOTH, expand=True)

        # Start the update process
        self.update_tables()

    def close(self):
        self.root.destroy()

    def update_tables(self):
        #logging.info(f"update_tables GUI is called, screen_list has {len(self.screen_list)} items, tuples_list has {len(self.tuples_list)} items")
        self.update_tuple_table()
        self.update_screen_table()
        self.update_element_locator_table()
        self.root.after(1000, self.update_tables)  # Update every second

    def update_tuple_table(self):
        # Clear the existing rows
        for row in self.tuple_tree.get_children():
            self.tuple_tree.delete(row)

        # Insert the new rows
        for tup in self.tuples_list:
            self.tuple_tree.insert('', tk.END, values=(tup.id, tup.source.id, tup.action, tup.destination.id))

    def update_screen_table(self):
        # Clear the existing rows
        for row in self.screen_tree.get_children():
            self.screen_tree.delete(row)

        # Insert the new rows
        for screen in self.screen_list:
            self.screen_tree.insert('', tk.END, values=(screen.id,))

    def update_element_locator_table(self):
        # Clear the existing rows
        for row in self.element_locator_tree.get_children():
            self.element_locator_tree.delete(row)

        for screen in self.screen_list:
            # Insert the new rows
            for element in screen.elements_locators_list:
                self.element_locator_tree.insert('', tk.END, values=(
                    element.screen_id, element.id, element.classification, element.class_name, element.text,
                    element.location, element.contentDesc, element.hint, element.bounds
                ))