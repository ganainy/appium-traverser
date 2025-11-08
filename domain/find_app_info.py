# -*- coding: utf-8 -*-
"""
Standalone Android App Package and Activity Finder

This module identifies the package name, application label (name), and main
activity of Android applications installed on a connected device using ADB.

The module creates a unified list of all discovered applications, each with an
`is_health_app` flag that indicates whether the app is health-related:
- `true`: App is identified as health-related
- `false`: App is identified as non-health-related
- `null`: Health status is unknown (AI filtering failed or was not applied)

Output:
- A JSON file named `device_<device_id>_app_info.json` will be created in the
  app_info_output_dir defined by the Config object (default:
  `OUTPUT_DATA_DIR/app_info/<device_id>`). The file contains:
  - `timestamp`: When the scan was performed
  - `device_id`: The device identifier
  - `ai_filtered`: Whether AI filtering was successfully applied
  - `apps`: A unified list of all applications, each with an `is_health_app` flag
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import traceback

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
    from domain.app_discovery_utils import get_device_id, get_app_cache_path
except ImportError as e:
    sys.stderr.write(
        f"FATAL: Could not import app discovery utilities. Error: {e}\n"
    )
    sys.exit(1)


from pathlib import Path

from utils.paths import find_project_root

CURRENT_SCRIPT_DIR = Path(__file__).resolve().parent
# Note: When this file is in domain/, PROJECT_ROOT will be correctly calculated
PROJECT_ROOT = str(find_project_root(CURRENT_SCRIPT_DIR))

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


CAN_ENABLE_AI_FILTERING_GLOBALLY = True  # Assume possible until checks fail

# Provider/API keys and model selection
DEFAULT_AI_MODEL_NAME = None
AI_MODEL_SAFETY_SETTINGS = None
PROVIDER_API_KEY_OR_URL = None

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




def get_installed_packages():
    """Retrieves list of all installed package names (including system apps)."""
    command = ["shell", "pm", "list", "packages"]

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


def generate_app_info_cache():
    """
    Discovers app information, always attempts AI filtering, and saves merged results.
    Returns the path to the cache file and the app info data structure.
    """
    print(
        f"--- Generating App Info Cache (Merged all apps + AI health filtering) ---"
    )

    # Always attempt AI filtering - check if the computed AI model name is available
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

    device_id = get_device_id()
    if not device_id or device_id == "unknown_device":
        print(
            "Warning: Could not obtain a valid device ID quickly. Proceeding with ADB-based discovery attempts.",
            file=sys.stderr,
        )
        # Continue with discovery; downstream ADB commands will surface clearer errors
        # (e.g., device not found or offline) if no device is actually available.

    print(f"Device ID: {device_id}")
    print(
        f"\n--- Discovering installed packages (All apps including system apps) ---"
    )
    packages = get_installed_packages()
    if not packages:
        print(
            "No packages found. Ensure device is connected.",
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
    ai_filtering_failed = False

    if not CAN_ENABLE_AI_FILTERING_GLOBALLY:
        print(
            "Warning: AI Filtering is globally unavailable (prerequisites failed).",
            file=sys.stderr,
        )
        health_apps_data = list(all_apps_info)
        ai_filtering_failed = True
    else:
        print(
            "Warning: AI filtering functionality has been removed. All apps will be marked as unknown.",
            file=sys.stderr,
        )
        health_apps_data = list(all_apps_info)
        ai_filtering_failed = True

    # Create unified list with is_health_app flags
    # Build a set of health app package names for efficient lookup
    health_app_packages = {app.get("package_name") for app in health_apps_data if app.get("package_name")}
    
    # Create unified apps list with is_health_app flags
    unified_apps = []
    for app in all_apps_info:
        app_copy = dict(app)  # Make a copy to avoid modifying original
        package_name = app_copy.get("package_name")
        
        if ai_filtering_failed or not ai_filter_was_effectively_applied:
            # AI filtering failed or wasn't effective - mark as unknown (null)
            app_copy["is_health_app"] = None
        elif package_name in health_app_packages:
            # App was identified as health app by AI
            app_copy["is_health_app"] = True
        else:
            # App was explicitly excluded by AI filtering
            app_copy["is_health_app"] = False
        
        unified_apps.append(app_copy)

    # Add timestamp to the output
    import datetime

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_data = {
        "timestamp": timestamp,
        "device_id": device_id,
        "ai_filtered": ai_filter_was_effectively_applied,
        "apps": unified_apps,  
    }

    # Use shared utility to get cache path 
    output_path = get_app_cache_path(device_id, cfg)

    print(
        f"\n--- Saving merged app info to: {output_path} ---"
    )
    print(f"  - Total apps: {len(unified_apps)}")
    health_count = sum(1 for app in unified_apps if app.get("is_health_app") is True)
    non_health_count = sum(1 for app in unified_apps if app.get("is_health_app") is False)
    unknown_count = sum(1 for app in unified_apps if app.get("is_health_app") is None)
    print(f"  - Health apps: {health_count}")
    print(f"  - Non-health apps: {non_health_count}")
    print(f"  - Unknown status: {unknown_count}")
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Android App Info Finder."
    )
    parser.parse_args()
    start_time = time.time()

    print(
        f"--- Starting App Info Finder (Discovery Mode) ---"
    )
    output_file_path, result_data = generate_app_info_cache()
    if output_file_path:
        # This print is crucial for ui_controller.py/cli_controller.py to parse the path
        print(f"\nCache file generated at: {output_file_path}")
        # Output a JSON string with the summary for better parsing by the caller
        # Count apps with is_health_app flag (unified format)
        app_count = (
            len(result_data.get("apps", []))
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
            "\nApp info cache generation failed or did not produce a file."
        )
        error_json = json.dumps(
            {"status": "error", "message": "Failed to generate app info cache"}
        )
        print(f"\nSUMMARY_JSON: {error_json}")

    end_time = time.time()
    print(f"\n--- Script Finished in {end_time - start_time:.2f} seconds ---")