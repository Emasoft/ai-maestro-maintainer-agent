"""Rule package — auto-discovers and imports every detector module.

Importing this package imports ``base`` first (defining the registry +
``__init_subclass__`` hook), then every sibling rule module, so each
concrete ``Rule`` subclass self-registers. The engine and policy
validator read ``Rule.registry`` after importing this package — no
hand-maintained rule list to drift.
"""

from __future__ import annotations

import importlib
import pkgutil

# Import base first so the registry hook exists before any rule module loads.
from . import base as base  # noqa: F401

# Modules that are infrastructure, not rules.
_NOT_A_RULE = {"base", "guard_patterns"}

for _module in pkgutil.iter_modules(__path__):
    if _module.name in _NOT_A_RULE or _module.name.startswith("_"):
        continue
    importlib.import_module(f"{__name__}.{_module.name}")
