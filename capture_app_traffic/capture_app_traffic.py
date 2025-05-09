import subprocess
import sys
import os
import re
import time
from datetime import datetime
from traverser_ai_api.config import TARGET_APP_PACKAGE

# --- Configuration ---
# <<< CHANGE THIS VALUE TO YOUR TARGET APP'S PACKAGE NAME >>>
# TARGET_APP_PACKAGE = "eu.smartpatient.mytherapy" # Example: Replace with your target app

PCAPDROID_PACKAGE = "com.emanuelef.remote_capture"
# Correct API entry point (Activity) as per documentation
PCAPDROID_ACTIVITY = f"{PCAPDROID_PACKAGE}/.activities.CaptureCtrl"
# Default location where PCAPdroid saves files when using pcap_name (since v1.6.0)
DEVICE_PCAP_DIR = "/sdcard/Download/PCAPdroid"
# Local directory to save the pulled pcap file
LOCAL_OUTPUT_DIR = "capture_app_traffic/output"
# Set to True to delete the pcap file from the device after successful download
CLEANUP_DEVICE_FILE = True

# --- ADB Helper Function ---
def run_adb_command(command_list, check_output=False, suppress_stderr=False):
    """Runs an ADB command."""
    try:
        adb_command = ['adb'] + command_list
        print(f"--- Running ADB: {' '.join(adb_command)}")
        result = subprocess.run(
            adb_command,
            capture_output=True,
            text=True,
            check=True, # Raise CalledProcessError on non-zero exit code
            encoding='utf-8',
            errors='ignore', # Ignore potential decoding errors in output
        )
        # Print stdout, useful for commands like 'devices' or if requested
        if check_output or result.stdout:
             print(f"--- ADB STDOUT:\n{result.stdout.strip()}")

        # Print stderr unless suppressed
        if result.stderr and not suppress_stderr:
            print(f"--- ADB STDERR:\n{result.stderr.strip()}", file=sys.stderr)
        return result.stdout.strip(), result.returncode
    except FileNotFoundError:
        print("Error: 'adb' command not found. Make sure ADB is installed and in your PATH.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        # Common error handling for ADB failures
        print(f"Error executing ADB command: {' '.join(e.cmd)}", file=sys.stderr)
        print(f"Return code: {e.returncode}", file=sys.stderr)
        # Capture and print stdout/stderr from the exception if available
        if e.stdout:
            print(f"Output (stdout):\n{e.stdout}", file=sys.stderr)
        if e.stderr and not suppress_stderr:
             print(f"Output (stderr):\n{e.stderr}", file=sys.stderr)

        # Specific error messages based on stderr content
        stderr_lower = e.stderr.lower() if e.stderr else ""
        if "device unauthorized" in stderr_lower:
             print("\n*** Device unauthorized. Please check your device and allow USB debugging (and revoke/re-allow if needed). ***", file=sys.stderr)
        elif "device" in stderr_lower and ("not found" in stderr_lower or "offline" in stderr_lower):
             print("\n*** Device not found or offline. Ensure device is connected, USB debugging is enabled, and the device is unlocked. ***", file=sys.stderr)
        elif "more than one device/emulator" in stderr_lower:
             print("\n*** More than one device detected. Please specify a target device using 'adb -s <serial> ...' or disconnect other devices/emulators. ***", file=sys.stderr)
        # Check if the target activity exists or if PCAPdroid isn't installed/responding
        elif ("does not exist" in stderr_lower or "unable to resolve intent" in stderr_lower or "error type 3" in stderr_lower) and PCAPDROID_ACTIVITY in ' '.join(e.cmd):
             print(f"\n*** Error: PCAPdroid control activity ({PCAPDROID_ACTIVITY}) not found or could not be started.", file=sys.stderr)
             print("*** Please ensure PCAPdroid is installed, up-to-date, and not disabled. Check device logs ('adb logcat') for more details. ***", file=sys.stderr)
        # Check for permission errors when starting the activity (less common, might indicate deeper issues)
        elif "permission denial" in stderr_lower and "start activity" in stderr_lower and PCAPDROID_ACTIVITY in ' '.join(e.cmd):
             print(f"\n*** Error: Permission denied starting PCAPdroid activity ({PCAPDROID_ACTIVITY}).", file=sys.stderr)
             print("*** This might happen if PCAPdroid is restricted from being launched by other apps (check battery optimization/background restrictions), or due to a system issue. Check device logs ('adb logcat'). ***", file=sys.stderr)

        # Return the error output (prefer stderr) and the non-zero return code
        return (e.stderr if e.stderr else e.stdout) , e.returncode

# --- Main Script Logic ---
def main():
    print("--- PCAPdroid Traffic Capture Script (Using Official API) ---")
    print(f"--- Target App Package: {TARGET_APP_PACKAGE} ---")

    # Basic validation for the configured package name
    if not TARGET_APP_PACKAGE or '.' not in TARGET_APP_PACKAGE or TARGET_APP_PACKAGE.startswith('.') or TARGET_APP_PACKAGE.endswith('.'):
        print(f"Error: Invalid TARGET_APP_PACKAGE configured: '{TARGET_APP_PACKAGE}'. Please set a valid Android package name.", file=sys.stderr)
        sys.exit(1)

    # === Step 1: Basic ADB and PCAPdroid Checks ===
    print("\n[1/7] Checking ADB connection...")
    stdout, retcode = run_adb_command(["devices"])
    # Check return code and that output is not empty and contains 'device' in the last line (typical for a single connected device)
    if retcode != 0 or not stdout or "device" not in stdout.splitlines()[-1].split():
        print("Error: No authorized ADB device found or ADB command failed. Exiting.", file=sys.stderr)
        if stdout: # Print output if command ran but device wasn't found/authorized
             print(f"ADB devices output:\n{stdout}", file=sys.stderr)
        sys.exit(1)
    print("ADB device found and authorized.")

    print("\n[2/7] Checking if PCAPdroid is installed...")
    stdout, retcode = run_adb_command(['shell', 'pm', 'path', PCAPDROID_PACKAGE], suppress_stderr=True) # Suppress stderr as non-zero exit is expected if not found
    if retcode != 0 or not stdout or not stdout.strip().startswith('package:'):
         print(f"Error: PCAPdroid package '{PCAPDROID_PACKAGE}' not found on the device.", file=sys.stderr)
         print("Please install PCAPdroid from the Play Store or F-Droid.", file=sys.stderr)
         sys.exit(1)
    print(f"PCAPdroid package '{PCAPDROID_PACKAGE}' found.")

    # === Step 2: User Interaction Reminder ===
    print("\n" + "="*50)
    print("IMPORTANT REMINDERS & FIRST-TIME SETUP:")
    print(f"1. PCAPdroid must be installed on the device.")
    print(f"2. The *first time* this script runs (or if permissions were")
    print(f"   reset), PCAPdroid WILL display a dialog on the device screen")
    print(f"   asking for permission to be controlled remotely by 'shell'.")
    print(f"   >>> YOU MUST APPROVE THIS DIALOG ON THE DEVICE. <<<")
    print(f"3. PCAPdroid will also likely ask for VPN permission if it's")
    print(f"   not already granted or running.")
    print(f"   >>> YOU MUST APPROVE THE VPN REQUEST ON THE DEVICE. <<<")
    print(f"4. You can manage granted API control permissions later in:")
    print(f"   PCAPdroid App -> Settings -> App API -> Control Permissions.")
    print("="*50 + "\n")
    try:
        input("Press Enter to acknowledge and continue...")
    except EOFError: # Handle cases where input is piped or unavailable
        print("Proceeding without Enter key confirmation.")


    # === Step 3: Prepare Filenames and Paths ===
    print("\n[3/7] Preparing file paths...")
    # Sanitize package name for use in filename
    sanitized_package = re.sub(r'[^\w\-.]+', '_', TARGET_APP_PACKAGE)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # This is the FILENAME passed to PCAPdroid via the API
    device_pcap_filename = f"{sanitized_package}_{timestamp}.pcap"
    # This is the FULL PATH on the device where PCAPdroid should save the file
    # (based on pcap_name documentation for v1.6.0+)
    device_pcap_full_path = os.path.join(DEVICE_PCAP_DIR, device_pcap_filename).replace("\\", "/") # Ensure forward slashes for ADB path

    # Prepare local path
    local_pcap_filename = device_pcap_filename # Use the same name locally for simplicity
    os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)
    local_pcap_path = os.path.join(LOCAL_OUTPUT_DIR, local_pcap_filename)

    print(f"  Target App Package: {TARGET_APP_PACKAGE}")
    print(f"  Device Filename Param (pcap_name): {device_pcap_filename}")
    print(f"  Expected Device Save Path: {device_pcap_full_path}")
    print(f"  Local Save Path: {local_pcap_path}")

    # === Step 4: Start Capture using PCAPdroid API ===
    print("\n[4/7] Sending 'start' action to PCAPdroid Activity via API...")
    # Construct the adb command using the official API parameters
    start_command = [
        'shell', 'am', 'start',          # Use 'am start' to launch the activity
        '-n', PCAPDROID_ACTIVITY,        # Target the specific CaptureCtrl activity
        '-e', 'action', 'start',         # Specify the 'start' action via extra
        '-e', 'pcap_dump_mode', 'pcap_file', # Tell PCAPdroid to save to a file
        '-e', 'app_filter', TARGET_APP_PACKAGE, # Filter traffic for the target app package
        '-e', 'pcap_name', device_pcap_filename, # Provide the desired base filename
        # --- Optional Parameters (Uncomment and modify as needed) ---
        # '-e', 'root_capture', 'true'      # Use root capture instead of VPN (requires root)
        '-e', 'tls_decryption', 'true'    # Enable built-in TLS decryption (requires CA cert install)
        # '-e', 'pcapng_format', 'true'     # Use PCAPNG format (paid feature)
        # '-e', 'dump_extensions', 'true'   # Include PCAPdroid metadata extensions
        # '-e', 'snaplen', '0'              # Capture full packets (0 = unlimited)
        # '-e', 'collector_ip_address', '127.0.0.1' # For udp_exporter mode
        # '-e', 'collector_port', '5123'            # For udp_exporter mode (use appropriate port type 'int')
    ]
    # Execute the start command
    stdout, retcode = run_adb_command(start_command)

    # Check if the command execution failed immediately
    if retcode != 0:
        print("\nError: Failed to send 'start' command to PCAPdroid.", file=sys.stderr)
        print("Check the ADB errors printed above.", file=sys.stderr)
        print("Ensure PCAPdroid is installed and you approved the necessary permissions on the device if prompted.", file=sys.stderr)
        sys.exit(1)

    # If `am start` succeeded, it doesn't mean capture is running yet (user interaction might be needed)
    print("\n'start' command sent successfully.")
    print(">>> Please check your device now! <<<")
    print("  1. Look for a PCAPdroid dialog asking for 'shell'/'remote control' permission (if first time). -> APPROVE IT.")
    print("  2. Look for a VPN connection request from PCAPdroid. -> APPROVE IT.")
    print("  3. Confirm the PCAPdroid notification shows 'Capture running'.")
    print("  4. Confirm the VPN key icon (usually a small key) is visible in the status bar.")
    print("Capture might fail silently if permissions are denied on the device.")

    # === Step 5: Wait for User to Perform Actions in Target App ===
    print("\n[5/7] Capture should now be active (if permissions were granted).")
    try:
        # Prompt user to interact with the app and press Enter when done
        input(f">>> Perform the desired actions in the target app ({TARGET_APP_PACKAGE}) now.\n"
              f"    Press Enter here when you are finished to stop the capture... ")
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Proceeding to stop capture...")
    except EOFError:
        print("\nEOF detected. Proceeding to stop capture (may occur in non-interactive environments)...")


    # === Step 6: Stop Capture using PCAPdroid API ===
    print("\n[6/7] Sending 'stop' action to PCAPdroid Activity via API...")
    stop_command = [
        'shell', 'am', 'start',      # Use 'am start' again
        '-n', PCAPDROID_ACTIVITY,    # Target the same activity
        '-e', 'action', 'stop'       # Specify the 'stop' action via extra
    ]
    # Execute the stop command
    stdout, retcode = run_adb_command(stop_command)

    if retcode != 0:
        # Log an error but continue, as the file might still exist
        print("\nWarning: Failed to send 'stop' command to PCAPdroid.", file=sys.stderr)
        print("Check the ADB errors printed above. The capture might still be running.", file=sys.stderr)
        print("Proceeding to attempt pulling the file anyway...", file=sys.stderr)
    else:
        print("'stop' command sent successfully.")
        print("Waiting a few seconds for PCAPdroid to finalize the file...")
        time.sleep(3) # Give PCAPdroid a moment to close the file handle

    # === Step 7: Pull the Captured PCAP File ===
    print("\n[7/7] Attempting to pull the PCAP file from the device...")
    # Use the full path determined earlier
    pull_command = ['pull', device_pcap_full_path, local_pcap_path]
    stdout, retcode = run_adb_command(pull_command)

    # Check if the pull command was successful
    if retcode != 0:
        print(f"\nError: Failed to pull the PCAP file '{device_pcap_full_path}'.", file=sys.stderr)
        print("Possible reasons:", file=sys.stderr)
        print("  - Capture never actually started (permissions denied on device?).", file=sys.stderr)
        print("  - No network traffic was generated by the target app during capture.", file=sys.stderr)
        print(f"  - The expected file path '{device_pcap_full_path}' is incorrect.", file=sys.stderr)
        print("  - Storage permissions issue on the device for PCAPdroid.", file=sys.stderr)
        print("  - PCAPdroid crashed or was stopped unexpectedly.", file=sys.stderr)
        print("\nTroubleshooting steps:", file=sys.stderr)
        print(f"  - Manually check the directory on the device using: adb shell ls -l {DEVICE_PCAP_DIR}", file=sys.stderr)
        print(f"  - Check PCAPdroid's logs or notifications on the device.", file=sys.stderr)
        sys.exit(1)

    # If pull succeeded, check if the local file exists and has content
    if os.path.exists(local_pcap_path):
        if os.path.getsize(local_pcap_path) > 0:
            print(f"\n--- Success! ---")
            print(f"PCAP file pulled successfully and saved locally to:")
            print(f"  --> {os.path.abspath(local_pcap_path)}") # Show absolute path

            # Optional: Clean up the file on the device
            if CLEANUP_DEVICE_FILE:
                cleanup_device_file(device_pcap_full_path)
        else:
            # File was pulled but is empty
            print(f"\n--- Warning! ---")
            print(f"PCAP file pulled to '{local_pcap_path}' but it is empty (0 bytes).", file=sys.stderr)
            print("This usually means no network traffic matching the filter was captured.", file=sys.stderr)
            print("Ensure the target app was used and generated network activity while capture was running.", file=sys.stderr)
            # Keep the empty file for inspection, but cleanup if requested
            if CLEANUP_DEVICE_FILE:
                cleanup_device_file(device_pcap_full_path)
    else:
        # Pull command reported success, but file doesn't exist locally (shouldn't happen often)
        print(f"\n--- Error! ---")
        print(f"ADB pull command seemed to succeed, but the local file '{local_pcap_path}' was not found.", file=sys.stderr)
        print("This indicates an unexpected issue with the adb pull process or file system.", file=sys.stderr)

def cleanup_device_file(device_pcap_full_path):
    """Helper function to clean up the file on the device."""
    print(f"\nCleaning up file on device: {device_pcap_full_path}...")
    rm_command = ['shell', 'rm', device_pcap_full_path]
    _, retcode_rm = run_adb_command(rm_command, suppress_stderr=True)
    if retcode_rm == 0:
        print("Device file deleted successfully.")
    else:
        print(f"Warning: Failed to delete file {device_pcap_full_path} from device (ADB error code {retcode_rm}). You may need to remove it manually.", file=sys.stderr)

if __name__ == "__main__":
    main()
