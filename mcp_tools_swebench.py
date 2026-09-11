"""
This file contains an MCP server build with FastMCP.

It contains useful tools that can be used in the agentic loop
for the Agent Smith project.
"""

import atexit
import base64
import contextlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from collections.abc import Iterator
from pathlib import Path
import sys
from typing import Literal, cast

import docker
from docker.errors import ImageNotFound
from docker.models.containers import Container
from fastmcp import FastMCP
from pydantic import ValidationError

from student.agent_swebench.task import SWEBenchTaskInput
from student.mcp_server_shared.share import (
    ENV_MCP_TIMEOUT_DELAY,
    ENV_MCP_TRANSPORT,
    ENV_SWE_TASK_JSON,
    TransportMode,
    truncate_output,
)


class SWEException(Exception):
    pass


# --- Server Setup ---

mcp = FastMCP("SWE Bench MCP Server")

# Loaded ONCE at startup from the env var the sandbox sets before
# starting the MCP Server.
try:
    TASK = SWEBenchTaskInput.model_validate(
        json.loads(os.environ.get(ENV_SWE_TASK_JSON, "null")) or {}
    )
except (ValidationError, json.JSONDecodeError):
    TASK = None

# Load the timeout delay
try:
    TIMEOUT_DELAY_SEC = int(os.environ.get(ENV_MCP_TIMEOUT_DELAY, -1))
    if TIMEOUT_DELAY_SEC < 1:
        raise ValueError('Invalid timeout delay')
except ValueError:
    print(f'Unable to load the env variable corresponding '
          f'to {ENV_MCP_TIMEOUT_DELAY}. Make sure it\'s present as '
          f'a positive int value (>=1).')
    exit(1)


_TESTBED_PATH_ENV = os.environ.get('TESTBED_PATH')

if TASK is None:
    if not _TESTBED_PATH_ENV:
        print(
            "Could not load the task. Please restart the MCP server with "
            f"a valid SWEBenchTaskInput in the {ENV_SWE_TASK_JSON} env "
            "variable, or point TESTBED_PATH at a repository.",
            file=sys.stderr,
        )
        exit(1)
    print(
        f"No task loaded ({ENV_SWE_TASK_JSON} unset) — exploring the "
        "repository at TESTBED_PATH. run_tests is unavailable without a "
        "task.",
        file=sys.stderr,
    )


# The path the SWE-bench task image checks the repository out at, and
# the path its own eval_script targets internally.
_TESTBED_IN_IMAGE = '/testbed'

# Where the repository actually lives, from this server's point of view.
#
# §V.4 (sujet v1.2): the moulinette sets TESTBED_PATH to the repository
# root before starting this server when it tests these tools in
# isolation — so when that variable is set, it *is* the repository.
# Otherwise the repo only exists inside the task's image, and we extract
# a copy we own.
#
# Deliberately says nothing about the caller: an MCP server has no
# business knowing whether its client runs in a Docker sandbox. Reaching
# into the client's container (the previous design) made this server
# unusable by any other agent — and unusable in isolation, where no such
# container exists at all.
_materialized_root: str | None = None


def _ensure_task_image(client: docker.DockerClient, image: str) -> None:
    """Pull the task image if it isn't present locally.

    Nothing else pulls it any more: the sandbox runs the generic image
    now, so this server is the only thing that needs the task's own.
    """
    try:
        client.images.get(image)
    except ImageNotFound:
        client.images.pull(image)


def _materialize_repo() -> str:
    """Extract the task image's /testbed into a directory we own.

    The image is created but never started, so no task code runs here —
    this is a file copy, not an execution. Measured at ~10-16s for
    161 MB on django__django-15851.
    """
    if TASK is None:
        raise SWEException(
            "No repository available: this server was started without "
            f"TESTBED_PATH and without a task ({ENV_SWE_TASK_JSON}), so "
            "there is nothing to explore."
        )
    dest = tempfile.mkdtemp(prefix='agent-smith-testbed-')
    client = docker.from_env()
    _ensure_task_image(client, TASK.docker_image)
    container = client.containers.create(TASK.docker_image, command='true')
    try:
        stream, _ = container.get_archive(_TESTBED_IN_IMAGE)
        with tempfile.TemporaryFile() as buffer:
            for chunk in stream:
                buffer.write(chunk)
            buffer.seek(0)
            with tarfile.open(fileobj=buffer) as tar:
                # The archive comes from a task image we are about to run
                # tests from anyway, but an absolute or ../ member would
                # write outside dest — refuse those rather than trust it.
                members = [
                    m for m in tar.getmembers()
                    if not m.name.startswith('/')
                    and '..' not in Path(m.name).parts
                ]
                tar.extractall(dest, members=members)
    finally:
        container.remove(force=True)
    # get_archive('/testbed') yields entries prefixed with 'testbed/'.
    return str(Path(dest) / Path(_TESTBED_IN_IMAGE).name)


