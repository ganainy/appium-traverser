# -*- coding: utf-8 -*-
"""
Standalone Android App Package and Activity Finder

This module identifies the package name, application label (name), and main
activity of Android applications installed on a connected device using ADB.

The module creates a unified list of all discovered applications, each with:
- `is_health_app` flag that indicates whether the app is health-related:
  - `true`: App is identified as health-related
  - `false`: App is identified as non-health-related
  - `null`: Health status is unknown (AI filtering failed or was not applied)
- `is_system_app` flag that indicates whether the app is a system app:
  - `true`: App is a system app (e.g., android.*, com.android.*, com.google.android.*, etc.)
  - `false`: App is a user-installed app

Output:
- A JSON file named `device_<device_id>_app_info.json` will be created in the
  app_info_output_dir defined by the Config object (default:
  `OUTPUT_DATA_DIR/app_info/<device_id>`). The file contains:
  - `timestamp`: When the scan was performed
  - `device_id`: The device identifier
  - `ai_filtered`: Whether AI filtering was successfully applied
  - `apps`: A unified list of all applications, each with `is_health_app` and `is_system_app` flags
"""

import argparse
import concurrent.futures
import datetime
import json
import re
import subprocess
import sys
import threading
import time
import traceback

# Provider-agnostic model adapters
try:
    from domain.model_adapters import check_dependencies, create_model_adapter
    from domain.provider_utils import get_provider_api_key, get_missing_key_name, validate_provider_config
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
    from config.app_config import Config
except ImportError as e:
    sys.stderr.write(
        f"FATAL: Could not import 'Config' class. Ensure config.py is accessible and there are no circular imports. Error: {e}\n"
    )
    sys.exit(1)


def _check_ai_filtering_prerequisites(config):
    """
    Validates AI filtering prerequisites and returns configuration dict.
    Returns dict with keys: enabled, provider, model_name, safety_settings, api_key_or_url
    """
    result = {
        "enabled": True,
        "provider": None,
        "model_name": None,
        "safety_settings": None,
        "api_key_or_url": None,
    }
    
    # Determine which AI provider to use (use whatever user set in config)
    provider = config.get("AI_PROVIDER")
    if not provider:
        print(
            "Error: AI_PROVIDER not set in configuration. AI Filtering will be globally unavailable.",
            file=sys.stderr,
        )
        result["enabled"] = False
        return result
    
    result["provider"] = str(provider).lower()
    
    # Check dependencies for selected provider
    deps_ok, deps_msg = check_dependencies(result["provider"])
    if not deps_ok:
        print(f"Error: {deps_msg} AI Filtering will be globally unavailable.", file=sys.stderr)
        result["enabled"] = False
        return result
    
    # Get provider credentials using provider-agnostic utility
    model_type = config.get("DEFAULT_MODEL_TYPE")
    
    # For Ollama, use default URL if not configured
    from config.urls import ServiceURLs
    default_ollama_url = ServiceURLs.OLLAMA if result["provider"] == "ollama" else None
    
    # Validate provider configuration
    is_valid, error_msg = validate_provider_config(config, result["provider"], default_ollama_url)
    if not is_valid:
        print(f"Error: {error_msg}. AI Filtering will be globally unavailable.", file=sys.stderr)
        result["enabled"] = False
        return result
    
    # Get API key or URL for the provider
    result["api_key_or_url"] = get_provider_api_key(config, result["provider"], default_ollama_url)
    
    # Validate credential / URL presence
    # For Ollama, it's okay if not set (will use default)
    if not result["api_key_or_url"] and result["provider"] != "ollama":
        missing_key_name = get_missing_key_name(result["provider"])
        print(
            f"Error: {missing_key_name} not found in configuration. AI Filtering will be globally unavailable.",
            file=sys.stderr,
        )
        result["enabled"] = False
        return result
    
    # For Ollama, ensure we have a URL (use default if not configured)
    if result["provider"] == "ollama" and not result["api_key_or_url"]:
        result["api_key_or_url"] = default_ollama_url
    
    # Validate model selection
    if not model_type:
        print(
            "Error: DEFAULT_MODEL_TYPE missing in Config. AI Filtering will be globally unavailable.",
            file=sys.stderr,
        )
        result["enabled"] = False
        return result
    
    result["model_name"] = model_type
    
    # Load safety settings if available (primarily for Gemini)
    if hasattr(config, "AI_SAFETY_SETTINGS") and isinstance(config.get('AI_SAFETY_SETTINGS'), dict):
        result["safety_settings"] = config.get('AI_SAFETY_SETTINGS')
    
    return result


