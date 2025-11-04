# -*- coding: utf-8 -*-
"""
Standalone Android App Package and Activity Finder

This script identifies the package name, application label (name), and main
activity of Android applications installed on a connected device using ADB.

AI Filtering Option:
If AI filtering is enabled via the Config object and prerequisites are met,
the script will use a provider-agnostic AI model (Gemini, OpenRouter, or Ollama)
to filter the discovered applications, keeping only those primarily related to
health, fitness, wellness, medical, medication management, or mental health
categories.

Output:
- A JSON file named `device_<device_id>_<all_apps|filtered_health_apps>.json` will be
  created in the app_info_output_dir defined by the Config object (default:
  `OUTPUT_DATA_DIR/app_info/<device_id>`), containing a list of app information
  dictionaries.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import traceback

# Add the parent directory to sys.path to make traverser_ai_api importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Provider-agnostic model adapters
try:
    from domain.model_adapters import check_dependencies, create_model_adapter
except ImportError:
    try:
        from domain.model_adapters import check_dependencies, create_model_adapter
    except ImportError as e:
        sys.stderr.write(
            f"FATAL: Could not import 'model_adapters'. Ensure the module is accessible. Error: {e}\n"
        )
        sys.exit(1)

# Shared app discovery utilities
try:
    from domain.app_discovery_utils import (
        get_device_id,
        get_app_cache_path,
    )
except ImportError as e:
    sys.stderr.write(
        f"FATAL: Could not import app discovery utilities. Error: {e}\n"
    )
    sys.exit(1)

# --- Try importing AI Libraries (handled via adapters) ---


# --- Centralized Configuration Setup ---
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Import the Config class itself
# This import path assumes config.py is in the same directory as find_app_info.py
# or traverser_ai_api is in PYTHONPATH. Adjust if find_app_info.py is outside this structure.
try:
    from config.config import Config
except ImportError as e:
    # Try relative import if it's part of a package and config.py is in the same package
    try:
        from config.config import Config
    except ImportError:
        sys.stderr.write(
            f"FATAL: Could not import 'Config' class. Ensure config.py is accessible and there are no circular imports. Error: {e}\n"
        )
        sys.exit(1)


# Instantiate Config early
try:
    cfg = Config()
except Exception as e:
    sys.stderr.write(f"CRITICAL ERROR initializing Config in find_app_info.py: {e}\n")
    traceback.print_exc(file=sys.stderr)
    sys.exit(100)

# --- Now use cfg for all configurations ---

if not hasattr(cfg, "MAX_APPS_TO_SEND_TO_AI"):
    raise ValueError("MAX_APPS_TO_SEND_TO_AI must be defined in Config object")
if not hasattr(cfg, "THIRD_PARTY_APPS_ONLY"):
    raise ValueError("THIRD_PARTY_APPS_ONLY must be defined in Config object")
if not hasattr(cfg, "USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY"):  # Used later
    raise ValueError(
        "USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY must be defined in Config object"
    )


CAN_ENABLE_AI_FILTERING_GLOBALLY = True  # Assume possible until checks fail

# Provider/API keys and model selection
DEFAULT_AI_MODEL_NAME = None
AI_MODEL_SAFETY_SETTINGS = None
PROVIDER_API_KEY_OR_URL = None

# Build cache path same way as health_app_scanner.py for consistency
# Note: cfg.BASE_DIR points to the config directory, api_dir is its parent (project root)
api_dir = os.path.abspath(os.path.join(cfg.BASE_DIR, ".."))
APP_INFO_DIR_BASE = os.path.join(
    api_dir,
    getattr(cfg, "OUTPUT_DATA_DIR", "output_data"),
    "app_info"
)
os.makedirs(APP_INFO_DIR_BASE, exist_ok=True)  # Ensure base directory exists
# Note: Individual device cache paths are created by get_app_cache_path()


print("Validating AI prerequisites for filtering (using Config instance)...")

# Determine which AI provider to use
AI_PROVIDER = getattr(cfg, "AI_PROVIDER", "gemini").lower()
print(f"Using AI provider: {AI_PROVIDER}")

# Check dependencies for selected provider
deps_ok, deps_msg = check_dependencies(AI_PROVIDER)
if not deps_ok:
    print(
        f"Error: {deps_msg} AI Filtering will be globally unavailable.", file=sys.stderr
    )
    CAN_ENABLE_AI_FILTERING_GLOBALLY = False

if CAN_ENABLE_AI_FILTERING_GLOBALLY:
    # Select models dict and required credentials per provider
    model_type = cfg.get("DEFAULT_MODEL_TYPE")
    selected_models = None
    if AI_PROVIDER == "gemini":
        PROVIDER_API_KEY_OR_URL = cfg.get("GEMINI_API_KEY")
        selected_models = cfg.get("GEMINI_MODELS")
    elif AI_PROVIDER == "openrouter":
        PROVIDER_API_KEY_OR_URL = cfg.get("OPENROUTER_API_KEY")
        # Aliases are deprecated for OpenRouter; use DEFAULT_MODEL_TYPE as the exact model id
        selected_models = None
    elif AI_PROVIDER == "ollama":
        # For Ollama, "api_key" arg is actually the base URL
        PROVIDER_API_KEY_OR_URL = cfg.get("OLLAMA_BASE_URL")
        selected_models = cfg.get("OLLAMA_MODELS")
    else:
        print(f"Error: Unsupported AI provider: {AI_PROVIDER}.", file=sys.stderr)
        CAN_ENABLE_AI_FILTERING_GLOBALLY = False

    # Validate credential / URL presence
    if CAN_ENABLE_AI_FILTERING_GLOBALLY and not PROVIDER_API_KEY_OR_URL:
        missing_key_name = {
            "gemini": "GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "ollama": "OLLAMA_BASE_URL",
        }.get(AI_PROVIDER, "API_KEY")
        print(
            f"Error: {missing_key_name} not found in configuration (via Config). AI Filtering will be globally unavailable.",
            file=sys.stderr,
        )
        CAN_ENABLE_AI_FILTERING_GLOBALLY = False

    # Validate model selection (with provider-specific fallbacks)
    if CAN_ENABLE_AI_FILTERING_GLOBALLY:
        if not model_type:
            print(
                "Error: DEFAULT_MODEL_TYPE missing in Config. AI Filtering will be globally unavailable.",
                file=sys.stderr,
            )
            CAN_ENABLE_AI_FILTERING_GLOBALLY = False
        else:
            # Resolve model name directly from DEFAULT_MODEL_TYPE for all providers
            if AI_PROVIDER in ["gemini", "openrouter", "ollama"]:
                DEFAULT_AI_MODEL_NAME = model_type
                print(
                    f"Using direct model id from Config: {DEFAULT_AI_MODEL_NAME} (provider: {AI_PROVIDER})"
                )
            else:
                # Unknown provider already handled above, keep safety
                print(
                    f"Error: Unsupported AI provider: {AI_PROVIDER}.", file=sys.stderr
                )
                CAN_ENABLE_AI_FILTERING_GLOBALLY = False

# Load safety settings if available (primarily for Gemini)
if CAN_ENABLE_AI_FILTERING_GLOBALLY:
    if hasattr(cfg, "AI_SAFETY_SETTINGS") and isinstance(cfg.get('AI_SAFETY_SETTINGS'), dict):
        AI_MODEL_SAFETY_SETTINGS = cfg.get('AI_SAFETY_SETTINGS')
        print(f"Using AI Safety Settings from Config: {AI_MODEL_SAFETY_SETTINGS}")
    else:
        # Not fatal for non-Gemini providers
        if AI_PROVIDER == "gemini":
            # Suppressed warning about missing AI_SAFETY_SETTINGS per configuration preference
            pass

if not CAN_ENABLE_AI_FILTERING_GLOBALLY:
    print(
        "Warning: AI filtering is GLOBALLY UNAVAILABLE for this script run due to missing prerequisites or configuration.",
        file=sys.stderr,
    )
else:
    print(
        "AI filtering is GLOBALLY AVAILABLE for this script run (prerequisites met via Config)."
    )


def run_adb_command(command_list):
    """Executes ADB, handles errors, returns stdout."""
    try:
        adb_command = ["adb"] + command_list
        result = subprocess.run(
            adb_command,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            errors="ignore",
        )
        if result.stderr:
            clean_stderr = "\n".join(
                line
                for line in result.stderr.splitlines()
                if not line.strip().startswith("Warning:")
            )
            if clean_stderr:
                # Only print if there's non-warning stderr content
                print(
                    f"--- ADB STDERR for `{' '.join(adb_command)}`:\n{clean_stderr.strip()}",
                    file=sys.stderr,
                )
        return result.stdout.strip()

    except FileNotFoundError:
        print(
            "Fatal Error: 'adb' command not found. Make sure ADB is installed and in your system PATH.",
            file=sys.stderr,
        )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        stderr_lower = e.stderr.lower() if e.stderr else ""
        if "device unauthorized" in stderr_lower:
            print(
                "\nFatal Error: Device unauthorized. Please check your device and allow USB debugging. ***",
                file=sys.stderr,
            )
            sys.exit(1)
        elif "device" in stderr_lower and (
            "not found" in stderr_lower or "offline" in stderr_lower
        ):
            print(
                "\nFatal Error: Device not found or offline. Ensure device is connected and USB debugging is enabled. Check 'adb devices'.",
                file=sys.stderr,
            )
            sys.exit(1)

        is_relevant_error = True
        if "No activity found" in str(e.output):
            is_relevant_error = False
        # "exit status 1" can be noisy from pm path if package doesn't exist, but pm list should be fine
        if "aapt" in " ".join(e.cmd) and not (
            "error:" in stderr_lower or "failed" in stderr_lower
        ):
            is_relevant_error = False

        if is_relevant_error:
            relevant_stderr = (
                "\n".join(
                    line
                    for line in e.stderr.splitlines()
                    if not line.strip().startswith("Warning:")
                )
                if e.stderr
                else ""
            )
            if relevant_stderr:  # Only print if there's non-warning stderr content
                print(
                    f"Warning: ADB command `{' '.join(e.cmd)}` failed.", file=sys.stderr
                )
                print(f"Stderr: {relevant_stderr.strip()}", file=sys.stderr)
        return None





def get_installed_packages(
    third_party_only_from_param=True,
):  # Parameter name more specific
    """Retrieves list of installed package names."""
    # This function can be called with a specific override.
    # If not, it defaults to the cfg setting when called internally by generate_app_info_cache.
    command = ["shell", "pm", "list", "packages"]
    if third_party_only_from_param:
        command.append("-3")

    output = run_adb_command(command)
    if output is None:
        print("Error: Failed to list packages via ADB.", file=sys.stderr)
        return []
    packages = [
        line.split(":", 1)[1]
        for line in output.splitlines()
        if line.strip().startswith("package:")
    ]
    return packages


def get_app_label(package_name):
    """Retrieves the user-facing application label (name) for a given package.

    Uses dumpsys package to get application label.
    """
    if not package_name:
        return None

    # Try dumpsys package
    try:
        dumpsys_command = ["shell", "dumpsys", "package", package_name]
        dumpsys_output = run_adb_command(dumpsys_command)
        if dumpsys_output:
            # Try specific patterns for application label
            patterns = [
                # Pattern 1: "Application label: AppName"
                (r"^\s*Application label(?:-[a-zA-Z_]+)*:\s*(.+?)$", re.MULTILINE),
                # Pattern 2: "label=AppName" with quotes
                (r"label=['\"]([^'\"]+)['\"]", re.MULTILINE | re.IGNORECASE),
                # Pattern 3: label= without quotes (be more flexible)
                (r"label=([^\s;]+)", re.MULTILINE),
            ]

            for pattern, flags in patterns:
                label_match = re.search(pattern, dumpsys_output, flags)
                if label_match:
                    label = label_match.group(1).strip()
                    # Filter out resource IDs (like 0x7f0a01b2)
                    if label and not (label.startswith("0x") and len(label) > 5):
                        return label
    except Exception as e:
        pass

    return None


def find_main_activity(package_name):
    """Finds the main launcher activity for a package."""
    if not package_name:
        return None
    resolve_cmd = [
        "shell",
        "cmd",
        "package",
        "resolve-activity",
        "--brief",
        "-a",
        "android.intent.action.MAIN",
        "-c",
        "android.intent.category.LAUNCHER",
        package_name,
    ]
    output_resolve = run_adb_command(resolve_cmd)
    if output_resolve:
        activity_line = output_resolve.splitlines()[-1].strip()  # Get the last line
        if (
            "/" in activity_line
            and "No activity found" not in activity_line
            and "does not handle" not in activity_line
        ):
            parts = activity_line.split("/")
            # pkg_from_resolve = parts[0] # Not always the same as input package_name
            act_relative = parts[1]
            if act_relative.startswith("."):
                return f"{package_name}{act_relative}"  # Prepend original package if relative
            if "." in act_relative:
                return act_relative  # It's already fully qualified (or just activity name if in same package)
            return (
                f"{package_name}.{act_relative}"  # Assume it's a class in the package
            )
    return None


def filter_apps_with_ai(app_data_list: list):
    """Uses AI (provider-agnostic adapters) to filter apps for health/fitness categories."""
    print("\n--- Filtering apps using AI ---")
    if not CAN_ENABLE_AI_FILTERING_GLOBALLY:
        print(
            "AI Filtering globally disabled - will NOT filter app list.",
            file=sys.stderr,
        )
        return app_data_list
    else:
        print("AI Filtering globally enabled - will attempt to filter app list.")

    if not app_data_list:
        print("No app data to filter.")
        return []

    # Initialize the appropriate AI adapter based on provider
    try:
        adapter = create_model_adapter(
            AI_PROVIDER,
            api_key=PROVIDER_API_KEY_OR_URL,
            model_name=DEFAULT_AI_MODEL_NAME,
        )
        # Build a minimal, direct model config; adapters apply provider defaults
        model_config = {
            "name": DEFAULT_AI_MODEL_NAME,
            "description": f"Direct model id '{DEFAULT_AI_MODEL_NAME}'",
            "generation_config": {
                "temperature": 0.7,
                "top_p": 0.95,
                "max_output_tokens": 4096,
            },
            "online": AI_PROVIDER in ["gemini", "openrouter"],
        }

        adapter.initialize(
            model_config=model_config, safety_settings=AI_MODEL_SAFETY_SETTINGS
        )
        print(
            f"Initialized AI adapter for provider '{AI_PROVIDER}' with model '{DEFAULT_AI_MODEL_NAME}'."
        )
    except Exception as init_error:
        print(f"Error initializing AI adapter: {init_error}", file=sys.stderr)
        traceback.print_exc()
        return app_data_list

    filtered_results = []
    for i in range(0, len(app_data_list), cfg.get('MAX_APPS_TO_SEND_TO_AI')):
        chunk = app_data_list[i : i + cfg.get('MAX_APPS_TO_SEND_TO_AI')]
        print(
            f"Processing chunk {i//cfg.get('MAX_APPS_TO_SEND_TO_AI') + 1}/{(len(app_data_list) + cfg.get('MAX_APPS_TO_SEND_TO_AI') - 1)//cfg.get('MAX_APPS_TO_SEND_TO_AI')} ({len(chunk)} apps)..."
        )

        try:
            app_data_json_str = json.dumps(chunk, indent=2)
        except Exception as e:
            print(f"Error encoding chunk to JSON: {e}", file=sys.stderr)
            continue

        print(f"Sending {len(chunk)} apps to AI model {DEFAULT_AI_MODEL_NAME}...")
        prompt = f"""Analyze the following list of Android applications provided in JSON format. Each entry includes the application's package name (`package_name`), its user-facing label (`app_name`, which *might be null* if the retrieval script failed), and its main activity (`activity_name`).

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

        try:
            # Generate response via adapter
            response_text, metadata = adapter.generate_response(prompt)
            if not response_text:
                print("Warning: Empty response from AI", file=sys.stderr)
                continue

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
                    print(
                        f"AI identified {len(chunk_filtered_list)} relevant apps in this chunk."
                    )
                    filtered_results.extend(chunk_filtered_list)
                else:
                    print(
                        f"Warning: AI response was not a JSON list. Snippet: {response_text[:200]}...",
                        file=sys.stderr,
                    )
            except json.JSONDecodeError as e:
                print(
                    f"Error: Could not parse AI response as JSON: {e}. Snippet: {response_text[:500]}...",
                    file=sys.stderr,
                )
        except Exception as e:  # Catch errors from generate_content or parsing
            print(
                f"Error during AI API call or processing for chunk: {e}",
                file=sys.stderr,
            )
            traceback.print_exc()  # Print full traceback for debugging

    print(
        f"\n--- AI Filtering Finished. Total relevant apps identified: {len(filtered_results)} ---"
    )
    return filtered_results


