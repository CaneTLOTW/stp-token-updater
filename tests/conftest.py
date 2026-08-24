"""Test package bootstrap for pure STP modules."""

from __future__ import annotations

import sys
import types
from pathlib import Path

PACKAGE = "custom_components.stp_token_updater"
try:
    import homeassistant  # noqa: F401
except ImportError:
    homeassistant_available = False
else:
    homeassistant_available = True

# Keep pure-parser tests usable without Home Assistant, but never shadow the
# real package in CI: diagnostics and config-flow tests import its typed entry
# aliases from __init__.py.
if not homeassistant_available and PACKAGE not in sys.modules:
    module = types.ModuleType(PACKAGE)
    module.__path__ = [
        str(Path(__file__).parents[1] / "custom_components" / "stp_token_updater")
    ]
    sys.modules[PACKAGE] = module
