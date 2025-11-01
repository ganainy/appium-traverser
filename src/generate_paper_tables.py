import collections
import json
import sqlite3
from pathlib import Path


def analyze_databases(output_dir: Path):
    """
    Analyzes all crawl databases to generate aggregated metrics for the paper.
    """
    db_files = list(output_dir.glob("**/*_crawl_data.db"))

    if not db_files:
        print(f"Error: No database files found in '{output_dir}'.")
        print("Please ensure you have run the crawler and that .db files exist in the session directories.")
        return

    print(f"Found {len(db_files)} database files to analyze...")

    # --- Aggregated Metrics Initialization ---
    total_identifier_successes = 0
    total_coordinate_fallbacks = 0
    total_targeted_clicks = 0
    
    total_stuck_events = 0
    total_successful_corrections = 0

    for db_path in db_files:
        print(f"  Analyzing: {db_path.parent.name}/{db_path.name}")
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # --- Metric 1: Mapper Fallback Reliance ---
            cursor.execute("""
                SELECT mapped_action_json
                FROM steps_log
                WHERE ai_suggestion_json LIKE '%"action": "click"%'
            """)
            click_steps = cursor.fetchall()
            
            app_id_success = 0
            app_coord_fallback = 0

            for step in click_steps:
                if not step['mapped_action_json']:
                    continue
                try:
                    mapped_action = json.loads(step['mapped_action_json'])
                    if mapped_action.get('type') == 'tap_coords':
                        app_coord_fallback += 1
                    elif mapped_action.get('type') == 'click':
                        app_id_success += 1
                except (json.JSONDecodeError, TypeError):
                    continue
            
            total_identifier_successes += app_id_success
            total_coordinate_fallbacks += app_coord_fallback
            total_targeted_clicks += len(click_steps)

            # --- Metric 2: AI Self-Correction Rate ---
            cursor.execute("""
                SELECT from_screen_id, to_screen_id, execution_success, ai_suggestion_json
                FROM steps_log
                ORDER BY step_number ASC
            """)
            all_steps = cursor.fetchall()

            app_stuck_events = 0
            app_successful_corrections = 0
            was_stuck = False

            for i, current_step in enumerate(all_steps):
                if was_stuck:
                    # Previous step was a no-op, check if this one is a correction
                    try:
                        prev_sugg = json.loads(all_steps[i-1]['ai_suggestion_json'])
                        curr_sugg = json.loads(current_step['ai_suggestion_json'])
                        prev_action = prev_sugg.get('action_to_perform', {}).get('action')
                        curr_action = curr_sugg.get('action_to_perform', {}).get('action')
                        
                        if prev_action != curr_action:
                            app_successful_corrections += 1
                    except (json.JSONDecodeError, TypeError, IndexError):
                        pass # Ignore if parsing fails or out of bounds
                    was_stuck = False # Reset flag

                # Check if the current step is a "no-op" or "stuck step"
                if current_step['from_screen_id'] == current_step['to_screen_id'] and current_step['execution_success']:
                    app_stuck_events += 1
                    was_stuck = True

            total_stuck_events += app_stuck_events
            total_successful_corrections += app_successful_corrections

            conn.close()

        except sqlite3.Error as e:
            print(f"    Could not process database {db_path.name}. Error: {e}")
            continue

    # --- Final Calculations ---
    fallback_reliance_rate = (total_coordinate_fallbacks / total_targeted_clicks * 100) if total_targeted_clicks > 0 else 0
    self_correction_rate = (total_successful_corrections / total_stuck_events * 100) if total_stuck_events > 0 else 0

    # --- Generate LaTeX Output ---
    print("\n" + "="*80)
    print("Copy the LaTeX code below into your paper's .tex file.")
    print("="*80 + "\n")

    # LaTeX Table for Self-Correction
    latex_table_self_correction = f"""
\\begin{{table}}[h!]
\\centering
\\caption{{Aggregated AI Self-Correction Rate Following 'NO CHANGE' Feedback}}
\\label{{tab:ai_self_correction_agg}}
\\begin{{tabular}}{{|l|c|}}
\\hline
\\textbf{{Metric}} & \\textbf{{Value}} \\\\ \\hline
Total "NO CHANGE" Events Detected & {total_stuck_events} \\\\ \\hline
Successful Self-Corrections (Next Step) & {total_successful_corrections} \\\\ \\hline
\\textbf{{Self-Correction Rate}} & \\textbf{{{self_correction_rate:.1f}\\%}} \\\\ \\hline
\\end{{tabular}}
\\end{{table}}
"""

    # LaTeX Table for Mapper Fallback
    latex_table_mapper_fallback = f"""
\\begin{{table}}[h!]
\\centering
\\caption{{Aggregated Action Mapper Performance for Targeted Clicks}}
\\label{{tab:mapper_fallback_agg}}
\\begin{{tabular}}{{|l|c|}}
\\hline
\\textbf{{Mapping Method}} & \\textbf{{Total Count}} \\\\ \\hline
Successful Identifier-Based Mapping & {total_identifier_successes} \\\\ \\hline
Required Coordinate-Based Fallback & {total_coordinate_fallbacks} \\\\ \\hline
\\textbf{{Total Targeted Clicks}} & \\textbf{{{total_targeted_clicks}}} \\\\ \\hline
\\textbf{{Fallback Reliance Rate}} & \\textbf{{{fallback_reliance_rate:.1f}\\%}} \\\\ \\hline
\\end{{tabular}}
\\end{{table}}
"""

    print("--- Table for AI Self-Correction ---")
    print(latex_table_self_correction)
    print("\n" + "--- Table for Mapper Fallback Reliance ---")
    print(latex_table_mapper_fallback)


if __name__ == '__main__':
    # The script assumes it's run from the project root.
    # It will look for the database files inside './output_data/' session directories
    project_root = Path(__file__).resolve().parent
    output_directory = project_root / 'output_data'
    analyze_databases(output_directory)
