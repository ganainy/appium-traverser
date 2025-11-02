"""
UI Element Annotator (Offline Only)

Offline annotator that overlays bounding boxes for actions recorded in the crawl database
onto the corresponding screenshots. No AI requests are performed.

It reads target_bounding_box from mapped_action_json (preferred) or ai_suggestion_json
in steps_log, resolves the screenshot for from/to screen_id, draws rectangles, and writes
annotated images plus an index.html gallery in the output directory.

Usage examples:
  python -m tools.ui_element_annotator --db-path "path/to/_crawl_data.db"
  python -m tools.ui_element_annotator --db-path "path/to/_crawl_data.db" --screens-dir ".../screenshots" --out-dir ".../annotated_screenshots"
  python -m tools.ui_element_annotator --run-id 12  # uses latest session DB via config if no db-path
"""

import os
import sys
import json
import argparse
from typing import Optional, Dict, Any, Tuple

# Ensure project root is on sys.path for absolute imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from config.config import Config
    from infrastructure.database import DatabaseManager
    from utils.utils import draw_rectangle_on_image
except Exception:
    from config.config import Config
    from infrastructure.database import DatabaseManager
    from utils.utils import draw_rectangle_on_image


def is_normalized_bbox(bbox: Dict[str, Any]) -> bool:
    try:
        y1, x1 = bbox["top_left"]
        y2, x2 = bbox["bottom_right"]
        return all(0.0 <= v <= 1.0 for v in [y1, x1, y2, x2])
    except Exception:
        return False


def clamp(val: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, val))


def bbox_to_pixels(bbox: Dict[str, Any], img_w: int, img_h: int) -> Optional[Tuple[int, int, int, int]]:
    """
    Convert standardized bbox dict {top_left:[y1,x1], bottom_right:[y2,x2]} to pixel coords.
    Handles normalized (0..1) and absolute pixels. Returns (x1,y1,x2,y2) or None if invalid.
    """
    try:
        y1, x1 = bbox["top_left"]
        y2, x2 = bbox["bottom_right"]

        if is_normalized_bbox(bbox):
            px_x1 = int(round(x1 * img_w))
            px_y1 = int(round(y1 * img_h))
            px_x2 = int(round(x2 * img_w))
            px_y2 = int(round(y2 * img_h))
        else:
            px_x1 = int(round(x1))
            px_y1 = int(round(y1))
            px_x2 = int(round(x2))
            px_y2 = int(round(y2))

        # Clamp to image bounds
        px_x1 = clamp(px_x1, 0, img_w - 1)
        px_y1 = clamp(px_y1, 0, img_h - 1)
        px_x2 = clamp(px_x2, 0, img_w - 1)
        px_y2 = clamp(px_y2, 0, img_h - 1)

        # Ensure proper ordering
        x1_final = min(px_x1, px_x2)
        y1_final = min(px_y1, px_y2)
        x2_final = max(px_x1, px_x2)
        y2_final = max(px_y1, px_y2)

        if x1_final == x2_final or y1_final == y2_final:
            return None

        return (x1_final, y1_final, x2_final, y2_final)
    except Exception:
        return None


def read_file_bytes(path: str) -> Optional[bytes]:
    try:
        with open(path, 'rb') as f:
            return f.read()
    except Exception:
        return None


def save_bytes(path: str, data: bytes) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data)
        return True
    except Exception:
        return False


def generate_index_html(dir_path: str):
    """Generate a simple index.html to browse annotated images."""
    try:
        files = sorted([f for f in os.listdir(dir_path) if f.lower().endswith('.png')])
        html = [
            "<!DOCTYPE html>",
            "<html><head><meta charset='utf-8'><title>Annotated Screenshots</title>",
            "<style>body{font-family:Arial,sans-serif} .grid{display:flex;flex-wrap:wrap;gap:12px} .item{width:48%} img{max-width:100%;height:auto;border:1px solid #ccc}</style>",
            "</head><body>",
            f"<h1>Annotated Screenshots ({len(files)})</h1>",
            "<div class='grid'>"
        ]
        for f in files:
            html.append(f"<div class='item'><h3>{f}</h3><img src='{f}' alt='{f}' loading='lazy'/></div>")
        html += ["</div>", "</body></html>"]
        with open(os.path.join(dir_path, 'index.html'), 'w', encoding='utf-8') as fh:
            fh.write("\n".join(html))
    except Exception:
        pass


