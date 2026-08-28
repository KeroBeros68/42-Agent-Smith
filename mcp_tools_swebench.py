"""
This file contains an MCP server build with FastMCP.

It contains useful tools that can be used in the agentic loop
for the Agent Smith project.
"""

import base64
import json
import os
import re
from pathlib import Path
import sys
from typing import Literal, cast

import docker
from docker.models.containers import Container
from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import ValidationError

from student.agent_swebench.task import SWEBenchTaskInput
from student.mcp_server_shared.share import truncate_output


class SWEException(Exception):
    pass


# --- Server Setup ---

load_dotenv()
mcp = FastMCP("SWE Bench MCP Server")

# Loaded ONCE at startup from the env var the sandbox sets before
# starting the MCP Server.
try:
    TASK = SWEBenchTaskInput.model_validate(
        json.loads(os.environ.get("SWE_TASK_JSON", "null")) or {}
    )
except (ValidationError, json.JSONDecodeError):
    TASK = None

# Load the timeout delay
try:
    TIMEOUT_DELAY_SEC = int(os.environ.get('MCP_TIMEOUT_DELAY', -1))
    if TIMEOUT_DELAY_SEC < 1:
        raise ValueError('Invalid timeout delay')
except ValueError:
    print('Unable to load the env variable corresponding '
          'to MCP_TIMEOUT_DELAY. Make sure it\'s present as '
          'a positive int value (>=1).')
    exit(1)


if TASK is None:
    print(
        "Could not load the task. Please restart "
        "the MCP server with a valid SWEBenchTaskInput in the "
        "SWE_TASK_JSON env variable.",
        file=sys.stderr,
    )
    exit(1)


# Root of the codebase the MCP server is allowed to explore. A writable
# copy of /testbed (see _ensure_workspace_repo), not /testbed itself —
# /testbed is part of the sandbox container's read-only rootfs (§V.2.3).
ROOT_DIR = '/workspace/testbed'

_SANDBOX_IMAGE_PREFIX = "sandbox-executor:"


def _find_sandbox_container() -> Container:
    """Find the running sandbox container for this session.

    MCP tools run outside the sandbox's execution restrictions (§V.2.5),
    but for SWE-bench the actual repository only exists inside that
    container's filesystem — this finds it by its derived image tag
    (unique per session: one sandbox container runs at a time, per the
    project's whole architecture).
    """
    client = docker.from_env()
    for container in client.containers.list():
        image = container.image
        if image is None:
            continue
        tags = image.tags or []
        if any(tag.startswith(_SANDBOX_IMAGE_PREFIX) for tag in tags):
            return container
    raise SWEException(
        "No running sandbox container found — is the sandbox started?"
    )


