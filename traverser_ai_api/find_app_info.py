# -*- coding: utf-8 -*-
"""
Standalone Android App Package and Activity Finder

This script identifies the package name, application label (name), and main launch
activity of Android applications installed on a connected device using ADB.

AI Filtering Option:
If AI filtering is enabled via the Config object and prerequisites are met,
the script will use the Google Gemini AI model to filter the discovered applications,
keeping only those primarily related to health, fitness, wellness, medical,
medication management, or mental health categories.

Output:
- A JSON file named `<device_id>_app_info_<all|health_filtered>.json` will be created
in the app_info_output_dir defined by the Config object, containing a list of
app information dictionaries.
"""

import subprocess
import sys
import re
import json
import os
import traceback
import argparse
import time

# --- Try importing Google AI Library (required only for filtering) ---
try:
    import google.generativeai as genai
    from google.generativeai.client import configure as genai_configure
    from google.generativeai.generative_models import GenerativeModel as GenAIModel
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    genai_configure = None # Define to None if import fails
    GenAIModel = None      # Define to None if import fails

# --- Centralized Configuration Setup ---
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Assuming find_app_info.py is in the same directory as config.py (e.g., within traverser_ai_api)
# If config.py is in the project root (one level up), this needs adjustment.
DEFAULT_CONFIG_MODULE_PATH_FOR_FIND_APP = os.path.join(CURRENT_SCRIPT_DIR, 'config.py')
USER_CONFIG_JSON_PATH_FOR_FIND_APP = os.path.join(CURRENT_SCRIPT_DIR, "user_config.json")

# Import the Config class itself
# This import path assumes config.py is in the same directory as find_app_info.py
# or traverser_ai_api is in PYTHONPATH. Adjust if find_app_info.py is outside this structure.
try:
    from config import Config
except ImportError as e:
    # Try relative import if it's part of a package and config.py is in the same package
    try:
        from .config import Config
    except ImportError:
        sys.stderr.write(f"FATAL: Could not import 'Config' class. Ensure config.py is accessible and there are no circular imports. Error: {e}\n")
        sys.exit(1)


# Instantiate Config early
try:
    cfg = Config(
        defaults_module_path=DEFAULT_CONFIG_MODULE_PATH_FOR_FIND_APP,
        user_config_json_path=USER_CONFIG_JSON_PATH_FOR_FIND_APP
    )
except Exception as e:
    sys.stderr.write(f"CRITICAL ERROR initializing Config in find_app_info.py: {e}\n")
    traceback.print_exc(file=sys.stderr)
    sys.exit(100)

# --- Now use cfg for all configurations ---

if not hasattr(cfg, 'MAX_APPS_TO_SEND_TO_AI'):
    raise ValueError("MAX_APPS_TO_SEND_TO_AI must be defined in Config object")
if not hasattr(cfg, 'THIRD_PARTY_APPS_ONLY'):
    raise ValueError("THIRD_PARTY_APPS_ONLY must be defined in Config object")
if not hasattr(cfg, 'USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY'): # Used later
    raise ValueError("USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY must be defined in Config object")


CAN_ENABLE_AI_FILTERING_GLOBALLY = True # Assume possible until checks fail

GEMINI_API_KEY = cfg.GEMINI_API_KEY # From Config (loads .env, defaults)
DEFAULT_AI_MODEL_NAME = None
AI_MODEL_SAFETY_SETTINGS = None

APP_INFO_DIR = cfg.APP_INFO_OUTPUT_DIR or os.path.join(os.getcwd(), 'app_info') # Default if None
if not isinstance(APP_INFO_DIR, str):
    APP_INFO_DIR = os.path.join(os.getcwd(), 'app_info')  # Fallback if invalid type
os.makedirs(APP_INFO_DIR, exist_ok=True) # Ensure it exists