def select_latest_run(dm: DatabaseManager) -> Optional[int]:
    try:
        rows = dm.execute_query("SELECT run_id, status, start_time FROM runs ORDER BY start_time DESC LIMIT 1")
        if rows:
            return int(rows[0][0])
        return None
    except Exception:
        return None


def select_latest_run_from_steps(dm: DatabaseManager) -> Optional[int]:
    """Fallback: derive latest run_id from steps_log if runs table is empty."""
    try:
        rows = dm.execute_query("SELECT DISTINCT run_id FROM steps_log ORDER BY run_id DESC LIMIT 1")
        if rows:
            val = rows[0][0] if isinstance(rows[0], (tuple, list)) else rows[0]
            return int(val)
        return None
    except Exception:
        return None


def find_latest_existing_session(cfg: Config) -> Optional[Tuple[str, str]]:
    """Find the latest session directory for the current APP_PACKAGE with an existing DB file."""
    base = getattr(cfg, 'OUTPUT_DATA_DIR', None) or 'output_data'
    app_pkg = getattr(cfg, 'APP_PACKAGE', None)
    if not os.path.isdir(base) or not app_pkg:
        return None
    candidates = []
    try:
        for name in os.listdir(base):
            path = os.path.join(base, name)
            if not os.path.isdir(path):
                continue
            if app_pkg in name:
                db_dir = os.path.join(path, 'database')
                if os.path.isdir(db_dir):
                    for f in os.listdir(db_dir):
                        if f.endswith('_crawl_data.db'):
                            db_path = os.path.join(db_dir, f)
                            try:
                                mtime = os.path.getmtime(db_path)
                            except Exception:
                                mtime = 0
                            candidates.append((mtime, path, db_path))
    except Exception:
        return None
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, session_dir, db_path = candidates[0]
    return session_dir, db_path


