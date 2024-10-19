import uiautomator2 as u2
import random
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Connect to the device
d = u2.connect()
logging.info("Connected to the device.")

# Define the package name of the app to be tested
app_package = 'de.jameda'  # Replace with your app's package name

# Launch the app
logging.info(f"Starting the app: {app_package}")
d.app_start(app_package)

# Define the duration of the test in seconds
test_duration = 10 * 60  # 10 minutes

# Get the screen size
width, height = d.window_size()
logging.info(f"Screen size: width={width}, height={height}")

# Define a list of possible actions
actions = ['click', 'swipe', 'long_click', 'back']

# Record the start time
global_start_time = time.time()
logging.info("Starting random actions...")


# Function to check if the current app is the target app
def is_in_app():
    current_app = d.app_current()
    return current_app['package'] == app_package


# Perform actions until the time limit is reached
while time.time() - global_start_time < test_duration:
    action = random.choice(actions)

    if action == 'click':
        x = random.randint(0, width)
        y = random.randint(0, height)
        logging.info(f"Clicking at ({x}, {y})")
        d.click(x, y)
    elif action == 'swipe':
        x = random.randint(0, width)
        y = random.randint(height // 5, height)  # Avoid top area
        x2 = random.randint(0, width)
        y2 = random.randint(height // 5, height)  # Avoid top area
        logging.info(f"Swiping from ({x}, {y}) to ({x2}, {y2})")
        d.swipe(x, y, x2, y2)
    elif action == 'long_click':
        x = random.randint(0, width)
        y = random.randint(0, height)
        logging.info(f"Long clicking at ({x}, {y})")
        d.long_click(x, y)
    elif action == 'back':
        logging.info("Pressing back button")
        d.press("back")

    # Minimal delay to optimize for speed
    time.sleep(0.025)

    # Check if still in the app, and if not, restart the app
    if not is_in_app():
        logging.warning(f"App {app_package} is no longer in the foreground. Relaunching the app.")
        d.app_start(app_package)

# Stop the app after the test is completed
logging.info(f"Stopping the app: {app_package}")
d.app_stop(app_package)

logging.info("Test completed.")
