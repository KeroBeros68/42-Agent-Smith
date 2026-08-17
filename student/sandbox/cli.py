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
import contextlib
import json
import sys
from pathlib import Path

import pydantic
from docker.errors import DockerException

from sandbox import repl
from sandbox.config import SandboxConfig
from sandbox.container import SandboxContainer
from sandbox.mcp_bridge import MCPBridge

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

    try:
        config = load_config(args.config_file)
    except FileNotFoundError:
        print(
            f"error: config file not found: {args.config_file}",
            file=sys.stderr,
        )
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"error: malformed config JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except pydantic.ValidationError as e:
        print(f"error: invalid sandbox config:\n{e}", file=sys.stderr)
        sys.exit(1)

    mcp_bridge = None
    if args.mcp_stdio is not None or args.mcp_server is not None:
        mcp_bridge = MCPBridge(
            stdio_command=args.mcp_stdio, server_url=args.mcp_server
        )
    try:
        container = SandboxContainer(
            config,
            image=DEFAULT_SANDBOX_IMAGE,
            build_context=SANDBOX_BUILD_CONTEXT,
        )
        with contextlib.ExitStack() as stack:
            if mcp_bridge is not None:
                stack.enter_context(mcp_bridge)
            c = stack.enter_context(container)
            repl.run(c)
    except DockerException as e:
        print(f"error: could not reach Docker: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
