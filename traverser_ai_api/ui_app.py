import sys
import re # Add re for stripping ANSI codes
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QTextEdit
from PyQt5.QtCore import QProcess, Qt

# ANSI escape code regex
ANSI_ESCAPE_REGEX = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

class CrawlerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Crawler UI")
        self.setGeometry(100, 100, 600, 400)

        self.crawler_process = QProcess()
        self.init_ui()

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)

        self.start_button = QPushButton("Start Crawl")
        self.start_button.clicked.connect(self.start_crawl)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Crawl")
        self.stop_button.clicked.connect(self.stop_crawl)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

        self.status_label = QLabel("Status: Idle")
        layout.addWidget(self.status_label)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)

    def save_config(self):
        # Placeholder for actual config saving logic
        # This might involve reading from UI elements and writing to user_config.json or config.py
        self.output_text.append("Configuration saved (placeholder).")
        print("Configuration saved (placeholder).")

    def start_crawl(self):
        self.save_config()
        self.output_text.clear()
        self.output_text.append("Starting crawler...")
        self.status_label.setText("Status: Starting...")

        # Ensure the path to main.py is correct relative to where ui_app.py is run from,
        # or use an absolute path. Assuming main.py is in the same directory.
        self.crawler_process.setProgram(sys.executable) # Path to Python interpreter
        self.crawler_process.setArguments(['main.py']) # Script to run

        # Connect signals
        self.crawler_process.readyReadStandardOutput.connect(self.read_stdout)
        self.crawler_process.readyReadStandardError.connect(self.read_stderr)
        self.crawler_process.stateChanged.connect(self.update_process_state) # Renamed to avoid conflict
        self.crawler_process.finished.connect(self.crawler_finished)

        try:
            self.crawler_process.start()
            if self.crawler_process.waitForStarted(5000): # Wait 5 seconds for start
                self.status_label.setText("Status: Running")
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
            else:
                self.status_label.setText(f"Status: Failed to start - {self.crawler_process.errorString()}")
                self.output_text.append(f"Error starting process: {self.crawler_process.errorString()}")
                self.start_button.setEnabled(True)
                self.stop_button.setEnabled(False)
        except Exception as e:
            self.status_label.setText(f"Status: Error - {str(e)}")
            self.output_text.append(f"Exception during start: {str(e)}")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)


    def stop_crawl(self):
        self.status_label.setText("Status: Stopping...")
        if self.crawler_process.state() == QProcess.ProcessState.Running:
            self.crawler_process.terminate() # Graceful termination
            # Optionally, use kill() if terminate() fails after a timeout
            # if not self.crawler_process.waitForFinished(5000):
            #     self.crawler_process.kill()
        else:
            self.crawler_finished(0, QProcess.ExitStatus.NormalExit) # Manually trigger if not running


    def read_stdout(self):
        raw_output_bytes = self.crawler_process.readAllStandardOutput()
        # Check if QByteArray is null or empty before trying to access data()
        if not raw_output_bytes or raw_output_bytes.isEmpty():
            return
        
        raw_output = raw_output_bytes.data().decode(errors='ignore')
        # Process line by line
        lines = raw_output.splitlines()

        for line in lines:
            clean_line = ANSI_ESCAPE_REGEX.sub('', line).strip()
            if not clean_line: # Skip empty lines after cleaning and stripping
                continue

            if clean_line.startswith("UI_STATUS:"):
                status_text = clean_line.split(":", 1)[1].strip()
                self.status_label.setText(f"Status: {status_text}")
            elif clean_line.startswith("UI_STEP:"):
                step_number = clean_line.split(":", 1)[1].strip()
                # Assumes that a UI_STATUS: RUNNING (or similar) has set the base status
                self.status_label.setText(f"Status: Running - Step {step_number}")
            elif clean_line.startswith("UI_ACTION:"):
                action_text = clean_line.split(":", 1)[1].strip()
                self.output_text.append(action_text) # Append action directly
            # Placeholder for UI_SCREENSHOT based on original commented code
            # elif clean_line.startswith("UI_SCREENSHOT:"):
            #     path = clean_line.split(":", 1)[1].strip()
            #     self.output_text.append(f"Screenshot: {path}")
            else:
                # Append other logs with a LOG prefix
                self.output_text.append(f"LOG: {clean_line}")

    def read_stderr(self):
        raw_error = self.crawler_process.readAllStandardError().data().decode(errors='ignore').strip()
        clean_error = ANSI_ESCAPE_REGEX.sub('', raw_error)
        if clean_error: # Only append if there's non-empty content after stripping
            self.output_text.append(f"STDERR: {clean_error}")
        # self.status_label.setText("Status: Error")

    def update_process_state(self, state):
        if state == QProcess.ProcessState.NotRunning:
            self.status_label.setText("Status: Not Running / Finished")
            # self.crawler_finished(self.crawler_process.exitCode(), self.crawler_process.exitStatus())
        elif state == QProcess.ProcessState.Starting:
            self.status_label.setText("Status: Starting...")
        elif state == QProcess.ProcessState.Running:
            self.status_label.setText("Status: Running")
        else:
            self.status_label.setText(f"Status: Unknown State {state}")


    def crawler_finished(self, exit_code, exit_status):
        self.output_text.append(f"Crawler process finished.")
        self.output_text.append(f"Exit Code: {exit_code}")
        self.output_text.append(f"Exit Status: {'Normal Exit' if exit_status == QProcess.ExitStatus.NormalExit else 'Crash Exit'}")
        
        final_status = "Status: Finished"
        if exit_status == QProcess.ExitStatus.CrashExit or exit_code != 0:
            final_status = f"Status: Finished with errors (Code: {exit_code})"
            
        self.status_label.setText(final_status)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = CrawlerApp()
    main_win.show()
    sys.exit(app.exec_())
