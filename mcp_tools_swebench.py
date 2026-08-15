"""
This file contains an MCP server build with FastMCP.

It contains useful tools that can be used in the agentic loop
for the Agent Smith project.
"""

import glob
import json
import os
import subprocess
import sys

from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import ValidationError

from student.data_models import SWEBenchTaskInput


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

    # DEBUG TASK
    # TASK = MBPPTaskInput.model_validate(
    #     json.loads(
    #         """
    #             {
    #             "task_id": 282,
    #             "task_definition": "Write a function to substaract two lists using map and lambda function.",
    #             "function_definition": "def sub_list(nums1,nums2):",
    #             "test_imports": [],
    #             "test_list": [
    #                 "assert sub_list([1,2],[3,4])==[-2,-2]",
    #                 "assert sub_list([90,120],[50,70])==[40,50]"
    #             ]
    #             }
    #         """
    #     ) or {}
    # )
except (ValidationError, json.JSONDecodeError):
    TASK = None

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
        return "Could not read the given lines. Some of these lines don't exist !"

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
        return "Could not read the given lines. Some of these lines don't exist !"

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

# @mcp.tool
# def search_code(pattern, file_pattern) -> str:
    

if __name__ == "__main__":
    # Listen to input
    # REPLACE THIS STRING TO 'http' TO USE HTTP INSTEAD OF STDIO
    mcp.run(transport="stdio")
