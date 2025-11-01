import os
import json
import shutil
from typing import Dict, Any, List
from typing import Optional
from traverser_ai_api.infrastructure.user_config_store import UserConfigStore

SECRETS_SUFFIXES = ("_API_KEY", "_TOKEN", "_SECRET")


def is_secret_key(key: str) -> bool:
    return any(key.lower().endswith(suf.lower()) for suf in SECRETS_SUFFIXES)


def migrate_user_config_json_to_sqlite(store: UserConfigStore, json_path: Optional[str] = None) -> Dict[str, Any]:
    result = {
        'migrated_count': 0,
        'skipped_secrets': [],
        'backup_path': None,
        'errors': []
    }
    if json_path is None:
        json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../user_config.json'))
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"user_config.json not found at {json_path}")
    backup_path = json_path + '.bak'
    shutil.copy2(json_path, backup_path)
    result['backup_path'] = backup_path
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        result['errors'].append(str(e))
        return result
    for key, value in data.items():
        if is_secret_key(key):
            result['skipped_secrets'].append(key)
            continue
        if key == 'focus_areas' and isinstance(value, list):
            for area in value:
                try:
                    store.add_focus_area(area)
                except Exception as e:
                    result['errors'].append(f"focus_area {area}: {e}")
            continue
        try:
            store.set(key, value)
            result['migrated_count'] += 1
        except Exception as e:
            result['errors'].append(f"{key}: {e}")
    return result


def main():
    store = UserConfigStore()
    try:
        result = migrate_user_config_json_to_sqlite(store)
        print("Migration complete.")
        print(f"Migrated: {result['migrated_count']} settings.")
        print(f"Skipped secrets: {result['skipped_secrets']}")
        print(f"Backup created at: {result['backup_path']}")
        if result['errors']:
            print("Errors:")
            for err in result['errors']:
                print(f"  - {err}")
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    main()