def generate_app_info_cache(perform_ai_filtering_on_this_call: bool = False):
    """
    Discovers app information, always attempts AI filtering, and saves merged results.
    Returns the path to the cache file and the app info data structure.
    """
    print(
        f"--- Generating App Info Cache (Merged all apps + AI health filtering) ---"
    )

    # Always attempt AI filtering regardless of the parameter
    perform_ai_filtering_on_this_call = True

    if perform_ai_filtering_on_this_call:
        # Check if the computed AI model name is available; use local DEFAULT_AI_MODEL_NAME
        # This value is resolved above based on provider and model type (including raw alias fallback).
        if not DEFAULT_AI_MODEL_NAME or not str(DEFAULT_AI_MODEL_NAME).strip():
            print(
                "Warning: AI model is not set. AI filtering cannot be performed.",
                file=sys.stderr,
            )
            # Provide CLI-based configuration steps tailored to the current provider
            print("Please configure an AI model to use this feature.", file=sys.stderr)
            print("\nHow to configure via CLI:", file=sys.stderr)
            print("1) Inspect current settings:", file=sys.stderr)
            print("   python run_cli.py --show-config AI_", file=sys.stderr)
            print("   python run_cli.py --show-config DEFAULT_MODEL_TYPE", file=sys.stderr)
            print("2) Select provider and model:", file=sys.stderr)
            print(
                f"   python run_cli.py --set-config AI_PROVIDER={AI_PROVIDER}",
                file=sys.stderr,
            )
            # Suggest a provider-specific DEFAULT_MODEL_TYPE example
            if AI_PROVIDER == "openrouter":
                print(
                    "   python run_cli.py --set-config DEFAULT_MODEL_TYPE=openai/gpt-oss-20b:free",
                    file=sys.stderr,
                )
                print(
                    "   (Optional) Refresh model list: python run_cli.py --refresh-openrouter-models",
                    file=sys.stderr,
                )
                print(
                    "3) Set provider credentials (PowerShell):",
                    file=sys.stderr,
                )
                print(
                    "   setx OPENROUTER_API_KEY \"sk-or-...\"   # or add to .env",
                    file=sys.stderr,
                )
            elif AI_PROVIDER == "gemini":
                print(
                    "   python run_cli.py --set-config DEFAULT_MODEL_TYPE=gemini-2.5-flash-image",
                    file=sys.stderr,
                )
                print(
                    "3) Set provider credentials (PowerShell):",
                    file=sys.stderr,
                )
                print(
                    "   setx GEMINI_API_KEY \"AIza...\"       # or add to .env",
                    file=sys.stderr,
                )
            elif AI_PROVIDER == "ollama":
                print(
                    "   python run_cli.py --set-config DEFAULT_MODEL_TYPE=llama3.2-vision",
                    file=sys.stderr,
                )
                print(
                    "3) Set provider URL and ensure Ollama is running:",
                    file=sys.stderr,
                )
                print(
                    "   setx OLLAMA_BASE_URL \"http://localhost:11434\"",
                    file=sys.stderr,
                )
                print(
                    "   ollama serve   # in a separate terminal",
                    file=sys.stderr,
                )
            # Fall back to generating the cache without AI filtering rather than failing outright
            perform_ai_filtering_on_this_call = False

    device_id = get_device_id()
    if not device_id or device_id == "unknown_device":
        print(
            "Warning: Could not obtain a valid device ID quickly. Proceeding with ADB-based discovery attempts.",
            file=sys.stderr,
        )
        # Continue with discovery; downstream ADB commands will surface clearer errors
        # (e.g., device not found or offline) if no device is actually available.

    print(f"Device ID: {device_id}")
    # Use THIRD_PARTY_APPS_ONLY from cfg instance
    print(
        f"\n--- Discovering installed packages (Third-party only: {cfg.get('THIRD_PARTY_APPS_ONLY')}) ---"
    )
    packages = get_installed_packages(
        third_party_only_from_param=cfg.get('THIRD_PARTY_APPS_ONLY')
    )  # Use cfg value
    if not packages:
        print(
            "No packages found. Ensure device is connected and has third-party apps if filter is on.",
            file=sys.stderr,
        )
        return None, []
    print(f"Found {len(packages)} packages.")

    all_apps_info = []
    print(
        f"\n--- Retrieving App Info (Label & Main Activity) for {len(packages)} packages ---"
    )
    for i, package_name in enumerate(packages):
        app_label = get_app_label(package_name)
        main_activity = find_main_activity(package_name)
        all_apps_info.append(
            {
                "package_name": package_name,
                "app_name": app_label,
                "activity_name": main_activity,
            }
        )
        if (i + 1) % 20 == 0 or (i + 1) == len(packages):  # Progress update
            print(f"  Processed {i+1}/{len(packages)} packages...")
    print(
        f"\n--- Retrieved info for {len(all_apps_info)} apps ---"
    )

    # Always store all apps
    all_apps_data = list(all_apps_info)

    # Always attempt AI filtering
    health_apps_data = []
    ai_filter_was_effectively_applied = False

    if perform_ai_filtering_on_this_call:
        if not CAN_ENABLE_AI_FILTERING_GLOBALLY:
            print(
                "Warning: AI Filtering is globally unavailable (prerequisites failed).",
                file=sys.stderr,
            )
            health_apps_data = list(all_apps_info)
        else:
            print(
                "Attempting AI filtering to identify health apps..."
            )
            filtered_apps_from_ai = filter_apps_with_ai(
                list(all_apps_info)
            )  # Pass a copy

            if filtered_apps_from_ai is not None:
                health_apps_data = filtered_apps_from_ai
                # Check if the list actually changed due to filtering
                if len(health_apps_data) < len(all_apps_info):
                    ai_filter_was_effectively_applied = True
                elif len(health_apps_data) == len(all_apps_info):
                    # Check if content is different (e.g., names were populated)
                    if health_apps_data != all_apps_info:
                        ai_filter_was_effectively_applied = True
                    else:
                        # No effective filtering
                        print(
                            "AI filtering did not reduce app list.",
                            file=sys.stderr,
                        )
                        health_apps_data = list(all_apps_info)
                print(
                    f"AI filtering identified {len(health_apps_data)} health apps."
                )
            else:  # filter_apps_with_ai might return original list on some errors, or None if very problematic
                print(
                    "AI filtering process failed.",
                    file=sys.stderr,
                )
                health_apps_data = list(all_apps_info)
    else:
        # This should not happen anymore since we always attempt filtering
        health_apps_data = list(all_apps_info)
        health_apps_data = list(all_apps_info)

    # Add timestamp to the output
    import datetime

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_data = {
        "timestamp": timestamp,
        "device_id": device_id,
        "ai_filtered": ai_filter_was_effectively_applied,
        "all_apps": all_apps_data,
        "health_apps": health_apps_data,
    }

    # Create device-specific directory
    APP_INFO_DIR = os.path.join(APP_INFO_DIR_BASE, device_id)
    os.makedirs(APP_INFO_DIR, exist_ok=True)

    # Use merged file name for all devices
    output_filename = f"device_{device_id}_app_info.json"
    output_path = os.path.join(APP_INFO_DIR, output_filename)

    print(
        f"\n--- Saving merged app info to: {output_path} ---"
    )
    print(f"  - All apps: {len(all_apps_data)}")
    print(f"  - Health apps: {len(health_apps_data)}")
    print(f"  - AI filtering applied: {ai_filter_was_effectively_applied}")

    try:
        # Save merged data to device-specific path
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved merged app data to {output_path}")
    except IOError as e:
        print(f"Error writing to file {output_path}: {e}", file=sys.stderr)
        traceback.print_exc()
        return None, result_data  # Return current data even if save fails
    return output_path, result_data