def main():
    parser = argparse.ArgumentParser(description="Offline UI element annotator: overlays bounding boxes from DB onto screenshots.")
    parser.add_argument("--run-id", type=int, default=None, help="Run ID to annotate. If omitted, latest run is used.")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of steps processed (0 = no limit).")
    parser.add_argument("--color", type=str, default="red", help="Primary rectangle color for bounding boxes.")
    parser.add_argument("--border-color", type=str, default="black", help="Border color for rectangles.")
    parser.add_argument("--line-thickness", type=int, default=3, help="Rectangle line thickness.")
    parser.add_argument("--border-size", type=int, default=1, help="Border size around rectangle.")
    parser.add_argument("--db-path", type=str, default=None, help="Explicit path to SQLite DB to use.")
    parser.add_argument("--screens-dir", type=str, default=None, help="Directory containing raw screenshots.")
    parser.add_argument("--out-dir", type=str, default=None, help="Directory to write annotated screenshots.")
    args = parser.parse_args()

    # Instantiate Config similar to main.py behavior
    defaults_module_path = os.path.join(PROJECT_ROOT, 'traverser_ai_api', 'config.py')
    user_config_json_path = os.path.join(PROJECT_ROOT, 'traverser_ai_api', 'user_config.json')
    cfg = Config(defaults_module_path=defaults_module_path, user_config_json_path=user_config_json_path)

    # Prefer using the latest existing session DB rather than a fresh session
    latest = None
    if not args.db_path:
        latest = find_latest_existing_session(cfg)
    if args.db_path or latest:
        if args.db_path:
            db_path = os.path.abspath(args.db_path)
            session_dir = os.path.dirname(os.path.dirname(db_path))
        else:
            session_dir, db_path = latest
        cfg.SESSION_DIR = session_dir
        cfg.DB_NAME = db_path
        cfg.SCREENSHOTS_DIR = args.screens_dir or os.path.join(session_dir, 'screenshots')
        cfg.ANNOTATED_SCREENSHOTS_DIR = args.out_dir or os.path.join(session_dir, 'annotated_screenshots')
    elif args.screens_dir or args.out_dir:
        if args.screens_dir:
            cfg.SCREENSHOTS_DIR = os.path.abspath(args.screens_dir)
        if args.out_dir:
            cfg.ANNOTATED_SCREENSHOTS_DIR = os.path.abspath(args.out_dir)

    dm = DatabaseManager(cfg)
    dm.connect()

    run_id = args.run_id or select_latest_run(dm) or select_latest_run_from_steps(dm)

    if run_id is not None:
        steps = dm.get_steps_for_run(run_id)
        if not steps:
            print(f"Run {run_id} has 0 steps in steps_log. Nothing to annotate.")
            print(f"DB: {cfg.DB_NAME}")
            return 1
    else:
        # Fallback: annotate across all steps in DB
        try:
            steps = dm._execute_sql("SELECT * FROM steps_log ORDER BY step_log_id ASC", fetch_all=True, commit=False) or []
        except Exception:
            steps = []
        if not steps:
            print("No steps found in database. Nothing to annotate.")
            print(f"DB: {cfg.DB_NAME}")
            return 1

    os.makedirs(cfg.ANNOTATED_SCREENSHOTS_DIR, exist_ok=True)

    processed = 0
    skipped = 0

    from PIL import Image  # local import to avoid heavy import if unused

    for step in steps:
        if args.limit and processed >= args.limit:
            break

        try:
            step_log_id = step[0]
            from_screen_id = step[3]
            to_screen_id = step[4]
            ai_json_str = step[6]
            mapped_json_str = step[7]
        except Exception:
            skipped += 1
            continue

        screen_id = from_screen_id or to_screen_id

        bbox: Optional[Dict[str, Any]] = None
        action_type: Optional[str] = None

        def extract_bbox(js: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
            if not js:
                return None, None
            try:
                data = json.loads(js)
                bb = data.get("target_bounding_box")
                at = data.get("action_type")
                if isinstance(bb, dict) and "top_left" in bb and "bottom_right" in bb:
                    return bb, at
            except Exception:
                return None, None
            return None, None

        bbox, action_type = extract_bbox(mapped_json_str)
        if bbox is None:
            bbox, action_type = extract_bbox(ai_json_str)

        if bbox is None:
            skipped += 1
            continue

        screenshot_path: Optional[str] = None
        if screen_id:
            try:
                screen_row = dm.get_screen_by_id(screen_id)
                if screen_row and isinstance(screen_row, (tuple, list)):
                    screenshot_path = screen_row[4] if len(screen_row) >= 5 else None
            except Exception:
                screenshot_path = None

        if not screenshot_path or not os.path.isfile(screenshot_path):
            skipped += 1
            continue

        img_bytes = read_file_bytes(screenshot_path)
        if not img_bytes:
            skipped += 1
            continue

        try:
            with Image.open(screenshot_path) as im:
                img_w, img_h = im.size
        except Exception:
            skipped += 1
            continue

        px_box = bbox_to_pixels(bbox, img_w, img_h)
        if not px_box:
            skipped += 1
            continue

        out_bytes = draw_rectangle_on_image(
            img_bytes,
            px_box,
            primary_color=args.color,
            border_color=args.border_color,
            line_thickness=args.line_thickness,
            border_size=args.border_size,
        )

        if not out_bytes:
            skipped += 1
            continue

        base_name = os.path.basename(screenshot_path)
        name_root, _ = os.path.splitext(base_name)
        action_suffix = action_type or "action"
        out_name = f"annotated_{name_root}_step{step_log_id}_{action_suffix}.png"
        out_path = os.path.join(cfg.ANNOTATED_SCREENSHOTS_DIR, out_name)

        if save_bytes(out_path, out_bytes):
            processed += 1
        else:
            skipped += 1

    generate_index_html(cfg.ANNOTATED_SCREENSHOTS_DIR)

    print(f"Annotated images saved: {processed}, skipped: {skipped}")
    print(f"Output directory: {cfg.ANNOTATED_SCREENSHOTS_DIR}")
    return 0 if processed > 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
