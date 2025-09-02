#!/usr/bin/env python3
"""
Script to organize existing output_data files into the new session-based directory structure.
"""

import os
import shutil
from datetime import datetime

def organize_output_data():
    """Organize existing output_data files into session-based directories."""

    output_dir = 'traverser_ai_api/output_data'

    # Define the apps and their data
    apps = [
        'com.ganainy.gymmasterscompose',
        'com.myfitnesspal.android',
        'com.teleClinic.teleClinic',
        'de.deltacity.android.blutspende',
        'de.gesund.app',
        'de.jameda',
        'de.ka.kamedi.heat_it',
        'eu.smartpatient.mytherapy',
        'fr.doctolib.www',
        'shop.shop_apotheke.com.shopapotheke'
    ]

    print("Starting organization of output_data directory...")

    # Create session directories for each app
    for app in apps:
        # Clean app name for filesystem
        clean_app = app.replace('.', '_')
        session_name = f'unknown_device_{clean_app}_30-05-25'  # Using the earliest date as base
        session_path = os.path.join(output_dir, session_name)

        # Create session directory structure
        os.makedirs(os.path.join(session_path, 'screenshots'), exist_ok=True)
        os.makedirs(os.path.join(session_path, 'annotated_screenshots'), exist_ok=True)
        os.makedirs(os.path.join(session_path, 'database'), exist_ok=True)
        os.makedirs(os.path.join(session_path, 'logs'), exist_ok=True)
        os.makedirs(os.path.join(session_path, 'traffic_captures'), exist_ok=True)
        os.makedirs(os.path.join(session_path, 'mobsf_scan_results'), exist_ok=True)
        os.makedirs(os.path.join(session_path, 'extracted_apk'), exist_ok=True)
        os.makedirs(os.path.join(session_path, 'reports'), exist_ok=True)
        os.makedirs(os.path.join(session_path, 'app_info'), exist_ok=True)

        print(f'Created session directory: {session_name}')

    # Move screenshots
    print("\nMoving screenshots...")
    screenshots_dir = os.path.join(output_dir, 'screenshots')
    if os.path.exists(screenshots_dir):
        for item in os.listdir(screenshots_dir):
            if item.startswith('crawl_screenshots_'):
                app_name = item.replace('crawl_screenshots_', '')
                clean_app = app_name.replace('.', '_')
                session_name = f'unknown_device_{clean_app}_30-05-25'
                session_screenshots = os.path.join(output_dir, session_name, 'screenshots')

                src_path = os.path.join(screenshots_dir, item)
                dst_path = os.path.join(session_screenshots, item)

                if os.path.exists(src_path):
                    shutil.move(src_path, dst_path)
                    print(f'Moved: {item} -> {session_name}/screenshots/')

            elif item.startswith('annotated_crawl_screenshots_'):
                app_name = item.replace('annotated_crawl_screenshots_', '')
                clean_app = app_name.replace('.', '_')
                session_name = f'unknown_device_{clean_app}_30-05-25'
                session_annotated = os.path.join(output_dir, session_name, 'annotated_screenshots')

                src_path = os.path.join(screenshots_dir, item)
                dst_path = os.path.join(session_annotated, item)

                if os.path.exists(src_path):
                    shutil.move(src_path, dst_path)
                    print(f'Moved: {item} -> {session_name}/annotated_screenshots/')

    # Move database files
    print("\nMoving database files...")
    db_dir = os.path.join(output_dir, 'database_output')
    if os.path.exists(db_dir):
        for app_dir in os.listdir(db_dir):
            if app_dir in apps:
                clean_app = app_dir.replace('.', '_')
                session_name = f'unknown_device_{clean_app}_30-05-25'
                session_db = os.path.join(output_dir, session_name, 'database')

                src_app_dir = os.path.join(db_dir, app_dir)
                for db_file in os.listdir(src_app_dir):
                    src_path = os.path.join(src_app_dir, db_file)
                    dst_path = os.path.join(session_db, db_file)
                    shutil.move(src_path, dst_path)
                    print(f'Moved: {db_file} -> {session_name}/database/')

    # Move log files
    print("\nMoving log files...")
    logs_dir = os.path.join(output_dir, 'logs')
    if os.path.exists(logs_dir):
        for app_dir in os.listdir(logs_dir):
            if app_dir != 'cli':  # Skip CLI logs
                if app_dir in apps:
                    clean_app = app_dir.replace('.', '_')
                    session_name = f'unknown_device_{clean_app}_30-05-25'
                    session_logs = os.path.join(output_dir, session_name, 'logs')

                    src_app_dir = os.path.join(logs_dir, app_dir)
                    for log_file in os.listdir(src_app_dir):
                        src_path = os.path.join(src_app_dir, log_file)
                        dst_path = os.path.join(session_logs, log_file)
                        shutil.move(src_path, dst_path)
                        print(f'Moved: {log_file} -> {session_name}/logs/')

    # Move traffic captures
    print("\nMoving traffic captures...")
    traffic_dir = os.path.join(output_dir, 'traffic_captures')
    if os.path.exists(traffic_dir):
        for app_dir in os.listdir(traffic_dir):
            if app_dir in apps:
                clean_app = app_dir.replace('.', '_')
                session_name = f'unknown_device_{clean_app}_30-05-25'
                session_traffic = os.path.join(output_dir, session_name, 'traffic_captures')

                src_app_dir = os.path.join(traffic_dir, app_dir)
                for traffic_file in os.listdir(src_app_dir):
                    src_path = os.path.join(src_app_dir, traffic_file)
                    dst_path = os.path.join(session_traffic, traffic_file)
                    shutil.move(src_path, dst_path)
                    print(f'Moved: {traffic_file} -> {session_name}/traffic_captures/')

    # Move extracted APKs
    print("\nMoving extracted APKs...")
    apk_dir = os.path.join(output_dir, 'extracted_apks')
    if os.path.exists(apk_dir):
        for apk_file in os.listdir(apk_dir):
            if apk_file.endswith('.apk'):
                # Extract app name from APK filename
                app_name = apk_file.replace('.apk', '')
                if app_name in apps:
                    clean_app = app_name.replace('.', '_')
                    session_name = f'unknown_device_{clean_app}_30-05-25'
                    session_apk = os.path.join(output_dir, session_name, 'extracted_apk')

                    src_path = os.path.join(apk_dir, apk_file)
                    dst_path = os.path.join(session_apk, apk_file)
                    shutil.move(src_path, dst_path)
                    print(f'Moved: {apk_file} -> {session_name}/extracted_apk/')

    # Move analysis reports
    print("\nMoving analysis reports...")
    for report_dir_name in ['analysis_reports', 'analysis_reports_10-6-25', 'analysis_reports_15-6-25', 'analysis_reports_30-5-25']:
        report_dir = os.path.join(output_dir, report_dir_name)
        if os.path.exists(report_dir):
            for pdf_file in os.listdir(report_dir):
                if pdf_file.endswith('_analysis.pdf'):
                    # Extract app name from PDF filename
                    app_name = pdf_file.replace('_analysis.pdf', '').replace('_run_1', '')
                    if app_name in apps:
                        clean_app = app_name.replace('.', '_')
                        session_name = f'unknown_device_{clean_app}_30-05-25'
                        session_reports = os.path.join(output_dir, session_name, 'reports')

                        src_path = os.path.join(report_dir, pdf_file)
                        dst_path = os.path.join(session_reports, pdf_file)
                        shutil.move(src_path, dst_path)
                        print(f'Moved: {pdf_file} -> {session_name}/reports/')

    # Move MobSF scan results (these are harder to associate with specific apps)
    print("\nMoving MobSF scan results...")
    mobsf_dir = os.path.join(output_dir, 'mobsf_scan_results')
    if os.path.exists(mobsf_dir):
        # For now, move all MobSF files to a general session or keep them in the main directory
        # Since we can't easily associate them with specific apps without more analysis
        print("MobSF files will remain in the main directory for manual organization")

    # Move app info files
    print("\nMoving app info files...")
    app_info_dir = os.path.join(output_dir, 'app_info')
    if os.path.exists(app_info_dir):
        # Move health_apps.json to a general location or keep in main directory
        health_apps_path = os.path.join(app_info_dir, 'health_apps.json')
        if os.path.exists(health_apps_path):
            # Keep this in the main app_info directory as it's shared across apps
            print("health_apps.json kept in main app_info directory")

        # Move device-specific app info files to appropriate sessions
        for info_file in os.listdir(app_info_dir):
            if info_file.endswith('_app_info_health_filtered.json'):
                # This is device-specific, keep in main directory for now
                print(f"Device-specific file {info_file} kept in main app_info directory")

    print("\nOrganization complete!")
    print("Note: Some files (MobSF results, device-specific app info) remain in the main directory")
    print("and may need manual organization based on your specific needs.")

if __name__ == '__main__':
    organize_output_data()
