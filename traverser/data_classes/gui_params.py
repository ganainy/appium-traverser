class GuiParams:
    def __init__(self,max_retries,expected_package,expected_start_activity,expected_target_device,global_project_name,global_project_version, stop_execution_flag, synthetic_delay_amount,similarity_threshold):
        self.max_retries = max_retries
        self.expected_package = expected_package
        self.expected_start_activity = expected_start_activity
        self.expected_target_device = expected_target_device
        self.global_project_name = global_project_name
        self.global_project_version = global_project_version
        self. stop_execution_flag =  stop_execution_flag
        self. synthetic_delay_amount =  synthetic_delay_amount
        self. similarity_threshold =  similarity_threshold

