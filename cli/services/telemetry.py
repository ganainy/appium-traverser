"""
Telemetry service for CLI operations.
"""

import logging
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from cli.constants import keys as KEYS
from cli.constants import messages as MSG


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
            KEYS.KEY_TIMESTAMP: datetime.now().isoformat(),
            KEYS.KEY_TYPE: event_type,
            KEYS.KEY_MESSAGE: message,
            KEYS.KEY_DATA: data or {}
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
        self.log_event(MSG.EVENT_COMMAND_START, MSG.LOG_STARTING_COMMAND.format(command_name=command_name), {KEYS.KEY_ARGS: args})
    
    def log_command_end(self, command_name: str, success: bool, duration: Optional[float] = None) -> None:
        """
        Log command completion.
        
        Args:
            command_name: Name of command
            success: Whether command succeeded
            duration: Command duration in seconds
        """
        data: Dict[str, Any] = {KEYS.KEY_SUCCESS: success}
        if duration is not None:
            data[KEYS.KEY_DURATION_SECONDS] = duration
        
        status = MSG.LOG_COMMAND_COMPLETED_SUCCESSFULLY.format(command_name=command_name) if success else MSG.LOG_COMMAND_FAILED.format(command_name=command_name)
        self.log_event(MSG.EVENT_COMMAND_END, status, data)
    
    def log_error(self, error: Exception, context: Optional[str] = None) -> None:
        """
        Log an error event.
        
        Args:
            error: Exception that occurred
            context: Optional context information
        """
        data = {
            KEYS.KEY_ERROR_TYPE: type(error).__name__,
            KEYS.KEY_ERROR_MESSAGE: str(error)
        }
        if context:
            data[KEYS.KEY_CONTEXT] = context
        
        self.log_event(MSG.EVENT_ERROR, MSG.LOG_ERROR_OCCURRED.format(error=error), data)
    
    def log_service_check(self, service_name: str, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a service check result.
        
        Args:
            service_name: Name of service
            status: Service status ('running', 'stopped', 'error')
            details: Optional service details
        """
        self.log_event(MSG.EVENT_SERVICE_CHECK, MSG.LOG_SERVICE_IS_STATUS.format(service_name=service_name, status=status), details)
    
    def get_session_summary(self) -> Dict[str, Any]:
        """
        Get session summary.
        
        Returns:
            Session summary dictionary
        """
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        command_count = len([e for e in self.events if e[KEYS.KEY_TYPE] == MSG.EVENT_COMMAND_START])
        error_count = len([e for e in self.events if e[KEYS.KEY_TYPE] == MSG.EVENT_ERROR])
        
        return {
            KEYS.KEY_START_TIME: self.start_time.isoformat(),
            KEYS.KEY_END_TIME: end_time.isoformat(),
            KEYS.KEY_DURATION_SECONDS: duration,
            KEYS.KEY_TOTAL_EVENTS: len(self.events),
            KEYS.KEY_COMMANDS_EXECUTED: command_count,
            KEYS.KEY_ERRORS_ENCOUNTERED: error_count,
            KEYS.KEY_SUCCESS_RATE: (command_count - error_count) / max(command_count, 1) * 100
        }
    
    def print_status_table(self, services: Dict[str, Dict[str, Any]]) -> None:
        """
        Print a formatted status table for services.
        
        Args:
            services: Dictionary of service information
        """
        print(f"\n{MSG.ICON_SEARCH} {MSG.UI_SERVICE_STATUS_SUMMARY}:")
        print("=" * 50)
        
        for service_name, service_info in services.items():
            status = service_info.get(KEYS.STATUS_KEY_STATUS, MSG.STATUS_UNKNOWN)
            message = service_info.get(KEYS.STATUS_KEY_MESSAGE, '')
            
            # Choose appropriate icon
            if status == MSG.STATUS_RUNNING:
                icon = MSG.ICON_SUCCESS
            elif status == MSG.STATUS_WARNING:
                icon = MSG.ICON_WARNING
            elif status == MSG.STATUS_ERROR:
                icon = MSG.ICON_ERROR
            else:
                icon = MSG.ICON_QUESTION
            
            print(f"{icon} {service_name}: {message}")
        
        print("=" * 50)
    
    def print_config_table(self, config: Dict[str, Any], filter_key: Optional[str] = None) -> None:
        """
        Print a formatted configuration table.
        
        Args:
            config: Configuration dictionary
            filter_key: Optional key to filter by
        """
        print(f"\n=== {MSG.UI_CURRENT_CONFIGURATION} ===")
        
        for key, value in sorted(config.items()):
            if filter_key and filter_key.lower() not in key.lower():
                continue
            print(f"  {key}: {value}")
        
        print("============================")
    
    def print_success(self, message: str) -> None:
        """
        Print a success message.
        
        Args:
            message: Success message
        """
        print(f"{MSG.ICON_SUCCESS} {message}")
        self.log_event(MSG.EVENT_SUCCESS, message)
    
    def print_warning(self, message: str) -> None:
        """
        Print a warning message.
        
        Args:
            message: Warning message
        """
        print(f"{MSG.ICON_WARNING}  {message}")
        self.log_event(MSG.EVENT_WARNING, message)
    
    def print_error(self, message: str) -> None:
        """
        Print an error message.
        
        Args:
            message: Error message
        """
        print(f"{MSG.ICON_ERROR} {message}")
        self.log_event(MSG.EVENT_ERROR, message)
    
    def print_info(self, message: str) -> None:
        """
        Print an info message.
        
        Args:
            message: Info message
        """
        print(f"{MSG.ICON_INFO}  {message}")
        self.log_event(MSG.EVENT_INFO, message)
    
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
        print(f"\n=== {MSG.UI_CRAWLER_STATUS} ===")
        print(f"  Process: {status.get(KEYS.PROCESS_KEY, MSG.UI_UNKNOWN)}")
        print(f"  State: {status.get(KEYS.STATE_KEY, MSG.UI_UNKNOWN)}")
        print(f"  Target App: {status.get(KEYS.TARGET_APP_KEY, MSG.UI_UNKNOWN)}")
        print(f"  Output Data Dir: {status.get(KEYS.OUTPUT_DIR_KEY, MSG.UI_UNKNOWN)}")
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
            areas: List of focus area dictionaries from get_focus_areas()
        """
        if not areas:
            print(MSG.UI_NO_FOCUS_AREAS_CONFIGURED)
            return
        
        print(f"\n=== {MSG.UI_FOCUS_AREAS} ===")
        for i, area in enumerate(areas):
            # Create display_name from raw data
            display_name = area.get(KEYS.FOCUS_AREA_TITLE) or area.get(KEYS.FOCUS_AREA_NAME) or f"Area {i+1}"
            enabled = area.get(KEYS.FOCUS_AREA_ENABLED, True)
            priority = area.get(KEYS.FOCUS_AREA_PRIORITY, i)
            print(f"{i+1:2d}. {display_name} | enabled={enabled} | priority={priority}")
        print("===================")
    
    def print_model_list(self, models: List[Dict[str, Any]]) -> None:
        """
        Print a formatted list of OpenRouter models.
        
        Args:
            models: List of model dictionaries
        """
        if not models:
            print(MSG.UI_NO_MODELS_AVAILABLE)
            return
        
        print(f"\n=== {MSG.UI_OPENROUTER_MODELS} ({len(models)}) ===")
        for i, model in enumerate(models):
            model_id = model.get(KEYS.MODEL_ID, MSG.UI_UNKNOWN)
            model_name = model.get(KEYS.MODEL_NAME, MSG.UI_UNKNOWN)
            pricing = model.get(KEYS.MODEL_PRICING, {})
           
            # Check if free
            is_free = (pricing.get(KEYS.MODEL_PROMPT_PRICE, "0") == "0" and
                      pricing.get(KEYS.MODEL_COMPLETION_PRICE, "0") == "0")
            
            free_marker = MSG.UI_FREE_MARKER if is_free else ""
            print(f"{i+1:2d}. {model_name} {free_marker}")
            print(f"    ID: {model_id}")
            print(f"    {MSG.UI_PROMPT}: {pricing.get(KEYS.MODEL_PROMPT_PRICE, MSG.UI_NOT_AVAILABLE)} | {MSG.UI_COMPLETION}: {pricing.get(KEYS.MODEL_COMPLETION_PRICE, MSG.UI_NOT_AVAILABLE)}")
            print()
        
        print("==============================")
    
    def print_selected_model(self, selected_model: Optional[Dict[str, Any]]) -> None:
        """
        Print the currently selected OpenRouter model.
        
        Args:
            selected_model: Model dictionary or None if no model is selected
        """
        if selected_model:
            model_id = selected_model.get(KEYS.MODEL_ID, MSG.UI_UNKNOWN)
            model_name = selected_model.get(KEYS.MODEL_NAME, MSG.UI_UNKNOWN)
            print(f"\n=== {MSG.UI_SELECTED_OPENROUTER_MODEL} ===")
            print(f"{MSG.UI_MODEL_NAME}: {model_name}")
            print(f"{MSG.UI_MODEL_ID}: {model_id}")
            print("==============================")
        else:
            print(MSG.UI_NO_OPENROUTER_MODEL_SELECTED)
    
    def print_json(self, data: Dict[str, Any]) -> None:
        """
        Print data as JSON.
        
        Args:
            data: Data to print as JSON
        """
        import json
        print(json.dumps(data, indent=2))
        self.log_event(MSG.EVENT_JSON_OUTPUT, MSG.LOG_OUTPUT_DATA_AS_JSON)
    
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
        self.log_event(MSG.EVENT_SESSION_RESET, MSG.LOG_TELEMETRY_EVENTS_CLEARED)
    
    def print_image_context_configuration(self, data: Dict[str, Any]) -> None:
        """
        Print image context configuration information.
        
        Args:
            data: Dictionary containing image context configuration data
        """
        model_name = data.get("model_name", MSG.UI_UNKNOWN)
        model_identifier = data.get("model_identifier", MSG.UI_UNKNOWN)
        supports_image = data.get(KEYS.KEY_SUPPORTS_IMAGE)
        current_setting = data.get(KEYS.KEY_CURRENT_SETTING)
        enabled = data.get(KEYS.KEY_ENABLED)
        action = data.get(KEYS.KEY_ACTION, "configured")
        
        print(f"\n=== {MSG.UI_OPENROUTER_IMAGE_CONTEXT_CONFIGURATION} ===")
        print(f"{MSG.UI_MODEL}: {model_name} ({model_identifier})")
        print(f"{MSG.UI_IMAGE_SUPPORT}: {MSG.UI_YES if supports_image else MSG.UI_NO}")
        
        if supports_image is True:
            # Model supports images
            if action == "checked":
                print(f"{MSG.UI_CURRENT_IMAGE_CONTEXT_SETTING}: {MSG.UI_ENABLED if current_setting else MSG.UI_DISABLED}")
                print(MSG.UI_THIS_MODEL_SUPPORTS_IMAGE_INPUTS)
            else:
                print(f"{MSG.ICON_SUCCESS} {MSG.UI_IMAGE_CONTEXT_ENABLED_FOR_MODEL} {model_name}" if enabled else f"{MSG.ICON_SUCCESS} {MSG.UI_IMAGE_CONTEXT_DISABLED_FOR_MODEL} {model_name}")
        elif supports_image is False:
            # Model doesn't support images
            if enabled is True:
                print(f"{MSG.ICON_WARNING} {MSG.UI_WARNING_MODEL_NO_IMAGE_SUPPORT}")
            print(f"{MSG.ICON_SUCCESS} {MSG.UI_IMAGE_CONTEXT_DISABLED_MODEL_NO_SUPPORT}")
        else:
            # Unknown capability - using heuristic
            heuristic_supports_image = data.get(KEYS.KEY_HEURISTIC_SUPPORTS_IMAGE, False)
            if action == "checked":
                print(f"{MSG.UI_CURRENT_IMAGE_CONTEXT_SETTING}: {MSG.UI_ENABLED if current_setting else MSG.UI_DISABLED}")
                print(f"{MSG.UI_MODEL_CAPABILITY_UNKNOWN}; {MSG.UI_HEURISTIC_SUGGESTS_SUPPORTS_IMAGES}." if heuristic_supports_image else f"{MSG.UI_MODEL_CAPABILITY_UNKNOWN}; {MSG.UI_HEURISTIC_SUGGESTS_NO_SUPPORT}.")
            else:
                if enabled is True and not heuristic_supports_image:
                    print(f"{MSG.ICON_WARNING} {MSG.UI_MODEL_CAPABILITY_UNKNOWN}; {MSG.UI_HEURISTIC_SUGGESTS_NO_SUPPORT}.")
                print(f"{MSG.ICON_SUCCESS} {MSG.UI_IMAGE_CONTEXT_ENABLED_FOR_MODEL if enabled else MSG.UI_IMAGE_CONTEXT_DISABLED_FOR_MODEL} {MSG.UI_HEURISTIC_BASED}")
    
    def print_model_details(self, data: Dict[str, Any]) -> None:
        """
        Print detailed model information.
        
        Args:
            data: Dictionary containing model details data
        """
        model = data.get(KEYS.KEY_MODEL, {})
        
        # Display detailed information
        print(f"\n=== {MSG.UI_OPENROUTER_MODEL_DETAILS} ===")
        print(f"{MSG.UI_MODEL_ID}: {model.get(KEYS.MODEL_ID, MSG.UI_NOT_AVAILABLE)}")
        print(f"{MSG.UI_MODEL_NAME}: {model.get(KEYS.MODEL_NAME, MSG.UI_NOT_AVAILABLE)}")
        print(f"{MSG.UI_DESCRIPTION}: {model.get(KEYS.MODEL_DESCRIPTION, MSG.UI_NOT_AVAILABLE)}")
        print(f"{MSG.UI_CONTEXT_LENGTH}: {model.get(KEYS.MODEL_CONTEXT_LENGTH, MSG.UI_NOT_AVAILABLE)}")
        
        # Pricing information
        pricing = model.get(KEYS.MODEL_PRICING, {})
        if pricing:
            print(f"\n{MSG.UI_PRICING}:")
            print(f"  {MSG.UI_PROMPT}: {pricing.get(KEYS.MODEL_PROMPT_PRICE, MSG.UI_NOT_AVAILABLE)}")
            print(f"  {MSG.UI_COMPLETION}: {pricing.get(KEYS.MODEL_COMPLETION_PRICE, MSG.UI_NOT_AVAILABLE)}")
            print(f"  {MSG.UI_IMAGE}: {pricing.get(KEYS.MODEL_IMAGE_PRICE, MSG.UI_NOT_AVAILABLE)}")
            
            # Free status
            is_free = data.get(KEYS.KEY_IS_FREE, False)
            print(f"  {MSG.UI_FREE_MODEL}: {MSG.UI_YES if is_free else MSG.UI_NO}")
        else:
            print(f"\n{MSG.UI_PRICING}: {MSG.UI_PRICING_NOT_AVAILABLE}")
        
        # Capabilities
        architecture = model.get(KEYS.MODEL_ARCHITECTURE, {})
        if architecture:
            print(f"\n{MSG.UI_CAPABILITIES}:")
            input_modalities = architecture.get(KEYS.MODEL_INPUT_MODALITIES, [])
            output_modalities = architecture.get(KEYS.MODEL_OUTPUT_MODALITIES, [])
            print(f"  {MSG.UI_INPUT_MODALITIES}: {', '.join(input_modalities) if input_modalities else MSG.UI_NOT_AVAILABLE}")
            print(f"  {MSG.UI_OUTPUT_MODALITIES}: {', '.join(output_modalities) if output_modalities else MSG.UI_NOT_AVAILABLE}")
            
            supports_image = model.get(KEYS.MODEL_SUPPORTS_IMAGE)
            print(f"  {MSG.UI_IMAGE_SUPPORT}: {MSG.UI_YES if supports_image else MSG.UI_NO}")
            
            supported_parameters = architecture.get(KEYS.MODEL_SUPPORTED_PARAMETERS, [])
            if supported_parameters:
                print(f"  {MSG.UI_SUPPORTED_PARAMETERS}: {', '.join(supported_parameters)}")
        
        # Provider information
        top_provider = model.get(KEYS.MODEL_TOP_PROVIDER, {})
        if top_provider:
            print(f"\n{MSG.UI_PROVIDER_INFORMATION}:")
            print(f"  {MSG.UI_PROVIDER_NAME}: {top_provider.get(KEYS.MODEL_PROVIDER_NAME, MSG.UI_NOT_AVAILABLE)}")
            print(f"  {MSG.UI_MODEL_FORMAT}: {top_provider.get(KEYS.MODEL_MODEL_FORMAT, MSG.UI_NOT_AVAILABLE)}")
        
        # Current configuration
        current_image_context = data.get(KEYS.KEY_CURRENT_IMAGE_CONTEXT, False)
        print(f"\n{MSG.UI_CURRENT_CONFIGURATION}:")
        print(f"  {MSG.UI_IMAGE_CONTEXT}: {MSG.UI_ENABLED if current_image_context else MSG.UI_DISABLED}")
        
        print("=================================")
