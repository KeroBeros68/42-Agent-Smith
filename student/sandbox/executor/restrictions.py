"""Import allowlist and restricted builtins enforcement (§V.2.3).

Stdlib only — no RestrictedPython or equivalent (explicitly forbidden).
Docker isolates the OS (network, filesystem, memory); this module is what
stops `import os` or dangerous builtins at the Python level.
"""

import importlib
import importlib.abc
import sys
from typing import Sequence

# Verified empirically (2026-08-18): 'os' is already present in sys.modules
# at interpreter startup, loaded by CPython's own bootstrap before any
# sandboxed code runs. Python checks sys.modules BEFORE consulting
# sys.meta_path, so a meta_path hook alone never sees an `import os` that
# hits this pre-existing cache entry — it must be purged explicitly.
PRELOADED_DANGEROUS_MODULES = ("os",)


def _is_authorized(module_name: str, authorized: Sequence[str]) -> bool:
    if module_name in authorized:
        return True
    return any(
        pattern.endswith(".*") and module_name.startswith(pattern[:-1])
        for pattern in authorized
    )


class RestrictedImportFinder(importlib.abc.MetaPathFinder):
    def __init__(self, authorized_imports: Sequence[str]) -> None:
        self._authorized = authorized_imports

    def find_spec(self, fullname, path, target=None):
        if _is_authorized(fullname, self._authorized):
            return None
        raise ImportError(
            f"Import of '{fullname}' is not allowed by the sandbox "
            f"configuration (not in authorized_imports)."
        )


def install(authorized_imports: Sequence[str]) -> None:
    # Resolve every authorized module's own internal dependencies (e.g.
    # json's json.decoder, random's `from os import urandom`) while nothing
    # is restricted yet. Once cached in sys.modules, those internal bindings
    # keep working even after a dependency like 'os' is purged below.
    for name in authorized_imports:
        if not name.endswith(".*"):
            importlib.import_module(name)

    for name in PRELOADED_DANGEROUS_MODULES:
        if not _is_authorized(name, authorized_imports):
            sys.modules.pop(name, None)
    sys.meta_path.insert(0, RestrictedImportFinder(authorized_imports))
