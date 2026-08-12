"""Import allowlist and restricted builtins enforcement (§V.2.3).

Stdlib only — no RestrictedPython or equivalent (explicitly forbidden).
Docker isolates the OS (network, filesystem, memory); this module is what
stops `import os` or dangerous builtins at the Python level.
"""
