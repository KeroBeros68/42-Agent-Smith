"""Self-contained, stdlib-only package copied as-is into the sandbox container.

Must not depend on anything outside this folder (no pydantic, no docker-py):
the same executor/ has to run unmodified inside a team-built MBPP image and
inside an arbitrary task-provided SWE-bench image.

Import convention (decided 2026-08-13): modules here import each other flat
(`import protocol`), never relatively (`from . import protocol`). Inside the
container the bundle is unpacked to /sandbox_executor and started as a plain
script, so that directory lands on sys.path[0] and no PYTHONPATH or nested
package layout is required. Consequence: protocol.py must not import any
sibling, since the host imports it as `sandbox.executor.protocol` while the
container imports it as `protocol`.
"""
