import os

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if os.path.isdir(_src) and _src not in __path__:
    __path__.insert(0, _src)