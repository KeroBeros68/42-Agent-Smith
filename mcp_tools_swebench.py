"""
This file contains an MCP server build with FastMCP.

It contains useful tools that can be used in the agentic loop
for the Agent Smith project.
"""

import glob
import json
import os
import re
from pathlib import Path
import subprocess
import sys
from typing import Literal

from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import ValidationError

from student.agent_swebench.task import SWEBenchTaskInput


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

if TASK is None:
    print(
        "Could not load the task. Please restart "
        "the MCP server with a valid SWEBenchTaskInput in the "
        "SWE_TASK_JSON env variable.",
        file=sys.stderr,
    )
    exit(1)

# Some evaluation scripts can take some times to run
TIMEOUT_DELAY_SEC = 600
MAX_OUTPUT_CHARS = 50_000


def truncate_output(text: str) -> str:
    if len(text) > MAX_OUTPUT_CHARS:
        return (text[:MAX_OUTPUT_CHARS] + ' (...)\n'
                'Output was truncated because it was too long.')
    return text


# Root of the codebase the MCP server is allowed to explore.
ROOT_DIR = '/testbed'

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

    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
        if start_line > len(lines):
            return ('Error: start_line is greater than the total '
                    f'number of lines of the file ({len(lines)}) !')
        if end_line > len(lines):
            return ('Error: end_line is greater than the total '
                    f'number of lines of the file ({len(lines)}) !')
    except Exception:
        pass

    try:
        with open(filepath, 'r') as f:
            # Read concerned lines
            lines: list[str] = f.readlines()[start_line - 1:end_line]

        output: str = ''
        current_line: int = start_line

        # Format output
        for line in lines:
            output = f'{output}{current_line}: {line}'
            current_line += 1
        return truncate_output(output)
    except PermissionError:
        return "Not enough permissions to read the file ! (PermissionError)"
    except UnicodeDecodeError:
        return "Could not read the given file ! (UnicodeDecodeError)"
    except FileNotFoundError:
        return "File not found. Could not read this file ! (FileNotFoundError)"


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

    try:
        # Open file
        with open(filepath, 'r') as f:
            file_content = f.read()
        # Check old_str presence
        if old_str not in file_content:
            return "Could not replace the string: old_str not found !"
        final_file_content = file_content.replace(old_str, new_str, 1)
        # Write output
        with open(filepath, 'w') as f:
            f.write(final_file_content)
        return 'Successfully replaced the string !'
    except PermissionError:
        return "Not enough permissions to read the file ! (PermissionError)"
    except UnicodeDecodeError:
        return "Could not read the given file ! (UnicodeDecodeError)"
    except FileNotFoundError:
        return "File not found. Could not read this file ! (FileNotFoundError)"


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

    search_path = os.path.join(directory, pattern)
    matches = sorted(glob.glob(search_path, recursive=True))
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
    results = []

    # Verify regex is valid
    try:
        # Create a regex object
        compiled_regex = re.compile(pattern)
    except re.error as e:
        return f"Error: Invalid regular expression pattern '{pattern}': {e}"

    # Error in case that the ROOT_DIR doesn't exist
    base_path = Path(ROOT_DIR).resolve()
    if not base_path.exists():
        return f"Error: Workspace path '{ROOT_DIR}' does not exist."

    # Recursively match files based on file_pattern
    for file_path in base_path.rglob(file_pattern):
        # Skip directories and non-regular files
        if not file_path.is_file():
            continue

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_number, line in enumerate(f, start=1):
                    if compiled_regex.search(line):
                        # Format: /absolute/path:<line_number> <line_content>
                        abs_path = file_path.resolve()
                        results.append(f"{abs_path}:{line_number} "
                                       f"{line.rstrip()}")
        except Exception:
            # Silently skip unreadable files or binary files
            continue

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
    # Create a regex pattern to match the function/class definition
    pattern = re.compile(
        rf"^\s*(?:async\s+)?(?:def|class)\s+{re.escape(name)}\b"
    )

    # Error in case that the ROOT_DIR doesn't exist
    base_path = Path(ROOT_DIR).resolve()
    if not base_path.exists():
        return f"Error: Workspace path '{ROOT_DIR}' does not exist."

    # Start searching
    results = []
    for file_path in base_path.rglob("*.py"):
        # Skip non-files
        if not file_path.is_file():
            continue
        # Read file
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_number, line in enumerate(f, start=1):
                    # Search for the pattern in this file
                    if pattern.search(line):
                        # Pattern found. Adding file to the results
                        results.append(
                            f"{file_path.resolve()}:{line_number} "
                            f"{line.rstrip()}"
                        )
        except Exception:
            # Skip this file in case of an error
            continue

    # Return formatted result, or clean error message
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

    # Create regex to match an object name
    # the \b correspond to a non-word char, e.g : "(", ".", etc.
    pattern = re.compile(rf"\b{re.escape(name)}\b")

    # Error in case that the ROOT_DIR doesn't exist
    base_path = Path(ROOT_DIR).resolve()
    if not base_path.exists():
        return f"Error: Workspace path '{ROOT_DIR}' does not exist."

    # Resolve the given path as a Path object
    definition_path = Path(filepath).resolve()
    if not definition_path.exists():
        return f"Error: Path '{definition_path}' does not exist."

    results = []
    for file_path in base_path.rglob("*.py"):
        # Skip non-files
        if not file_path.is_file():
            continue
        is_definition_file = file_path.resolve() == definition_path
        # Read file
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_number, line_content in enumerate(f, start=1):
                    # Skip definition line
                    if is_definition_file and line_number == line:
                        continue

                    # Search for the pattern in this line
                    if pattern.search(line_content):
                        # Match found. Adding it to the results
                        results.append(
                            f"{file_path.resolve()}:{line_number} "
                            f"{line_content.rstrip()}"
                        )
        except Exception:
            # Skip this file in case of an error
            continue

    # Return formatted result, or clean error message
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
    try:
        # Start the evaluation process
        proc = subprocess.run(
            ['bash', '-c', TASK.eval_script],
            timeout=TIMEOUT_DELAY_SEC,
            input="",
            capture_output=True,
            text=True,
            cwd=ROOT_DIR
        )

        # Return the result
        return truncate_output(proc.stdout)

    except subprocess.TimeoutExpired:
        return f'Test failed, timeout expired ({TIMEOUT_DELAY_SEC}s)!'


