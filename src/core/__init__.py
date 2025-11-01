"""
Core shared components for the Appium Traverser AI.

This module contains shared orchestration logic used by both CLI and UI interfaces.
"""

# Lazy factory helpers to avoid eager imports
def get_process_backend(use_qt: bool = False):
    """Factory to create process backend without eager imports."""
    if use_qt:
        from .adapters import QtProcessBackend
        return QtProcessBackend()
    else:
        from .adapters import SubprocessBackend
        return SubprocessBackend()

def get_validation_service(config):
    """Factory to create validation service without eager imports."""
    from .validation import ValidationService
    return ValidationService(config)

def get_crawler_orchestrator(config, backend):
    """Factory to create crawler orchestrator without eager imports."""
    from .controller import CrawlerOrchestrator
    return CrawlerOrchestrator(config, backend)

__all__ = [
    "get_process_backend",
    "get_validation_service",
    "get_crawler_orchestrator"
]
