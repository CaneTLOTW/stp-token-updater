"""Test package bootstrap for pure STP modules."""

from __future__ import annotations

import sys
import types
from pathlib import Path

PACKAGE = "custom_components.stp_token_updater"
if PACKAGE not in sys.modules:
    module = types.ModuleType(PACKAGE)
    module.__path__ = [
        str(Path(__file__).parents[1] / "custom_components" / "stp_token_updater")
    ]
    sys.modules[PACKAGE] = module
