"""
Infrastructure layer for external dependencies and persistence.

This module contains infrastructure concerns that should not depend on
application logic, keeping dependencies unidirectional.
"""

# Avoid circular imports - don't import modules that depend on config here
# Import directly from submodules when needed instead

__all__ = []