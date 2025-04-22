"""
Android App Package and Activity Finder

This script helps identify the package name and main activity of Android applications
installed on a connected device. It uses ADB (Android Debug Bridge) to:
1. List installed packages (with optional filtering)
2. Find the main/launcher activity for a selected package
3. Output the results in a format suitable for Appium configuration

Requirements:
- ADB installed and in system PATH
- Android device connected via USB with debugging enabled
- Device must be authorized for debugging

Usage:
    python find_app_info.py
    Then follow the interactive prompts to:
    1. Enter a search term (optional)
    2. Select from matching packages
    3. Get package and activity information
"""

import subprocess
import sys
import re
import json # Added for JSON output
import os   # Added for path joining

def run_adb_command(command_list):
    """
    Execute an ADB command and return its output.

    Args:
        command_list (list): List of command components (excluding 'adb')

    Returns:
        str or None: Command output if successful, None if command fails

    Raises:
        SystemExit: If ADB is not found in PATH
    """
    try:
        adb_command = ['adb'] + command_list
        # print(f"--- Running ADB: {' '.join(adb_command)}") # Optional: uncomment for verbose debugging
        result = subprocess.run(
            adb_command,
            capture_output=True,
            text=True,
            check=True, # Raise CalledProcessError on non-zero exit code
            encoding='utf-8',
            errors='ignore' # Ignore potential decoding errors in adb output
        )
        if result.stderr:
            # Filter out common benign warnings like "Warning: ..." from dumpsys
            if not result.stderr.strip().startswith("Warning:"):
                 print(f"--- ADB STDERR:\n{result.stderr.strip()}", file=sys.stderr)
        return result.stdout.strip()
    except FileNotFoundError:
        print("Error: 'adb' command not found. Make sure ADB is installed and in your PATH.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        # Don't print the full error for common 'not found' issues during lookup, just return None
        if "No activity found" not in e.output and "exit" not in e.stderr.lower():
             print(f"Error executing ADB command: {' '.join(e.cmd)}", file=sys.stderr)
             # print(f"Return code: {e.returncode}", file=sys.stderr)
             # print(f"Output:\n{e.output}", file=sys.stderr)
             print(f"Stderr:\n{e.stderr.strip()}", file=sys.stderr) # Print stripped stderr
        if "device unauthorized" in e.stderr.lower():
             print("\n*** Device unauthorized. Please check your device and allow USB debugging. ***", file=sys.stderr)
             sys.exit(1) # Exit if device is unauthorized
        elif "device" in e.stderr.lower() and ("not found" in e.stderr.lower() or "offline" in e.stderr.lower()):
             print("\n*** Device not found or offline. Ensure device is connected and USB debugging is enabled. ***", file=sys.stderr)
             sys.exit(1) # Exit if no device
        return None # Indicate failure

def get_device_serial():
    """Gets the serial number of the connected device."""
    output = run_adb_command(['get-serialno'])
    if output and output != "unknown":
        # Sanitize for filename (though serials are usually safe)
        serial = re.sub(r'[^\w\-.]', '_', output)
        return serial
    else:
        print("Error: Could not get device serial number.", file=sys.stderr)
        # Fallback filename if serial fails
        devices_output = run_adb_command(['devices'])
        if devices_output and len(devices_output.splitlines()) > 1:
            # Try to grab first device ID from 'adb devices' if serial fails
            first_device_line = devices_output.splitlines()[1]
            fallback_id = first_device_line.split('\t')[0]
            print(f"Using fallback identifier: {fallback_id}", file=sys.stderr)
            return re.sub(r'[^\w\-.]', '_', fallback_id)
        else:
             print("Using generic filename 'unknown_device'.", file=sys.stderr)
             return "unknown_device"


def get_installed_packages(filter_keyword=None, third_party_only=True):
    """Gets a list of installed package names."""
    command = ['shell', 'pm', 'list', 'packages']
    if third_party_only:
        command.append('-3')
    # No grep needed here, get all packages specified
    output = run_adb_command(command)
    if output is None:
        return []

    packages = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            packages.append(line.split(":", 1)[1])
    return packages

def find_main_activity(package_name):
    """Finds the main launcher activity for a given package."""
    if not package_name:
        return None

    # Using 'cmd package resolve-activity' - often works well for launcher
    command = ['shell', 'cmd', 'package', 'resolve-activity', '--brief', package_name]
    output = run_adb_command(command)

    if output:
        activity_line = output.splitlines()[-1].strip()
        if activity_line and not activity_line.startswith("No activity found") and '/' in activity_line:
            parts = activity_line.split('/')
            pkg = parts[0]
            act_relative = parts[1]
            if act_relative.startswith('.'):
                return f"{pkg}{act_relative}"
            else:
                if '.' not in act_relative:
                    return f"{pkg}.{act_relative}"
                elif not act_relative.startswith(pkg):
                    return f"{pkg}.{act_relative}"
                else:
                    return act_relative

    # If 'cmd package resolve-activity' failed or gave bad output, try dumpsys
    # print(f"Trying dumpsys for {package_name}...") # Optional: uncomment for debugging fallback
    return find_main_activity_dumpsys(package_name)


def find_main_activity_dumpsys(package_name):
    """
    Fallback method to find main activity using dumpsys.
    Parses the detailed package information to find activities with
    MAIN action and LAUNCHER category.

    Args:
        package_name (str): The Android package name to investigate

    Returns:
        str or None: Full activity name if found, None otherwise

    Note:
        This method is slower but more thorough than resolve-activity.
        It parses the full activity resolver table to find the correct
        MAIN/LAUNCHER activity combination.
    """
    command = ['shell', 'dumpsys', 'package', package_name]
    output = run_adb_command(command)

    if output is None:
        return None

    # Simpler Regex focused on the MAIN/LAUNCHER intent filter block
    # Look for Activity section -> intent filter -> MAIN action -> LAUNCHER category
    activity_regex = re.compile(r'Activity\s+Record\{[^ ]+\s+[^ ]+\s+' + re.escape(package_name) + r'/([^ ]+)\s*')
    intent_filter_regex = re.compile(r'IntentFilter\{[^ ]+\s+Actions:\[([^]]+)\]\s+Categories:\[([^]]+)\]')

    current_activity = None
    lines = output.splitlines()

    for line in lines:
        stripped_line = line.strip()

        # Check if we are entering a new Activity definition
        activity_match = activity_regex.search(stripped_line + ' ') # Add space for regex anchor
        if activity_match:
            potential_activity = activity_match.group(1)
            # Qualify if it starts with '.'
            if potential_activity.startswith('.'):
                current_activity = package_name + potential_activity
            else:
                current_activity = potential_activity # Assume full path if not starting with .
            continue # Move to next line to check filters for this activity

        # Check for intent filters *after* finding an activity candidate
        if current_activity:
            filter_match = intent_filter_regex.search(stripped_line)
            if filter_match:
                actions = filter_match.group(1)
                categories = filter_match.group(2)
                # Check if this filter is the MAIN/LAUNCHER one
                if 'android.intent.action.MAIN' in actions and \
                   'android.intent.category.LAUNCHER' in categories:
                    return current_activity # Found it!

            # If the line isn't blank or an intent filter, we've likely left the relevant section for the current_activity
            elif stripped_line and not stripped_line.startswith("IntentFilter"):
                 current_activity = None # Reset if we moved past filters for this activity

    # Fallback if regex fails: Look for the specific MAIN/LAUNCHER pattern in dumpsys output
    main_action_found = False
    activity_name_from_main = None
    for i, line in enumerate(lines):
        stripped_line = line.strip()
        if "android.intent.action.MAIN:" in stripped_line:
            main_action_found = True
            continue
        if main_action_found:
            match = re.search(r'[a-f0-9]+\s+(' + re.escape(package_name) + r'/[^ ]+)\s+filter', stripped_line)
            if match:
                potential_activity_path = match.group(1)
                # Look ahead for LAUNCHER category
                for j in range(i + 1, min(i + 5, len(lines))):
                     if "Category: \"android.intent.category.LAUNCHER\"" in lines[j]:
                         activity_part = potential_activity_path.split('/')[1]
                         if activity_part.startswith('.'):
                              activity_name_from_main = package_name + activity_part
                         else:
                              activity_name_from_main = activity_part # Assume full or needs pkg prefix if simple
                              if '.' not in activity_name_from_main: # Simple name like MainActivity
                                   activity_name_from_main = f"{package_name}.{activity_name_from_main}"
                         return activity_name_from_main # Return as soon as found

            if not stripped_line or ":" in stripped_line and not stripped_line.endswith("MAIN:"):
                main_action_found = False # Reset if we exited the MAIN section

    # If neither regex nor specific pattern worked
    # print(f"Could not find MAIN/LAUNCHER activity for {package_name} using dumpsys.", file=sys.stderr)
    return None


# --- Main Execution ---
if __name__ == "__main__":
    print("Attempting to connect to device and get serial number...")
    device_serial = get_device_serial()
    if not device_serial:
        sys.exit(1) # Exit if we couldn't get any identifier

    print(f"Device identifier: {device_serial}")
    print("Fetching list of third-party packages...")

    packages = get_installed_packages(third_party_only=True)

    if not packages:
        print("No third-party packages found on the device.")
        sys.exit(0)

    print(f"Found {len(packages)} third-party packages. Processing...")

    all_app_data = []
    total_packages = len(packages)

    for i, package_name in enumerate(packages):
        print(f"[{i+1}/{total_packages}] Processing: {package_name}")
        main_activity = find_main_activity(package_name)

        app_info = {
            "package_name": package_name,
            "activity_name": main_activity # This will be None if not found
        }
        all_app_data.append(app_info)

        if main_activity is None:
            print(f"  -> Main activity not found for {package_name}")
        # else:
            # print(f"  -> Found activity: {main_activity}") # Optional: uncomment for verbose success log

    # --- Prepare JSON Output and Save to File ---
    output_filename = f"{device_serial}_app_info.json"
    output_dir = os.path.join(os.path.dirname(__file__) or '.', "output") # Define the output directory path
    os.makedirs(output_dir, exist_ok=True) # Create the output directory if it doesn't exist
    output_filepath = os.path.join(output_dir, output_filename) # Create the full path to the file inside the output directory

    print(f"\nProcessing complete. Saving data to: {output_filepath}")

    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(all_app_data, f, indent=4) # Use indent for readability
        print("Successfully saved app information.")
    except IOError as e:
        print(f"Error writing to file {output_filepath}: {e}", file=sys.stderr)
        # Fallback: Print JSON to console if file write fails
        print("\n--- JSON Output (Could not save to file) ---")
        print(json.dumps(all_app_data, indent=4))
        print("--- End JSON Output ---")