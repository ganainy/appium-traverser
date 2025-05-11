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
# Determine project root assuming this script is in project_root/traverser_ai_api/
project_root_env = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
dotenv_path = os.path.join(project_root_env, '.env')


# Check if the specified .env file exists
if os.path.exists(dotenv_path):
    print(f"Loading environment variables from: {dotenv_path}")
    load_dotenv(dotenv_path=dotenv_path, override=True) # override=True ensures .env takes precedence
else:
    # Optionally, load from the current directory or default locations
    print(f"Warning: Specified .env path not found: {dotenv_path}")
    print("Attempting to load .env from default locations (e.g., script directory).")
    load_dotenv(override=True) # Fallback to default behavior

# CHANGED: Default to True for AI filtering when called from UI.
# UI controller expects health-filtered list by default.
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
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output_data", "app_info"))
MAX_APPS_TO_SEND_TO_AI = 200 # Adjust based on model limits and typical response sizes
THIRD_PARTY_APPS_ONLY = True # Set to False to include system apps

# --- Validate AI Prerequisites if Filtering Enabled ---
if ENABLE_AI_FILTERING:
    print("AI Filtering is ENABLED (default or by script setting).")
    if not GENAI_AVAILABLE:
        print("Error: AI Filtering enabled, but the 'google-generativeai' library is not installed.", file=sys.stderr)
        print("       Please install it: pip install google-generativeai", file=sys.stderr)
        ENABLE_AI_FILTERING = False # Can't filter without library
        print("Warning: Disabling AI filtering due to missing library.", file=sys.stderr)
    elif not GEMINI_API_KEY:
        print("Error: AI Filtering enabled, but the GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        print("       Please set it in your environment or in the .env file.", file=sys.stderr)
        ENABLE_AI_FILTERING = False # Can't filter without key
        print("Warning: Disabling AI filtering due to missing API key.", file=sys.stderr)
    else:
        print(f"Using AI Model: {DEFAULT_AI_MODEL_NAME}")
else:
    print("AI Filtering is DISABLED (either by script setting or missing prerequisites).")
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
        sys.exit(1) # Exit if ADB not found, critical for this script
    except subprocess.CalledProcessError as e:
        stderr_lower = e.stderr.lower() if e.stderr else ""
        if "device unauthorized" in stderr_lower:
             print("\nFatal Error: Device unauthorized. Please check your device and allow USB debugging. ***", file=sys.stderr)
             sys.exit(1) # Exit on critical device errors
        elif "device" in stderr_lower and ("not found" in stderr_lower or "offline" in stderr_lower):
             print("\nFatal Error: Device not found or offline. Ensure device is connected and USB debugging is enabled. Check 'adb devices'.", file=sys.stderr)
             sys.exit(1) # Exit on critical device errors
        
        # Don't print warnings for expected failures like 'activity not found'
        # Check if it's a relevant error or just noise
        is_relevant_error = True
        if "No activity found" in str(e.output): is_relevant_error = False
        if "exit status" in stderr_lower: is_relevant_error = False # Often noisy from pm path etc.
        # `aapt` often prints to stderr for non-errors or info, filter those too
        if "aapt" in ' '.join(e.cmd) and not ("error:" in stderr_lower or "failed" in stderr_lower):
            is_relevant_error = False


        if is_relevant_error:
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
        return "unknown_device" # Return a placeholder, but UI might need to handle this


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
    """
    if not package_name:
        return None
    # print(f"\n--- Getting label for: {package_name} ---") 

    path_output = run_adb_command(['shell', 'pm', 'path', package_name])
    apk_path = None
    if path_output:
        path_lines = path_output.splitlines()
        base_apk_line = next((line for line in path_lines if line.startswith('package:')), None)
        if base_apk_line:
            apk_path = base_apk_line.split(':', 1)[1]

    if apk_path:
        aapt_command = ['shell', 'aapt', 'dump', 'badging', apk_path]
        aapt_output = run_adb_command(aapt_command) 

        if aapt_output:
            label_match = re.search(r"application-label(?:-[a-zA-Z_]+)*:['\"]([^'\"]+)['\"]", aapt_output)
            if label_match:
                return label_match.group(1).strip()
            label_match_alt = re.search(r"application:\s*.*?label=['\"]([^'\"]+)['\"].*?", aapt_output)
            if label_match_alt:
                 return label_match_alt.group(1).strip()

    dumpsys_command = ['shell', 'dumpsys', 'package', package_name]
    dumpsys_output = run_adb_command(dumpsys_command)

    if dumpsys_output:
        label_match_dumpsys_specific = re.search(r"^\s*Application label(?:-[a-zA-Z_]+)*:\s*(.+)$", dumpsys_output, re.MULTILINE | re.IGNORECASE)
        if label_match_dumpsys_specific:
            label = label_match_dumpsys_specific.group(1).strip()
            if not (label.startswith("0x") and len(label) > 5):
                 return label

        label_match_dumpsys_quoted = re.search(r"^\s*label=['\"]([^'\"]+)['\"]", dumpsys_output, re.MULTILINE)
        if label_match_dumpsys_quoted:
            label = label_match_dumpsys_quoted.group(1).strip()
            if not (label.startswith("0x") and len(label) > 5):
                return label

        app_info_match = re.search(r'ApplicationInfo\{.*?label=([^}\s,]+).*?\}', dumpsys_output, re.DOTALL)
        if app_info_match:
            label = app_info_match.group(1).strip()
            if not (label.startswith("0x") and len(label) > 5):
                return label
        
        label_match_dumpsys_simple = re.search(r'^\s*label=([^\s]+)$', dumpsys_output, re.MULTILINE)
        if label_match_dumpsys_simple:
            label = label_match_dumpsys_simple.group(1).strip()
            if not (label.startswith("0x") and len(label) > 5):
                return label
    return None

def find_main_activity(package_name):
    """Finds the main launcher activity for a package."""
    if not package_name: return None

    resolve_cmd = [
        'shell', 'cmd', 'package', 'resolve-activity', '--brief',
        '-a', 'android.intent.action.MAIN',
        '-c', 'android.intent.category.LAUNCHER',
        package_name
    ]
    output_resolve = run_adb_command(resolve_cmd)
    if output_resolve:
        activity_line = output_resolve.splitlines()[-1].strip()
        if '/' in activity_line and "No activity found" not in activity_line and "does not handle" not in activity_line:
            parts = activity_line.split('/')
            pkg_from_resolve = parts[0] # This might differ from package_name if it's an alias
            act_relative = parts[1]
            if act_relative.startswith('.'): return f"{package_name}{act_relative}" # Use original package_name for consistency
            if '.' in act_relative: return act_relative 
            return f"{package_name}.{act_relative}" 

    output_dumpsys = run_adb_command(['shell', 'dumpsys', 'package', package_name])
    if not output_dumpsys: return None

    regex = re.compile(
        r'^\s+Activity\s+Record\{.*? ' + re.escape(package_name) + r'/([^\s\}]+)\s*.*?\}\n' 
        r'(?:.*?\n)*?' 
        r'^\s+IntentFilter\{.*?\n' 
        r'(?:.*?\n)*?' 
        r'^\s+Action: "android\.intent\.action\.MAIN"\n' 
        r'(?:.*?\n)*?' 
        r'^\s+Category: "android\.intent\.category\.LAUNCHER"\n' 
        r'(?:.*?\n)*?' 
        r'^\s+\}', 
        re.MULTILINE | re.DOTALL
    )
    match = regex.search(output_dumpsys)
    if match:
        activity_part = match.group(1)
        if activity_part.startswith('.'): return package_name + activity_part
        elif '.' in activity_part: return activity_part
        else: return package_name + '.' + activity_part
    return None


def filter_apps_with_ai(app_data_list: list):
    """Uses Google Gemini AI to filter apps for health/fitness categories."""
    print("\n--- Filtering apps using AI ---")
    if not app_data_list:
        print("No app data to filter.")
        return []
    if not GENAI_AVAILABLE or not GEMINI_API_KEY: # Re-check here as it's critical
        print("AI prerequisites not met (GenAI lib or API Key missing). Skipping AI filtering.", file=sys.stderr)
        return app_data_list # Return original list if AI cannot be used

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name=DEFAULT_AI_MODEL_NAME,
            safety_settings=AI_SAFETY_SETTINGS
        )
    except Exception as e:
        print(f"Error configuring Google AI SDK: {e}", file=sys.stderr)
        traceback.print_exc()
        return app_data_list 

    filtered_results = []
    for i in range(0, len(app_data_list), MAX_APPS_TO_SEND_TO_AI):
        chunk = app_data_list[i : i + MAX_APPS_TO_SEND_TO_AI]
        print(f"Processing chunk {i//MAX_APPS_TO_SEND_TO_AI + 1}/{(len(app_data_list) + MAX_APPS_TO_SEND_TO_AI - 1)//MAX_APPS_TO_SEND_TO_AI} ({len(chunk)} apps)...")

        try:
            app_data_json_str = json.dumps(chunk, indent=2) # Renamed to avoid conflict
        except Exception as e:
            print(f"Error encoding chunk to JSON: {e}", file=sys.stderr)
            continue 

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
                {app_data_json_str} 
                ```
                Output ONLY a valid JSON array containing the entries from the input JSON that match the health-related criteria. Do not include any explanatory text, comments, or markdown formatting like json ... around the JSON array in your response. The output must be parseable directly as a JSON list of objects. If no apps in the input match the criteria, output an empty JSON array [].
                """
        print(f"Sending {len(chunk)} apps to AI model {DEFAULT_AI_MODEL_NAME}...")
        try:
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            if not response_text or response_text == "[]":
                print("AI identified 0 relevant apps in this chunk.")
                continue

            chunk_filtered_list = json.loads(response_text)
            if isinstance(chunk_filtered_list, list):
                print(f"AI identified {len(chunk_filtered_list)} relevant apps in this chunk.")
                filtered_results.extend(chunk_filtered_list)
            else:
                print(f"Warning: AI response for chunk was not a JSON list. Snippet: {response.text[:200]}...", file=sys.stderr)

        except json.JSONDecodeError as e:
            print(f"Error: Could not parse AI response for chunk as JSON: {e}", file=sys.stderr)
            print(f"AI Response snippet: {response.text[:500]}...", file=sys.stderr)
        except AttributeError: # Handle cases where response.text might not exist (e.g. blocked content)
            print("Error: AI response object issue (no '.text' attribute, possibly blocked).", file=sys.stderr)
            if hasattr(response, 'prompt_feedback'): print(f"Prompt Feedback: {response.prompt_feedback}", file=sys.stderr)
        except Exception as e: # Catch other errors during AI call or processing
            print(f"Error during AI API call or processing for chunk: {e}", file=sys.stderr)
            if hasattr(response, 'prompt_feedback'): print(f"Prompt Feedback: {response.prompt_feedback}", file=sys.stderr)
            else: traceback.print_exc()
    print(f"\n--- AI Filtering Finished. Total relevant apps identified: {len(filtered_results)} ---")
    return filtered_results

def generate_app_info_cache(target_package_name_filter=None, target_app_label_filter=None, use_ai_filtering_for_this_cache: bool = False):
    """
    Discovers app information, optionally filters it, and saves it.
    Returns the path to the cache file and the list of app_info.
    """
    print(f"--- (Re)generating App Info Cache (AI filter requested for this cache: {use_ai_filtering_for_this_cache}) ---")
    device_id = get_device_serial()
    if not device_id or device_id == "unknown_device":
        print("Critical Error: Could not obtain a valid device ID. Cannot generate cache.", file=sys.stderr)
        return None, [] 

    print(f"Device ID: {device_id}")
    print(f"\n--- Discovering installed packages (Third-party only: {THIRD_PARTY_APPS_ONLY}) ---")
    packages = get_installed_packages(third_party_only=THIRD_PARTY_APPS_ONLY)
    if not packages:
        print("No packages found. Ensure device is connected and has third-party apps if filter is on.", file=sys.stderr)
        return None, [] 
    print(f"Found {len(packages)} packages.")

    all_apps_info = []
    print(f"\n--- Retrieving App Info (Label & Main Activity) for {len(packages)} packages ---")
    for i, package_name in enumerate(packages):
        app_label = get_app_label(package_name)
        main_activity = find_main_activity(package_name)
        all_apps_info.append({"package_name": package_name, "app_name": app_label, "activity_name": main_activity})
        if (i + 1) % 20 == 0 or (i + 1) == len(packages):
            print(f"  Processed {i+1}/{len(packages)} packages...")
    print(f"\n--- Retrieved info for {len(all_apps_info)} apps before any AI filtering ---")

    apps_to_save = list(all_apps_info)
    ai_filter_was_applied_successfully = False

    if use_ai_filtering_for_this_cache: # This is True by default now because ENABLE_AI_FILTERING is True
        if not ENABLE_AI_FILTERING: # This check is now somewhat redundant but good for clarity
            print("Warning: AI Filtering requested for cache, but globally disabled. Skipping.", file=sys.stderr)
        elif not GENAI_AVAILABLE or not GEMINI_API_KEY:
             print("Warning: AI Filtering requested for cache, but AI prerequisites not met. Skipping.", file=sys.stderr)
        else:
            print("Attempting AI filtering for this cache generation...")
            filtered_apps = filter_apps_with_ai(list(all_apps_info)) 
            if filtered_apps is not None:
                apps_to_save = filtered_apps
                if len(apps_to_save) != len(all_apps_info) or any(app not in all_apps_info for app in apps_to_save):
                     ai_filter_was_applied_successfully = True
                print(f"AI filtering for cache resulted in {len(apps_to_save)} apps. Filter effectively applied: {ai_filter_was_applied_successfully}")
            else:
                print("AI filtering for cache returned None. Using all apps.", file=sys.stderr)
    else:
        print("AI Filtering not requested/applicable for this cache generation. Using all discovered apps.")

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: {OUTPUT_DIR}")

    file_suffix = "health_filtered" if use_ai_filtering_for_this_cache and ai_filter_was_applied_successfully else "all"
    output_filename = f"{device_id}_app_info_{file_suffix}.json"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    print(f"\n--- Saving app info to: {output_path} (Suffix: {file_suffix}) ---")
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
    Loads app data from an existing JSON file, filters it using AI,
    and saves the filtered data to a new JSON file.
    """
    if not os.path.exists(input_filepath):
        print(f"Error: Input file not found: {input_filepath}", file=sys.stderr)
        return None

    print(f"--- Processing existing app info file: {input_filepath} ---")
    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            all_apps_data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON from {input_filepath}: {e}", file=sys.stderr)
        return None

    if not isinstance(all_apps_data, list):
        print(f"Error: Data in {input_filepath} is not a JSON list.", file=sys.stderr)
        return None
    
    if not ENABLE_AI_FILTERING or not GENAI_AVAILABLE or not GEMINI_API_KEY:
        print("Warning: AI Filtering disabled or prerequisites not met. Cannot filter existing file.", file=sys.stderr)
        return None # Cannot perform the main task of this function

    print(f"Sending {len(all_apps_data)} apps from input file to AI for health filtering...")
    ai_filtered_list = filter_apps_with_ai(list(all_apps_data)) 

    if ai_filtered_list is None: # filter_apps_with_ai might return original on error, or []
        print("AI filtering returned None or failed significantly. No output file will be saved.", file=sys.stderr)
        return None
    
    base, ext = os.path.splitext(os.path.basename(input_filepath))
    # Ensure output has a distinct name if input was already filtered or "all"
    new_suffix = "health_filtered_again" if "health_filtered" in base else "health_filtered"
    output_filename = f"{base.replace('_all', '').replace('_health_filtered', '')}_{new_suffix}{ext}"
    output_filepath = os.path.join(os.path.dirname(input_filepath), output_filename)

    print(f"--- Saving filtered app info to: {output_filepath} ---")
    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(ai_filtered_list, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved {len(ai_filtered_list)} filtered app(s) to {output_filepath}")
        return output_filepath
    except IOError as e:
        print(f"Error writing to file {output_filepath}: {e}", file=sys.stderr)
        return None

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
        help="Path to an existing app info JSON file to be filtered by AI. Required if --mode is 'filter-existing'."
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
        # ENABLE_AI_FILTERING is now True by default in this script.
        # generate_app_info_cache will use this.
        output_file_path, _ = generate_app_info_cache(
            use_ai_filtering_for_this_cache=ENABLE_AI_FILTERING 
        )
        if output_file_path:
            # This print is crucial for ui_controller.py to parse the path
            print(f"\nCache file generated at: {output_file_path}") 
        else:
            print("\nApp info cache generation failed or did not produce a file.")

    end_time = time.time()
    print(f"\n--- Script Finished in {end_time - start_time:.2f} seconds ---")