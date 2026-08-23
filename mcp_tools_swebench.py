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

TIMEOUT_DELAY_SEC = 10

# --- MCP Tools ---


@mcp.tool
def read_file(filepath: str, start_line: int, end_line: int) -> str:
    """
    Reads a file by opening pens the given file from start_line to end_line
    and returns the content of each line.
    """
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
        return output
    except PermissionError:
        return "Not enough permissions to read the file ! (PermissionError)"
    except UnicodeDecodeError:
        return "Could not read the given file ! (UnicodeDecodeError)"
    except FileNotFoundError:
        return "File not found. Could not read this file ! (FileNotFoundError)"
    except IndexError:
        return ("Could not read the given lines. Some of these lines don't "
                "exist !")


@mcp.tool
def edit_file(filepath: str, old_str: str, new_str: str) -> str:
    """
    Replace an exact string in a file with a new string. Only replaces
    the first occurence of the string.
    """
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
    except IndexError:
        return ("Could not read the given lines. Some of these lines don't "
                "exist !")


@mcp.tool
def list_files(directory: str, pattern: str) -> str:
    """
    List files in a directory matching a given pattern.
    """
    search_path = os.path.join(directory, pattern)
    matches = sorted(glob.glob(search_path, recursive=True))
    if not matches:
        return f"No files matching '{pattern}' found in {directory}."
    return "\n".join(matches)


@mcp.tool
def search_code(pattern: str, file_pattern: str = "*") -> str:
    """
    Performs a grep-like search across the
    codebase and returns formatted matches.
    """
    root_dir = '/testbed'
    results = []

    # Verify regex is valid
    try:
        compiled_regex = re.compile(pattern)
    except re.error as e:
        return f"Error: Invalid regular expression pattern '{pattern}': {e}"

    # Error in case that the root_dir doesn't exist
    base_path = Path(root_dir).resolve()
    if not base_path.exists():
        return f"Error: Workspace path '{root_dir}' does not exist."

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

    return "\n".join(results)


@mcp.tool
def search_function_or_class_definition_in_code(name: str) -> str:
    """
    Find the definition of a function or a class.
    """
    root_dir = '/testbed'

    # Create a regex pattern to match the function/class definition
    pattern = re.compile(
        rf"^\s*(?:async\s+)?(?:def|class)\s+{re.escape(name)}\b"
    )

    # Error in case that the root_dir doesn't exist
    base_path = Path(root_dir).resolve()
    if not base_path.exists():
        return f"Error: Workspace path '{root_dir}' does not exist."

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
    return "\n".join(results) if results else ("No definition "
                                               f"found for '{name}'.")


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
