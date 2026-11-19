"""Local, non-authorizing evidence-relative reporting. No network or app hooks."""

from .derive import from_result, unavailable
from .contract import Report

__all__ = ["Report", "from_result", "unavailable"]
