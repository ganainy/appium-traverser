# analysis_viewer.py
import json
import os
import sqlite3
import logging
from typing import Optional, List, Dict, Any, Tuple
from html import escape
from pathlib import Path 
import base64 

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(asctime)s %(module)s: %(message)s')

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
    WEASYPRINT_AVAILABLE = False

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
            if not self.conn:
                return

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
               s_from.screenshot_path AS from_screenshot_path, s_from.xml_content AS from_xml_content, s_from.activity_name AS from_activity_name,
               s_to.screenshot_path AS to_screenshot_path, s_to.activity_name AS to_activity_name
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

    def analyze_run_to_cli(self, run_id: int):
        run_data, steps = self._fetch_run_and_steps_data(run_id)

        if not run_data:
            print(f"Run ID {run_id} not found.")
            self._close_db_connection() 
            self.list_runs() 
            return

        print(f"\n--- Analyzing Run ID: {run_id} for App: {run_data['app_package']} ---")
        start_time_str = run_data['start_time'][:19] if run_data['start_time'] else "N/A"
        end_time_str = run_data['end_time'][:19] if run_data['end_time'] else "N/A"
        print(f"Start Time: {start_time_str}, End Time: {end_time_str}, Status: {run_data['status']}\n")

        if not steps:
            print("No steps found for this run.")
            self._close_db_connection()
            return

        for i, step in enumerate(steps):
            print(f"\n==================== Step {step['step_number']} (Log ID: {step['step_log_id']}) ====================")
            print("\n  [FROM SCREEN]")
            from_activity = step['from_activity_name'] if step['from_activity_name'] else 'N/A'
            print(f"    Activity: {from_activity}")
            from_screenshot_path_db = step['from_screenshot_path']
            full_from_ss_path = self._get_screenshot_full_path(from_screenshot_path_db)
            print(f"    Screenshot Path: {full_from_ss_path if full_from_ss_path else 'N/A'}")
            if full_from_ss_path and not os.path.exists(full_from_ss_path):
                 print(f"      WARNING: Screenshot file not found at '{full_from_ss_path}'")
            print("\n  [AI INPUT CONTEXT (Approximated)]")
            # XML is not printed to CLI by default for brevity
            if i > 0: 
                prev_step_action_desc = steps[i-1]['action_description']
                prev_step_mapped_json = steps[i-1]['mapped_action_json']
                prev_action_display = prev_step_action_desc 
                if prev_step_mapped_json:
                    try:
                        mapped = json.loads(prev_step_mapped_json)
                        prev_action_display = f"Type: {mapped.get('action_type', 'N/A')}, Target: {truncate_text(mapped.get('target_element_desc', 'N/A'), 30)}"
                        if mapped.get('input_text'):
                            prev_action_display += f", Input: '{truncate_text(mapped.get('input_text'), 20)}'"
                    except json.JSONDecodeError:
                        logger.debug(f"Could not parse prev_step_mapped_json for display: {prev_step_mapped_json}")
                print(f"    Last Action (Previous Step): {truncate_text(prev_action_display, 100)}")
            else:
                print(f"    Last Action (Previous Step): N/A (Start of run)")
            print("\n  [AI OUTPUT]")
            ai_suggestion_text = "N/A"
            ai_reasoning_text = "N/A"
            if step['ai_suggestion_json']:
                try:
                    suggestion_data = json.loads(step['ai_suggestion_json'])
                    action_source_dict = None
                    if isinstance(suggestion_data, dict):
                        if 'action_to_perform' in suggestion_data and isinstance(suggestion_data.get('action_to_perform'), dict):
                            action_source_dict = suggestion_data['action_to_perform']
                        elif 'action' in suggestion_data: 
                            action_source_dict = suggestion_data
                    if action_source_dict:
                        act_type = action_source_dict.get('action', 'N/A')
                        target_id = action_source_dict.get('target_identifier')
                        if target_id is None: target_id = action_source_dict.get('target_element_desc')
                        if target_id is None: target_id = action_source_dict.get('target_element_description')
                        if target_id is None: target_id = 'N/A' 
                        input_txt = action_source_dict.get('input_text')
                        reasoning = action_source_dict.get('reasoning')
                        if reasoning is None: reasoning = action_source_dict.get('short_reasoning')
                        if reasoning is None: reasoning = action_source_dict.get('explanation')
                        ai_reasoning_text = reasoning if reasoning is not None else "N/A"
                        ai_suggestion_text = f"Action: {act_type}"
                        if target_id != 'N/A': ai_suggestion_text += f" on '{truncate_text(str(target_id), 50)}'"
                        if input_txt: ai_suggestion_text += f" | Input: '{truncate_text(input_txt, 30)}'"
                        if ai_reasoning_text == "N/A" and not any(k in action_source_dict for k in ['reasoning', 'short_reasoning', 'explanation']):
                            ai_reasoning_text = "Reasoning field missing"
                        elif reasoning is None and any(k in action_source_dict for k in ['reasoning', 'short_reasoning', 'explanation']):
                            ai_reasoning_text = "Reasoning field present but empty/null"
                    else: 
                        ai_suggestion_text = f"Raw JSON: {truncate_text(str(suggestion_data), 100)}"
                        ai_reasoning_text = "N/A (Could not parse AI suggestion structure)"
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse ai_suggestion_json: {step['ai_suggestion_json']}")
                    ai_suggestion_text = f"Error parsing JSON: {truncate_text(step['ai_suggestion_json'])}"
                except Exception as e:
                    logger.error(f"Unexpected error processing AI suggestion: {e} - Data: {step['ai_suggestion_json']}", exc_info=True)
                    ai_suggestion_text = f"Error processing: {truncate_text(str(step['ai_suggestion_json']))}"
            print(f"    Suggested: {ai_suggestion_text}")
            print(f"    Reasoning: {truncate_text(ai_reasoning_text, 300)}")
            print("\n  [CRAWLER ACTION EXECUTED]")
            action_desc_text = step['action_description'] if step['action_description'] else "N/A"
            print(f"    High-Level: {action_desc_text}")
            mapped_action_display = "N/A"
            if step['mapped_action_json']:
                try:
                    mapped_data = json.loads(step['mapped_action_json'])
                    mapped_action_display = f"Type: {mapped_data.get('action_type', 'N/A')}, Target: {truncate_text(mapped_data.get('target_element_desc', 'N/A'), 50)}"
                    if mapped_data.get('input_text'): mapped_action_display += f", Input: '{truncate_text(mapped_data.get('input_text'), 30)}'"
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse mapped_action_json: {step['mapped_action_json']}")
                    mapped_action_display = f"Error parsing JSON: {truncate_text(step['mapped_action_json'])}"
            print(f"    Mapped/Executed: {mapped_action_display}")
            print(f"    Execution Success: {step['execution_success']}")
            if not step['execution_success'] and step['error_message']:
                print(f"    Error Message: {truncate_text(step['error_message'])}")
            if step['to_screen_id'] is not None:
                print("\n  [TO SCREEN]")
                to_activity = step['to_activity_name'] if step['to_activity_name'] else 'N/A'
                print(f"    Activity: {to_activity}")
                to_screenshot_path_db = step['to_screenshot_path']
                full_to_ss_path = self._get_screenshot_full_path(to_screenshot_path_db)
                print(f"    Screenshot Path: {full_to_ss_path if full_to_ss_path else 'N/A'}")
                if full_to_ss_path and not os.path.exists(full_to_ss_path):
                    print(f"      WARNING: Screenshot file not found at '{full_to_ss_path}'")
            elif step['execution_success']:
                 print("\n  [TO SCREEN]: N/A (Action succeeded, but no distinct 'to_screen' recorded or transition out of app)")
            else:
                 print("\n  [TO SCREEN]: N/A (Action failed or did not result in a screen change)")
        print(f"\n--- End of Analysis for Run ID: {run_id} ---")
        self._close_db_connection()

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
                h2 { font-size: 12pt; margin-top: 12px; border-bottom: 1px solid #ccc; padding-bottom: 2px; margin-bottom: 8px;} 
                h3 { font-size: 11pt; margin-top: 10px; margin-bottom: 6px; color: #222; background-color: #e9e9e9; padding: 4px 6px; border-radius: 3px;}
                h4 { font-size: 9.5pt; margin-top: 8px; margin-bottom: 3px; color: #333; font-weight: bold; border-bottom: 1px dotted #ddd; padding-bottom: 2px;} 
                
                p.feature-item { margin: 4px 0 6px 5px; } /* Consistent spacing for feature items */
                strong.feature-title { font-weight: bold; color: #111; display: block; margin-bottom: 1px;} /* Title on its own line */
                
                .step-container { 
                    margin-bottom: 12px; 
                    padding: 8px; 
                    border: 1px solid #c8c8c8; 
                    background-color: #fcfcfc;
                    page-break-inside: avoid !important;
                }
                .step-text-content {
                    margin-bottom: 10px; 
                }
                .step-screenshots-container { 
                    display: -pdf-flex-box; 
                    -pdf-flex-direction: row; 
                    -pdf-justify-content: space-around; 
                    gap: 8px; 
                    margin-top: 8px;
                    border-top: 1px solid #eee;
                    padding-top: 8px;
                }
                .step-screenshots-container > div { 
                    -pdf-flex: 1; 
                    text-align: center; 
                    padding: 0 4px;
                }
                .step-screenshots-container img.screenshot { 
                    max-width: 95%; 
                    max-height: 240px; 
                    width: auto; 
                    height: auto; 
                    border: 1px solid #bbb; 
                    margin-top: 2px; margin-bottom: 4px;
                    display: inline-block; 
                }
                .screenshot-warning { color: red; font-size: 7pt; }
                pre { 
                    white-space: pre-wrap; 
                    word-wrap: break-word; 
                    background-color: #f0f0f0; 
                    border: 1px solid #ccc; 
                    padding: 5px;
                    font-size: 7.5pt; 
                    max-height: 100px; 
                    overflow: hidden; 
                    margin-left: 5px;
                    margin-bottom: 5px;
                }
                hr { border: 0; border-top: 1px solid #ddd; margin: 12px 0; } 
                .to-screen-section-na { 
                    margin-left: 5px;
                    font-style: italic;
                }
            </style>
        </head>
        <body>
        """]

        # Run Summary is removed as per request

        if not steps:
            html_parts.append("<p>No steps found for this run.</p>")
        else:
            html_parts.append(f"<h1>Run Analysis Report - Run ID: {run_id} (App: {escape(str(run_data['app_package']))})</h1>")
            html_parts.append("<h2>Step Details</h2>")
            for i, step in enumerate(steps):
                html_parts.append(f"<div class='step-container'><h3>Step {step['step_number']} (Log ID: {step['step_log_id']})</h3>")
                
                html_parts.append("<div class='step-text-content'>")

                # FROM SCREEN Text
                html_parts.append(f"<h4>FROM SCREEN</h4>")
                html_parts.append(f"<p class='feature-item'><strong class='feature-title'>Activity:</strong>{escape(step['from_activity_name'] or 'N/A')}</p>")
                # XML content for 'from_xml_content' is intentionally omitted from PDF

                # AI INPUT CONTEXT
                html_parts.append(f"<h4>AI INPUT CONTEXT (Approximated)</h4>")
                prev_action_display_html = "N/A (Start of run)"
                if i > 0:
                    prev_s_action_desc = steps[i-1]['action_description']
                    prev_s_mapped_json = steps[i-1]['mapped_action_json']
                    prev_action_display_html = escape(prev_s_action_desc or "N/A")
                    if prev_s_mapped_json:
                        try:
                            mapped = json.loads(prev_s_mapped_json)
                            target_desc_prev = mapped.get('target_element_desc', 'N/A')
                            input_text_prev = mapped.get('input_text')
                            prev_action_display_html = f"Type: {escape(mapped.get('action_type', 'N/A'))}, Target: {escape(target_desc_prev)}"
                            if input_text_prev: prev_action_display_html += f", Input: '{escape(input_text_prev)}'"
                        except json.JSONDecodeError: pass
                html_parts.append(f"<p class='feature-item'><strong class='feature-title'>Last Action (Previous Step):</strong>{prev_action_display_html}</p>")

                # AI OUTPUT
                html_parts.append(f"<h4>AI OUTPUT</h4>")
                ai_sugg_text_html, ai_reas_text_html = "N/A", "N/A"
                if step['ai_suggestion_json']:
                    try:
                        sugg_data = json.loads(step['ai_suggestion_json'])
                        act_src_dict = sugg_data.get('action_to_perform') if isinstance(sugg_data.get('action_to_perform'), dict) else (sugg_data if isinstance(sugg_data, dict) and 'action' in sugg_data else None)
                        if act_src_dict:
                            act_t = act_src_dict.get('action', 'N/A')
                            tgt_id = act_src_dict.get('target_identifier') or act_src_dict.get('target_element_desc') or act_src_dict.get('target_element_description') or 'N/A'
                            in_txt = act_src_dict.get('input_text')
                            rsng = act_src_dict.get('reasoning') or act_src_dict.get('short_reasoning') or act_src_dict.get('explanation')
                            ai_reas_text_html = escape(rsng or "N/A")
                            ai_sugg_text_html = f"Action: {escape(act_t)}"
                            if tgt_id != 'N/A': ai_sugg_text_html += f" on '{escape(str(tgt_id))}'"
                            if in_txt: ai_sugg_text_html += f" | Input: '{escape(in_txt)}'"
                            if ai_reas_text_html == "N/A" and not any(k in act_src_dict for k in ['reasoning', 'short_reasoning', 'explanation']): ai_reas_text_html = "Reasoning field missing"
                            elif rsng is None and any(k in act_src_dict for k in ['reasoning', 'short_reasoning', 'explanation']): ai_reas_text_html = "Reasoning field present but empty/null"
                        else: ai_sugg_text_html, ai_reas_text_html = f"Raw JSON: {escape(str(sugg_data))}", "N/A (Could not parse AI suggestion structure)"
                    except json.JSONDecodeError: ai_sugg_text_html = f"Error parsing JSON: {escape(step['ai_suggestion_json'])}"
                    except Exception: ai_sugg_text_html = f"Error processing: {escape(step['ai_suggestion_json'])}"
                html_parts.append(f"<p class='feature-item'><strong class='feature-title'>Suggested:</strong>{ai_sugg_text_html}</p>")
                html_parts.append(f"<p class='feature-item'><strong class='feature-title'>Reasoning:</strong></p><pre>{ai_reas_text_html}</pre>")
                
                # CRAWLER ACTION EXECUTED
                html_parts.append(f"<h4>CRAWLER ACTION EXECUTED</h4>")
                html_parts.append(f"<p class='feature-item'><strong class='feature-title'>High-Level:</strong>{escape(step['action_description'] or 'N/A')}</p>")
                map_act_disp_html = "N/A"
                if step['mapped_action_json']:
                    try:
                        map_data = json.loads(step['mapped_action_json'])
                        target_desc_map, input_text_map = map_data.get('target_element_desc', 'N/A'), map_data.get('input_text')
                        map_act_disp_html = f"Type: {escape(map_data.get('action_type', 'N/A'))}, Target: {escape(target_desc_map)}"
                        if input_text_map: map_act_disp_html += f", Input: '{escape(input_text_map)}'"
                    except json.JSONDecodeError: map_act_disp_html = f"Error parsing JSON: {escape(step['mapped_action_json'])}"
                html_parts.append(f"<p class='feature-item'><strong class='feature-title'>Mapped/Executed:</strong>{map_act_disp_html}</p>")
                html_parts.append(f"<p class='feature-item'><strong class='feature-title'>Execution Success:</strong>{step['execution_success']}</p>")
                if not step['execution_success'] and step['error_message']:
                    html_parts.append(f"<p class='feature-item'><strong class='feature-title'>Error Message:</strong>{escape(step['error_message'] or 'N/A')}</p>")

                # TO SCREEN Text
                if step['to_screen_id'] is not None:
                    html_parts.append(f"<h4>TO SCREEN</h4>")
                    html_parts.append(f"<p class='feature-item'><strong class='feature-title'>Activity:</strong>{escape(step['to_activity_name'] or 'N/A')}</p>")
                elif step['execution_success']:
                    html_parts.append("<p class='to-screen-section-na feature-item'><strong class='feature-title'>TO SCREEN:</strong>N/A (Action succeeded, but no distinct 'to_screen' recorded or transition out of app)</p>")
                else:
                    html_parts.append("<p class='to-screen-section-na feature-item'><strong class='feature-title'>TO SCREEN:</strong>N/A (Action failed or did not result in a screen change)</p>")
                
                html_parts.append("</div>") # End step-text-content

                # Screenshots container at the end of the step
                html_parts.append("<div class='step-screenshots-container'>")
                from_ss_html_added = False
                full_from_ss_path = self._get_screenshot_full_path(step['from_screenshot_path'])
                if full_from_ss_path:
                    base64_image = self._image_to_base64(full_from_ss_path)
                    if base64_image:
                        html_parts.append(f"<div><p><strong class='feature-title'>FROM Screen:</strong></p><img src='{base64_image}' class='screenshot' alt='From screen {step['step_number']}'></div>")
                        from_ss_html_added = True
                if not from_ss_html_added: # Fallback if no image
                     html_parts.append(f"<div><p><strong class='feature-title'>FROM Screen:</strong> N/A</p></div>")


                to_ss_html_added = False
                if step['to_screen_id'] is not None:
                    full_to_ss_path = self._get_screenshot_full_path(step['to_screenshot_path'])
                    if full_to_ss_path:
                        base64_image_to = self._image_to_base64(full_to_ss_path)
                        if base64_image_to:
                            html_parts.append(f"<div><p><strong class='feature-title'>TO Screen:</strong></p><img src='{base64_image_to}' class='screenshot' alt='To screen {step['step_number']}'></div>")
                            to_ss_html_added = True
                if not to_ss_html_added: # Fallback if no TO screen image (or no TO screen)
                    html_parts.append(f"<div><p><strong class='feature-title'>TO Screen:</strong> N/A</p></div>")
                
                html_parts.append("</div>") # End step-screenshots-container
                html_parts.append("</div>") # End step-container
                if i < len(steps) - 1: html_parts.append("<hr>")
        html_parts.append("</body></html>")
        full_html = "".join(html_parts)

        try:
            pisa_document = None
            with open(pdf_filepath, "wb") as f_pdf:
                if pisa:
                    pisa_document = pisa.CreatePDF(full_html, dest=f_pdf, encoding='utf-8')
                else:
                    logger.error("xhtml2pdf (pisa) is None. Cannot generate PDF.")
                    print("Error: xhtml2pdf (pisa) is not available. PDF not generated.")
                    self._close_db_connection()
                    return

            pdf_generated_successfully = False 

            if pisa_document is None:
                logger.error("Error generating PDF: xhtml2pdf.CreatePDF returned None.")
                print("Error generating PDF: Creation failed (PDF library returned None). Check logs.")
            elif isinstance(pisa_document, (bytes, bytearray, memoryview)):
                logger.error(f"Error generating PDF: xhtml2pdf.CreatePDF returned raw bytes-like object ({type(pisa_document).__name__}) unexpectedly when a destination file was provided.")
                print("Error generating PDF: Unexpected data type from PDF library. Check logs.")
            elif hasattr(pisa_document, 'err'):
                err_code = pisa_document.err 
                if err_code == 0:
                    pdf_generated_successfully = True
                    logger.info(f"Successfully generated PDF report: {pdf_filepath}")
                    print(f"PDF report generated: {pdf_filepath}")
                    if hasattr(pisa_document, 'warn') and pisa_document.warn:
                        logger.warning(f"xhtml2pdf warnings during PDF generation: {pisa_document.warn}")
                        print(f"PDF report generated with warnings: {pdf_filepath}. Check logs for details.")
                else:
                    error_message = f"Error generating PDF with xhtml2pdf. Error code: {err_code}"
                    if hasattr(pisa_document, 'warn') and pisa_document.warn:
                        error_message += f", Warnings: {pisa_document.warn}"
                    logger.error(error_message)
                    print(f"Error generating PDF (code: {err_code}). Check logs.")
            else:
                logger.error(f"Error generating PDF: xhtml2pdf.CreatePDF returned an object of type {type(pisa_document).__name__} which lacks an 'err' attribute. This is unexpected.")
                print("Error generating PDF: Unexpected result from PDF library (missing 'err' attribute). Check logs.")

            if not pdf_generated_successfully:
                html_debug_filepath = os.path.splitext(pdf_filepath)[0] + "_debug.html"
                try:
                    with open(html_debug_filepath, "w", encoding="utf-8") as f_html:
                        f_html.write(full_html) 
                    logger.info(f"Saved HTML content for debugging to: {html_debug_filepath}")
                    print(f"Saved HTML for debugging: {html_debug_filepath}")
                except Exception as e_debug_save:
                    logger.error(f"Failed to save debug HTML file: {e_debug_save}")
                    print(f"Additionally, failed to save debug HTML: {e_debug_save}")
        except Exception as e:
            logger.error(f"Unexpected error during PDF generation: {e}", exc_info=True)
            print(f"Unexpected error generating PDF: {e}. Check logs for details.")
            html_debug_filepath = os.path.splitext(pdf_filepath)[0] + "_debug.html"
            try:
                with open(html_debug_filepath, "w", encoding="utf-8") as f_html: f_html.write(full_html)
                logger.info(f"Saved HTML content for debugging to: {html_debug_filepath}")
                print(f"Saved HTML for debugging: {html_debug_filepath}")
            except Exception as e_debug_save_outer:
                 logger.error(f"Failed to save debug HTML file after unexpected error: {e_debug_save_outer}")
                 print(f"Additionally, failed to save debug HTML after unexpected error: {e_debug_save_outer}")
        finally:
            self._close_db_connection()