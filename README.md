# 42-Agent-Smith


## Initialize connection to the MCP server
```json
{"jsonrpc": "2.0","id": 1,"method": "initialize","params": {"protocolVersion": "2025-03-26","capabilities": {"roots": {"listChanged": true},"sampling": {}},"clientInfo": {"name": "ExampleClient","version": "1.0.0"}}}
```

## Validate connection
```json
{"jsonrpc": "2.0","method": "notifications/initialized"}
```

## Calling run_tests tool (MBPP)
```json
{"jsonrpc": "2.0","id": 2,"method": "tools/call","params": {"name": "run_tests","arguments": {"code": "def sub_list(nums1, nums2):\n    return list(map(lambda x, y: x - y, nums1, nums2))"}}}
```

## Calling read_file tool (SWE)
```json
{"jsonrpc": "2.0","id": 2,"method": "tools/call","params": {"name": "read_file","arguments": {"filepath": "sandbox_template.json", "start_line": 1, "end_line": 5}}}
```

## Calling edit_file tool (SWE)
```json
{"jsonrpc": "2.0","id": 2,"method": "tools/call","params": {"name": "edit_file","arguments": {"filepath": ".gitignore", "old_str": "testtest", "new_str": "done"}}}
```

## Calling list_files tool (SWE)
```json
{"jsonrpc": "2.0","id": 2,"method": "tools/call","params": {"name": "list_files","arguments": {"directory": "./", "pattern": "**/*.py"}}}
```

## Calling search_code tool (SWE)
```json
{"jsonrpc": "2.0","id": 2,"method": "tools/call","params": {"name": "search_code","arguments": {"pattern": "Input", "file_pattern": "**/mbpp_task.py"}}}
```
