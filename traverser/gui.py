import tkinter as tk
from tkinter import ttk  # Import ttk for dropdown menus
import logging

from traverser import screen_traverse  # Assuming this is your main traversal logic
#todo add time and fix stop button and make the selected settings reflect to global variables and maybe add the logs from console to gui with screenshots
# Initialize logging
logging.basicConfig(level=logging.INFO)

# Define global variables
max_retries = 1
expected_package = "eu.smartpatient.mytherapy"
expected_start_activity = "eu.smartpatient.mytherapy.feature.account.presentation.onboarding.WelcomeActivity"
expected_target_device = "279cb9b1"
global_project_name = "vins-dataset-no-wire-modified"
global_project_version = 2

def start_execution():
    global max_retries, expected_package, expected_start_activity, expected_target_device
    global global_project_name, global_project_version

    # Fetch values from the GUI inputs
    max_retries = int(max_retries_entry.get())
    expected_package = package_entry.get()
    expected_start_activity = activity_entry.get()
    expected_target_device = device_entry.get()
    global_project_name = project_name_entry.get()
    global_project_version = int(project_version_entry.get())

    # Log the parameters
    logging.info("Starting execution with the following settings:")
    logging.info(f"Max Retries: {max_retries}")
    logging.info(f"Expected Package: {expected_package}")
    logging.info(f"Expected Start Activity: {expected_start_activity}")
    logging.info(f"Expected Target Device: {expected_target_device}")
    logging.info(f"Global Project Name: {global_project_name}")
    logging.info(f"Global Project Version: {global_project_version}")

    # Call the main function with parameters
    screen_traverse.main()

def stop_execution():
    # Placeholder function to stop execution
    logging.info("Execution stopped (functionality to be implemented).")

# Create the main window
root = tk.Tk()
root.title("Script Controller")
root.geometry("1000x400")  # Set window size

# Create and place labels and entry fields for each variable with larger space
tk.Label(root, text="Max Retries:").grid(row=0, column=0, pady=10, padx=10)
max_retries_entry = tk.Entry(root, width=100)  # Increased width
max_retries_entry.insert(0, str(max_retries))  # Default value
max_retries_entry.grid(row=0, column=1, pady=10, padx=10)

tk.Label(root, text="Expected Package:").grid(row=1, column=0, pady=10, padx=10)
package_entry = ttk.Combobox(root, width=100)  # Increased width
package_entry['values'] = ["eu.smartpatient.mytherapy", "another.package.name"]  # Example values
package_entry.set(expected_package)  # Default value
package_entry.grid(row=1, column=1, pady=10, padx=10)

tk.Label(root, text="Expected Start Activity:").grid(row=2, column=0, pady=10, padx=10)
activity_entry = ttk.Combobox(root, width=100)  # Increased width
activity_entry['values'] = ["Activity1", "Activity2"]  # Example values
activity_entry.set(expected_start_activity)  # Default value
activity_entry.grid(row=2, column=1, pady=10, padx=10)

tk.Label(root, text="Expected Target Device:").grid(row=3, column=0, pady=10, padx=10)
device_entry = ttk.Combobox(root, width=100)  # Increased width
device_entry['values'] = ["279cb9b1", "another_device_id"]  # Example values
device_entry.set(expected_target_device)  # Default value
device_entry.grid(row=3, column=1, pady=10, padx=10)

tk.Label(root, text="Global Project Name:").grid(row=4, column=0, pady=10, padx=10)
project_name_entry = tk.Entry(root, width=100)  # Increased width
project_name_entry.insert(0, global_project_name)
project_name_entry.grid(row=4, column=1, pady=10, padx=10)

tk.Label(root, text="Global Project Version:").grid(row=5, column=0, pady=10, padx=10)
project_version_entry = tk.Entry(root, width=100)  # Increased width
project_version_entry.insert(0, str(global_project_version))
project_version_entry.grid(row=5, column=1, pady=10, padx=10)

# Create Start and Stop buttons
start_button = tk.Button(root, text="Start", command=start_execution, width=15)
start_button.grid(row=6, column=0, columnspan=2, pady=20)

stop_button = tk.Button(root, text="Stop", command=stop_execution, width=15)
stop_button.grid(row=7, column=0, columnspan=2, pady=10)

# Run the Tkinter event loop
root.mainloop()
