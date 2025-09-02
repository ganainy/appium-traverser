#!/usr/bin/env python3
"""
Script to clean up empty directories after organizing output_data.
"""

import os
import shutil

def cleanup_empty_dirs():
    """Remove empty directories from the old structure."""

    output_dir = 'traverser_ai_api/output_data'

    # Directories to check and potentially remove
    dirs_to_check = [
        'analysis_reports',
        'analysis_reports_10-6-25',
        'analysis_reports_15-6-25',
        'analysis_reports_30-5-25',
        'database_output',
        'extracted_apks',
        'logs',
        'screenshots',
        'traffic_captures'
    ]

    print("Cleaning up empty directories...")

    for dir_name in dirs_to_check:
        dir_path = os.path.join(output_dir, dir_name)
        if os.path.exists(dir_path):
            try:
                # Check if directory is empty or contains only empty subdirectories
                if is_empty_or_only_empty_dirs(dir_path):
                    shutil.rmtree(dir_path)
                    print(f"Removed empty directory: {dir_name}")
                else:
                    print(f"Directory {dir_name} is not empty, keeping it")
            except Exception as e:
                print(f"Error removing {dir_name}: {e}")

def is_empty_or_only_empty_dirs(path):
    """Check if a directory is empty or contains only empty subdirectories."""
    if not os.path.exists(path):
        return True

    if os.path.isfile(path):
        return False

    try:
        contents = os.listdir(path)
        if not contents:
            return True

        for item in contents:
            item_path = os.path.join(path, item)
            if os.path.isfile(item_path):
                return False
            elif os.path.isdir(item_path):
                if not is_empty_or_only_empty_dirs(item_path):
                    return False
        return True
    except PermissionError:
        return False

if __name__ == '__main__':
    cleanup_empty_dirs()