print("Validating AI prerequisites for filtering (using Config instance)...")
if not GENAI_AVAILABLE:
    print("Error: 'google-generativeai' library not installed. AI Filtering will be globally unavailable.", file=sys.stderr)
    CAN_ENABLE_AI_FILTERING_GLOBALLY = False

if CAN_ENABLE_AI_FILTERING_GLOBALLY and not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in configuration (via Config). AI Filtering will be globally unavailable.", file=sys.stderr)
    CAN_ENABLE_AI_FILTERING_GLOBALLY = False

if CAN_ENABLE_AI_FILTERING_GLOBALLY:
    if not cfg.DEFAULT_MODEL_TYPE or not cfg.GEMINI_MODELS or \
       not isinstance(cfg.GEMINI_MODELS, dict) or not cfg.GEMINI_MODELS.get(cfg.DEFAULT_MODEL_TYPE):
        print("Error: DEFAULT_MODEL_TYPE or GEMINI_MODELS (with entry for default) not valid in Config. AI Filtering will be globally unavailable.", file=sys.stderr)
        CAN_ENABLE_AI_FILTERING_GLOBALLY = False
    else:
        model_type = cfg.DEFAULT_MODEL_TYPE
        model_details = cfg.GEMINI_MODELS[model_type]
        DEFAULT_AI_MODEL_NAME = model_details.get('name')
        if not DEFAULT_AI_MODEL_NAME:
            print(f"Error: 'name' for model type '{model_type}' not in GEMINI_MODELS (Config). AI Filtering will be globally unavailable.", file=sys.stderr)
            CAN_ENABLE_AI_FILTERING_GLOBALLY = False
        else:
            print(f"Using AI Model from Config: {DEFAULT_AI_MODEL_NAME} (type: {model_type})")

    if CAN_ENABLE_AI_FILTERING_GLOBALLY: # Check again before accessing AI_SAFETY_SETTINGS
        if not hasattr(cfg, 'AI_SAFETY_SETTINGS') or not isinstance(cfg.AI_SAFETY_SETTINGS, dict):
            print("Error: AI_SAFETY_SETTINGS not a valid dictionary in Config. AI Filtering will be globally unavailable.", file=sys.stderr)
            CAN_ENABLE_AI_FILTERING_GLOBALLY = False
        else:
            AI_MODEL_SAFETY_SETTINGS = cfg.AI_SAFETY_SETTINGS
            print(f"Using AI Safety Settings from Config: {AI_MODEL_SAFETY_SETTINGS}")

if not CAN_ENABLE_AI_FILTERING_GLOBALLY:
    print("Warning: AI filtering is GLOBALLY UNAVAILABLE for this script run due to missing prerequisites or configuration.", file=sys.stderr)
else:
    print("AI filtering is GLOBALLY AVAILABLE for this script run (prerequisites met via Config).")


def run_adb_command(command_list):
    """Executes ADB, handles errors, returns stdout."""
    try:
        adb_command = ['adb'] + command_list
        result = subprocess.run(
            adb_command,
            capture_output=True, text=True, check=True,
            encoding='utf-8', errors='ignore'
        )
        if result.stderr:
            clean_stderr = "\n".join(line for line in result.stderr.splitlines() if not line.strip().startswith("Warning:"))
            if clean_stderr:
                # Only print if there's non-warning stderr content
                print(f"--- ADB STDERR for `{' '.join(adb_command)}`:\n{clean_stderr.strip()}", file=sys.stderr)
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
        
        is_relevant_error = True
        if "No activity found" in str(e.output): is_relevant_error = False
        # "exit status 1" can be noisy from pm path if package doesn't exist, but pm list should be fine
        if "aapt" in ' '.join(e.cmd) and not ("error:" in stderr_lower or "failed" in stderr_lower):
            is_relevant_error = False

        if is_relevant_error:
            relevant_stderr = "\n".join(line for line in e.stderr.splitlines() if not line.strip().startswith("Warning:")) if e.stderr else ""
            if relevant_stderr: # Only print if there's non-warning stderr content
                print(f"Warning: ADB command `{' '.join(e.cmd)}` failed.", file=sys.stderr)
                print(f"Stderr: {relevant_stderr.strip()}", file=sys.stderr)
        return None

