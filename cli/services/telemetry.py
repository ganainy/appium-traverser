"""
Telemetry service for CLI operations.
"""

import logging
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional


class TelemetryService:
    """Service for managing telemetry and status reporting."""
    
    def __init__(self):
        """Initialize telemetry service."""
        self.start_time = datetime.now()
        self.events: List[Dict[str, Any]] = []
    
    def log_event(self, event_type: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a telemetry event.
        
        Args:
            event_type: Type of event
            message: Event message
            data: Optional event data
        """
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'message': message,
            'data': data or {}
        }
        self.events.append(event)
        
        # Also log to standard logging
        logging.info(f"[{event_type.upper()}] {message}")
    
    def log_command_start(self, command_name: str, args: Dict[str, Any]) -> None:
        """
        Log command start.
        
        Args:
            command_name: Name of command
            args: Command arguments
        """
        self.log_event('command_start', f"Starting command: {command_name}", {'args': args})
    
    def log_command_end(self, command_name: str, success: bool, duration: Optional[float] = None) -> None:
        """
        Log command completion.
        
        Args:
            command_name: Name of command
            success: Whether command succeeded
            duration: Command duration in seconds
        """
        data: Dict[str, Any] = {'success': success}
        if duration is not None:
            data['duration_seconds'] = duration
        
        status = "completed successfully" if success else "failed"
        self.log_event('command_end', f"Command {command_name} {status}", data)
    
    def log_error(self, error: Exception, context: Optional[str] = None) -> None:
        """
        Log an error event.
        
        Args:
            error: Exception that occurred
            context: Optional context information
        """
        data = {
            'error_type': type(error).__name__,
            'error_message': str(error)
        }
        if context:
            data['context'] = context
        
        self.log_event('error', f"Error occurred: {error}", data)
    
    def log_service_check(self, service_name: str, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a service check result.
        
        Args:
            service_name: Name of service
            status: Service status ('running', 'stopped', 'error')
            details: Optional service details
        """
        self.log_event('service_check', f"Service {service_name} is {status}", details)
    
    def get_session_summary(self) -> Dict[str, Any]:
        """
        Get session summary.
        
        Returns:
            Session summary dictionary
        """
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        command_count = len([e for e in self.events if e['type'] == 'command_start'])
        error_count = len([e for e in self.events if e['type'] == 'error'])
        
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration,
            'total_events': len(self.events),
            'commands_executed': command_count,
            'errors_encountered': error_count,
            'success_rate': (command_count - error_count) / max(command_count, 1) * 100
        }
    
    def print_status_table(self, services: Dict[str, Dict[str, Any]]) -> None:
        """
        Print a formatted status table for services.
        
        Args:
            services: Dictionary of service information
        """
        print("\n🔍 Service Status Summary:")
        print("=" * 50)
        
        for service_name, service_info in services.items():
            status = service_info.get('status', 'unknown')
            message = service_info.get('message', '')
            
            # Choose appropriate icon
            if status == 'running':
                icon = "✅"
            elif status == 'warning':
                icon = "⚠️"
            elif status == 'error':
                icon = "❌"
            else:
                icon = "❓"
            
            print(f"{icon} {service_name}: {message}")
        
        print("=" * 50)
    
    def print_config_table(self, config: Dict[str, Any], filter_key: Optional[str] = None) -> None:
        """
        Print a formatted configuration table.
        
        Args:
            config: Configuration dictionary
            filter_key: Optional key to filter by
        """
        print("\n=== Current Configuration ===")
        
        for key, value in sorted(config.items()):
            if filter_key and filter_key.lower() not in key.lower():
                continue
            print(f"  {key}: {value}")
        
        print("============================")
    
    def print_list_table(self, items: List[Dict[str, Any]], title: str, key_mapping: Optional[Dict[str, str]] = None) -> None:
        """
        Print a formatted list table.
        
        Args:
            items: List of items to display
            title: Table title
            key_mapping: Optional mapping of internal keys to display names
        """
        if not items:
            print(f"\n=== {title} ===")
            print("No items found.")
            print("=" * (len(title) + 10))
            return
        
        print(f"\n=== {title} ({len(items)}) ===")
        
        key_mapping = key_mapping or {}
        
        for i, item in enumerate(items, 1):
            print(f"{i:2d}. ", end="")
            
            # Display item based on key mapping or default keys
            if 'name' in item:
                print(item['name'])
            elif 'title' in item:
                print(item['title'])
            elif 'app_name' in item:
                print(f"App: {item['app_name']}")
                if 'package_name' in item:
                    print(f"     Pkg: {item['package_name']}")
                if 'activity_name' in item:
                    print(f"     Act: {item['activity_name']}")
            else:
                # Default to showing first few key-value pairs
                first_items = list(item.items())[:3]
                details = ", ".join([f"{k}: {v}" for k, v in first_items])
                print(details)
        
        print("=" * (len(title) + 10))
    
    def print_success(self, message: str) -> None:
        """
        Print a success message.
        
        Args:
            message: Success message
        """
        print(f"✅ {message}")
        self.log_event('success', message)
    
    def print_warning(self, message: str) -> None:
        """
        Print a warning message.
        
        Args:
            message: Warning message
        """
        print(f"⚠️  {message}")
        self.log_event('warning', message)
    
    def print_error(self, message: str) -> None:
        """
        Print an error message.
        
        Args:
            message: Error message
        """
        print(f"❌ {message}")
        self.log_event('error', message)
    
    def print_info(self, message: str) -> None:
        """
        Print an info message.
        
        Args:
            message: Info message
        """
        print(f"ℹ️  {message}")
        self.log_event('info', message)
    
    def get_recent_events(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent events.
        
        Args:
            count: Number of recent events to return
            
        Returns:
            List of recent events
        """
        return self.events[-count:] if self.events else []
    
    def print_crawler_status(self, status: Dict[str, Any]) -> None:
        """
        Print formatted crawler status.
        
        Args:
            status: Status dictionary from crawler service
        """
        print("\n=== Crawler Status ===")
        print(f"  Process: {status.get('process', 'Unknown')}")
        print(f"  State: {status.get('state', 'Unknown')}")
        print(f"  Target App: {status.get('target_app', 'Unknown')}")
        print(f"  Output Data Dir: {status.get('output_dir', 'Unknown')}")
        print("=======================")
    
    def print_device_list(self, devices: List[str]) -> None:
        """
        Print a formatted list of connected devices.
        
        Args:
            devices: List of device identifiers
        """
        from cli.constants import messages as MSG
        
        if not devices:
            print(MSG.NO_CONNECTED_DEVICES_FOUND)
            return
        
        print(MSG.CONNECTED_DEVICES_HEADER)
        for i, device in enumerate(devices):
            print(MSG.CONNECTED_DEVICE_ITEM.format(index=i+1, device=device))
        print(MSG.CONNECTED_DEVICES_FOOTER)
    
    def print_focus_areas(self, areas: List[dict]) -> None:
        """
        Print a formatted list of focus areas.
        
        Args:
            areas: List of focus area dictionaries with consistent properties
        """
        if not areas:
            print("No focus areas configured.")
            return
        
        print("\n=== Focus Areas ===")
        for i, area in enumerate(areas):
            name = area.get("display_name", f"Area {i+1}")
            enabled = area.get("enabled", True)
            priority = area.get("priority", i)
            print(f"{i+1:2d}. {name} | enabled={enabled} | priority={priority}")
        print("===================")
    
    def print_model_list(self, models: List[Dict[str, Any]]) -> None:
        """
        Print a formatted list of OpenRouter models.
        
        Args:
            models: List of model dictionaries
        """
        if not models:
            print("No models available.")
            return
        
        print(f"\n=== OpenRouter Models ({len(models)}) ===")
        for i, model in enumerate(models):
            model_id = model.get("id", "Unknown")
            model_name = model.get("name", "Unknown")
            pricing = model.get("pricing", {})
            
            # Check if free
            is_free = (pricing.get("prompt", "0") == "0" and
                      pricing.get("completion", "0") == "0")
            
            free_marker = "[FREE]" if is_free else ""
            print(f"{i+1:2d}. {model_name} {free_marker}")
            print(f"    ID: {model_id}")
            print(f"    Prompt: {pricing.get('prompt', 'N/A')} | Completion: {pricing.get('completion', 'N/A')}")
            print()
        
        print("==============================")
    
    def print_selected_model(self, selected_model: Optional[Dict[str, Any]]) -> None:
        """
        Print the currently selected OpenRouter model.
        
        Args:
            selected_model: Model dictionary or None if no model is selected
        """
        if selected_model:
            model_id = selected_model.get("id", "Unknown")
            model_name = selected_model.get("name", "Unknown")
            print(f"\n=== Selected OpenRouter Model ===")
            print(f"Name: {model_name}")
            print(f"ID: {model_id}")
            print("==============================")
        else:
            print("No OpenRouter model selected.")
    
    def print_json(self, data: Dict[str, Any]) -> None:
        """
        Print data as JSON.
        
        Args:
            data: Data to print as JSON
        """
        import json
        print(json.dumps(data, indent=2))
        self.log_event('json_output', "Output data as JSON")
    
    def print_package_list(self, packages: List[str]) -> None:
        """
        Print a formatted list of packages.
        
        Args:
            packages: List of package names
        """
        from cli.constants import messages as MSG
        
        if not packages:
            self.print_info(MSG.LIST_PACKAGES_NO_PKGS)
        else:
            self.print_info(MSG.LIST_PACKAGES_HEADER.format(count=len(packages)))
            for i, pkg in enumerate(packages, 1):
                self.print_info(MSG.LIST_PACKAGES_ITEM.format(index=i, package=pkg))
        
        def confirm_action(self, prompt_message: str) -> bool:
            """
            Prompt user for confirmation with a yes/no question.
            
            Args:
                prompt_message: Message to display to the user
                
            Returns:
                True if user confirms (yes/y), False if user cancels
            """
            from cli.constants import keys as KEYS
            from cli.constants import messages as MSG
            
            self.print_warning(prompt_message)
            response = input(MSG.CLEAR_PACKAGES_PROMPT).strip().lower()
            if response not in (KEYS.INPUT_YES, KEYS.INPUT_Y):
                self.print_info(MSG.CLEAR_PACKAGES_CANCELLED)
                return False
            return True
        
        def clear_events(self) -> None:
            """Clear all events."""
            self.events.clear()
            self.log_event('session_reset', "Telemetry events cleared")
