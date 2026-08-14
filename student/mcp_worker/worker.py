"""
This file contains a Worker class that will create a custom
python environment to execute code from an MCP server.

e.g: If I want to try unit tests, I use the Worker
to spawn a python instance and try them.
"""

class Worker():
    @staticmethod
    def run(code, MBPP):