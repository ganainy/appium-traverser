# -*- coding: utf-8 -*-
"""
Standalone Android App Package and Activity Finder

This script identifies the package name, application label (name), and main launch
activity of Android applications installed on a connected device using ADB.

AI Filtering Option:
If the environment variable `FILTER_HEALTH_APPS` is set to `true` (case-insensitive),
the script will use the Google Gemini AI model to filter the discovered applications,
keeping only those primarily related to health, fitness, wellness, medical,
medication management, or mental health categories.

Output:
- A JSON file named `<device_id>_app_info_<all|health_filtered>.json` will be created
  in an 'output' subdirectory, containing a list of app information dictionaries.

Environment Variables:
    FILTER_HEALTH_APPS=true   : Enable AI filtering. Defaults to false if not set.
    GEMINI_API_KEY=<your_key> : Your Google Gemini API key. Required if filtering.
"""

import subprocess
import sys
import re
import json
import os
import traceback
from PIL.Image import Image
from dotenv import load_dotenv
import time # Added for potential delays/retries if needed

# --- Try importing Google AI Library (required only for filtering) ---
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
# -------------------------------------------------------------------

# --- Load Environment Variables ---
# Specify the exact path to the .env file
# Use raw string for Windows paths or forward slashes
dotenv_path = r'C:\Users\amrmo\PycharmProjects\appium-traverser\traverser_ai_api\.env'

# Check if the specified .env file exists
if os.path.exists(dotenv_path):
    print(f"Loading environment variables from: {dotenv_path}")
    load_dotenv(dotenv_path=dotenv_path, override=True) # override=True ensures .env takes precedence
else:
    # Optionally, load from the current directory or default locations
    print(f"Warning: Specified .env path not found: {dotenv_path}")
    print("Attempting to load .env from default locations (e.g., script directory).")
    load_dotenv(override=True) # Fallback to default behavior

ENABLE_AI_FILTERING = True
# Read the API key after loading
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# --- Configuration ---
DEFAULT_AI_MODEL_NAME = 'gemini-1.5-flash-latest' # Or 'gemini-pro'
AI_SAFETY_SETTINGS = {
    "HARM_CATEGORY_HARASSMENT": "BLOCK_MEDIUM_AND_ABOVE",
    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_MEDIUM_AND_ABOVE",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_MEDIUM_AND_ABOVE",
    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_MEDIUM_AND_ABOVE",
}
OUTPUT_DIR = os.path.join(os.path.dirname(__file__) or '.', "output")
MAX_APPS_TO_SEND_TO_AI = 200 # Adjust based on model limits and typical response sizes
THIRD_PARTY_APPS_ONLY = True # Set to False to include system apps

