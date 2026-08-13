"""Entry point for `uv run sandbox` (§V.2.1).

Usage:
  uv run sandbox                                             interactive REPL
  uv run sandbox sandbox_template.json                       custom config
  uv run sandbox --mcp-stdio "python mcp_tools_mbpp.py" sandbox_template.json
  uv run sandbox --mcp-server <URL>                          HTTP transport

Wires together: config loading, container lifecycle, mcp_bridge, and either
the REPL (no task) or a single task run.
"""

import argparse
import json
from pathlib import Path

from sandbox.config import SandboxConfig
from sandbox.container import SandboxContainer

PROG_NAME = "sandbox"
PROG_DESCRIPTION = "Secure sandbox for LLM-generated code execution."

CONFIG_FILE_HELP = (
    "Path to a SandboxConfig JSON file (e.g. sandbox_template.json)."
)
MCP_STDIO_HELP = (
    "Command launching an MCP server over "
    'stdio (e.g. "python mcp_tools_mbpp.py").'
)
MCP_SERVER_HELP = (
    "URL of an MCP server reachable over HTTP streamable transport."
)

DEFAULT_SANDBOX_IMAGE = "agent-smith-sandbox:latest"
SANDBOX_BUILD_CONTEXT = Path(__file__).parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG_NAME, description=PROG_DESCRIPTION
    )
    parser.add_argument(
        "config_file",
        nargs="?",
        default=None,
        help=CONFIG_FILE_HELP,
    )

    mcp_group = parser.add_mutually_exclusive_group()
    mcp_group.add_argument(
        "--mcp-stdio", metavar="COMMAND", help=MCP_STDIO_HELP
    )
    mcp_group.add_argument("--mcp-server", metavar="URL", help=MCP_SERVER_HELP)
    return parser


def load_config(config_file: str | None) -> SandboxConfig:
    if config_file is None:
        return SandboxConfig()
    data = json.loads(Path(config_file).read_text())
    return SandboxConfig(**data)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config_file)
    container = SandboxContainer(
        config, image=DEFAULT_SANDBOX_IMAGE, build_context=SANDBOX_BUILD_CONTEXT
    )