def get_device_serial():
    """Gets a unique device identifier."""
    output = run_adb_command(['get-serialno'])
    if output and output != "unknown" and "error" not in output.lower() and output.strip() != "": # Added empty check
        serial = re.sub(r'[^\w\-.:]', '_', output) # Allow colon for emulators like 'emulator-5554:5555'
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
                    return re.sub(r'[^\w\-.:]', '_', fallback_id)
        print("Error: Could not get any device identifier. Using generic 'unknown_device'.", file=sys.stderr)
        return "unknown_device"

def get_installed_packages(third_party_only_from_param=True): # Parameter name more specific
    """Retrieves list of installed package names."""
    # This function can be called with a specific override.
    # If not, it defaults to the cfg setting when called internally by generate_app_info_cache.
    command = ['shell', 'pm', 'list', 'packages']
    if third_party_only_from_param:
        command.append('-3')

    output = run_adb_command(command)
    if output is None:
        print("Error: Failed to list packages via ADB.", file=sys.stderr)
        return []
    packages = [line.split(":", 1)[1] for line in output.splitlines() if line.strip().startswith("package:")]
    return packages

def get_app_label(package_name):
    """Retrieves the user-facing application label (name) for a given package."""
    if not package_name:
        return None
    path_output = run_adb_command(['shell', 'pm', 'path', package_name])
    apk_path = None
    if path_output:
        # Find the line starting with 'package:' which contains the base APK path
        base_apk_line = next((line for line in path_output.splitlines() if line.startswith('package:')), None)
        if base_apk_line:
            apk_path = base_apk_line.split(':', 1)[1]
    if apk_path:
        aapt_command = ['shell', 'aapt', 'dump', 'badging', apk_path]
        aapt_output = run_adb_command(aapt_command)
        if aapt_output:
            label_match = re.search(r"application-label(?:-[a-zA-Z_]+)*:['\"]([^'\"]+)['\"]", aapt_output)
            if label_match: return label_match.group(1).strip()
            # Alternative common pattern for app label in aapt output
            label_match_alt = re.search(r"application:\s*.*?label=['\"]([^'\"]+)['\"].*?", aapt_output)
            if label_match_alt: return label_match_alt.group(1).strip()

    # Fallback to dumpsys if aapt fails or doesn't yield label
    dumpsys_command = ['shell', 'dumpsys', 'package', package_name]
    dumpsys_output = run_adb_command(dumpsys_command)
    if dumpsys_output:
        # More specific patterns first
        label_match_dumpsys_specific = re.search(r"^\s*Application label(?:-[a-zA-Z_]+)*:\s*(.+)$", dumpsys_output, re.MULTILINE | re.IGNORECASE)
        if label_match_dumpsys_specific:
            label = label_match_dumpsys_specific.group(1).strip()
            if not (label.startswith("0x") and len(label) > 5): return label # Avoid raw resource IDs

        label_match_dumpsys_quoted = re.search(r"^\s*label=['\"]([^'\"]+)['\"]", dumpsys_output, re.MULTILINE)
        if label_match_dumpsys_quoted:
            label = label_match_dumpsys_quoted.group(1).strip()
            if not (label.startswith("0x") and len(label) > 5): return label
        
        # General pattern within ApplicationInfo block
        app_info_match = re.search(r'ApplicationInfo\{.*?label=([^}\s,]+).*?\}', dumpsys_output, re.DOTALL)
        if app_info_match:
            label = app_info_match.group(1).strip()
            if not (label.startswith("0x") and len(label) > 5): return label
        
        label_match_dumpsys_simple = re.search(r'^\s*label=([^\s]+)$', dumpsys_output, re.MULTILINE)
        if label_match_dumpsys_simple:
            label = label_match_dumpsys_simple.group(1).strip()
            if not (label.startswith("0x") and len(label) > 5): return label
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
        activity_line = output_resolve.splitlines()[-1].strip() # Get the last line
        if '/' in activity_line and "No activity found" not in activity_line and "does not handle" not in activity_line:
            parts = activity_line.split('/')
            # pkg_from_resolve = parts[0] # Not always the same as input package_name
            act_relative = parts[1]
            if act_relative.startswith('.'): return f"{package_name}{act_relative}" # Prepend original package if relative
            if '.' in act_relative: return act_relative # It's already fully qualified (or just activity name if in same package)
            return f"{package_name}.{act_relative}" # Assume it's a class in the package

    # Fallback to dumpsys package info
    output_dumpsys = run_adb_command(['shell', 'dumpsys', 'package', package_name])
    if not output_dumpsys: return None
    # Regex to find LAUNCHER activity in dumpsys output
    regex = re.compile(
        r'^\s+Activity\s+Record\{.*? ' + re.escape(package_name) + r'/([^\s\}]+)\s*.*?\}\n' # Capture activity name
        r'(?:.*?\n)*?' # Non-greedy match for any lines in between
        r'^\s+IntentFilter\{.*?\n' # Start of IntentFilter block
        r'(?:.*?\n)*?'
        r'^\s+Action: "android\.intent\.action\.MAIN"\n' # MAIN action
        r'(?:.*?\n)*?'
        r'^\s+Category: "android\.intent\.category\.LAUNCHER"\n' # LAUNCHER category
        r'(?:.*?\n)*?'
        r'^\s+\}', # End of IntentFilter block
        re.MULTILINE | re.DOTALL
    )
    match = regex.search(output_dumpsys)
    if match:
        activity_part = match.group(1)
        if activity_part.startswith('.'): return package_name + activity_part
        elif '.' in activity_part: return activity_part # Already qualified or just class name
        else: return package_name + '.' + activity_part # Prepend package name
    return None

