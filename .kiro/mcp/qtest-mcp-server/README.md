# qTest MCP Server

A custom Model Context Protocol (MCP) server that integrates Tricentis qTest Manager with Kiro agents.

## Setup

### 1. Install Python dependencies

```bash
pip install -r .kiro/mcp/qtest-mcp-server/requirements.txt
```

### 2. Set environment variables

```bash
# Windows (PowerShell)
$env:QTEST_BASE_URL = "https://yoursite.qtestnet.com"
$env:QTEST_TOKEN = "your-bearer-token-from-qtest"
$env:QTEST_PROJECT_ID = "12345"

# Linux/Mac
export QTEST_BASE_URL="https://yoursite.qtestnet.com"
export QTEST_TOKEN="your-bearer-token-from-qtest"
export QTEST_PROJECT_ID="12345"
```

To get your token: qTest Manager → User menu → Download Resources → copy the API token.

### 3. Configure in Kiro

The MCP server is already configured in `.kiro/mcp/mcp.json`. Just ensure your environment variables are set before launching Kiro.

## Available Tools

| Tool | Description |
|------|-------------|
| `list_projects` | List all accessible qTest projects |
| `get_test_case_fields` | Get custom field definitions (Priority, Category, etc.) |
| `list_modules` | List test case folders/modules |
| `create_module` | Create a new folder for test cases |
| `get_test_cases` | Get test cases from a module |
| `get_test_case_detail` | Get full test case with steps |
| `create_test_case` | Create a single test case |
| `bulk_create_test_cases` | Create multiple test cases at once |
| `create_test_cycle` | Create a test cycle (sprint container) |
| `create_test_run` | Create an executable test run |
| `submit_test_result` | Submit pass/fail execution results |
| `create_requirement` | Create a requirement for traceability |
| `link_requirement_to_test_case` | Link requirement ↔ test case |

## Testing the server

Run directly to verify it starts:

```bash
python .kiro/mcp/qtest-mcp-server/server.py
```

The server communicates via stdio (standard MCP transport) — Kiro handles the connection automatically.