# --- Validate AI Prerequisites if Filtering Enabled ---
if ENABLE_AI_FILTERING:
    print("AI Filtering is ENABLED via environment variable.")
    if not GENAI_AVAILABLE:
        print("Error: AI Filtering enabled, but the 'google-generativeai' library is not installed.", file=sys.stderr)
        print("       Please install it: pip install google-generativeai", file=sys.stderr)
        # Allow script to continue without filtering if library is missing
        ENABLE_AI_FILTERING = False
        print("Warning: Disabling AI filtering due to missing library.", file=sys.stderr)
    elif not GEMINI_API_KEY:
        print("Error: AI Filtering enabled, but the GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        print("       Please set it in your environment or in the .env file.", file=sys.stderr)
        # Allow script to continue without filtering if key is missing
        ENABLE_AI_FILTERING = False
        print("Warning: Disabling AI filtering due to missing API key.", file=sys.stderr)
    else:
        print(f"Using AI Model: {DEFAULT_AI_MODEL_NAME}")
else:
    print("AI Filtering is DISABLED.")
# --- End Configuration and Checks ---


def run_adb_command(command_list):
    """Executes ADB, handles errors, returns stdout."""
    try:
        adb_command = ['adb'] + command_list
        # print(f"--- Running ADB: {' '.join(adb_command)}") # Uncomment for debugging
        result = subprocess.run(
            adb_command,
            capture_output=True, text=True, check=True,
            encoding='utf-8', errors='ignore'
        )
        if result.stderr:
            clean_stderr = "\n".join(line for line in result.stderr.splitlines() if not line.strip().startswith("Warning:"))
            if clean_stderr:
                 print(f"--- ADB STDERR:\n{clean_stderr.strip()}", file=sys.stderr)
        return result.stdout.strip()

    except FileNotFoundError:
        print("Fatal Error: 'adb' command not found. Make sure ADB is installed and in your system PATH.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        stderr_lower = e.stderr.lower() if e.stderr else ""
        if "device unauthorized" in stderr_lower:
             print("\nFatal Error: Device unauthorized. Please check your device and allow USB debugging. ***", file=sys.stderr)
             sys.exit(1)
        elif "device" in stderr_lower and ("not found" in stderr_lower or "offline" in stderr_lower):
             print("\nFatal Error: Device not found or offline. Ensure device is connected and USB debugging is enabled. Check 'adb devices'.", file=sys.stderr)
             sys.exit(1)
        # Don't print warnings for expected failures like 'activity not found'
        if "No activity found" not in str(e.output) and "exit status" not in stderr_lower and "error:" not in stderr_lower:
             # Only print stderr if it seems relevant and not just standard warnings
             relevant_stderr = "\n".join(line for line in e.stderr.splitlines() if not line.strip().startswith("Warning:")) if e.stderr else ""
             if relevant_stderr:
                  print(f"Warning: ADB command {' '.join(e.cmd)} failed.", file=sys.stderr)
                  print(f"Stderr: {relevant_stderr.strip()}", file=sys.stderr)

        return None # Indicate command failure


def get_device_serial():
    """Gets a unique device identifier."""
    output = run_adb_command(['get-serialno'])
    if output and output != "unknown" and "error" not in output.lower():
        serial = re.sub(r'[^\w\-.]', '_', output)
        return serial
    else:
        print("Warning: Could not get device serial via get-serialno. Trying 'adb devices'...", file=sys.stderr)
        devices_output = run_adb_command(['devices'])
        if devices_output:
            lines = devices_output.strip().splitlines()
            device_lines = [line for line in lines[1:] if line.strip() and '\tdevice' in line]
            if device_lines:
                first_device_line = device_lines[0]
                fallback_id = first_device_line.split('\t')[0]
                if fallback_id:
                    print(f"Using fallback identifier from 'adb devices': {fallback_id}", file=sys.stderr)
                    return re.sub(r'[^\w\-.]', '_', fallback_id)

        print("Error: Could not get any device identifier. Using generic 'unknown_device'.", file=sys.stderr)
        return "unknown_device"


def get_installed_packages(third_party_only=True):
    """Retrieves list of installed package names."""
    command = ['shell', 'pm', 'list', 'packages']
    if third_party_only:
        command.append('-3')

    output = run_adb_command(command)
    if output is None:
        print("Error: Failed to list packages via ADB.", file=sys.stderr)
        return []

    packages = [line.split(":", 1)[1] for line in output.splitlines() if line.strip().startswith("package:")]
    return packages


def get_app_label(package_name):
    """
    Retrieves the user-facing application label (name) for a given package.
    Tries 'aapt' first (if accessible), then falls back to refined 'dumpsys' parsing.

    Args:
        package_name (str): The package name to query.

    Returns:
        str or None: The application label if found, otherwise None.
    """
    if not package_name:
        return None
    # print(f"\n--- Getting label for: {package_name} ---") # Optional: Keep for detailed per-app logs

    # --- Attempt 1: Use aapt dump badging ---
    # This section remains, even though we know it fails on your specific setup,
    # because it's the preferred method when available. It will gracefully fail.
    # print("  Attempting 'pm path'...") # DEBUG
    path_output = run_adb_command(['shell', 'pm', 'path', package_name])
    apk_path = None
    if path_output:
        # print(f"  'pm path' output: {path_output[:100]}...") # DEBUG
        path_lines = path_output.splitlines()
        base_apk_line = next((line for line in path_lines if line.startswith('package:')), None)
        if base_apk_line:
            apk_path = base_apk_line.split(':', 1)[1]
            # print(f"  Found APK path: {apk_path}") # DEBUG
        # else:
            # print("  'pm path' output did not contain 'package:' line.") # DEBUG
    # else:
        # print("  'pm path' command failed or returned empty.") # DEBUG

    if apk_path:
        # print(f"  Attempting 'aapt dump badging' on {apk_path}...") # DEBUG
        aapt_command = ['shell', 'aapt', 'dump', 'badging', apk_path]
        aapt_output = run_adb_command(aapt_command) # run_adb_command handles errors/None return

        if aapt_output:
            # print(f"  'aapt' output received (first 200 chars): {aapt_output[:200]}...") # DEBUG
            # Regex priority: application-label variants first (handle single/double quotes)
            label_match = re.search(r"application-label(?:-[a-zA-Z_]+)*:['\"]([^'\"]+)['\"]", aapt_output)
            if label_match:
                # print(f"  (Label found via aapt [app-label] for {package_name})") # Debug
                return label_match.group(1).strip()

            # Fallback: application: label= variant (handle single/double quotes)
            label_match_alt = re.search(r"application:\s*.*?label=['\"]([^'\"]+)['\"].*?", aapt_output)
            if label_match_alt:
                 # print(f"  (Label found via aapt [app: label=] for {package_name})") # Debug
                 return label_match_alt.group(1).strip()
            # else:
                 # print(f"  (aapt ran for {package_name} but no label regex matched)") # DEBUG
        # else:
             # print(f"  'aapt dump badging' command likely failed or is unavailable for {package_name}.") # DEBUG - More specific message
    # else:
        # print(f"  Skipping 'aapt' because APK path wasn't found for {package_name}.") # DEBUG

    # --- Attempt 2: Fallback to dumpsys package (Refined Regex) ---
    # This is now the crucial part for your setup.
    # print(f"  (aapt failed/skipped for {package_name}, falling back to dumpsys for label)") # Debug
    dumpsys_command = ['shell', 'dumpsys', 'package', package_name]
    # print("  Attempting 'dumpsys package'...") # DEBUG
    dumpsys_output = run_adb_command(dumpsys_command)

    if dumpsys_output:
        # print(f"  'dumpsys' output received (first 500 chars): {dumpsys_output[:500]}...") # DEBUG - Essential if still failing

        # --- Refined Regex Attempts for dumpsys ---

        # Attempt A: Look for "Application label:" line (often present in newer dumpsys)
        # Handles potential localization codes like "Application label-en:"
        label_match_dumpsys_specific = re.search(r"^\s*Application label(?:-[a-zA-Z_]+)*:\s*(.+)$", dumpsys_output, re.MULTILINE | re.IGNORECASE)
        if label_match_dumpsys_specific:
            label = label_match_dumpsys_specific.group(1).strip()
            # Basic check to avoid resource IDs if possible (though less likely here)
            if not (label.startswith("0x") and len(label) > 5):
                 # print(f"  (Label found via dumpsys ['Application label:'] for {package_name})") # Debug
                 return label

        # Attempt B: Look for 'label=' line, handling quotes (more generic)
        label_match_dumpsys_quoted = re.search(r"^\s*label=['\"]([^'\"]+)['\"]", dumpsys_output, re.MULTILINE)
        if label_match_dumpsys_quoted:
            label = label_match_dumpsys_quoted.group(1).strip()
            # Basic check to avoid resource IDs
            if not (label.startswith("0x") and len(label) > 5):
                # print(f"  (Label found via dumpsys [quoted 'label='] for {package_name})") # Debug
                return label

        # Attempt C: Look for label within ApplicationInfo block (original, higher risk of resource ID)
        app_info_match = re.search(r'ApplicationInfo\{.*?label=([^}\s,]+).*?\}', dumpsys_output, re.DOTALL)
        if app_info_match:
            label = app_info_match.group(1).strip()
            # Explicitly check if it looks like a resource ID (hexadecimal)
            if not (label.startswith("0x") and len(label) > 5):
                # print(f"  (Label found via dumpsys [AppInfo block] for {package_name})") # Debug
                return label
            # else:
                # print(f"  (Label found via dumpsys [AppInfo block] for {package_name}, but looks like resource ID: {label})") # Debug Resource ID case

        # Attempt D: Look for the simple label= value without quotes (less common, but possible)
        label_match_dumpsys_simple = re.search(r'^\s*label=([^\s]+)$', dumpsys_output, re.MULTILINE)
        if label_match_dumpsys_simple:
            label = label_match_dumpsys_simple.group(1).strip()
            if not (label.startswith("0x") and len(label) > 5):
                # print(f"  (Label found via dumpsys [simple 'label='] for {package_name})") # Debug
                return label


        # If none of the dumpsys patterns matched...
        # print(f"  (dumpsys ran for {package_name} but no suitable label regex matched.)") # DEBUG

    # else:
        # print(f"  'dumpsys package' command failed or returned empty for {package_name}.") # DEBUG

    # --- Label Not Found ---
    # print(f"  *** Label not found for {package_name} by any method ***") # Debug failure
    return None

def find_main_activity(package_name):
    """Finds the main launcher activity for a package."""
    if not package_name: return None

    # Method 1: Use 'cmd package resolve-activity' (faster)
    # Query for MAIN/LAUNCHER intent specifically
    resolve_cmd = [
        'shell', 'cmd', 'package', 'resolve-activity', '--brief',
        '-a', 'android.intent.action.MAIN',
        '-c', 'android.intent.category.LAUNCHER',
        package_name
    ]
    output_resolve = run_adb_command(resolve_cmd)
    if output_resolve:
        activity_line = output_resolve.splitlines()[-1].strip()
        # Check if it's a valid activity path (contains '/') and not an error message
        if '/' in activity_line and "No activity found" not in activity_line and "does not handle" not in activity_line:
            # Example: com.example.app/.MainActivity or com.example.app/com.example.app.MainActivity
            parts = activity_line.split('/')
            pkg = parts[0]
            act_relative = parts[1]
            # Construct fully qualified name if relative (starts with '.')
            if act_relative.startswith('.'): return f"{pkg}{act_relative}"
            # If it contains a '.', assume it's fully qualified relative to *some* package.
            # If it doesn't start with the *target* package name, it *might* be an alias or different internal package.
            # However, often it's just the full name. Let's assume full name if it contains '.'
            if '.' in act_relative: return act_relative # Assume FQN like com.example.app.MainActivity
            # If no '.' and not starting with '.', assume relative to package
            return f"{pkg}.{act_relative}" # Assume relative like .MainActivity -> com.example.app.MainActivity

    # Method 2: Use 'dumpsys package' (more thorough fallback)
    # print(f"  (resolve-activity failed for {package_name}, falling back to dumpsys for activity)") # Debugging
    output_dumpsys = run_adb_command(['shell', 'dumpsys', 'package', package_name])
    if not output_dumpsys: return None

    # Regex to find MAIN/LAUNCHER activities within the package's section
    # Looks for "Activity ... package/activity" followed by the correct intent filter
    # Uses DOTALL because intent filters can span multiple lines
    # Non-greedy matching .*? is important
    regex = re.compile(
        r'^\s+Activity\s+Record\{.*? ' + re.escape(package_name) + r'/([^\s\}]+)\s*.*?\}\n' # Capture activity name after /
        r'(?:.*?\n)*?' # Match lines non-greedily until the filter
        r'^\s+IntentFilter\{.*?\n' # Start of IntentFilter block
        r'(?:.*?\n)*?' # Match lines within filter non-greedily
        r'^\s+Action: "android\.intent\.action\.MAIN"\n' # Must have MAIN action
        r'(?:.*?\n)*?' # Match lines non-greedily
        r'^\s+Category: "android\.intent\.category\.LAUNCHER"\n' # Must have LAUNCHER category
        r'(?:.*?\n)*?' # Match lines non-greedily until end of filter
        r'^\s+\}', # End of IntentFilter block
        re.MULTILINE | re.DOTALL
    )

    match = regex.search(output_dumpsys)
    if match:
        activity_part = match.group(1)
        # Construct fully qualified name if needed
        if activity_part.startswith('.'):
            return package_name + activity_part
        elif '.' in activity_part: # Contains a dot, assume fully qualified
            return activity_part
        else: # Doesn't start with '.' and has no '.', prepend package
             return package_name + '.' + activity_part

    return None # Activity not found by either method


def filter_apps_with_ai(app_data_list: list):
    """Uses Google Gemini AI to filter apps for health/fitness categories."""
    print("\n--- Filtering apps using AI ---")
    if not app_data_list:
        print("No app data to filter.")
        return []
    if not GENAI_AVAILABLE or not GEMINI_API_KEY:
        print("AI prerequisites not met, skipping filtering.")
        return app_data_list

    try:
        # Configure GenAI (do this inside the function to ensure key is loaded)
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name=DEFAULT_AI_MODEL_NAME,
            safety_settings=AI_SAFETY_SETTINGS
        )
    except Exception as e:
        print(f"Error configuring Google AI SDK: {e}", file=sys.stderr)
        traceback.print_exc()
        return app_data_list # Return original on config error

    filtered_results = []
    # Process in chunks if the list is too large
    for i in range(0, len(app_data_list), MAX_APPS_TO_SEND_TO_AI):
        chunk = app_data_list[i : i + MAX_APPS_TO_SEND_TO_AI]
        print(f"Processing chunk {i//MAX_APPS_TO_SEND_TO_AI + 1}/{(len(app_data_list) + MAX_APPS_TO_SEND_TO_AI - 1)//MAX_APPS_TO_SEND_TO_AI} ({len(chunk)} apps)...")

        try:
            app_data_json = json.dumps(chunk, indent=2)
        except Exception as e:
            print(f"Error encoding chunk to JSON: {e}", file=sys.stderr)
            continue # Skip this chunk on encoding error

        # Construct the prompt for the AI model
        prompt = f"""
                Analyze the following list of Android applications provided in JSON format. Each entry includes the application's package name (`package_name`), its user-facing label (`app_name`, which *might be null* if the retrieval script failed), and its main activity (`activity_name`).

Your tasks are:

1.  **Filter:** Identify ONLY the applications from the input list that are primarily related to **health, fitness, wellness, medical purposes, medication management, or mental health**. Exclude general utilities, system apps, games (unless specifically health/fitness focused), social media, etc. Focus on the app's *primary purpose*.

2.  **Populate Missing Names & Preserve Fields:** For the applications you identified in step 1 (the health-related ones):
    *   You *must* ensure the `app_name` field in your output JSON is populated.
        *   If the input `app_name` for a selected health app is **not** `null` and is a valid-looking name, **use that existing `app_name`** in your output.
        *   If the input `app_name` for a selected health app **is** `null` or empty, **infer a likely, user-friendly application name** based primarily on the `package_name`. Use common sense for naming (e.g., `com.myfitnesspal.android` should become `"MyFitnessPal"`, `com.google.android.apps.fitness` should become `"Google Fit"`). Make your best guess for a concise, readable name.
    *   You *must* include the original `package_name` from the input.
    *   You *must* include the original `activity_name` from the input (this field can be `null` if it was `null` in the input data for that app).
    *   You *must* infer a general application category (e.g., "Fitness", "Medical", "Wellness", "Productivity", "Social", "Game", "Utility") for each identified health-related app based on its `app_name` and `package_name`. Add this as a new field called `app_category` in your output.

Output ONLY a valid JSON array containing the entries for the health-related applications identified in step 1. Each object in the output array MUST have the `package_name`, `app_name` (non-null, populated as per step 2), `activity_name` (preserved from input), and `app_category` (inferred as per step 2) fields.

Do not include any explanatory text, comments, markdown formatting like ```json ... ``` around the JSON array, or any text other than the final JSON array itself. The output must be directly parseable as a JSON list of objects. If no apps in the input match the health criteria, output an empty JSON array `[]`.
                Input JSON:
                ```json
                {app_data_json} 
                Output ONLY a valid JSON array containing the entries from the input JSON that match the health-related criteria. Do not include any explanatory text, comments, or markdown formatting like json ... around the JSON array in your response. The output must be parseable directly as a JSON list of objects. If no apps in the input match the criteria, output an empty JSON array [].
                """
        print(f"Sending {len(chunk)} apps to AI model {DEFAULT_AI_MODEL_NAME}...")
        try:
            response = model.generate_content(prompt)

            # --- Debugging: Print raw AI response ---
            # print("--- Raw AI Response Text ---")
            # try:
            #    print(response.text)
            # except Exception as e:
            #    print(f"Error accessing response text: {e}")
            #    if hasattr(response, 'prompt_feedback'):
            #         print(f"Prompt Feedback: {response.prompt_feedback}")
            # print("--------------------------")
            # --- End Debugging ---

            # Extract and parse the JSON response
            try:
                # Clean potential markdown fences and whitespace
                response_text = response.text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()

                # Handle empty response or potential non-JSON preamble
                if not response_text or response_text == "[]":
                    print("AI identified 0 relevant apps in this chunk.")
                    continue # Move to next chunk if response is empty array

                # Attempt to parse
                chunk_filtered_list = json.loads(response_text)

                # Basic validation: Check if it's a list
                if isinstance(chunk_filtered_list, list):
                    print(f"AI identified {len(chunk_filtered_list)} relevant apps in this chunk.")
                    filtered_results.extend(chunk_filtered_list)
                else:
                    print(f"Warning: AI response for chunk was not a JSON list. Response type: {type(chunk_filtered_list)}", file=sys.stderr)
                    print(f"AI Response snippet: {response.text[:200]}...", file=sys.stderr)

            except json.JSONDecodeError as e:
                print(f"Error: Could not parse AI response for chunk as JSON: {e}", file=sys.stderr)
                print(f"AI Response snippet: {response.text[:500]}...", file=sys.stderr)
                # Optionally add chunk to results anyway, or skip
                # print("Warning: Including original chunk data due to AI parsing error.")
                # filtered_results.extend(chunk)
            except AttributeError:
                print("Error: AI response object issue (no '.text'?). Check for blocking.", file=sys.stderr)
                if hasattr(response, 'prompt_feedback'):
                    print(f"Prompt Feedback: {response.prompt_feedback}", file=sys.stderr)
                else:
                    print(f"AI Response object type: {type(response)}", file=sys.stderr)
                # print("Warning: Including original chunk data due to AI response error.")
                # filtered_results.extend(chunk)
            except Exception as e:
                print(f"Error processing AI response for chunk: {e}", file=sys.stderr)
                if hasattr(response, 'prompt_feedback'):
                    print(f"Prompt Feedback: {response.prompt_feedback}", file=sys.stderr)
                traceback.print_exc()
                # print("Warning: Including original chunk data due to AI processing error.")
                # filtered_results.extend(chunk)

        except Exception as e:
            print(f"Error during AI API call for chunk: {e}", file=sys.stderr)
            print("AI filtering for this chunk failed.")
            # Check if the error is due to prompt feedback (e.g., blocked content)
            # This structure might vary slightly depending on the google-generativeai version
            if hasattr(e, 'response') and hasattr(e.response, 'prompt_feedback'):
                print(f"Prompt Feedback: {e.response.prompt_feedback}", file=sys.stderr)
            else:
                traceback.print_exc() # Print full traceback for unexpected AI errors
            # Decide how to handle chunk failure - skip or include original?
            # print("Warning: Including original chunk data due to AI API error.")
            # filtered_results.extend(chunk)

        # Optional delay between chunks if hitting rate limits
        # time.sleep(1)

    print(f"\n--- AI Filtering Finished. Total relevant apps identified: {len(filtered_results)} ---")
    return filtered_results

#==============================================================================
# Main Execution Logic
#==============================================================================
if __name__ == "__main__":
    start_time = time.time()
    print("--- Starting App Info Finder ---")
    # 1. Get Device ID
    device_id = get_device_serial()
    if not device_id or device_id == "unknown_device":
        print("\nFatal Error: Could not determine device ID. Ensure device is connected and authorized.", file=sys.stderr)
        sys.exit(1)
    print(f"Target device ID: {device_id}")

    # 2. Create Output Directory
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        print(f"Output directory: {os.path.abspath(OUTPUT_DIR)}")
    except OSError as e:
        print(f"\nFatal Error: Could not create output directory '{OUTPUT_DIR}': {e}", file=sys.stderr)
        sys.exit(1)

    # 3. Get Installed Packages
    pkg_type = "third-party" if THIRD_PARTY_APPS_ONLY else "all"
    print(f"Fetching installed {pkg_type} packages...")
    packages = get_installed_packages(third_party_only=THIRD_PARTY_APPS_ONLY)
    if not packages:
        print(f"\nNo {pkg_type} packages found or error retrieving packages. Exiting.")
        sys.exit(0) # Exit gracefully if no packages found
    print(f"Found {len(packages)} {pkg_type} packages.")

    # 4. Retrieve App Info (Label and Activity)
    all_app_data = []
    print("Retrieving app label and main activity for each package...")
    total_packages = len(packages)
    label_missing_count = 0 # Track apps where label couldn't be found

    activity_missing_count = 0 # Track apps where activity couldn't be found

    for i, pkg_name in enumerate(packages):
        progress_percent = ((i + 1) / total_packages) * 100
        # Display progress on the same line
        print(f"\\rProcessing package {i+1}/{total_packages} ({progress_percent:.1f}%) [{pkg_name[:30].ljust(30)}]...", end="", flush=True)

        app_label = get_app_label(pkg_name)
        if not app_label:
            label_missing_count += 1
            # print(f"Warning: App label not found for {pkg_name}") # Optional detailed warning

        main_activity = find_main_activity(pkg_name)
        if not main_activity:
            activity_missing_count += 1
            # print(f"Warning: Main activity not found for {pkg_name}") # Optional detailed warning

        current_app_info = {
            "package_name": pkg_name,
            "app_name": app_label,
            "activity_name": main_activity
        }
        all_app_data.append(current_app_info)

    # Print final status for info retrieval (clear the progress line first)
    print(f"\\r{' ' * 80}\\r", end="") # Clear line
    print(f"Finished retrieving info for {total_packages} packages.")
    if label_missing_count > 0:
        print(f"Warning: Could not determine app label for {label_missing_count} app(s).")
    if activity_missing_count > 0:
        print(f"Warning: Could not determine main activity for {activity_missing_count} app(s).")

    # 5. Apply AI Filtering (if enabled and possible)
    final_app_data = all_app_data
    output_suffix = "all"
    if ENABLE_AI_FILTERING: # Check if filtering was requested AND prerequisites were met
        if not all_app_data:
            print("\nSkipping AI filtering as no app data was collected.")
        else:
            final_app_data = filter_apps_with_ai(all_app_data)
            # Only change suffix if filtering was actually performed AND returned a potentially different list
            if final_app_data is not all_app_data:
                # Further check: Did the AI actually filter anything?
                if len(final_app_data) < len(all_app_data):
                    output_suffix = "health_filtered"
                else:
                    # AI ran but returned all apps (or failed and returned original)
                    print("\nAI filtering process completed, but all apps were returned or filtering failed (check logs).")
            elif final_app_data is all_app_data: # Handle case where filter_apps_with_ai explicitly returned original due to errors
                print("\nAI filtering process failed or was skipped (check logs). Outputting all apps.")
    # Inform user if filtering was requested but skipped due to missing prerequisites earlier
    elif os.getenv('FILTER_HEALTH_APPS', 'false').lower() == 'true':
        print("\nAI Filtering was requested via environment variable but prerequisites were not met earlier. Outputting all apps.")

    # 6. Determine Output File Path
    output_filename = f"{device_id}_app_info_{output_suffix}.json"
    output_filepath = os.path.join(OUTPUT_DIR, output_filename)

    # 7. Write Results to JSON File
    print(f"\nWriting {len(final_app_data)} app entries to: {output_filepath}")
    try:
        # Ensure None values are written as null in JSON
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(final_app_data, f, indent=4, ensure_ascii=False)
        print(f"--- App information saved successfully to {output_filepath} ---")
    except IOError as e:
        print(f"\nError writing output file '{output_filepath}': {e}", file=sys.stderr)
    except Exception as e:
        print(f"\nAn unexpected error occurred during file writing: {e}", file=sys.stderr)
        traceback.print_exc()

    end_time = time.time()
    print(f"--- Script finished in {end_time - start_time:.2f} seconds. ---")