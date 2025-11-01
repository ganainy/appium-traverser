# Add Focus Area Dialog - UI Implementation

## Overview

The "+ Add Focus Area" button now opens an interactive dialog form that allows users to add new focus areas directly from the UI.

## Implementation Details

### Dialog Form Fields

The `AddFocusAreaDialog` includes the following input fields:

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| **ID** | Text Input | Unique identifier for the focus area | Yes |
| **Name** | Text Input | Display name for the focus area | Yes |
| **Description** | Multi-line Text | Brief description of the focus area | No |
| **Prompt Modifier** | Multi-line Text | AI prompt instructions for this focus area | No |
| **Priority** | Number Input | Order priority (lower = higher priority, default: 999) | No |

### Usage Flow

1. **Click the Button**: User clicks "+ Add Focus Area" in the widget header
2. **Dialog Opens**: `AddFocusAreaDialog` is displayed with input fields
3. **Fill Form**: User enters focus area details
4. **Submit**: User clicks "Ok" button
5. **Validation**: ID and Name fields are required
6. **Add to Database**: Focus area is added via `focus_service.add_focus_area()`
7. **Reload UI**: Widget reloads focus areas from database
8. **Display**: New focus area appears in the list

### Code Architecture

**Files Modified:**
- `traverser_ai_api/ui/focus_areas_widget.py`
  - Added `AddFocusAreaDialog` class (lines 223-303)
  - Added imports: `QDialog`, `QDialogButtonBox`, `QSpinBox`, `QTextEdit`, `QLineEdit`
  - Updated `FocusAreasWidget.__init__()` to accept `focus_service` parameter
  - Added `show_add_dialog()` method to handle button clicks
  - Added `reload_focus_areas()` method to refresh from database

- `traverser_ai_api/ui/components.py`
  - Updated `_create_focus_areas_group()` to pass `focus_service` to widget
  - Added logic to retrieve focus service from main controller

### Connection to Core Components

The dialog is connected to the CRUD service layer:

```python
def show_add_dialog(self):
    """Show dialog to add a new focus area."""
    dialog = AddFocusAreaDialog(self)
    
    if dialog.exec() == QDialog.DialogCode.Accepted:
        data = dialog.get_data()
        
        # Add via service if available
        if self.focus_service:
            success = self.focus_service.add_focus_area(
                id_or_name=data['id'],
                title=data['name'],
                description=data['description'],
                prompt_modifier=data['prompt_modifier'],
                priority=data['priority'],
                enabled=True
            )
            if success:
                self.reload_focus_areas()  # Reload from database
```

### Fallback Behavior

If `focus_service` is not available:
- Dialog still works (local-only)
- Focus area is added to the widget's in-memory list
- No database persistence
- Changes are emitted via `focus_areas_changed` signal

## User Experience

### Visual Design

- Clean, dark-themed dialog matching the overall UI
- Clear labels for each field
- Helpful placeholder text and tooltips
- Field validation on form submission
- Standard Ok/Cancel buttons

### Input Validation

- **ID**: Required, must not be empty
- **Name**: Required, must not be empty
- **Description**: Optional
- **Prompt Modifier**: Optional, uses sensible default instructions
- **Priority**: Optional, defaults to 999 (low priority)

### Error Handling

- Missing required fields: Shows warning log
- Service errors: Logged and handled gracefully
- Reload failures: User notified via logging

## Examples

### Example 1: Privacy Policy Focus Area

```
ID: privacy_policy
Name: Privacy Policy
Description: Check privacy policies and terms of service
Prompt Modifier: **PRIVACY FOCUS: Policy Documents** - Actively seek out and thoroughly explore privacy policies, terms of service, data processing agreements, and any legal documents.
Priority: 0
```

### Example 2: Permissions Focus Area

```
ID: permissions
Name: App Permissions
Description: Focus on permission requests and privacy settings
Prompt Modifier: **PRIVACY FOCUS: Permissions** - Pay special attention to permission requests (location, camera, microphone, contacts, storage, phone).
Priority: 1
```

## Integration with Core Services

The dialog leverages the existing `FocusAreaService` from the core layer:

```python
# From traverser_ai_api/cli/services/focus_area_service.py
def add_focus_area(
    self,
    id_or_name: str,
    title: str = "",
    description: str = "",
    priority: int = 999,
    enabled: bool = True
) -> bool:
    """Add a new focus area."""
    # Creates focus area in database
```

## Testing Checklist

- [ ] Dialog opens when clicking "+ Add Focus Area"
- [ ] All fields are editable and accept input
- [ ] Cancel button closes dialog without saving
- [ ] Ok button validates required fields
- [ ] Missing ID or Name shows warning
- [ ] Valid submission adds focus area to database
- [ ] New focus area appears in the widget list after submission
- [ ] Multiple focus areas can be added in sequence
- [ ] Focus areas persist after reloading the application
- [ ] Dialog works with and without focus_service

## Future Enhancements

1. **Field Validation UI**: Show inline error messages for invalid fields
2. **Template Suggestions**: Dropdown with predefined prompt modifiers
3. **Bulk Import**: Add button to import multiple focus areas from JSON
4. **Edit Dialog**: Allow editing existing focus areas
5. **Delete Confirmation**: Confirm before deleting focus areas
6. **Drag-to-Reorder Edit**: More intuitive priority management
