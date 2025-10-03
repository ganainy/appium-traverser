# analysis_viewer.py
import json
import os
import sqlite3
import logging
from typing import Optional, List, Dict, Any, Tuple
from html import escape
from pathlib import Path 
import base64 
from datetime import datetime

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(asctime)s %(module)s: %(message)s')

try:
    logger.info("Attempting to import xhtml2pdf.pisa in analysis_viewer.py...")
    from xhtml2pdf import pisa
    logger.info("Successfully imported xhtml2pdf.pisa in analysis_viewer.py.")
    XHTML2PDF_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import xhtml2pdf.pisa in analysis_viewer.py. Error: {e}", exc_info=True)
    XHTML2PDF_AVAILABLE = False
    pisa = None


def truncate_text(text: Optional[str], max_length: int = 200) -> str:
    if text is None:
        return "N/A"
    if len(text) > max_length:
        return text[:max_length - 3] + "..."
    return text

class RunAnalyzer:
    def __init__(self, db_path: str, output_data_dir: str, app_package_for_run: Optional[str] = None):
        self.db_path = db_path
        self.output_data_dir = output_data_dir
        self.app_package_for_run = app_package_for_run
        self.conn: Optional[sqlite3.Connection] = None

        if not os.path.exists(self.db_path):
            logger.error(f"Database file not found: {self.db_path}")
            raise FileNotFoundError(f"Database file not found: {self.db_path}")
        
        self._connect_db()

    def _connect_db(self):
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row 
            logger.info(f"Successfully connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database {self.db_path}: {e}")
            self.conn = None
            raise

    def _close_db_connection(self):
        if self.conn:
            self.conn.close()
            logger.info(f"Database connection closed: {self.db_path}")
            self.conn = None

    def list_runs(self):
        if not self.conn:
            logger.error("No database connection available to list runs.")
            self._connect_db() 
            if not self.conn: return

        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT run_id, app_package, start_activity, start_time, end_time, status FROM runs ORDER BY run_id DESC")
            runs = cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Error fetching runs from database: {e}")
            self._close_db_connection()
            return

        if not runs:
            print("No runs found in the database.")
        else:
            print("\nAvailable Runs:")
            print("---------------------------------------------------------------------------------------------------")
            print(f"{'ID':<5} {'App Package':<35} {'Start Activity':<35} {'Start Time':<20} {'Status':<10}")
            print("---------------------------------------------------------------------------------------------------")
            for run_item in runs:
                start_time_str = run_item['start_time'][:19] if run_item['start_time'] else "N/A"
                print(f"{run_item['run_id']:<5} {truncate_text(run_item['app_package'], 33):<35} {truncate_text(run_item['start_activity'], 33):<35} {start_time_str:<20} {run_item['status']:<10}")
            print("---------------------------------------------------------------------------------------------------")
        print("Use 'analyze-run <ID>' to see details for a specific run (CLI) or 'analyze-run <ID> --pdf-output <file.pdf>' for PDF.")
        self._close_db_connection()

    def _get_screenshot_full_path(self, db_screenshot_path: Optional[str]) -> Optional[str]:
        if not db_screenshot_path:
            return None
        
        if os.path.isabs(db_screenshot_path):
            if os.path.exists(db_screenshot_path):
                return os.path.abspath(db_screenshot_path)
            else:
                logger.warning(f"Absolute screenshot path from DB does not exist: '{db_screenshot_path}'")
                if self.output_data_dir and self.app_package_for_run:
                    potential_path_rel = os.path.join(self.output_data_dir, "screenshots", f"crawl_screenshots_{self.app_package_for_run}", os.path.basename(db_screenshot_path))
                    if os.path.exists(potential_path_rel):
                        logger.info(f"Resolved misconfigured absolute path '{db_screenshot_path}' to '{potential_path_rel}' relative to output dir.")
                        return os.path.abspath(potential_path_rel)
                return None

        if self.output_data_dir and self.app_package_for_run:
            potential_path = os.path.join(self.output_data_dir, "screenshots", f"crawl_screenshots_{self.app_package_for_run}", os.path.basename(db_screenshot_path))
            if os.path.exists(potential_path):
                 logger.debug(f"Resolved relative path '{db_screenshot_path}' to '{potential_path}'")
                 return os.path.abspath(potential_path)
            else:
                potential_path_flat = os.path.join(self.output_data_dir, "screenshots", db_screenshot_path)
                if os.path.exists(potential_path_flat):
                    logger.debug(f"Resolved relative path '{db_screenshot_path}' to '{potential_path_flat}' (flat structure).")
                    return os.path.abspath(potential_path_flat)

        logger.warning(f"Screenshot path '{db_screenshot_path}' could not be reliably resolved to an existing absolute path. PDF generation might fail for this image.")
        return None
    
    def _calculate_summary_metrics(self, run_id: int, run_data: sqlite3.Row, steps: List[sqlite3.Row]) -> Dict[str, Any]:
        """Calculates all the summary metrics for a given run."""
        metrics = {}
        total_steps = len(steps)
        
        # General Run Info
        if run_data['start_time'] and run_data['end_time']:
            start = datetime.fromisoformat(run_data['start_time'])
            end = datetime.fromisoformat(run_data['end_time'])
            duration = end - start
            metrics['Total Duration'] = str(duration).split('.')[0]
        else:
            metrics['Total Duration'] = "N/A (Run Incomplete)"

        metrics['Final Status'] = run_data['status']
        metrics['Total Steps'] = total_steps
        
        # Coverage Metrics
        unique_screen_ids = {s['from_screen_id'] for s in steps if s['from_screen_id']} | {s['to_screen_id'] for s in steps if s['to_screen_id']}
        metrics['Unique Screens Discovered'] = len(unique_screen_ids)
        
        unique_transitions = {(s['from_screen_id'], s['to_screen_id'], s['action_description']) for s in steps}
        metrics['Unique Transitions'] = len(unique_transitions)
        
        if self.conn and unique_screen_ids:
            cursor = self.conn.cursor()
            placeholders = ','.join('?' for _ in unique_screen_ids)
            query = f"SELECT COUNT(DISTINCT activity_name) FROM screens WHERE screen_id IN ({placeholders})"
            cursor.execute(query, list(unique_screen_ids))
            metrics['Activity Coverage'] = cursor.fetchone()[0]
        else:
            metrics['Activity Coverage'] = "N/A"

        action_types = [json.loads(s['ai_suggestion_json']).get('action') for s in steps if s['ai_suggestion_json']]
        action_distribution = {action: action_types.count(action) for action in set(action_types) if action}
        metrics['Action Distribution'] = ", ".join([f"{k}: {v}" for k, v in action_distribution.items()])

        # Efficiency Metrics
        if metrics['Unique Screens Discovered'] > 0:
            metrics['Steps per New Screen'] = f"{total_steps / metrics['Unique Screens Discovered']:.2f}"
        else:
            metrics['Steps per New Screen'] = "N/A"
            
        total_tokens = sum(s['total_tokens'] for s in steps if s['total_tokens'])
        metrics['Total Token Usage'] = f"{total_tokens:,}" if total_tokens else "N/A"
        
        valid_response_times = [s['ai_response_time_ms'] for s in steps if s['ai_response_time_ms'] is not None]
        if valid_response_times:
            avg_time = sum(valid_response_times) / len(valid_response_times)
            metrics['Avg AI Response Time'] = f"{avg_time:.0f} ms"
        else:
            metrics['Avg AI Response Time'] = "N/A"
            
        # Robustness Metrics
        stuck_steps = sum(1 for s in steps if s['from_screen_id'] == s['to_screen_id'])
        metrics['Stuck Steps (No-Op)'] = stuck_steps
        
        exec_failures = sum(1 for s in steps if not s['execution_success'])
        metrics['Execution Failures'] = exec_failures
        
        if total_steps > 0:
            metrics['Action Success Rate'] = f"{(1 - (exec_failures / total_steps)) * 100:.1f}%"
        else:
            metrics['Action Success Rate'] = "N/A"
            
        return metrics

    def _generate_summary_table_html(self, metrics: Dict[str, Any]) -> str:
        """Generates an HTML table from the metrics dictionary."""
        
        html = """
        <div class="summary-table-container">
            <h2>Run Summary Metrics</h2>
            <table class="summary-table">
                <tr><th colspan="2">General</th></tr>
                <tr><td>Total Duration</td><td>{Total Duration}</td></tr>
                <tr><td>Final Status</td><td>{Final Status}</td></tr>
                <tr><td>Total Steps</td><td>{Total Steps}</td></tr>
                
                <tr><th colspan="2">Coverage</th></tr>
                <tr><td>Unique Screens Discovered</td><td>{Unique Screens Discovered}</td></tr>
                <tr><td>Unique Transitions</td><td>{Unique Transitions}</td></tr>
                <tr><td>Activity Coverage</td><td>{Activity Coverage}</td></tr>
                <tr><td>Action Distribution</td><td>{Action Distribution}</td></tr>
                
                <tr><th colspan="2">Efficiency</th></tr>
                <tr><td>Steps per New Screen</td><td>{Steps per New Screen}</td></tr>
                <tr><td>Avg. AI Response Time</td><td>{Avg AI Response Time}</td></tr>
                <tr><td>Total Token Usage</td><td>{Total Token Usage}</td></tr>
                
                <tr><th colspan="2">Robustness</th></tr>
                <tr><td>Action Success Rate</td><td>{Action Success Rate}</td></tr>
                <tr><td>Execution Failures</td><td>{Execution Failures}</td></tr>
                <tr><td>Stuck Steps (No-Op)</td><td>{Stuck Steps (No-Op)}</td></tr>
            </table>
        </div>
        """
        
        return html.format(**{k: metrics.get(k, 'N/A') for k in [
            'Total Duration', 'Final Status', 'Total Steps', 'Unique Screens Discovered',
            'Unique Transitions', 'Activity Coverage', 'Action Distribution', 'Steps per New Screen',
            'Avg AI Response Time', 'Total Token Usage', 'Action Success Rate', 'Execution Failures', 'Stuck Steps (No-Op)'
        ]})

    def _fetch_run_and_steps_data(self, run_id: int) -> Tuple[Optional[sqlite3.Row], Optional[List[sqlite3.Row]]]:
        if not self.conn:
            logger.error(f"No database connection to fetch data for run {run_id}.")
            self._connect_db()
            if not self.conn:
                return None, None
        
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            run_data = cursor.fetchone()
        except sqlite3.Error as e:
            logger.error(f"Error fetching run data for run_id {run_id}: {e}")
            return None, None

        if not run_data:
            return None, None

        if not self.app_package_for_run and run_data['app_package']:
            self.app_package_for_run = run_data['app_package']
            logger.info(f"Set app_package_for_run to '{self.app_package_for_run}' from run data for run ID {run_id}.")
        
        query = """
        SELECT sl.*,
               s_from.screenshot_path AS from_screenshot_path, s_from.activity_name AS from_activity_name, s_from.composite_hash AS from_hash,
               s_to.screenshot_path AS to_screenshot_path, s_to.activity_name AS to_activity_name, s_to.composite_hash AS to_hash
        FROM steps_log sl
        LEFT JOIN screens s_from ON sl.from_screen_id = s_from.screen_id
        LEFT JOIN screens s_to ON sl.to_screen_id = s_to.screen_id
        WHERE sl.run_id = ? ORDER BY sl.step_number ASC
        """
        try:
            cursor.execute(query, (run_id,))
            steps = cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Error fetching steps for run_id {run_id}: {e}")
            return run_data, None
        
        return run_data, steps

    def _image_to_base64(self, image_path: str) -> Optional[str]:
        if not os.path.exists(image_path):
            logger.warning(f"Cannot encode image to base64: File not found at {image_path}")
            return None
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            image_type = Path(image_path).suffix.lower().lstrip('.')
            if image_type == 'jpg': image_type = 'jpeg'
            if image_type not in ['jpeg', 'png', 'gif']: image_type = 'png' 
            return f"data:image/{image_type};base64,{encoded_string}"
        except Exception as e:
            logger.error(f"Error encoding image {image_path} to base64: {e}", exc_info=True)
            return None

    def analyze_run_to_pdf(self, run_id: int, pdf_filepath: str):
        if not XHTML2PDF_AVAILABLE:
            logger.error("xhtml2pdf library is not installed. Cannot generate PDF. Please install it using: pip install xhtml2pdf")
            print("xhtml2pdf library is not installed. PDF generation aborted. Install with: pip install xhtml2pdf")
            self._close_db_connection()
            return

        run_data, steps = self._fetch_run_and_steps_data(run_id)

        if not run_data:
            print(f"Run ID {run_id} not found. PDF will not be generated.")
            logger.info(f"Run ID {run_id} not found. PDF generation aborted.")
            self._close_db_connection()
            return

        steps = steps or []

        metrics_data = self._calculate_summary_metrics(run_id, run_data, steps)
        summary_table_html = self._generate_summary_table_html(metrics_data)
        
        html_parts = ["""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Run Analysis Report</title>
            <style>
                @page { 
                    size: a4 portrait; 
                    margin: 0.6in; 
                }
                body { font-family: Helvetica, Arial, sans-serif; margin: 0; font-size: 9pt; line-height: 1.25; }
                h1 { font-size: 16pt; text-align: center; margin-top:0; margin-bottom: 12px; } 
                h2 { font-size: 12pt; margin-top: 18px; border-bottom: 1px solid #ccc; padding-bottom: 2px; margin-bottom: 8px;} 
                h3 { font-size: 11pt; margin-top: 10px; margin-bottom: 6px; color: #222; background-color: #e9e9e9; padding: 4px 6px; border-radius: 3px;}
                h4 { font-size: 9.5pt; margin-top: 8px; margin-bottom: 3px; color: #333; font-weight: bold; border-bottom: 1px dotted #ddd; padding-bottom: 2px;} 
                
                .summary-table-container { page-break-after: always; }
                .summary-table { border-collapse: collapse; width: 100%; margin-bottom: 20px; font-size: 8.5pt; }
                .summary-table th { background-color: #e9e9e9; text-align: left; padding: 6px; border: 1px solid #ccc; }
                .summary-table td { padding: 5px; border: 1px solid #ddd; }
                .summary-table td:first-child { font-weight: bold; width: 40%; }
                
                p.feature-item { margin: 4px 0 6px 5px; } 
                strong.feature-title { font-weight: bold; color: #111; display: block; margin-bottom: 1px;} 
                
                .step-container { 
                    margin-bottom: 12px; 
                    padding: 8px; 
                    border: 1px solid #c8c8c8; 
                    background-color: #fcfcfc;
                    page-break-inside: avoid !important;
                }
                .step-text-content { margin-bottom: 10px; }
                .step-screenshots-container { 
                    display: -pdf-flex-box; 
                    -pdf-flex-direction: row; 
                    -pdf-justify-content: space-around; 
                    gap: 8px; 
                    margin-top: 8px;
                    border-top: 1px solid #eee;
                    padding-top: 8px;
                }
                .step-screenshots-container > div { -pdf-flex: 1; text-align: center; padding: 0 4px; }
                .step-screenshots-container img.screenshot { max-width: 95%; max-height: 240px; width: auto; height: auto; border: 1px solid #bbb; margin-top: 2px; margin-bottom: 4px; display: inline-block; }
                .screenshot-warning { color: red; font-size: 7pt; }
                pre { white-space: pre-wrap; word-wrap: break-word; background-color: #f0f0f0; border: 1px solid #ccc; padding: 5px; font-size: 7.5pt; max-height: 100px; overflow: hidden; margin-left: 5px; margin-bottom: 5px; }
                hr { border: 0; border-top: 1px solid #ddd; margin: 12px 0; } 
                .to-screen-section-na { margin-left: 5px; font-style: italic; }
            </style>
        </head>
        <body>
        """]

        html_parts.append(summary_table_html)
        html_parts.append(f"<h1>Run Analysis Report - Run ID: {run_id} (App: {escape(str(run_data['app_package']))})</h1>")
        
        if not steps:
            html_parts.append("<p>No steps found for this run.</p>")
        else:
            html_parts.append("<h2>Step Details</h2>")
            for i, step in enumerate(steps):
                html_parts.append(f"<div class='step-container'><h3>Step {step['step_number']} (Log ID: {step['step_log_id']})</h3>")
                
                html_parts.append("<div class='step-text-content'>")

                html_parts.append(f"<h4>FROM SCREEN</h4>")
                html_parts.append(f"<p class='feature-item'><strong class='feature-title'>Activity:</strong>{escape(step['from_activity_name'] or 'N/A')}</p>")

                html_parts.append(f"<h4>AI INPUT CONTEXT (Approximated)</h4>")
                prev_action_display_html = "N/A (Start of run)"
                if i > 0: prev_action_display_html = escape(steps[i-1]['action_description'] or "N/A")
                html_parts.append(f"<p class='feature-item'><strong class='feature-title'>Last Action (Previous Step):</strong>{prev_action_display_html}</p>")

                html_parts.append(f"<h4>AI OUTPUT</h4>")
                ai_sugg_text_html, ai_reas_text_html, ai_response_time_html = "N/A", "N/A", ""
                
                if 'ai_response_time_ms' in step.keys() and step['ai_response_time_ms'] is not None:
                    ai_response_time_html = f"<p class='feature-item'><strong class='feature-title'>Response Time:</strong>{step['ai_response_time_ms']/1000:.2f} seconds</p>"

                if step['ai_suggestion_json']:
                    try:
                        sugg_data = json.loads(step['ai_suggestion_json'])
                        act_src_dict = sugg_data.get('action_to_perform') or sugg_data
                        if act_src_dict and isinstance(act_src_dict, dict):
                            act_t = act_src_dict.get('action', 'N/A')
                            tgt_id = act_src_dict.get('target_identifier', 'N/A')
                            in_txt = act_src_dict.get('input_text')
                            rsng = act_src_dict.get('reasoning', "N/A")
                            ai_reas_text_html = escape(rsng)
                            ai_sugg_text_html = f"Action: {escape(act_t)}"
                            if tgt_id != 'N/A': ai_sugg_text_html += f" on '{escape(str(tgt_id))}'"
                            if in_txt: ai_sugg_text_html += f" | Input: '{escape(in_txt)}'"
                    except (json.JSONDecodeError, AttributeError):
                        ai_sugg_text_html = f"Error parsing JSON: {escape(step['ai_suggestion_json'])}"
                html_parts.append(f"<p class='feature-item'><strong class='feature-title'>Suggested:</strong>{ai_sugg_text_html}</p>")
                html_parts.append(ai_response_time_html)
                html_parts.append(f"<p class='feature-item'><strong class='feature-title'>Reasoning:</strong></p><pre>{ai_reas_text_html}</pre>")
                
                html_parts.append(f"<h4>CRAWLER ACTION EXECUTED</h4>")
                html_parts.append(f"<p class='feature-item'><strong class='feature-title'>High-Level:</strong>{escape(step['action_description'] or 'N/A')}</p>")
                
                status_color = "#28a745" if step['execution_success'] else "#dc3545"
                html_parts.append(f"<p class='feature-item'><strong class='feature-title'>Execution Status:</strong><span style='color: {status_color}; font-weight: bold;'>{'Success' if step['execution_success'] else 'Failed'}</span></p>")
                
                if not step['execution_success'] and step['error_message']:
                    html_parts.append(f"<p class='feature-item'><strong class='feature-title'>Error Message:</strong><span style='color: #dc3545;'>{escape(step['error_message'])}</span></p>")
                
                html_parts.append("</div>")

                html_parts.append("<div class='step-screenshots-container'>")
                if full_from_ss_path := self._get_screenshot_full_path(step['from_screenshot_path']):
                    if base64_image := self._image_to_base64(full_from_ss_path):
                        html_parts.append(f"<div><p><strong>FROM Screen:</strong></p><img src='{base64_image}' class='screenshot'></div>")
                
                if step['to_screen_id'] is not None:
                    if full_to_ss_path := self._get_screenshot_full_path(step['to_screenshot_path']):
                        if base64_image_to := self._image_to_base64(full_to_ss_path):
                            html_parts.append(f"<div><p><strong>TO Screen:</strong></p><img src='{base64_image_to}' class='screenshot'></div>")

                html_parts.append("</div></div>")
                if i < len(steps) - 1: html_parts.append("<hr>")
        
        html_parts.append("</body></html>")
        full_html = "".join(html_parts)

        # --- MODIFIED: More robust PDF generation block ---
        try:
            with open(pdf_filepath, "wb") as f_pdf:
                if pisa:
                    # pisa.CreatePDF returns a pisaDocument status object
                    pisa_status = pisa.CreatePDF(full_html, dest=f_pdf, encoding='utf-8')
                    
                    # Check if the status object was created and if it has a non-zero error code
                    if pisa_status and not pisa_status.err: # type: ignore
                        logger.info(f"Successfully generated PDF report: {pdf_filepath}")
                        print(f"PDF report generated: {pdf_filepath}")
                    else:
                        error_code = getattr(pisa_status, 'err', -1) # Safely get error code
                        logger.error(f"Error generating PDF. Error code: {error_code}")
                        print(f"Error generating PDF (code: {error_code}). Check logs for details.")
                else:
                    logger.error("xhtml2pdf is not available.")
                    print("Error: xhtml2pdf is not available. PDF not generated.")
        except Exception as e:
            logger.error(f"Unexpected error during PDF generation: {e}", exc_info=True)
            # Try to save debug HTML even on unexpected errors
            html_debug_filepath = os.path.splitext(pdf_filepath)[0] + "_debug.html"
            try:
                with open(html_debug_filepath, "w", encoding="utf-8") as f_html:
                    f_html.write(full_html)
                logger.info(f"Saved HTML content for debugging to: {html_debug_filepath}")
            except Exception as e_debug:
                logger.error(f"Failed to save debug HTML file: {e_debug}")
        finally:
            self._close_db_connection()

    def print_run_summary(self, run_id: int):
        """Compute summary metrics for a run and print them to the console.

        This provides a quick CLI-friendly overview without generating a PDF.
        """
        run_data, steps = self._fetch_run_and_steps_data(run_id)

        if not run_data:
            print(f"Run ID {run_id} not found. No summary available.")
            logger.info(f"Run ID {run_id} not found. Summary printing aborted.")
            self._close_db_connection()
            return

        steps = steps or []

        metrics_data = self._calculate_summary_metrics(run_id, run_data, steps)

        # Pretty-print summary
        print("\n=== Run Summary ===")
        print(f"Run ID: {run_id}")
        print(f"App Package: {run_data['app_package']}")
        print(f"Start Activity: {run_data['start_activity']}")
        print(f"Start Time: {run_data['start_time'] or 'N/A'}")
        print(f"End Time: {run_data['end_time'] or 'N/A'}")
        print("-------------------")
        print("General:")
        print(f"  Total Duration: {metrics_data.get('Total Duration', 'N/A')}")
        print(f"  Final Status: {metrics_data.get('Final Status', 'N/A')}")
        print(f"  Total Steps: {metrics_data.get('Total Steps', 'N/A')}")
        print("Coverage:")
        print(f"  Unique Screens Discovered: {metrics_data.get('Unique Screens Discovered', 'N/A')}")
        print(f"  Unique Transitions: {metrics_data.get('Unique Transitions', 'N/A')}")
        print(f"  Activity Coverage: {metrics_data.get('Activity Coverage', 'N/A')}")
        print(f"  Action Distribution: {metrics_data.get('Action Distribution', 'N/A')}")
        print("Efficiency:")
        print(f"  Steps per New Screen: {metrics_data.get('Steps per New Screen', 'N/A')}")
        print(f"  Avg AI Response Time: {metrics_data.get('Avg AI Response Time', 'N/A')}")
        print(f"  Total Token Usage: {metrics_data.get('Total Token Usage', 'N/A')}")
        print("Robustness:")
        print(f"  Action Success Rate: {metrics_data.get('Action Success Rate', 'N/A')}")
        print(f"  Execution Failures: {metrics_data.get('Execution Failures', 'N/A')}")
        print(f"  Stuck Steps (No-Op): {metrics_data.get('Stuck Steps (No-Op)', 'N/A')}")
        print("====================\n")

        self._close_db_connection()