def _filter_warning_lines(stderr_text):
    """Filters out warning lines from stderr output."""
    if not stderr_text:
        return ""
    return "\n".join(
        line
        for line in stderr_text.splitlines()
        if not line.strip().startswith("Warning:")
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
            clean_stderr = _filter_warning_lines(result.stderr)
            if clean_stderr:
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
            relevant_stderr = _filter_warning_lines(e.stderr)
            if relevant_stderr:
                print(
                    f"Warning: ADB command `{' '.join(e.cmd)}` failed.", file=sys.stderr
                )
                print(f"Stderr: {relevant_stderr.strip()}", file=sys.stderr)
        return None




def get_installed_packages():
    """Retrieves list of user-installed package names (third-party apps only, excludes system apps)."""
    command = ["shell", "pm", "list", "packages", "-3"]

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


def _extract_label_from_pm_dump(pm_output):
    """Extracts app label from pm dump output."""
    if not pm_output:
        return None
    
    label_patterns = [
        r"applicationLabel=(?:'([^']+)'|([^\s\n]+))",
        r"applicationLabel=(?:resId=|0x[0-9a-fA-F]+\s+)?['\"]?([^'\"]+)['\"]?",
    ]
    for pattern in label_patterns:
        match = re.search(pattern, pm_output, re.IGNORECASE | re.MULTILINE)
        if match:
            for i in range(1, match.lastindex + 1 if match.lastindex else 1):
                if match.group(i):
                    label = match.group(i).strip()
                    if label and not (label.startswith("0x") and len(label) > 5):
                        return label
    return None


def _is_system_package(package_name):
    """Quick check if package is likely a system package."""
    from config.package_constants import PackageConstants
    return PackageConstants.is_system_package(package_name)


def _process_single_package(package_name):
    """Processes a single package to retrieve its label and main activity.
    
    Optimized for speed: 
    - Always gets activity (fast with resolve-activity)
    - Skips label extraction for system packages (saves significant time)
    - Only uses slow dumpsys as absolute last resort
    Returns a tuple: (package_name, app_info_dict)
    """
    app_label = None
    main_activity = None
    is_system = _is_system_package(package_name)
    
    # Step 1: Get activity using resolve-activity (FAST - always do this)
    try:
        resolve_cmd = [
            "shell", "cmd", "package", "resolve-activity", "--brief",
            "-a", "android.intent.action.MAIN",
            "-c", "android.intent.category.LAUNCHER",
            package_name,
        ]
        output_resolve = run_adb_command(resolve_cmd)
        if output_resolve:
            for line in output_resolve.splitlines():
                line = line.strip()
                if not line or line.startswith("No activity found") or "does not handle" in line:
                    continue
                
                # Extract activity from "name=package/.Activity" or "package/.Activity"
                if "name=" in line:
                    line = line.split("name=", 1)[1].strip()
                
                if "/" in line:
                    parts = line.split("/", 1)
                    act_relative = parts[1].strip()
                    if act_relative:
                        if act_relative.startswith("."):
                            main_activity = f"{package_name}{act_relative}"
                        elif "." in act_relative:
                            main_activity = act_relative
                        else:
                            main_activity = f"{package_name}.{act_relative}"
                        break
    except Exception:
        pass
    
    # Step 2: Get label - try for all apps (not just user apps with launchers)
    # This ensures we get app names even if they don't have launcher activities
    if not app_label:  # Only try if we don't already have a label
        try:
            pm_dump_cmd = ["shell", "pm", "dump", package_name]
            pm_output = run_adb_command(pm_dump_cmd)
            if pm_output:
                app_label = _extract_label_from_pm_dump(pm_output)
        except Exception:
            pass
    
    return (
        package_name,
        {
            "package_name": package_name,
            "app_name": app_label,
            "activity_name": main_activity,
            "is_system_app": is_system,
        }
    )


def generate_app_info_cache():
    """
    Discovers app information, always attempts AI filtering, and saves merged results.
    Returns the path to the cache file and the app info data structure.
    """

    # Instantiate Config to get current configuration (reads fresh each time)
    try:
        cfg = Config()
    except Exception as e:
        sys.stderr.write(f"CRITICAL ERROR initializing Config in find_app_info.py: {e}\n")
        traceback.print_exc(file=sys.stderr)
        return None, []
    
    # Check AI filtering prerequisites dynamically (reads current config)
    
    ai_config = _check_ai_filtering_prerequisites(cfg)
    can_enable_ai_filtering = ai_config["enabled"]
    ai_provider = ai_config["provider"]
    default_ai_model_name = ai_config["model_name"]
    ai_model_safety_settings = ai_config["safety_settings"]
    provider_api_key_or_url = ai_config["api_key_or_url"]
    
    
    if not can_enable_ai_filtering:
        print(
            "Warning: AI filtering is not available. All apps will be marked with unknown health status.",
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
        f"\n--- Discovering installed packages (User-installed apps only) ---"
    )
    packages = get_installed_packages()
    if not packages:
        print(
            "No packages found. Ensure device is connected.",
            file=sys.stderr,
        )
        return None, []
    print(f"Found {len(packages)} packages.")

    print(
        f"\n--- Retrieving App Info (Label & Main Activity) for {len(packages)} packages ---"
    )
    
    # Use parallel processing to speed up ADB commands
    # ThreadPoolExecutor is ideal for I/O-bound operations like ADB commands
    # Increased workers since we're now making fewer ADB calls per package
    max_workers = min(20, len(packages))  # Use up to 20 workers for better parallelism
    
    # Thread-safe progress tracking
    progress_lock = threading.Lock()
    processed_count = [0]  # Use list to allow modification in nested function
    
    def update_progress():
        """Thread-safe progress update."""
        with progress_lock:
            processed_count[0] += 1
            count = processed_count[0]
            if count % 20 == 0 or count == len(packages):
                print(f"  Processed {count}/{len(packages)} packages...")
    
    # Process packages in parallel
    package_results = {}  # Dict to maintain order: {package_name: app_info}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_package = {
            executor.submit(_process_single_package, package_name): package_name
            for package_name in packages
        }
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_package):
            try:
                package_name, app_info = future.result()
                package_results[package_name] = app_info
                update_progress()
            except Exception as e:
                package_name = future_to_package[future]
                print(
                    f"  Warning: Error processing package {package_name}: {e}",
                    file=sys.stderr
                )
                # Still add the package with None values
                package_results[package_name] = {
                    "package_name": package_name,
                    "app_name": None,
                    "activity_name": None,
                    "is_system_app": _is_system_package(package_name),
                }
                update_progress()
    
    # Reconstruct list in original package order
    all_apps_info = [package_results[package_name] for package_name in packages]
    
    print(
        f"\n--- Retrieved info for {len(all_apps_info)} apps ---"
    )

    # AI filtering: Always attempt to classify apps as health-related or not
    unified_apps = []
    ai_filter_was_effectively_applied = False
    ai_filter_error = None
    
    if can_enable_ai_filtering and default_ai_model_name and provider_api_key_or_url:
        try:
            # Initialize the model adapter
            model_adapter = create_model_adapter(
                provider=ai_provider,
                api_key=provider_api_key_or_url,
                model_name=default_ai_model_name
            )
            
            # Identify apps with missing names
            apps_with_missing_names = []
            for idx, app in enumerate(all_apps_info):
                app_name = app.get("app_name")
                # Check for None, empty string, or "Unknown" (handle null from JSON)
                if not app_name or app_name == "Unknown" or (isinstance(app_name, str) and app_name.strip() == ""):
                    apps_with_missing_names.append(idx)
            
            # Get counts for prompt building
            num_apps = len(all_apps_info)
            num_missing_names = len(apps_with_missing_names)
            
            # Initialize with basic config
            # Let the AI model decide how many tokens it needs (no max_output_tokens limit)
            model_config = {
                "description": f"Health app classifier using {default_ai_model_name}",
                "generation_config": {
                    "temperature": 0.1,  # Low temperature for consistent classification
                }
            }
            model_adapter.initialize(model_config, ai_model_safety_settings)
            
            print(f"  Using AI model: {default_ai_model_name} (provider: {ai_provider})")
            print(f"  Classifying {num_apps} apps in a single AI call...")
            
            # Build a single prompt with all apps
            apps_list = []
            for idx, app in enumerate(all_apps_info):
                app_name = app.get("app_name")
                # Handle None/null values from JSON
                if not app_name or (isinstance(app_name, str) and app_name.strip() == ""):
                    app_name_display = "[MISSING - please provide]"
                else:
                    app_name_display = app_name
                package_name = app.get("package_name", "")
                
                if not app_name or (isinstance(app_name, str) and app_name.strip() == ""):
                    apps_list.append(f"{idx}. App name: [MISSING - please provide] | Package: {package_name}")
                else:
                    apps_list.append(f"{idx}. App name: {app_name} | Package: {package_name}")
            
            apps_text = "\n".join(apps_list)
            
            # Build JSON format example - include app_name only when needed
            if num_missing_names > 0:
                json_format_example = """{
  "classifications": [
    {"index": 0, "is_health_app": true, "app_name": "App Name Here"},
    {"index": 1, "is_health_app": false, "app_name": "Another App Name"},
    ...
  ]
}"""
                app_name_instruction = f"\nIMPORTANT: Only include the 'app_name' field in your response for apps that have '[MISSING - please provide]' as the app name. For apps that already have a name, DO NOT include the 'app_name' field in your response - only include 'index' and 'is_health_app'."
            else:
                json_format_example = """{
  "classifications": [
    {"index": 0, "is_health_app": true},
    {"index": 1, "is_health_app": false},
    ...
  ]
}"""
                app_name_instruction = ""
            
            prompt = f"""Classify the following Android apps as health-related or not. A health app is one that:
- Tracks fitness, exercise, or physical activity
- Monitors health metrics (heart rate, blood pressure, sleep, etc.)
- Manages medical conditions or medications
- Provides health information or telemedicine services
- Connects to health devices or wearables
- Manages diet, nutrition, or weight

Return ONLY a valid JSON object with this exact format:
{json_format_example}

For each app, set "is_health_app" to true if it's health-related, false if it's not.{app_name_instruction}
IMPORTANT: You must return classifications for ALL {num_apps} apps (indices 0 to {num_apps - 1}). Do not truncate the response.

Apps to classify:
{apps_text}

Return the complete JSON classification for all {num_apps} apps now:"""
            
            # Show loading indicator while AI is processing
            from utils import LoadingIndicator
            
            with LoadingIndicator("AI is processing"):
                # Get AI classification for all apps in one call
                try:
                    response_text, metadata = model_adapter.generate_response(prompt)
                    if not response_text or len(response_text.strip()) == 0:
                        raise ValueError("AI model returned empty response. Check if the model is running and accessible.")
                    response_text = response_text.strip()
                except Exception as ai_error:
                    raise  # Re-raise to be caught by outer exception handler
            
            # Try to extract JSON from the response
            # Sometimes the model wraps JSON in markdown code blocks
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
            else:
                json_text = response_text
            
            # Check if JSON appears incomplete (common signs: missing closing brackets, incomplete last entry)
            json_text_stripped = json_text.strip()
            if json_text_stripped and not json_text_stripped.endswith("}"):
                print(f"  ⚠️ Warning: JSON response appears incomplete (doesn't end with '}}'). Response length: {len(json_text)} chars", file=sys.stderr)
                print(f"  Last 200 chars: {json_text[-200:]}", file=sys.stderr)
            
            # Parse the JSON response
            try:
                classifications_data = json.loads(json_text)
                classifications = classifications_data.get("classifications", [])
                
                # Create a mapping from index to classification and app name
                classification_map = {}
                app_name_map = {}
                for item in classifications:
                    idx = item.get("index")
                    is_health = item.get("is_health_app")
                    app_name = item.get("app_name")
                    if idx is not None:
                        classification_map[idx] = is_health
                        # Only store app names from AI if the app actually needs a name
                        # This prevents misalignment where AI provides names for apps that already have them
                        # Also ignore placeholder text that the AI might return
                        if (app_name and 
                            app_name != "[MISSING - please provide]" and
                            idx < len(all_apps_info)):
                            current_app = all_apps_info[idx]
                            current_name = current_app.get("app_name")
                            # Only store if the current name is missing, None, or "Unknown"
                            # Handle None (null from JSON) and empty strings
                            if (not current_name or 
                                current_name == "Unknown" or 
                                current_name == "[MISSING - please provide]" or
                                (isinstance(current_name, str) and current_name.strip() == "")):
                                app_name_map[idx] = app_name
                
                # Apply classifications and app names to apps
                names_filled = 0
                for idx, app in enumerate(all_apps_info):
                    is_health = classification_map.get(idx)
                    ai_provided_name = app_name_map.get(idx)
                    
                    # Update app name if AI provided one and current name is missing
                    # Only update if the app name is actually missing, None, or "Unknown"
                    # This prevents misalignment issues where AI provides names for apps that already have them
                    updated_app = {**app}
                    current_app_name = app.get("app_name")
                    # Handle None (null from JSON), empty strings, and "Unknown"
                    if ai_provided_name and (
                        not current_app_name or 
                        current_app_name == "Unknown" or 
                        (isinstance(current_app_name, str) and current_app_name.strip() == "")
                    ):
                        # Only apply the AI-provided name if the current name is truly missing
                        updated_app["app_name"] = ai_provided_name
                        names_filled += 1
                    
                    if is_health is None:
                        # If classification missing, mark as unknown
                        print(f"    Warning: No classification for app {idx} ({updated_app.get('package_name', 'unknown')})", file=sys.stderr)
                        unified_apps.append({**updated_app, "is_health_app": None})
                    else:
                        unified_apps.append({**updated_app, "is_health_app": bool(is_health)})
                
                classified_count = len([a for a in unified_apps if a.get("is_health_app") is not None])
                ai_filter_was_effectively_applied = True
                print(f"  ✓ Successfully classified {classified_count}/{len(all_apps_info)} apps using AI (single call)")
                if names_filled > 0:
                    print(f"  ✓ Filled in {names_filled} missing app names")
                
            except json.JSONDecodeError as e:
                ai_filter_error = f"Failed to parse AI response as JSON: {e}"
                print(f"  ✗ {ai_filter_error}", file=sys.stderr)
                print(f"  Error location: line {e.lineno}, column {e.colno}", file=sys.stderr)
                print(f"  AI response length: {len(response_text)} chars", file=sys.stderr)
                print(f"  AI response (first 500 chars): {response_text[:500]}", file=sys.stderr)
                if len(response_text) > 500:
                    print(f"  AI response (last 500 chars): {response_text[-500:]}", file=sys.stderr)
                
                # Check if response was likely truncated due to token limit
                if len(response_text) > 0 and not response_text.rstrip().endswith("}"):
                    print(f"  ⚠️ Response appears truncated (doesn't end with '}}'). This may indicate the model hit a token limit.", file=sys.stderr)
                    print(f"  💡 Suggestion: Try using a model with a larger context window, or reduce the number of apps classified at once.", file=sys.stderr)
                
                print(f"  Falling back to marking all apps as unknown health status.")
                # Fall through to mark all as unknown
                unified_apps = [
                    {**app, "is_health_app": None}
                    for app in all_apps_info
                ]
            
        except Exception as e:
            ai_filter_error = str(e)
            print(f"  ✗ AI filtering failed: {e}", file=sys.stderr)
            if not isinstance(e, ValueError):
                traceback.print_exc(file=sys.stderr)
            print(f"  Falling back to marking all apps as unknown health status.")
            # Fall through to mark all as unknown
            unified_apps = [
                {**app, "is_health_app": None}
                for app in all_apps_info
            ]
    else:
        # AI filtering prerequisites not met
        reason = []
        if not can_enable_ai_filtering:
            reason.append("prerequisites check failed")
        if not default_ai_model_name:
            reason.append("model name not configured")
        if not provider_api_key_or_url:
            reason.append("API key/URL not configured")
        
        ai_filter_error = f"AI filtering disabled: {', '.join(reason)}"
        print(f"  ✗ {ai_filter_error}", file=sys.stderr)
        print(f"  All apps will be marked with unknown health status (is_health_app: null)")
        
        # Mark all apps as unknown
        unified_apps = [
            {**app, "is_health_app": None}
            for app in all_apps_info
        ]
    
    # Final step: Generate app names from package names for any apps still missing names
    # This provides a fallback when both ADB and AI fail to provide names
    def _derive_app_name_from_package(package_name: str) -> str:
        """Derive a readable app name from package name as a last resort."""
        if not package_name:
            return "Unknown"
        
        # Remove common prefixes
        parts = package_name.split(".")
        
        # Try to find a meaningful part (usually the last or second-to-last)
        # Skip common words like "com", "android", "app", etc.
        skip_words = {"com", "org", "net", "io", "app", "android", "apps", "www"}
        
        for part in reversed(parts):
            if part and part not in skip_words and len(part) > 2:
                # Capitalize first letter and make it readable
                name = part.replace("_", " ").replace("-", " ")
                # Title case
                name = " ".join(word.capitalize() for word in name.split())
                return name
        
        # If nothing found, use the last part
        if parts:
            last_part = parts[-1]
            if last_part:
                return last_part.replace("_", " ").replace("-", " ").title()
        
        return "Unknown"
    
    # Apply fallback names to apps that still don't have names
    # This handles cases where ADB and AI both failed, or AI returned placeholder text
    for app in unified_apps:
        current_name = app.get("app_name")
        # Check for missing names: None, empty, "Unknown", or the placeholder text from prompts
        if (not current_name or 
            current_name == "Unknown" or 
            current_name == "[MISSING - please provide]" or
            (isinstance(current_name, str) and current_name.strip() == "")):
            package_name = app.get("package_name", "")
            derived_name = _derive_app_name_from_package(package_name)
            app["app_name"] = derived_name

    # Add timestamp to the output
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_data = {
        "timestamp": timestamp,
        "device_id": device_id,
        "ai_filtered": ai_filter_was_effectively_applied,
        "apps": unified_apps,  
    }

    # Use shared utility to get cache path 
    output_path = get_app_cache_path(device_id, cfg)

    print(f"  - Total apps: {len(unified_apps)}")
    health_count = sum(1 for app in unified_apps if app.get("is_health_app") is True)
    non_health_count = sum(1 for app in unified_apps if app.get("is_health_app") is False)
    unknown_count = sum(1 for app in unified_apps if app.get("is_health_app") is None)
    print(f"  - Health apps: {health_count}")
    print(f"  - Non-health apps: {non_health_count}")
    print(f"  - Unknown status: {unknown_count}")
    print(f"  - AI filtering applied: {ai_filter_was_effectively_applied}")
    # Don't print ai_filter_error here - it's already been printed in the exception handler

    try:
        # Save merged data to device-specific path
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=4, ensure_ascii=False)
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