def filter_apps_with_ai(app_data_list: list):
    """Uses Google Gemini AI to filter apps for health/fitness categories."""
    print("\n--- Filtering apps using AI ---")
    if not CAN_ENABLE_AI_FILTERING_GLOBALLY:
        print("AI Filtering globally disabled - will NOT filter app list.", file=sys.stderr)
        return app_data_list
    else:
        print("AI Filtering globally enabled - will attempt to filter app list.")

    if not app_data_list:
        print("No app data to filter.")
        return []

    if not genai_configure or not GenAIModel or not DEFAULT_AI_MODEL_NAME or AI_MODEL_SAFETY_SETTINGS is None:
        print("Error: Google AI SDK components, model name, or safety settings missing. Cannot proceed.", file=sys.stderr)
        return app_data_list  # Return original on configuration error

    try:
        genai_configure(api_key=GEMINI_API_KEY)
        model = GenAIModel(model_name=DEFAULT_AI_MODEL_NAME, safety_settings=AI_MODEL_SAFETY_SETTINGS)
    except Exception as e:
        print(f"Error configuring Google AI SDK or initializing model: {e}", file=sys.stderr)
        traceback.print_exc()
        return app_data_list  # Return original list on SDK error

    filtered_results = []
    for i in range(0, len(app_data_list), cfg.MAX_APPS_TO_SEND_TO_AI):
        chunk = app_data_list[i : i + cfg.MAX_APPS_TO_SEND_TO_AI]
        print(f"Processing chunk {i//cfg.MAX_APPS_TO_SEND_TO_AI + 1}/{(len(app_data_list) + cfg.MAX_APPS_TO_SEND_TO_AI - 1)//cfg.MAX_APPS_TO_SEND_TO_AI} ({len(chunk)} apps)...")

        try:
            app_data_json_str = json.dumps(chunk, indent=2)
        except Exception as e:
            print(f"Error encoding chunk to JSON: {e}", file=sys.stderr)
            continue

        print(f"Sending {len(chunk)} apps to AI model {DEFAULT_AI_MODEL_NAME}...")
        prompt = (
            f"""Analyze the following list of Android applications provided in JSON format. Each entry includes the application's package name (`package_name`), its user-facing label (`app_name`, which *might be null* if the retrieval script failed), and its main activity (`activity_name`).

Your tasks are:
1.  **Filter:** Identify ONLY the applications from the input list that are primarily related to **health, fitness, wellness, medical purposes, medication management, or mental health**. Exclude general utilities, system apps, games (unless specifically health/fitness focused), social media, etc. Focus on the app's *primary purpose*.
2.  **Populate Missing Names & Preserve Fields:** For the applications you identified in step 1 (the health-related ones):
    * You *must* ensure the `app_name` field in your output JSON is populated.
        * If the input `app_name` for a selected health app is **not** `null` and is a valid-looking name, **use that existing `app_name`** in your output.
        * If the input `app_name` for a selected health app **is** `null` or empty, **infer a likely, user-friendly application name** based primarily on the `package_name`. Use common sense for naming (e.g., `com.myfitnesspal.android` should become `"MyFitnessPal"`, `com.google.android.apps.fitness` should become `"Google Fit"`). Make your best guess for a concise, readable name.
    * You *must* include the original `package_name` from the input.
    * You *must* include the original `activity_name` from the input (this field can be `null` if it was `null` in the input data for that app).
    * You *must* infer a general application category (e.g., "Fitness", "Medical", "Wellness", "Productivity", "Social", "Game", "Utility") for each identified health-related app based on its `app_name` and `package_name`. Add this as a new field called `app_category` in your output.

Output ONLY a valid JSON array containing the entries for the health-related applications identified in step 1. Each object in the output array MUST have the `package_name`, `app_name` (non-null, populated as per step 2), `activity_name` (preserved from input), and `app_category` (inferred as per step 2) fields.
Do not include any explanatory text, comments, markdown formatting like ```json ... ``` around the JSON array, or any text other than the final JSON array itself. The output must be directly parseable as a JSON list of objects. If no apps in the input match the health criteria, output an empty JSON array `[]`.

Input JSON:
{app_data_json_str}"""
        )

        try:
            response = model.generate_content(prompt)
            if response is None:
                print("Error: AI returned None response", file=sys.stderr)
                continue  # Skip to the next chunk
            response_text = response.text.strip() if hasattr(response, 'text') else ""
            if not response_text:
                print("Warning: Empty response from AI", file=sys.stderr)
                if hasattr(response, 'prompt_feedback'):
                    print(f"Prompt Feedback: {response.prompt_feedback}", file=sys.stderr)
                continue  # Skip to the next chunk

            # Clean up JSON formatting if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            if not response_text or response_text == "[]":
                print("AI identified 0 relevant apps in this chunk.")
                continue  # Skip to the next chunk

            try:
                chunk_filtered_list = json.loads(response_text)
                if isinstance(chunk_filtered_list, list):
                    print(f"AI identified {len(chunk_filtered_list)} relevant apps in this chunk.")
                    filtered_results.extend(chunk_filtered_list)
                else:
                    print(f"Warning: AI response was not a JSON list. Snippet: {response_text[:200]}...", file=sys.stderr)
            except json.JSONDecodeError as e:
                print(f"Error: Could not parse AI response as JSON: {e}. Snippet: {response_text[:500]}...", file=sys.stderr)
        except Exception as e:  # Catch errors from generate_content or parsing
            print(f"Error during AI API call or processing for chunk: {e}", file=sys.stderr)
            traceback.print_exc()  # Print full traceback for debugging

    print(f"\n--- AI Filtering Finished. Total relevant apps identified: {len(filtered_results)} ---")
    return filtered_results


