"""
Core shared components for the Appium Traverser AI.

This module contains shared orchestration logic used by both CLI and UI interfaces.
"""

from traverser_ai_api.core.adapters import ProcessBackend, SubprocessBackend
from traverser_ai_api.core.controller import CrawlerLaunchPlan, CrawlerOrchestrator, FlagController
from traverser_ai_api.core.validation import ValidationService

__all__ = [
    "CrawlerLaunchPlan",
    "CrawlerOrchestrator", 
    "FlagController",
    "ValidationService",
    "ProcessBackend",
    "SubprocessBackend"
]