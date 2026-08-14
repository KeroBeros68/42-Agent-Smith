# 42-Agent-Smith


## Initialize connection to the MCP server
```json
{"jsonrpc": "2.0","id": 1,"method": "initialize","params": {"protocolVersion": "2025-03-26","capabilities": {"roots": {"listChanged": true},"sampling": {}},"clientInfo": {"name": "ExampleClient","version": "1.0.0"}}}
```

## Validate connection
```json
{"jsonrpc": "2.0","method": "notifications/initialized"}
```

## Calling run_tests tool
```json
{"jsonrpc": "2.0","id": 2,"method": "tools/call","params": {"name": "run_tests","arguments": {"code": "def sub_list(nums1, nums2):\n    return list(map(lambda x, y: x - y, nums1, nums2))"}}}
```