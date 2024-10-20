import tkinter as tk
from tkinter import ttk  # Import ttk for dropdown menus
import threading  # For running the execution in a separate thread
from traverser.data_classes.gui_params import GuiParams

#todo add time and implement stop button in main code
# todo maybe add the logs from console to gui with screenshots

# Global variables
max_retries = 1
expected_package = "eu.smartpatient.mytherapy"
expected_start_activity = "eu.smartpatient.mytherapy.feature.account.presentation.onboarding.WelcomeActivity"
expected_target_device = "279cb9b1"
global_project_name = "vins-dataset-no-wire-modified"
global_project_version = 2
global_synthetic_delay_amount = 0.5
global_similarity_threshold = 0.85


# Thread control
execution_thread = None
stop_execution_flag = False

def start_execution():
    global max_retries, expected_package, expected_start_activity, expected_target_device
    global global_project_name, global_project_version, execution_thread, stop_execution_flag
    global global_synthetic_delay_amount,global_similarity_threshold

    # Fetch values from the GUI inputs
    max_retries = int(max_retries_entry.get())
    expected_package = package_entry.get()
    expected_start_activity = activity_entry.get()
    expected_target_device = device_entry.get()
    global_project_name = project_name_entry.get()
    global_project_version = int(project_version_entry.get())
    global_synthetic_delay_amount = float(synthetic_delay_amount_entry.get())
    global_similarity_threshold = float(similarity_threshold_entry.get())

    # Create a new thread for the execution
    stop_execution_flag = False
    execution_thread = threading.Thread(target=run_execution, args=())
    execution_thread.start()

def run_execution():
    from traverser import screen_traverse
    global stop_execution_flag

    # Call the main function with parameters
    params = GuiParams(max_retries, expected_package, expected_start_activity, expected_target_device,
                       global_project_name, global_project_version, stop_execution_flag,global_synthetic_delay_amount,global_similarity_threshold)

    # Simulating a long-running process, where you can check stop_execution_flag
    screen_traverse.main(params)

#todo
def stop_execution():
    global stop_execution_flag
    stop_execution_flag = True

# Create the main window
root = tk.Tk()
root.title("Script Controller")
root.geometry("1000x600")  # Set window size, larger to accommodate explanations

# Create and place labels, entry fields, and explanations for each variable

# Max Retries
tk.Label(root, text="Max Retries:").grid(row=0, column=0, pady=10, padx=10)
max_retries_entry = ttk.Combobox(root, width=100)
max_retries_entry['values'] = ["1", "2", "3", "4", "5"]
max_retries_entry.set(max_retries)  # Default value
max_retries_entry.grid(row=0, column=1, pady=10, padx=10)
tk.Label(root, text="Explanation: Number of times the app will retry on crash.", fg="grey").grid(row=1, column=0, columnspan=2, padx=10)

# Package Name
tk.Label(root, text="Package name:").grid(row=2, column=0, pady=10, padx=10)
package_entry = ttk.Combobox(root, width=100)
package_entry['values'] = ["eu.smartpatient.mytherapy", "todo another.package.name"]
package_entry.set(expected_package)  # Default value
package_entry.grid(row=2, column=1, pady=10, padx=10)
tk.Label(root, text="Explanation: The package name of the app you want to automate.", fg="grey").grid(row=3, column=0, columnspan=2, padx=10)

# Start Activity
tk.Label(root, text="Start activity:").grid(row=4, column=0, pady=10, padx=10)
activity_entry = ttk.Combobox(root, width=100)
activity_entry['values'] = ["todo", "todo"]
activity_entry.set(expected_start_activity)  # Default value
activity_entry.grid(row=4, column=1, pady=10, padx=10)
tk.Label(root, text="Explanation: The initial activity of the app where the script starts.", fg="grey").grid(row=5, column=0, columnspan=2, padx=10)

# Device
tk.Label(root, text="Device:").grid(row=6, column=0, pady=10, padx=10)
device_entry = ttk.Combobox(root, width=100)
device_entry['values'] = ["279cb9b1", "Android"]  # Example values
device_entry.set(expected_target_device)  # Default value
device_entry.grid(row=6, column=1, pady=10, padx=10)
tk.Label(root, text="Explanation: The target device ID or name to run the script on.", fg="grey").grid(row=7, column=0, columnspan=2, padx=10)

# Delay Amount
tk.Label(root, text="Delay:").grid(row=8, column=0, pady=10, padx=10)
synthetic_delay_amount_entry = tk.Entry(root, width=100)
synthetic_delay_amount_entry.insert(0, str(global_synthetic_delay_amount))
synthetic_delay_amount_entry.grid(row=8, column=1, pady=10, padx=10)
tk.Label(root, text="Explanation: Time delay (in seconds) between interactions with the app.", fg="grey").grid(row=9, column=0, columnspan=2, padx=10)

# Model Name
tk.Label(root, text="Model Name:").grid(row=10, column=0, pady=10, padx=10)
project_name_entry = tk.Entry(root, width=100)
project_name_entry.insert(0, global_project_name)
project_name_entry.grid(row=10, column=1, pady=10, padx=10)
tk.Label(root, text="Explanation: The name of the deep learning model to be used.", fg="grey").grid(row=11, column=0, columnspan=2, padx=10)

# Model Version
tk.Label(root, text="Model Version:").grid(row=12, column=0, pady=10, padx=10)
project_version_entry = tk.Entry(root, width=100)
project_version_entry.insert(0, str(global_project_version))
project_version_entry.grid(row=12, column=1, pady=10, padx=10)
tk.Label(root, text="Explanation: The version of the deep learning model.", fg="grey").grid(row=13, column=0, columnspan=2, padx=10)

# Similarity Threshold
tk.Label(root, text="Similarity threshold:").grid(row=14, column=0, pady=10, padx=10)
similarity_threshold_entry = ttk.Combobox(root, width=100)
similarity_threshold_entry['values'] = ["0.1", "0.2", "0.3", "0.4", "0.5", "0.7", "0.8", "0.9", "1.0"]
similarity_threshold_entry.set(global_similarity_threshold)  # Default value
similarity_threshold_entry.grid(row=14, column=1, pady=10, padx=10)
tk.Label(root, text="Explanation: How similar two screenshots need to be to be considered the same screen (values from 0 to 1).", fg="grey").grid(row=15, column=0, columnspan=2, padx=10)

# Create Start and Stop buttons
start_button = tk.Button(root, text="Start", command=start_execution, width=15)
start_button.grid(row=16, column=0, columnspan=2, pady=20)

stop_button = tk.Button(root, text="Stop", command=stop_execution, width=15)
stop_button.grid(row=17, column=0, columnspan=2, pady=10)

# Run the Tkinter event loop
root.mainloop()
