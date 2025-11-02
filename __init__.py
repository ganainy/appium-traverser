# Package shim to make `traverser_ai_api.*` resolve to files under the repository `src/` directory.
import os

# Add the repository 'src' directory to this package's __path__ so imports like
# `from traverser_ai_api.config import Config` resolve to `src/config.py`.
_src = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if os.path.isdir(_src) and _src not in __path__:
    __path__.insert(0, _src)