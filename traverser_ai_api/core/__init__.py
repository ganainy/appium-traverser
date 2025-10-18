"""
Core shared components for the Appium Traverser AI.

This module contains shared orchestration logic used by both CLI and UI interfaces.
"""

from .controller import CrawlerLaunchPlan, CrawlerOrchestrator, FlagController
from .validation import ValidationService
from .adapters import ProcessBackend, SubprocessBackend

__all__ = [
    "CrawlerLaunchPlan",
    "CrawlerOrchestrator", 
    "FlagController",
    "ValidationService",
    "ProcessBackend",
    "SubprocessBackend"
]