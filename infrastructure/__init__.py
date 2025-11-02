"""
Infrastructure layer for external dependencies and persistence.

This module contains infrastructure concerns that should not depend on
application logic, keeping dependencies unidirectional.
"""

# Note: AllowedPackagesManager is imported lazily to avoid circular imports.
# Import it directly when needed: from infrastructure.allowed_packages_manager import AllowedPackagesManager

__all__ = []