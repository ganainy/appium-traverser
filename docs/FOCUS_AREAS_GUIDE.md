# Focus Areas Guide

## Overview

Focus areas allow the AI agent to concentrate on specific privacy-related aspects during app exploration. **Focus areas are no longer hardcoded** - they must be explicitly created by users through either the CLI or the UI.

## Starting with Empty Focus Areas

When you first start the application:
- The UI will show an empty focus areas panel with a message: "No focus areas added yet. Click '+ Add Focus Area' to get started."
- The database starts with no default focus areas
- Users must add focus areas before they can be used during crawling

## Adding Focus Areas

### Via CLI

Use the `focus add` command to create new focus areas:

```bash
# Add a basic focus area
python -m traverser_ai_api focus add "Privacy Policy"

# Add with description
python -m traverser_ai_api focus add "Permissions" --description "Check app permission requests"

# Add with priority (lower number = higher priority)
python -m traverser_ai_api focus add "Data Collection" --priority 1

# Add with disabled state
python -m traverser_ai_api focus add "Network Traffic" --priority 2 --disabled
```

### Via UI

1. Open the Traverser UI
2. Navigate to "AI Privacy Focus Areas" section
3. Click the "+ Add Focus Area" button
4. A form will appear (note: currently requires CLI as UI form is TBD)
5. Fill in the required fields and save

**Note:** Full UI form for adding focus areas is to be implemented.

## Managing Focus Areas

### List Focus Areas

```bash
# List all configured focus areas
python -m traverser_ai_api focus list
```

Output:
```
=== Focus Areas ===
 1. Privacy Policy | enabled=True | priority=0
 2. Permissions | enabled=True | priority=1
 3. Data Collection | enabled=True | priority=2
===================
```

### Edit Focus Areas

```bash
# Edit by position (1-based indexing)
python -m traverser_ai_api focus edit 1 --title "Privacy Policies & Terms"

# Edit by name
python -m traverser_ai_api focus edit "Privacy Policy" --description "Check privacy policies and terms"

# Update priority
python -m traverser_ai_api focus edit 1 --priority 10

# Enable/disable
python -m traverser_ai_api focus edit 1 --enabled
python -m traverser_ai_api focus edit 2 --disabled
```

### Remove Focus Areas

```bash
# Remove by position
python -m traverser_ai_api focus remove 1

# Remove by name
python -m traverser_ai_api focus remove "Privacy Policy"
```

## Import/Export Focus Areas

### Export to JSON

```bash
# Export all focus areas to a JSON file
python -m traverser_ai_api focus export focus_areas_backup.json
```

### Import from JSON

```bash
# Import focus areas from a JSON file
python -m traverser_ai_api focus import focus_areas_backup.json
```

### JSON Format

Focus areas are stored in JSON format:

```json
[
  {
    "id": "privacy_policy",
    "title": "Privacy Policies & Terms",
    "description": "Prioritize exploring privacy policies and terms of service",
    "prompt_modifier": "**PRIVACY FOCUS: Policy Documents** - Actively seek out and thoroughly explore privacy policies...",
    "enabled": true,
    "priority": 0
  },
  {
    "id": "permissions",
    "title": "App Permissions",
    "description": "Focus on permission requests and privacy settings",
    "prompt_modifier": "**PRIVACY FOCUS: Permissions** - Pay special attention to permission requests...",
    "enabled": true,
    "priority": 1
  }
]
```

## Focus Area Structure

Each focus area contains:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier for the focus area |
| `title` | string | Display name of the focus area |
| `description` | string | Brief description of what this focus area covers |
| `prompt_modifier` | string | AI prompt instructions for this focus area |
| `enabled` | boolean | Whether this focus area is active (default: true) |
| `priority` | integer | Order priority (0-based, lower = higher priority) |

## Using Focus Areas in Crawling

Once focus areas are configured:

1. **Enable/Disable**: Use checkboxes in the UI or CLI to control which areas are active
2. **Reorder**: Drag items in the UI to change priority, or use CLI to update priority values
3. **Crawl**: When starting a crawl, the AI agent will be influenced by the enabled focus areas

## Workflow Example

```bash
# 1. Add focus areas
python -m traverser_ai_api focus add "Privacy Policy" --priority 0
python -m traverser_ai_api focus add "Permissions" --priority 1
python -m traverser_ai_api focus add "Data Collection" --priority 2

# 2. List to verify
python -m traverser_ai_api focus list

# 3. Export as backup
python -m traverser_ai_api focus export my_focus_areas.json

# 4. Adjust as needed
python -m traverser_ai_api focus edit 1 --description "Updated description"

# 5. Use in crawling
# Launch UI or CLI crawler with these focus areas enabled
```

## Common Patterns

### Privacy-Focused Analysis

```bash
python -m traverser_ai_api focus add "Privacy Policy"
python -m traverser_ai_api focus add "Data Collection Forms"
python -m traverser_ai_api focus add "Third-Party Integrations"
python -m traverser_ai_api focus add "Permissions"
python -m traverser_ai_api focus add "Account & Profile Privacy"
```

### Security Analysis

```bash
python -m traverser_ai_api focus add "Authentication"
python -m traverser_ai_api focus add "Encryption"
python -m traverser_ai_api focus add "Security Settings"
python -m traverser_ai_api focus add "Credential Handling"
```

### Compliance Checking

```bash
python -m traverser_ai_api focus add "GDPR Compliance"
python -m traverser_ai_api focus add "CCPA Compliance"
python -m traverser_ai_api focus add "Data Subject Rights"
python -m traverser_ai_api focus add "Consent Management"
```

## Tips & Best Practices

1. **Start Small**: Begin with 2-3 focus areas and expand based on needs
2. **Clear Descriptions**: Use descriptive titles and descriptions for clarity
3. **Priority Order**: Arrange focus areas by importance using priority values
4. **Export Regularly**: Backup your focus areas configuration with export
5. **Reuse Templates**: Export successful configurations for reuse with different apps
6. **Test Before Use**: Verify focus areas are working as expected before running long crawls

## Troubleshooting

### No Focus Areas Showing

- Check if any focus areas have been added: `python -m traverser_ai_api focus list`
- Add focus areas using the CLI commands
- Refresh the UI if changes aren't reflected

### Changes Not Saved

- Ensure you're using the same database file
- Check database connectivity: `python -m traverser_ai_api focus list`
- Export before making batch changes as a safety precaution

### Import Failing

- Verify JSON file format is correct
- Check file permissions and path
- Ensure JSON follows the expected schema
