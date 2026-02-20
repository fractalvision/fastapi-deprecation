__version__ = "0.1.0"

from .utils import format_deprecation_date, format_sunset_date
from .dependencies import DeprecationDependency
from .core import deprecated
from .openapi import auto_deprecate_openapi
from .middleware import DeprecationMiddleware
from .engine import DeprecationConfig, set_deprecation_callback

__all__ = [
    "format_deprecation_date",
    "format_sunset_date",
    "DeprecationDependency",
    "deprecated",
    "auto_deprecate_openapi",
    "set_deprecation_callback",
    "DeprecationMiddleware",
    "DeprecationConfig",
]