def generate_app_info_cache(perform_ai_filtering_on_this_call: bool = False):
    """
    Discovers app information, optionally filters it, and saves it.
    Returns the path to the cache file and the list of app_info.
    """
    print(f"--- Generating App Info Cache (AI filter specifically requested for this call: {perform_ai_filtering_on_this_call}) ---")
    device_id = get_device_serial()
    if not device_id or device_id == "unknown_device":
        print("Critical Error: Could not obtain valid device ID. Cannot generate cache.", file=sys.stderr)
        return None, []

    print(f"Device ID: {device_id}")
    # Use THIRD_PARTY_APPS_ONLY from cfg instance
    print(f"\n--- Discovering installed packages (Third-party only: {cfg.THIRD_PARTY_APPS_ONLY}) ---")
    packages = get_installed_packages(third_party_only_from_param=cfg.THIRD_PARTY_APPS_ONLY) # Use cfg value
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
        if (i + 1) % 20 == 0 or (i + 1) == len(packages): # Progress update
            print(f"  Processed {i+1}/{len(packages)} packages...")
    print(f"\n--- Retrieved info for {len(all_apps_info)} apps before any explicit AI filtering for this call ---")

    apps_to_save = list(all_apps_info) # Default to all apps
    ai_filter_was_effectively_applied = False

    if perform_ai_filtering_on_this_call:
        if not CAN_ENABLE_AI_FILTERING_GLOBALLY:
            print("Warning: AI Filtering requested for this cache generation, but it's globally unavailable (prerequisites failed). Skipping.", file=sys.stderr)
        else:
            print("Attempting AI filtering for this cache generation as requested and globally available...")
            filtered_apps_from_ai = filter_apps_with_ai(list(all_apps_info)) # Pass a copy
            
            if filtered_apps_from_ai is not None:
                apps_to_save = filtered_apps_from_ai
                # Check if the list actually changed due to filtering
                if len(apps_to_save) < len(all_apps_info) or \
                   (len(apps_to_save) == len(all_apps_info) and apps_to_save != all_apps_info): # Content check if lengths are same
                    ai_filter_was_effectively_applied = True
                print(f"AI filtering for cache resulted in {len(apps_to_save)} apps. Filter effectively applied: {ai_filter_was_effectively_applied}")
            else: # filter_apps_with_ai might return original list on some errors, or None if very problematic
                print("AI filtering process returned None or an unchanged list. Using all discovered apps for safety.", file=sys.stderr)
                apps_to_save = list(all_apps_info) # Ensure we use the original if AI func returns None
    else:
        print("AI Filtering not specifically requested for this cache generation call. Using all discovered apps.")

    # APP_INFO_DIR is an absolute path from cfg and directory is already created
    file_suffix = "health_filtered" if perform_ai_filtering_on_this_call and ai_filter_was_effectively_applied else "all"
    output_filename = f"{device_id}_app_info_{file_suffix}.json"
    output_path = os.path.join(APP_INFO_DIR, output_filename)

    print(f"\n--- Saving app info to: {output_path} (Suffix based on effective filtering: {file_suffix}) ---")
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(apps_to_save, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved {len(apps_to_save)} app(s) to {output_path}")
    except IOError as e:
        print(f"Error writing to file {output_path}: {e}", file=sys.stderr)
        traceback.print_exc()
        return None, apps_to_save # Return current list even if save fails
    return output_path, apps_to_save


def filter_existing_app_info_file(input_filepath: str):
    """
    Loads app data from an existing JSON file, filters it using AI,
    and saves the filtered data to a new JSON file.
    """
    if not os.path.exists(input_filepath):
        print(f"Error: Input file not found: {input_filepath}", file=sys.stderr)
        return None

    print(f"--- Processing existing app info file for AI filtering: {input_filepath} ---")
    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            all_apps_data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON from {input_filepath}: {e}", file=sys.stderr)
        return None

    if not isinstance(all_apps_data, list):
        print(f"Error: Data in {input_filepath} is not a JSON list.", file=sys.stderr)
        return None
    
    if not CAN_ENABLE_AI_FILTERING_GLOBALLY:
        print("Warning: AI Filtering is globally unavailable. Cannot filter existing file.", file=sys.stderr)
        return None # Or return input_filepath if you want to signify no operation could be done

    print(f"Sending {len(all_apps_data)} apps from input file to AI for health filtering...")
    ai_filtered_list = filter_apps_with_ai(list(all_apps_data)) # Pass a copy

    if ai_filtered_list is None or (len(ai_filtered_list) == len(all_apps_data) and ai_filtered_list == all_apps_data):
        print("AI filtering returned None, failed, or did not change the app list. No new output file will be saved from this operation.", file=sys.stderr)
        return input_filepath # Return original path if no effective filtering occurred

    base, ext = os.path.splitext(os.path.basename(input_filepath))
    # Ensure output has a distinct name, avoiding simple overwrite if possible
    if "_all" in base:
        new_suffix = "health_filtered_from_all"
        output_base = base.replace("_all", "")
    elif "_health_filtered" in base: # If re-filtering an already filtered list
        new_suffix = "health_filtered_again"
        output_base = base.replace("_health_filtered", "")
    else:
        new_suffix = "health_filtered"
        output_base = base # Use original base if no known suffix
        
    output_filename = f"{output_base}_{new_suffix}{ext}"
    output_filepath = os.path.join(APP_INFO_DIR, output_filename) # APP_INFO_DIR from cfg

    print(f"--- Saving AI-filtered app info to: {output_filepath} ---")
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
        help="Path to an existing app info JSON file to be filtered. Required if --mode is 'filter-existing'."
    )
    parser.add_argument(
        "--ai-filter",
        action='store_true', # If present, args.ai_filter is True, else False
        help="Explicitly enable AI-based health app filtering during 'discover' mode. If not set, behavior depends on cfg.USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY."
    )

    args = parser.parse_args()
    start_time = time.time()

    should_attempt_ai_filtering_for_discover = False
    if args.mode == 'discover':
        # 1. If --ai-filter flag is explicitly used, it takes precedence.
        if args.ai_filter: # This means --ai-filter was given on command line
            should_attempt_ai_filtering_for_discover = True
            print("CLI --ai-filter flag is set, will attempt AI filtering.")
        # 2. If --ai-filter flag is NOT used, rely on the config setting.
        #    This is the typical path when called by UI/CLI controllers.
        else:
            # cfg.USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY should be a boolean from your Config
            should_attempt_ai_filtering_for_discover = cfg.USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY
            print(f"CLI --ai-filter flag NOT set. Defaulting to Config 'USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY': {should_attempt_ai_filtering_for_discover}")


    if args.mode == 'filter-existing':
        if not args.input_file:
            print("Error: --input-file is required for 'filter-existing' mode.", file=sys.stderr)
            sys.exit(1)
        print("--- Starting App Info Filter (Filter Existing File Mode) ---")
        # The parameter for filter_existing_app_info_file is input_filepath not args.input_filepath
        output_file_path = filter_existing_app_info_file(args.input_file) 
        if output_file_path and output_file_path != args.input_file:
            print(f"Filtered file generated at: {output_file_path}")
        elif output_file_path == args.input_file :
            print(f"AI Filtering did not result in a changed app list. Original file remains: {output_file_path}")
        else:
            print("App info filtering (filter-existing mode) failed or did not produce a file.")

    elif args.mode == 'discover':
        print(f"--- Starting App Info Finder (Discovery Mode, Attempt AI Filter: {should_attempt_ai_filtering_for_discover}) ---")
        output_file_path, _ = generate_app_info_cache(
            perform_ai_filtering_on_this_call=should_attempt_ai_filtering_for_discover
        )
        if output_file_path:
            # This print is crucial for ui_controller.py/cli_controller.py to parse the path
            print(f"\nCache file generated at: {output_file_path}")
        else:
            print("\nApp info cache generation (discover mode) failed or did not produce a file.")

    end_time = time.time()
    print(f"\n--- Script Finished in {end_time - start_time:.2f} seconds ---")