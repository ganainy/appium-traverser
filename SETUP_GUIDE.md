## Prerequisites

Before you begin, ensure you have the following installed and configured:

1.  **Python 3.x:**
    *   Download and install from [python.org](https://www.python.org/).
    *   **Crucially, ensure Python is added to your system's PATH environment variable during installation.** If you missed this, you might need to add it manually or use the `py` launcher (e.g., `py -m venv .venv`) instead of `python -m venv .venv` on Windows.
2.  **Node.js and npm:**
    *   Required to install the Appium server. Download from [nodejs.org](https://nodejs.org/).
3.  **Appium Server:**
    *   Install globally using npm: `npm install -g appium`
    *   Verify installation: `appium --version`
4.  **Appium Drivers:** You need the driver for Android automation.
    *   Install the UiAutomator2 driver: `appium driver install uiautomator2`
    *   Verify installation: `appium driver list --installed`
5.  **Android SDK:**
    *   Usually installed with Android Studio.
    *   **Crucially, you MUST set either the `ANDROID_HOME` or `ANDROID_SDK_ROOT` environment variable** pointing to the root directory of your SDK installation (e.g., `C:\Users\YourUser\AppData\Local\Android\Sdk`). Appium needs this to find tools like `adb`. Refer to [Android documentation](https://developer.android.com/studio/command-line/variables) for details. Restart your terminal and the Appium server after setting this variable.
6.  **Required Python Packages:** These will be installed using the `requirements.txt` file provided.

## Setup

1.  **Clone Repository:**
    ```bash
    git clone <repository-url>
    cd appium-traverser
    ```
2.  **Create a Python Virtual Environment:** It's highly recommended to use a virtual environment to isolate project dependencies. Navigate to the project directory in your terminal and run:
    ```bash
    # On Windows (if python is in PATH)
    python -m venv .venv
    # OR (if python is not in PATH but 'py' works)
    py -m venv .venv

    # On macOS/Linux
    python3 -m venv .venv
    ```
3.  **Activate the Virtual Environment:** You need to activate the environment *each time* you open a new terminal session for this project.
    ```bash
    # On Windows PowerShell
    .\.venv\Scripts\Activate.ps1
    # (If you get an error about script execution, you might need to run this once in PowerShell as Admin:
    # Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
    # Or temporarily for the current process:
    # Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process )

    # On Windows Command Prompt (cmd.exe)
    .\.venv\Scripts\activate.bat

    # On macOS/Linux
    source .venv/bin/activate
    ```
    Your terminal prompt should now be prefixed with `(.venv)`.

4.  **Install Python Packages:** While the virtual environment is active, install the required packages:
    ```bash
    pip install -r requirements.txt
    ```
5.  **Appium Server Setup:**
    *   Start the Appium server in a separate terminal window by simply running: `appium`
    *   Keep this server running while you execute the Python script.
6.  **Android Device/Emulator Setup:**
    *   Ensure you have an Android device connected via USB with **Developer Options** and **USB Debugging** enabled, or have an Android Virtual Device (Emulator) running.
    *   Verify your device is recognized by ADB: `adb devices` (You might need to run this from the Android SDK's `platform-tools` directory if it's not in your PATH).

## Configuration

Modify the following variables near the top of the `screen_traverse.py` script:

*   `expected_package`: The package name of the Android app you want to test (e.g., `"eu.smartpatient.mytherapy"`).
*   `expected_start_activity`: The main launcher activity of the app (you might need `adb` or tools like "App Inspector" to find this).
*   `expected_target_device`: The device ID (from `adb devices`) or the name of your Android emulator (e.g., `"emulator-5554"`).

## Running the Script

1.  Ensure the **Appium server is running** in a separate terminal.
2.  Ensure your target **Android device/emulator is connected** and recognized (`adb devices`).
3.  Open a **new terminal**, navigate to the project directory (`cd appium-traverser`).
4.  **Activate the virtual environment** (see Setup step 3).
5.  Run the script using the Python interpreter from the virtual environment:
    ```bash
    # On Windows
    .\.venv\Scripts\python.exe main_script.py

    # On macOS/Linux
    python main_script.py
    ```
## Usage

Run the script using Python:
`python main_script.py`