def _exec(
    container: Container,
    cmd: list[str],
    workdir: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[str, str, int]:
    """Run a command inside the sandbox container, argv-style (no shell
    interpolation — arguments are never string-concatenated into a shell
    command, avoiding injection)."""
    # user="1000" (numeric, not "sandbox"): the container drops
    # cap_drop=["ALL"] (including DAC_OVERRIDE), so even the default root
    # exec user can't bypass file permissions — /workspace is tmpfs
    # mounted uid=1000, found by testing (root got "Permission denied" on
    # both list and write). The name "sandbox" only exists in our own
    # MBPP Dockerfile's /etc/passwd — a task-provided SWE-bench image has
    # no such entry ("unable to find user sandbox"), so the numeric UID
    # is used instead, which Docker accepts without a passwd lookup.
    result = container.exec_run(
        cmd, workdir=workdir, demux=True, user="1000", environment=env
    )
    # The docker-stubs type for .output is too loose (bytes | Iterator[bytes]
    # — it doesn't model demux=True specifically), but demux=True guarantees
    # a (stdout, stderr) tuple at runtime, and leaving stream/socket at their
    # default False guarantees a real exit_code (per docker-py's own
    # docstring: both are None only when stream or socket is True).
    if result.exit_code is None:
        raise SWEException("exec_run returned no exit code (unexpected).")
    stdout, stderr = cast(
        "tuple[bytes | None, bytes | None]", result.output
    )
    return (
        (stdout or b"").decode("utf-8", errors="replace"),
        (stderr or b"").decode("utf-8", errors="replace"),
        result.exit_code,
    )


def _ensure_workspace_repo(container: Container) -> None:
    """Copy /testbed to a writable location, once per container.

    /testbed is part of the container's read-only rootfs (§V.2.3) — only
    /workspace and /tmp are writable (tmpfs, see sandbox/container.py).
    edit_file/run_tests need to write into the repo, so tools operate on
    this writable copy instead of the original.
    """
    _, _, exit_code = _exec(
        container,
        ["sh", "-c",
         "[ -d /workspace/testbed ] || cp -a /testbed /workspace/testbed"],
    )
    if exit_code != 0:
        raise SWEException("Could not prepare a writable copy of /testbed.")


def _get_container() -> Container:
    container = _find_sandbox_container()
    _ensure_workspace_repo(container)
    return container


# The path task.eval_script hardcodes internally (e.g. "cd /testbed") —
# distinct from ROOT_DIR, which is the writable copy our tools operate
# on. run_tests() rewrites the script to target that copy instead.
_TESTBED_ORIGINAL = '/testbed'

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
import glob, os, sys
directory, pattern = sys.argv[1], sys.argv[2]
matches = sorted(glob.glob(os.path.join(directory, pattern), recursive=True))
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
                    results.append(
                        f"{file_path.resolve()}:{line_number} {line.rstrip()}"
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
                    results.append(
                        f"{file_path.resolve()}:{line_number} {line.rstrip()}"
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
                    results.append(
                        f"{file_path.resolve()}:{line_number} "
                        f"{line_content.rstrip()}"
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
    # Prevent interracting with out of boundaries files
    path = Path(filepath).resolve()
    if not path.is_relative_to(ROOT_DIR):
        return ('Error: you are trying to interract with a file outside your '
                f'allowed directory ({ROOT_DIR})')

    # Prevent invalid lines
    if start_line <= 0 or end_line <= 0:
        return 'Error: start_line and end_line must be at least 1 !'
    if start_line > end_line:
        return 'Error: end_line cannot be less than start_line !'

    container = _get_container()
    stdout, stderr, exit_code = _exec(container, ["cat", filepath])
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
    # Prevent interracting with out of boundaries files
    path = Path(filepath).resolve()
    if not path.is_relative_to(ROOT_DIR):
        return ('Error: you are trying to interract with a file outside your '
                f'allowed directory ({ROOT_DIR})')

    container = _get_container()
    stdout, stderr, exit_code = _exec(container, ["cat", filepath])
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

    b64content = base64.b64encode(
        final_content.encode("utf-8")
    ).decode("ascii")
    _, werr, wexit = _exec(
        container, ["python3", "-c", _WRITE_FILE_SCRIPT, filepath, b64content]
    )
    if wexit != 0:
        return f"Error writing file: {werr}"
    return 'Successfully replaced the string !'


@mcp.tool
def list_files(directory: str, pattern: str) -> str:
    """
    List files in a directory matching a given glob pattern.

    Args:
        directory: Absolute path to the directory to search.
        pattern: Glob pattern to match filenames. To search subdirectories
            recursively, prefix it with '**/', e.g. '**/*.py' — a bare
            pattern like '*.py' only matches the directory's top level.

    Returns:
        The matching file paths, one per line, or a message if none match.
    """
    # Prevent interracting with out of boundaries files
    path = Path(directory).resolve()
    if not path.is_relative_to(ROOT_DIR):
        return ('Error: you are trying to interract with a file outside your '
                f'allowed directory ({ROOT_DIR})')

    container = _get_container()
    stdout, stderr, exit_code = _exec(
        container, ["python3", "-c", _LIST_FILES_SCRIPT, directory, pattern]
    )
    if exit_code != 0:
        return f"Error listing files: {stderr}"
    matches = [m for m in stdout.splitlines() if m]
    if not matches:
        return f"No files matching '{pattern}' found in {directory}."
    return truncate_output("\n".join(matches))


@mcp.tool
def search_code(pattern: str, file_pattern: str = "*") -> str:
    """
    Perform a grep-like search for a regular expression across the codebase.

    Args:
        pattern: The regular expression to search for, e.g. 'def parse'.
        file_pattern: Glob pattern to select which files to search
            (default '*' = every file under ROOT_DIR).

    Returns:
        The matches, one per line, formatted as
        '/absolute/path.py:<line_number> <line_content>'.
        An error message if the regex is invalid or ROOT_DIR does not exist,
        or 'No matches found.' if nothing matches.
    """
    # Verify regex is valid
    try:
        re.compile(pattern)
    except re.error as e:
        return f"Error: Invalid regular expression pattern '{pattern}': {e}"

    container = _get_container()
    _, _, exists_code = _exec(container, ["test", "-d", ROOT_DIR])
    if exists_code != 0:
        return f"Error: Workspace path '{ROOT_DIR}' does not exist."

    stdout, stderr, exit_code = _exec(
        container,
        ["python3", "-c", _SEARCH_CODE_SCRIPT, ROOT_DIR, pattern,
         file_pattern],
    )
    if exit_code != 0:
        return f"Error searching code: {stderr}"
    results = [r for r in stdout.splitlines() if r]
    if not results:
        return "No matches found."
    return truncate_output("\n".join(results))


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
    container = _get_container()
    _, _, exists_code = _exec(container, ["test", "-d", ROOT_DIR])
    if exists_code != 0:
        return f"Error: Workspace path '{ROOT_DIR}' does not exist."

    stdout, stderr, exit_code = _exec(
        container, ["python3", "-c", _SEARCH_DEF_SCRIPT, ROOT_DIR, name]
    )
    if exit_code != 0:
        return f"Error searching definitions: {stderr}"
    results = [r for r in stdout.splitlines() if r]
    if results:
        return truncate_output("\n".join(results))
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
    # Prevent interracting with out of boundaries files
    path = Path(filepath).resolve()
    if not path.is_relative_to(ROOT_DIR):
        return ('Error: you are trying to interract with a file outside your '
                f'allowed directory ({ROOT_DIR})')

    container = _get_container()
    _, _, exists_code = _exec(container, ["test", "-d", ROOT_DIR])
    if exists_code != 0:
        return f"Error: Workspace path '{ROOT_DIR}' does not exist."
    _, _, path_exists_code = _exec(container, ["test", "-e", filepath])
    if path_exists_code != 0:
        return f"Error: Path '{path}' does not exist."

    stdout, stderr, exit_code = _exec(
        container,
        ["python3", "-c", _FIND_REFERENCES_SCRIPT, ROOT_DIR, name, filepath,
         str(line)],
    )
    if exit_code != 0:
        return f"Error finding references: {stderr}"
    results = [r for r in stdout.splitlines() if r]
    if not results:
        return f"No references found for '{name}'."
    return truncate_output("\n".join(results))


@mcp.tool
def run_tests() -> str:
    """
    Runs some tests to verify that the current state
    of the codebase is working well.
    """
    # Verify task is present (needed for mypy)
    if TASK is None:
        raise SWEException('Could not run tests: tests not loaded ! '
                           'This is a server-side problem.')
    container = _get_container()
    adapted_script = TASK.eval_script.replace(_TESTBED_ORIGINAL, ROOT_DIR)
    # Our sandbox is network_mode="none" (§V.2.3) — a plain `pip install
    # -e .` (build isolation on by default) tries to fetch setuptools
    # from PyPI, fails ("Temporary failure in name resolution"), and the
    # editable-install pointer is never refreshed to ROOT_DIR — it keeps
    # pointing at the image's original /testbed, so the test runner
    # silently imports the *unedited* code. Found by isolating a real
    # false-negative: a manually-verified-correct fix still failed
    # run_tests() until this flag combo (which skips the network-
    # dependent build step) was added. --no-deps for the same reason
    # (dependency resolution also needs network).
    adapted_script = adapted_script.replace(
        "pip install -e .", "pip install -e . --no-build-isolation --no-deps"
    )
    stdout, stderr, exit_code = _exec(
        container,
        ["timeout", str(TIMEOUT_DELAY_SEC), "bash", "-c", adapted_script],
        workdir=ROOT_DIR,
        # PYTHONPATH takes priority over the editable-install pointer,
        # which stays frozen on the image's original /testbed (pip
        # install -e . can't refresh it here — no network, and the
        # user-install fallback needs to write outside our writable
        # mounts). Forces `import django` (and the rest of the repo) to
        # resolve from the fixed copy without depending on pip at all —
        # generic, not specific to Django/conda.
        env={"PYTHONPATH": ROOT_DIR},
    )
    if exit_code == 124:
        return f'Evaluation timed out ({TIMEOUT_DELAY_SEC}s)!'
    return truncate_output(f'=== stdout ===\n{stdout}=== stderr ===\n{stderr}')


@mcp.tool
def get_patch() -> str:
    """
    Retrieve the unified git diff of all changes made to the repository.

    Runs the command 'git diff HEAD' and outputs the result.
    New files must be added with 'git add' (or 'git add -N') to be
    included in the output.
    """
    container = _get_container()
    stdout, stderr, exit_code = _exec(
        container,
        ["timeout", str(TIMEOUT_DELAY_SEC),
         "git", "-c", "core.fileMode=false", 'diff', 'HEAD'],
        workdir=ROOT_DIR,
    )
    if exit_code == 124:
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
    # Prevent interracting with out of boundaries files
    path = Path(workdir).resolve()
    if not path.is_relative_to(ROOT_DIR):
        return ('Error: you are trying to interract with a file outside your '
                f'allowed directory ({ROOT_DIR})')

    container = _get_container()
    _, _, exists_code = _exec(container, ["test", "-d", workdir])
    if exists_code != 0:
        return "Error: The given workdir does not exist !"

    stdout, stderr, exit_code = _exec(
        container,
        ["timeout", str(TIMEOUT_DELAY_SEC), "bash", "-c", command],
        workdir=workdir,
    )
    if exit_code == 124:
        return ('Timeout expired while executing '
                f'your command ({TIMEOUT_DELAY_SEC}s)!')
    return ("=== STDOUT ===\n"
            f'{truncate_output(stdout)}\n'
            '=== STDERR ===\n'
            f'{truncate_output(stderr)}\n'
            '=== EXIT CODE ===\n'
            f'{exit_code}')


if __name__ == "__main__":
    # Get transport mode from env variable MCP_TRANSPORT
    transport_mode = os.environ.get("MCP_TRANSPORT", "stdio")

    # Verify transport mode
    if transport_mode != "http" and transport_mode != "stdio":
        raise TypeError(
            f'Wrong transport mode ("{transport_mode}") '
            'provided in the env variable "MCP_TRANSPORT".'
        )

    # Use literal value for mypy
    mode: Literal["http", "stdio"] = "http"
    if transport_mode == 'stdio':
        mode = 'stdio'

    # Listen
    mcp.run(transport=mode, show_banner=False)
