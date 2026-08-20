"""Import allowlist and restricted builtins enforcement (§V.2.3).

Stdlib only — no RestrictedPython or equivalent (explicitly forbidden).
Docker isolates the OS (network, filesystem, memory); this module is what
stops `import os` or dangerous builtins at the Python level.
"""

import builtins as _builtins
import importlib
import importlib.abc
import os as _os
import sys
from typing import Any, Sequence

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


# Deliberately excluded: eval/exec/compile (build/run new code outside
# the sandbox's own dispatch), input/breakpoint/help (read from stdin,
# which is our protocol channel — would corrupt or hang the session,
# not just a security concern). `open` is not excluded — it is replaced
# below with a path-checked version instead, since allowed_directories
# has nothing to apply to if file access is banned outright.
#
# __import__ and __build_class__ look dangerous but must stay: they are
# the hidden builtins the `import` and `class` statements compile down
# to. __import__ is safe to keep since it already goes through
# RestrictedImportFinder above.
#
# Known limitation, not closed here: object introspection
# (`().__class__.__bases__[0].__subclasses__()` and similar) can reach
# classes already loaded in memory without ever calling `import` or
# any of the names below, bypassing this allowlist entirely. Closing
# that fully would require an AST-level sandbox, which the subject
# explicitly forbids (no RestrictedPython or equivalent). Docker
# (network none, read-only fs, dropped capabilities) is the real
# security boundary; this module is defense in depth on top of it.
SAFE_BUILTINS = (
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
    "callable", "chr", "classmethod", "complex", "delattr", "dict",
    "divmod", "enumerate", "filter", "float", "format", "frozenset",
    "getattr", "hasattr", "hash", "hex", "id", "int", "isinstance",
    "issubclass", "iter", "len", "list", "map", "max", "min", "next",
    "object", "oct", "ord", "pow", "print", "property", "range",
    "repr", "reversed", "round", "set", "setattr", "slice", "sorted",
    "staticmethod", "str", "sum", "super", "tuple", "type", "zip",
    "exit", "quit",
    "True", "False", "None", "NotImplemented", "Ellipsis",
    "__import__", "__build_class__", "__name__",
    "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    "AttributeError", "ZeroDivisionError", "StopIteration",
    "StopAsyncIteration", "RuntimeError", "NameError",
    "UnboundLocalError", "NotImplementedError", "ArithmeticError",
    "OverflowError", "LookupError", "AssertionError", "ImportError",
    "ModuleNotFoundError", "GeneratorExit", "MemoryError",
    "RecursionError", "FloatingPointError", "OSError", "IOError",
)


def _make_restricted_open(allowed_directories: Sequence[str]) -> Any:
    real_open = _builtins.open
    allowed_roots = [_os.path.realpath(d) for d in allowed_directories]

    def restricted_open(
        file: Any, mode: str = "r", *args: Any, **kwargs: Any
    ) -> Any:
        if isinstance(file, (str, bytes, _os.PathLike)):
            target = _os.path.realpath(_os.fsdecode(file))
            if not any(
                target == root or target.startswith(root + _os.sep)
                for root in allowed_roots
            ):
                raise PermissionError(
                    f"Access to {file!r} is not allowed by the sandbox "
                    f"configuration (outside allowed_directories)."
                )
        return real_open(file, mode, *args, **kwargs)

    return restricted_open


def restricted_builtins(
    allowed_directories: Sequence[str] = (),
) -> dict[str, Any]:
    result = {
        name: getattr(_builtins, name)
        for name in SAFE_BUILTINS
        if hasattr(_builtins, name)
    }
    result["open"] = _make_restricted_open(allowed_directories)
    return result