def filter_existing_app_info_file(input_filepath: str):
    """
    Loads app data from an existing JSON file, filters it using AI,
    and saves the filtered data to a new JSON file.
    """
    if not os.path.exists(input_filepath):
        print(f"Error: Input file not found: {input_filepath}", file=sys.stderr)
        return None

    print(
        f"--- Processing existing app info file for AI filtering: {input_filepath} ---"
    )
    try:
        with open(input_filepath, "r", encoding="utf-8") as f:
            all_apps_data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON from {input_filepath}: {e}", file=sys.stderr)
        return None

    if not isinstance(all_apps_data, list):
        print(f"Error: Data in {input_filepath} is not a JSON list.", file=sys.stderr)
        return None

    if not CAN_ENABLE_AI_FILTERING_GLOBALLY:
        print(
            "Warning: AI Filtering is globally unavailable. Cannot filter existing file.",
            file=sys.stderr,
        )
        return None  # Or return input_filepath if you want to signify no operation could be done

    print(
        f"Sending {len(all_apps_data)} apps from input file to AI for health filtering..."
    )
    ai_filtered_list = filter_apps_with_ai(list(all_apps_data))  # Pass a copy

    if ai_filtered_list is None or (
        len(ai_filtered_list) == len(all_apps_data)
        and ai_filtered_list == all_apps_data
    ):
        print(
            "AI filtering returned None, failed, or did not change the app list. No new output file will be saved from this operation.",
            file=sys.stderr,
        )
        return input_filepath  # Return original path if no effective filtering occurred

    base, ext = os.path.splitext(os.path.basename(input_filepath))
    # Ensure output has a distinct name, avoiding simple overwrite if possible
    if "_all" in base:
        new_suffix = "health_filtered_from_all"
        output_base = base.replace("_all", "")
    elif "_health_filtered" in base:  # If re-filtering an already filtered list
        new_suffix = "health_filtered_again"
        output_base = base.replace("_health_filtered", "")
    else:
        new_suffix = "health_filtered"
        output_base = base  # Use original base if no known suffix

    # Extract device_id from input file path if possible, otherwise get from device
    device_id = get_device_id()
    if not device_id or device_id == "unknown_device":
        # Try to extract from filename pattern like device_<device_id>_...
        match = re.search(r'device_([^_]+)_', os.path.basename(input_filepath))
        if match:
            device_id = match.group(1)

    # Create device-specific directory for filter_existing output
    APP_INFO_DIR = os.path.join(APP_INFO_DIR_BASE, device_id)
    os.makedirs(APP_INFO_DIR, exist_ok=True)

    output_filename = f"{output_base}_{new_suffix}{ext}"
    output_filepath = os.path.join(
        APP_INFO_DIR, output_filename
    )  # APP_INFO_DIR from cfg

    print(f"--- Saving AI-filtered app info to: {output_filepath} ---")
    try:
        with open(output_filepath, "w", encoding="utf-8") as f:
            json.dump(ai_filtered_list, f, indent=4, ensure_ascii=False)
        print(
            f"Successfully saved {len(ai_filtered_list)} filtered app(s) to {output_filepath}"
        )
        return output_filepath
    except IOError as e:
        print(f"Error writing to file {output_filepath}: {e}", file=sys.stderr)
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Android App Info Finder and AI Filter."
    )
    parser.add_argument(
        "--mode",
        choices=["discover", "filter-existing"],
        default="discover",
        help="Operation mode: 'discover' new app info (default), or 'filter-existing' an input JSON file.",
    )
    parser.add_argument(
        "--input-file",
        type=str,
        help="Path to an existing app info JSON file to be filtered. Required if --mode is 'filter-existing'.",
    )
    parser.add_argument(
        "--ai-filter",
        action="store_true",  # If present, args.ai_filter is True, else False
        help="Explicitly enable AI-based health app filtering during 'discover' mode. If not set, behavior depends on cfg.USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY.",
    )

    args = parser.parse_args()
    start_time = time.time()

    should_attempt_ai_filtering_for_discover = False
    if args.mode == "discover":
        # 1. If --ai-filter flag is explicitly used, it takes precedence.
        if args.ai_filter:  # This means --ai-filter was given on command line
            should_attempt_ai_filtering_for_discover = True
            print("CLI --ai-filter flag is set, will attempt AI filtering.")
        # 2. If --ai-filter flag is NOT used, rely on the config setting.
        #    This is the typical path when called by UI/CLI controllers.
        else:
            # cfg.USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY should be a boolean from your Config
            should_attempt_ai_filtering_for_discover = (
                cfg.get('USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY')
            )
            print(
                f"CLI --ai-filter flag NOT set. Defaulting to Config 'USE_AI_FILTER_FOR_TARGET_APP_DISCOVERY': {should_attempt_ai_filtering_for_discover}"
            )

    if args.mode == "filter-existing":
        if not args.input_file:
            print(
                "Error: --input-file is required for 'filter-existing' mode.",
                file=sys.stderr,
            )
            sys.exit(1)
        print("--- Starting App Info Filter (Filter Existing File Mode) ---")
        # The parameter for filter_existing_app_info_file is input_filepath not args.input_filepath
        output_file_path = filter_existing_app_info_file(args.input_file)
        if output_file_path and output_file_path != args.input_file:
            print(f"Filtered file generated at: {output_file_path}")
        elif output_file_path == args.input_file:
            print(
                f"AI Filtering did not result in a changed app list. Original file remains: {output_file_path}"
            )
        else:
            print(
                "App info filtering (filter-existing mode) failed or did not produce a file."
            )

    elif args.mode == "discover":
        print(
            f"--- Starting App Info Finder (Discovery Mode, Attempt AI Filter: {should_attempt_ai_filtering_for_discover}) ---"
        )
        output_file_path, result_data = generate_app_info_cache(
            perform_ai_filtering_on_this_call=should_attempt_ai_filtering_for_discover
        )
        if output_file_path:
            # This print is crucial for ui_controller.py/cli_controller.py to parse the path
            print(f"\nCache file generated at: {output_file_path}")
            # Output a JSON string with the summary for better parsing by the caller
            app_count = (
                len(result_data.get("health_apps", []))
                if isinstance(result_data, dict)
                else 0
            )
            summary_json = json.dumps(
                {
                    "status": "success",
                    "file_path": output_file_path,
                    "app_count": app_count,
                    "timestamp": (
                        result_data.get("timestamp")
                        if isinstance(result_data, dict)
                        else ""
                    ),
                }
            )
            print(f"\nSUMMARY_JSON: {summary_json}")
        else:
            print(
                "\nApp info cache generation (discover mode) failed or did not produce a file."
            )
            error_json = json.dumps(
                {"status": "error", "message": "Failed to generate app info cache"}
            )
            print(f"\nSUMMARY_JSON: {error_json}")

    end_time = time.time()
    print(f"\n--- Script Finished in {end_time - start_time:.2f} seconds ---")