def _repo_root() -> str:
    """Absolute path to the repository, materializing it on first use."""
    global _materialized_root
    if _TESTBED_PATH_ENV:
        return _TESTBED_PATH_ENV
    if _materialized_root is None:
        _materialized_root = _materialize_repo()
    return _materialized_root


@atexit.register
def _cleanup_materialized_repo() -> None:
    # Only ever removes a directory we created ourselves — a
    # caller-provided TESTBED_PATH is never touched.
    if _materialized_root is not None:
        shutil.rmtree(Path(_materialized_root).parent, ignore_errors=True)


def _run(
    argv: list[str],
    workdir: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[str, str, int]:
    """Run a command against the repository, argv-style (no shell
    interpolation — arguments are never concatenated into a shell string,
    avoiding injection)."""
    result = subprocess.run(
        argv,
        cwd=workdir,
        env={**os.environ, **env} if env else None,
        capture_output=True,
        text=True,
        errors='replace',
        # Never let a child inherit this server's stdin: on the stdio
        # transport that pipe carries the MCP protocol itself, so a
        # command that reads stdin (run_command with a bare `cat`, say)
        # would either steal protocol bytes or hang forever.
        stdin=subprocess.DEVNULL,
    )
    return result.stdout, result.stderr, result.returncode


@contextlib.contextmanager
def _task_container() -> Iterator[Container]:
    """A disposable container from the task image, repo bind-mounted.

    Created per call and removed in the finally: a lifetime that never
    outlives a single tool call means a crash can leave at most one
    container behind, itself bounded by the tool's own timeout. §V.4
    makes cleanup our responsibility and the evaluation checks for
    orphans, so a long-lived cached container is not worth the seconds
    it would save.

    Mounted at /testbed — the exact path the eval_script and the image's
    editable install already target, so neither needs rewriting. Runs as
    the host uid: verified that running as root instead leaves hundreds
    of root-owned files (__pycache__ and friends) in the repo through the
    mount, breaking every later host-side edit.
    """
    if TASK is None:
        raise SWEException(
            'Could not start a task container: no task was loaded '
            f'({ENV_SWE_TASK_JSON} is unset). This is a server-side '
            'problem.'
        )
    client = docker.from_env()
    _ensure_task_image(client, TASK.docker_image)
    root = _repo_root()
    # Mounted at /testbed because that is what the eval_script and the
    # image's editable install target, and *also* at its host path
    # because the search tools hand the agent host paths that it then
    # passes back to run_command — both must resolve inside.
    mounts = [
        docker.types.Mount(target=_TESTBED_IN_IMAGE, source=root, type='bind')
    ]
    if root != _TESTBED_IN_IMAGE:
        mounts.append(
            docker.types.Mount(target=root, source=root, type='bind')
        )
    container = client.containers.create(
        TASK.docker_image,
        command=['sleep', 'infinity'],
        network_mode='none',
        working_dir=_TESTBED_IN_IMAGE,
        user=f'{os.getuid()}:{os.getgid()}',
        mounts=mounts,
    )
    try:
        container.start()
        yield container
    finally:
        container.remove(force=True)


def _exec_in(
    container: Container,
    argv: list[str],
    workdir: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[str, str, int]:
    """Run a command inside a task container (see _task_container)."""
    result = container.exec_run(
        argv, workdir=workdir, demux=True, environment=env
    )
    if result.exit_code is None:
        raise SWEException('exec_run returned no exit code (unexpected).')
    stdout, stderr = cast('tuple[bytes | None, bytes | None]', result.output)
    return (
        (stdout or b'').decode('utf-8', errors='replace'),
        (stderr or b'').decode('utf-8', errors='replace'),
        result.exit_code,
    )


def _resolve_within_root(path_str: str) -> tuple[Path, str | None]:
    """Resolve path_str and check it's inside the repository root — the
    guard duplicated identically across every tool taking a filesystem
    path argument. Returns (resolved_path, None) on success, or
    (resolved_path, error_message) if outside it — callers check the
    second element and `return` it directly.

    A relative path_str (e.g. ".", "django/db") resolves against the
    repository root, not this process's cwd. The root is resolved too: a
    caller-provided TESTBED_PATH may be relative or go through symlinks,
    and comparing a resolved path against an unresolved root never
    matches.
    """
    root = Path(_repo_root()).resolve()
    path = Path(path_str)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if not path.is_relative_to(root):
        return path, (
            'Error: you are trying to interact with a file outside your '
            f'allowed directory ({root})'
        )
    return path, None


# The shell `timeout` command's exit code when it kills the process.
TIMEOUT_EXIT_CODE = 124

# Upper bound on how many entries a listing/search tool returns. A single
# 50k-char observation costs ~12k input tokens, and every later LLM call
# re-sends it — one unbounded listing can eat a whole SWE-bench input
# budget (300k) by itself, which is exactly how a real run died. Bounding
# by entries keeps the result readable and tells the model to narrow its
# search instead of silently burning the budget.
MAX_RESULT_ENTRIES = 200


def _format_entries(entries: list[str], what: str) -> str:
    """Join result lines, bounded by MAX_RESULT_ENTRIES."""
    if len(entries) <= MAX_RESULT_ENTRIES:
        return truncate_output("\n".join(entries))
    hidden = len(entries) - MAX_RESULT_ENTRIES
    return truncate_output(
        "\n".join(entries[:MAX_RESULT_ENTRIES])
        + f"\n... {hidden} more {what} not shown — narrow your pattern."
    )


_PYTHONWARNINGS_RE = re.compile(r"PYTHONWARNINGS=(['\"]?)([^'\"\s]*)\1")

_PIP_EDITABLE_INSTALL_RE = re.compile(
    r'((?:python\s+-m\s+)?pip\s+install\s+(?:-e|--editable)\s+'
    r'"?\.(?:\[[^\]"]*\])?"?)'
)


def _suppress_deprecation_noise(script: str) -> str:
    """Append ignore::DeprecationWarning to any inline PYTHONWARNINGS=...
    assignment in the eval_script, on top of the env-level default passed
    to _exec_in() — needed because `VAR=val cmd` fully overrides an
    inherited env var for that one command, not merges with it. Found on
    a real task (sympy__sympy-13480): its own test invocation already
    sets PYTHONWARNINGS='ignore::UserWarning,ignore::SyntaxWarning',
    silently discarding our env-level default for that command and
    leaving DeprecationWarning noise unsuppressed.
    """
    def _add(match: re.Match[str]) -> str:
        quote, value = match.group(1), match.group(2)
        if "DeprecationWarning" in value:
            return match.group(0)
        new_value = (
            f"{value},ignore::DeprecationWarning"
            if value else "ignore::DeprecationWarning"
        )
        return f"PYTHONWARNINGS={quote}{new_value}{quote}"
    return _PYTHONWARNINGS_RE.sub(_add, script)


_WRITE_FILE_SCRIPT = """
import base64, sys
filepath, b64content = sys.argv[1], sys.argv[2]
with open(filepath, "wb") as f:
    f.write(base64.b64decode(b64content))
"""

# The 5 read-only tools run a small python3 script inside the container
# (the SWE-bench image always has python3) rather than trying to
# replicate every case with shell one-liners. Arguments are passed as
# argv, never string-interpolated into the script itself, so a filename
# or regex containing quotes can't break out of the script.

_LIST_FILES_SCRIPT = """
import sys
from pathlib import Path
directory, pattern, root = sys.argv[1], sys.argv[2], sys.argv[3]
root_path = Path(root).resolve()
matches = sorted(
    str(p.resolve().relative_to(root_path))
    for p in Path(directory).rglob(pattern)
)
print("\\n".join(matches))
"""

_SEARCH_CODE_SCRIPT = """
import re, sys
from pathlib import Path
root_dir, pattern, file_pattern = sys.argv[1], sys.argv[2], sys.argv[3]
compiled = re.compile(pattern)
base_path = Path(root_dir).resolve()
results = []
for file_path in base_path.rglob(file_pattern):
    if not file_path.is_file():
        continue
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_number, line in enumerate(f, start=1):
                if compiled.search(line):
                    abs_path = file_path.resolve()
                    results.append(
                        f"{abs_path}:{line_number} {line.rstrip()}"
                    )
    except Exception:
        continue
print("\\n".join(results))
"""

_SEARCH_DEF_SCRIPT = """
import re, sys
from pathlib import Path
root_dir, name = sys.argv[1], sys.argv[2]
pattern = re.compile(
    rf"^\\s*(?:async\\s+)?(?:def|class)\\s+{re.escape(name)}\\b"
)
base_path = Path(root_dir).resolve()
results = []
for file_path in base_path.rglob("*.py"):
    if not file_path.is_file():
        continue
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_number, line in enumerate(f, start=1):
                if pattern.search(line):
                    abs_path = file_path.resolve()
                    results.append(
                        f"{abs_path}:{line_number} {line.rstrip()}"
                    )
    except Exception:
        continue
print("\\n".join(results))
"""

_FIND_REFERENCES_SCRIPT = """
import re, sys
from pathlib import Path
root_dir, name, def_filepath, def_line = (
    sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
)
pattern = re.compile(rf"\\b{re.escape(name)}\\b")
base_path = Path(root_dir).resolve()
definition_path = Path(def_filepath).resolve()
results = []
for file_path in base_path.rglob("*.py"):
    if not file_path.is_file():
        continue
    is_definition_file = file_path.resolve() == definition_path
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_number, line_content in enumerate(f, start=1):
                if is_definition_file and line_number == def_line:
                    continue
                if pattern.search(line_content):
                    abs_path = file_path.resolve()
                    results.append(
                        f"{abs_path}:{line_number} {line_content.rstrip()}"
                    )
    except Exception:
        continue
print("\\n".join(results))
"""


# --- MCP Tools ---


@mcp.tool
def read_file(filepath: str, start_line: int, end_line: int) -> str:
    """
    Read the content of a file from start_line to end_line, with line numbers.

    Args:
        filepath: Absolute path to the file to read.
        start_line: First line to return (1-based, inclusive).
        end_line: Last line to return (1-based, inclusive).

    Returns:
        The selected lines, one per line, formatted as
        '<line_number>: <line_content>' (like `cat -n`).
        An error message if the file cannot be read or the lines don't exist.
    """
    path, error = _resolve_within_root(filepath)
    if error is not None:
        return error

    # Prevent invalid lines
    if start_line <= 0 or end_line <= 0:
        return 'Error: start_line and end_line must be at least 1 !'
    if start_line > end_line:
        return 'Error: end_line cannot be less than start_line !'

    stdout, stderr, exit_code = _run(["cat", str(path)])
    if exit_code != 0:
        if "No such file" in stderr:
            return ("File not found. Could not read this file ! "
                    "(FileNotFoundError)")
        if "Permission denied" in stderr:
            return ("Not enough permissions to read the file ! "
                    "(PermissionError)")
        return f"Error reading file: {stderr}"

    lines = stdout.splitlines(keepends=True)
    nb_lines = len(lines)
    if start_line > nb_lines:
        return ('Error: start_line is greater than the total '
                f'number of lines of the file ({nb_lines}) !')
    if end_line > nb_lines:
        return ('Error: end_line is greater than the total '
                f'number of lines of the file ({nb_lines}) !')

    output: str = ''
    current_line: int = start_line
    for line in lines[start_line - 1:end_line]:
        output = f'{output}{current_line}: {line}'
        current_line += 1
    return truncate_output(output)


@mcp.tool
def edit_file(filepath: str, old_str: str, new_str: str) -> str:
    """
    Replace the first occurrence of an exact string in a file with a new one.

    Args:
        filepath: Absolute path to the file to edit.
        old_str: The exact string to find and replace.
        new_str: The string to substitute in place of old_str.

    Returns:
        A confirmation message on success, or an error message if the file
        cannot be read/written or old_str is not found in it.
    """
    path, error = _resolve_within_root(filepath)
    if error is not None:
        return error

    stdout, stderr, exit_code = _run(["cat", str(path)])
    if exit_code != 0:
        if "No such file" in stderr:
            return ("File not found. Could not read this file ! "
                    "(FileNotFoundError)")
        if "Permission denied" in stderr:
            return ("Not enough permissions to read the file ! "
                    "(PermissionError)")
        return f"Error reading file: {stderr}"

    if old_str not in stdout:
        return "Could not replace the string: old_str not found !"
    final_content = stdout.replace(old_str, new_str, 1)

    try:
        b64content = base64.b64encode(
            final_content.encode("utf-8")
        ).decode("ascii")
        _, werr, wexit = _run(
            [sys.executable, "-c", _WRITE_FILE_SCRIPT, str(path), b64content]
        )
    except OSError:
        return 'Error when trying to write the file. The edit was too large.'
    if wexit != 0:
        return f"Error writing file: {werr}"
    return 'Successfully replaced the string !'


@mcp.tool
def list_files(directory: str, pattern: str) -> str:
    """
    List files in a directory matching a given glob pattern, recursively.

    Args:
        directory: Absolute path to the directory to search.
        pattern: Glob pattern to match filenames (e.g. '*.py'). Matches
            recursively through all subdirectories.

    Returns:
        The matching file paths, one per line, or a message if none match.
    """
    path, error = _resolve_within_root(directory)
    if error is not None:
        return error

    stdout, stderr, exit_code = _run(
        [sys.executable, "-c", _LIST_FILES_SCRIPT, str(path), pattern,
         _repo_root()]
    )
    if exit_code != 0:
        return f"Error listing files: {stderr}"
    matches = [m for m in stdout.splitlines() if m]
    if not matches:
        return f"No files matching '{pattern}' found in {directory}."
    return _format_entries(matches, "files")


@mcp.tool
def search_code(pattern: str, file_pattern: str = "*") -> str:
    """
    Perform a grep-like search for a regular expression across the codebase.

    Args:
        pattern: The regular expression to search for, e.g. 'def parse'.
        file_pattern: Glob pattern to select which files to search
            (default '*' = every file in the repository).

    Returns:
        The matches, one per line, formatted as
        '/absolute/path.py:<line_number> <line_content>'.
        An error message if the regex is invalid or the repository root
        does not exist,
        or 'No matches found.' if nothing matches.
    """
    # Verify regex is valid
    try:
        re.compile(pattern)
    except re.error as e:
        return f"Error: Invalid regular expression pattern '{pattern}': {e}"

    root = _repo_root()
    if not Path(root).is_dir():
        return f"Error: Workspace path '{root}' does not exist."

    stdout, stderr, exit_code = _run(
        [sys.executable, "-c", _SEARCH_CODE_SCRIPT, root, pattern,
         file_pattern],
    )
    if exit_code != 0:
        return f"Error searching code: {stderr}"
    results = [r for r in stdout.splitlines() if r]
    if not results:
        return "No matches found."
    return _format_entries(results, "matches")


@mcp.tool
def search_function_or_class_definition_in_code(name: str) -> str:
    """
    Find the definition line of a function or class with the given name.

    Only definitions (e.g. 'def name(...)' or 'class name(...)') are matched,
    not calls or other uses of the name. Searches Python files only.

    Args:
        name: The name of the function or class to look up.

    Returns:
        The definition, formatted as
        '/absolute/path.py:<line_number> <line_content>'.
        'No definition found for '<name>'.' if it is defined nowhere.
    """
    root = _repo_root()
    if not Path(root).is_dir():
        return f"Error: Workspace path '{root}' does not exist."

    stdout, stderr, exit_code = _run(
        [sys.executable, "-c", _SEARCH_DEF_SCRIPT, root, name]
    )
    if exit_code != 0:
        return f"Error searching definitions: {stderr}"
    results = [r for r in stdout.splitlines() if r]
    if results:
        return _format_entries(results, "definitions")
    return f"No definition found for '{name}'."


@mcp.tool
def find_references(name: str, filepath: str, line: int) -> str:
    """
    Find all usages of a symbol (function or class) across the codebase.

    `filepath` and `line` identify the symbol's definition site. The
    definition line itself is excluded from the results: it is the symbol's
    declaration, not a usage.
    Output format is similar to search_code.
    """
    path, error = _resolve_within_root(filepath)
    if error is not None:
        return error

    root = _repo_root()
    if not Path(root).is_dir():
        return f"Error: Workspace path '{root}' does not exist."
    if not path.exists():
        return f"Error: Path '{path}' does not exist."

    stdout, stderr, exit_code = _run(
        [sys.executable, "-c", _FIND_REFERENCES_SCRIPT, root, name,
         str(path), str(line)],
    )
    if exit_code != 0:
        return f"Error finding references: {stderr}"
    results = [r for r in stdout.splitlines() if r]
    if not results:
        return f"No references found for '{name}'."
    return _format_entries(results, "references")


@mcp.tool
def run_tests() -> str:
    """
    Runs some tests to verify that the current state
    of the codebase is working well.
    """
    if TASK is None:
        return ('Error: no task was loaded, so there is no test suite to '
                f'run — this server was started without {ENV_SWE_TASK_JSON}.')
    # The task container is network_mode="none" — a plain `pip install
    # -e .` (build isolation on by default) tries to fetch setuptools
    # from PyPI, fails ("Temporary failure in name resolution"), and the
    # editable-install pointer is never refreshed, so the test runner
    # silently imports the *unedited* code. Found by isolating a real
    # false-negative: a manually-verified-correct fix still failed
    # run_tests() until this flag combo (which skips the network-
    # dependent build step) was added. --no-deps for the same reason
    # (dependency resolution also needs network).
    adapted_script = _PIP_EDITABLE_INSTALL_RE.sub(
        r"\1 --no-build-isolation --no-deps", TASK.eval_script
    )
    # Repetitive DeprecationWarning noise (e.g. sympy's `collections`
    # ABC imports, re-triggered per test module) can fill even the
    # truncate_output() tail budget and bury the real pass/fail verdict
    # — found on a real run (sympy__sympy-13480): a genuinely correct
    # fix, confirmed independently via the moulinette, was unreadable
    # from the agent's own observation because "45 passed" never made
    # it into the truncated output.
    adapted_script = _suppress_deprecation_noise(adapted_script)
    # No path rewriting: the repository is bind-mounted at /testbed,
    # exactly where the script already looks.
    with _task_container() as container:
        stdout, stderr, exit_code = _exec_in(
            container,
            ["timeout", str(TIMEOUT_DELAY_SEC), "bash", "-c", adapted_script],
            workdir=_TESTBED_IN_IMAGE,
            # PYTHONPATH makes `import django` (and the rest of the repo)
            # resolve from the mounted copy without depending on pip at
            # all — generic, not specific to Django/conda. PYTHONWARNINGS
            # is a baseline only: a script that sets its own (via
            # `VAR=val cmd`) fully overrides it for that command, which
            # _suppress_deprecation_noise above patches in the script text.
            env={
                "PYTHONPATH": _TESTBED_IN_IMAGE,
                "PYTHONWARNINGS": "ignore::DeprecationWarning",
            },
        )
    # The script's own `git apply` / `git checkout` of the test file
    # leaves the index recording a mode change against HEAD, which
    # core.fileMode=false does not suppress (it only governs how the
    # worktree is read). get_patch() reads this same repository
    # afterwards, so reset the index back to HEAD — worktree untouched —
    # to keep that noise out of the submitted patch.
    _run(["git", "reset"], workdir=_repo_root())
    if exit_code == TIMEOUT_EXIT_CODE:
        return f'Evaluation timed out ({TIMEOUT_DELAY_SEC}s)!'
    # Truncated separately, not as one concatenated blob: stderr carries
    # the full `bash -x` trace of the eval_script (conda activation,
    # git...), often large enough on its own to push the real pass/fail
    # verdict — which sits right at the stdout/stderr boundary — into
    # the gap that a single combined truncation would cut. Found on a
    # real task (sympy__sympy-13480): the verdict was present in stdout
    # but still lost because the combined blob's truncation window
    # landed elsewhere.
    return (
        truncate_output(f'=== stdout ===\n{stdout}')
        + truncate_output(f'=== stderr ===\n{stderr}')
    )


@mcp.tool
def get_patch() -> str:
    """
    Retrieve the unified git diff of all changes made to the repository,
    including newly created files.

    Runs 'git add -A -N' (intent-to-add, records new files without
    staging their content) so untracked files show up in the diff, then
    'git diff HEAD'.
    """
    root = _repo_root()
    _run(["git", "add", "-A", "-N"], workdir=root)
    stdout, stderr, exit_code = _run(
        ["timeout", str(TIMEOUT_DELAY_SEC),
         "git", "-c", "core.fileMode=false", 'diff', 'HEAD'],
        workdir=root,
    )
    if exit_code == TIMEOUT_EXIT_CODE:
        return ('Timeout expired while getting git '
                f'diff ({TIMEOUT_DELAY_SEC}s)!')
    if exit_code != 0:
        return f'Error occurred :\nstderr: {stderr}\nstdout: {stdout}'
    if not stdout.strip():
        return "(No output was generated by the git diff)"
    return truncate_output(stdout)


@mcp.tool
def run_command(command: str, workdir: str) -> str:
    """
    Execute a shell command in the specified working directory.
    Returns the command's stdout, stderr, and exit code.
    """
    path, error = _resolve_within_root(workdir)
    if error is not None:
        return error
    # The repository is bind-mounted into the task container, so a
    # host-side check is authoritative in both modes.
    if not path.is_dir():
        return "Error: The given workdir does not exist !"

    argv = ["timeout", str(TIMEOUT_DELAY_SEC), "bash", "-c", command]
    # With a task loaded, the command runs in that task's container: the
    # model writes these commands, and the task's own environment (conda,
    # installed deps) is what makes them meaningful. Pointed at a plain
    # TESTBED_PATH instead, there is no such image and no sandboxed agent
    # in the picture — the caller aimed this server at its own
    # filesystem, so the command runs there.
    if TASK is None:
        stdout, stderr, exit_code = _run(argv, workdir=str(path))
    else:
        with _task_container() as container:
            stdout, stderr, exit_code = _exec_in(
                container, argv, workdir=str(path)
            )
    if exit_code == TIMEOUT_EXIT_CODE:
        return ('Timeout expired while executing '
                f'your command ({TIMEOUT_DELAY_SEC}s)!')
    return ("=== STDOUT ===\n"
            f'{truncate_output(stdout)}\n'
            '=== STDERR ===\n'
            f'{truncate_output(stderr)}\n'
            '=== EXIT CODE ===\n'
            f'{exit_code}')


# --- MCP Resources & Prompts ---


_NO_TASK_MESSAGE = (
    "No task is loaded: this server was started to explore a repository "
    f"({ENV_SWE_TASK_JSON} unset), not to solve a SWE-bench instance."
)


@mcp.resource("swebench://task")
def task_resource() -> str:
    """The current SWE-bench task: instance id, repo, issue, hints."""
    if TASK is None:
        return _NO_TASK_MESSAGE
    hints = TASK.hints_text or "(none)"
    return (
        f"Instance ID: {TASK.instance_id}\n"
        f"Repository: {TASK.repo}\n"
        f"Problem statement:\n{TASK.problem_statement}\n\n"
        f"Hints:\n{hints}"
    )


@mcp.prompt
def solve_swebench_task() -> str:
    """Prompt template: fix the reported bug and verify it."""
    if TASK is None:
        return _NO_TASK_MESSAGE
    return (
        f"Fix the following bug in {TASK.repo}, checked out at "
        f"{_repo_root()}.\n\n"
        f"Issue:\n{TASK.problem_statement}\n\n"
        "Explore the repository, apply a fix, verify it with run_tests(), "
        "then submit the diff via get_patch() and final_answer(patch)."
    )


if __name__ == "__main__":
    # Get transport mode from env variable MCP_TRANSPORT
    transport_mode = os.environ.get(
        ENV_MCP_TRANSPORT, TransportMode.STDIO.value
    )

    # Verify transport mode
    if transport_mode not in (
        TransportMode.HTTP.value, TransportMode.STDIO.value
    ):
        raise TypeError(
            f'Wrong transport mode ("{transport_mode}") '
            f'provided in the env variable "{ENV_MCP_TRANSPORT}".'
        )

    # Use literal value for mypy
    mode: Literal["http", "stdio"] = TransportMode.HTTP.value
    if transport_mode == TransportMode.STDIO.value:
        mode = TransportMode.STDIO.value

    # Listen
    mcp.run(transport=mode, show_banner=False)
