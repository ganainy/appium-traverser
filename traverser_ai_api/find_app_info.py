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
from PIL.Image import Image # Assuming this is used elsewhere, keeping it. If not, it could be removed.
from dotenv import load_dotenv
import argparse # Added for command line arguments
import time # Added: Missing import for time.time()

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
# OUTPUT_DIR = os.path.join(os.path.dirname(__file__) or '.', "output_data", "app_info") # Old path
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output_data", "app_info")) # Changed to point to project root's output_data
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

def generate_app_info_cache(target_package_name_filter=None, target_app_label_filter=None, use_ai_filtering_for_this_cache: bool = False):
    """
    Discovers app information, optionally filters it based on the use_ai_filtering_for_this_cache flag, 
    and saves it to a cache file.
    Returns the path to the cache file and the list of discovered app_info.

    Args:
        target_package_name_filter (str, optional): Specific package name to look for (not currently used for filtering logic here).
        target_app_label_filter (str, optional): Specific app label to look for (not currently used for filtering logic here).
        use_ai_filtering_for_this_cache (bool): If True, attempts to apply AI filtering. Defaults to False.
    """
    print(f"--- (Re)generating App Info Cache (AI filter requested for this cache: {use_ai_filtering_for_this_cache}) ---")
    # 1. Get Device ID
    device_id = get_device_serial()
    if not device_id or device_id == "unknown_device":
        print("Critical Error: Could not obtain a valid device ID. Exiting.", file=sys.stderr)
        return None, [] # Indicate failure

    print(f"Device ID: {device_id}")

    # 2. Get Installed Packages
    print(f"\\n--- Discovering installed packages (Third-party only: {THIRD_PARTY_APPS_ONLY}) ---")
    packages = get_installed_packages(third_party_only=THIRD_PARTY_APPS_ONLY)
    if not packages:
        print("No packages found. Ensure device is connected and has third-party apps if filter is on.", file=sys.stderr)
        return None, [] # Indicate failure

    print(f"Found {len(packages)} packages.")

    # 3. Get App Info (Label and Main Activity) for each package
    all_apps_info = []
    print(f"\\n--- Retrieving App Info (Label & Main Activity) for {len(packages)} packages ---")
    for i, package_name in enumerate(packages):
        # print(f"Processing package {i+1}/{len(packages)}: {package_name}") # Verbose
        app_label = get_app_label(package_name)
        main_activity = find_main_activity(package_name)

        app_info = {
            "package_name": package_name,
            "app_name": app_label, # Can be None
            "activity_name": main_activity # Can be None
        }
        all_apps_info.append(app_info)
        if (i + 1) % 20 == 0 or (i + 1) == len(packages):
            print(f"  Processed {i+1}/{len(packages)} packages...")


    print(f"\\n--- Retrieved info for {len(all_apps_info)} apps before any AI filtering ---")

    # 4. AI Filtering (if requested for this specific cache generation)
    apps_to_save = list(all_apps_info) # Start with a copy of all apps
    ai_filter_was_applied_successfully = False

    if use_ai_filtering_for_this_cache:
        if not ENABLE_AI_FILTERING:
            print("Warning: AI Filtering was requested for cache, but it is globally disabled in find_app_info.py. Skipping AI filtering.", file=sys.stderr)
        elif not GENAI_AVAILABLE or not GEMINI_API_KEY:
            print("Warning: AI Filtering was requested for cache, but AI prerequisites (library/API key) are not met. Skipping AI filtering.", file=sys.stderr)
        else:
            print("Attempting AI filtering for this cache generation...")
            filtered_apps = filter_apps_with_ai(list(all_apps_info)) # Pass a copy to AI
            if filtered_apps is not None: # filter_apps_with_ai returns original on some errors, or []
                apps_to_save = filtered_apps
                # Check if filtering actually changed the list compared to the original full list
                if len(apps_to_save) != len(all_apps_info) or any(app not in all_apps_info for app in apps_to_save):
                     ai_filter_was_applied_successfully = True # Mark that AI did something
                print(f"AI filtering for cache resulted in {len(apps_to_save)} apps. Filter effectively applied: {ai_filter_was_applied_successfully}")
            else:
                # This case implies a more significant issue within filter_apps_with_ai if it returns None
                print("AI filtering for cache returned None, indicating a problem. Using all apps for this cache.", file=sys.stderr)
    else:
        print("AI Filtering not requested for this cache generation. Using all discovered apps.")

    # 5. Prepare Output
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: {OUTPUT_DIR}")

    # Suffix depends on whether AI filtering was requested AND successfully changed the app list.
    file_suffix = "health_filtered" if use_ai_filtering_for_this_cache and ai_filter_was_applied_successfully else "all"
    output_filename = f"{device_id}_app_info_{file_suffix}.json"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    print(f"\\n--- Saving app info to: {output_path} (Suffix: {file_suffix}) ---")
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(apps_to_save, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved {len(apps_to_save)} app(s) to {output_path}")
    except IOError as e:
        print(f"Error writing to file {output_path}: {e}", file=sys.stderr)
        traceback.print_exc()
        return None, apps_to_save 

    return output_path, apps_to_save

def filter_existing_app_info_file(input_filepath: str):
    """
    Loads app data from an existing JSON file, filters it using AI based on a desired category,
    and saves the filtered data to a new JSON file.
    """
    if not os.path.exists(input_filepath):
        print(f"Error: Input file not found: {input_filepath}", file=sys.stderr)
        return None

    print(f"--- Processing existing app info file: {input_filepath} ---")
    # The filter_apps_with_ai function uses a hardcoded prompt for health/fitness.

    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            all_apps_data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON from {input_filepath}: {e}", file=sys.stderr)
        return None

    if not isinstance(all_apps_data, list):
        print(f"Error: Data in {input_filepath} is not a JSON list.", file=sys.stderr)
        return None

    filtered_apps_data = []
    if not all_apps_data:
        print(f"Input file {input_filepath} contains no app data. Nothing to filter.", file=sys.stderr)
        # Output will be an empty list, written to file.
    else:
        # Ensure AI is available and configured for filtering
        if not ENABLE_AI_FILTERING: # This global is defined near the top of the script
            print("Warning: AI Filtering is globally disabled in this script. Cannot filter.", file=sys.stderr)
            return None 
        if not GENAI_AVAILABLE or not GEMINI_API_KEY: # These globals are also defined/checked near the top
            print("Warning: AI prerequisites (library/API key) are not met. Cannot filter.", file=sys.stderr)
            return None

        print(f"Sending {len(all_apps_data)} apps from input file to AI for filtering...")
        # filter_apps_with_ai is an existing function in this file
        ai_filtered_list = filter_apps_with_ai(list(all_apps_data)) # Pass a copy

        if ai_filtered_list is None:
            print("AI filtering returned None, indicating a problem. No output file will be saved.", file=sys.stderr)
            return None
        filtered_apps_data = ai_filtered_list

    # Determine output filename
    base, ext = os.path.splitext(os.path.basename(input_filepath)) # Use basename for constructing new filename
    output_filename = f"{base}_fitness_filtered{ext}"
    # Save in the same directory as the input file
    output_filepath = os.path.join(os.path.dirname(input_filepath), output_filename)

    print(f"--- Saving filtered app info to: {output_filepath} ---")
    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(filtered_apps_data, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved {len(filtered_apps_data)} filtered app(s) to {output_filepath}")
        return output_filepath
    except IOError as e:
        print(f"Error writing to file {output_filepath}: {e}", file=sys.stderr)
        traceback.print_exc()
        return None

#==============================================================================
# Main Execution Logic
#==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Android App Info Finder and AI Filter.")
    parser.add_argument(
        "--mode",
        choices=['discover', 'filter-existing'],
        default='discover',
        help="Operation mode: 'discover' new app info (default), or 'filter-existing' an input JSON file."
    )
    parser.add_argument(
        "--input-file",
        type=str,
        help="Path to an existing app info JSON file (e.g., ..._all.json) to be filtered by AI. Required if --mode is 'filter-existing'."
    )

    args = parser.parse_args()
    start_time = time.time()

    if args.mode == 'filter-existing':
        if not args.input_file:
            print("Error: --input-file is required when --mode is 'filter-existing'.", file=sys.stderr)
            sys.exit(1)
        print(f"--- Starting App Info Filter (Filter Existing File Mode) ---")
        output_file_path = filter_existing_app_info_file(args.input_file)
        if output_file_path:
            print(f"Filtered file generated at: {output_file_path}")
        else:
            print("App info filtering failed or did not produce a file.")

    elif args.mode == 'discover':
        print("--- Starting App Info Finder (Standalone Discovery Mode) ---")
        # When run standalone, use_ai_filtering_for_this_cache is determined by the script's own ENABLE_AI_FILTERING setting
        # and also depends on GENAI_AVAILABLE and GEMINI_API_KEY being set up.
        # The generate_app_info_cache function handles the logic of whether to apply AI filtering.
        output_file_path, _ = generate_app_info_cache( # _ to ignore discovered_apps list
            use_ai_filtering_for_this_cache=ENABLE_AI_FILTERING 
        )

        if output_file_path:
            print(f"\\nCache file generated at: {output_file_path}")
        else:
            print("\\nApp info cache generation failed or did not produce a file.")

    end_time = time.time()
    print(f"\\n--- Script Finished in {end_time - start_time:.2f} seconds ---")