@mcp.tool
def get_patch() -> str:
    """
    Retrieve the unified git diff of all changes made to the repository.

    Runs the command 'git diff'. Created files must therefore be added before
    with 'git add' to be part of the git diff.
    """
    try:
        # Run the git diff
        proc = subprocess.run(
            ['git', 'diff'],
            timeout=TIMEOUT_DELAY_SEC,
            input="",
            capture_output=True,
            text=True,
            cwd=ROOT_DIR
        )

        # Check the output of the terminal
        if proc.returncode != 0:
            return (f'Error occurred :\nstderr: {proc.stderr}\n'
                    f'stdout: {proc.stdout}')

        # If the result is empty, return message
        if not proc.stdout.strip():
            return "(No output was generated by the git diff)"

        # Return the result
        return truncate_output(proc.stdout)

    except subprocess.TimeoutExpired:
        return ('Timeout expired while getting git '
                f'diff ({TIMEOUT_DELAY_SEC}s)!')


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

    abs_path = Path(workdir).resolve()
    if not abs_path.exists():
        return "Error: The given workdir does not exist !"

    try:
        # Run the command
        proc = subprocess.run(
            ['bash', '-c', command],
            timeout=TIMEOUT_DELAY_SEC,
            input="",
            capture_output=True,
            text=True,
            cwd=abs_path
        )

        return ("=== STDOUT ===\n"
                f'{truncate_output(proc.stdout)}\n'
                '=== STDERR ===\n'
                f'{truncate_output(proc.stderr)}\n'
                '=== EXIT CODE ===\n'
                f'{proc.returncode}')

    except subprocess.TimeoutExpired:
        return ('Timeout expired while executing '
                f'your command ({TIMEOUT_DELAY_SEC}s)!')


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
    mcp.run(transport=mode)
