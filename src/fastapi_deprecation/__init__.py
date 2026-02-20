__version__ = "0.1.0"

from .utils import format_deprecation_date, format_sunset_date
from .dependencies import DeprecationDependency, set_deprecation_callback
from .core import deprecated
from .openapi import auto_deprecate_openapi
from .middleware import DeprecationMiddleware

__all__ = [
    "format_deprecation_date",
    "format_sunset_date",
    "DeprecationDependency",
    "deprecated",
    "auto_deprecate_openapi",
    "set_deprecation_callback",
    "DeprecationMiddleware",
]
