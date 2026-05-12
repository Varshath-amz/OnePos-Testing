"""
qTest MCP Server - Model Context Protocol server for Tricentis qTest integration.

This server exposes qTest Manager REST API operations as MCP tools that Kiro agents
can invoke directly from chat.

Environment Variables Required:
    QTEST_BASE_URL: Your qTest instance URL (e.g., https://yoursite.qtestnet.com)
    QTEST_TOKEN: Bearer token from qTest Download Resources page
    QTEST_PROJECT_ID: Default project ID (optional, can be passed per-call)
"""

import os
import json
import sys
from typing import Optional

try:
    from dotenv import load_dotenv
    # Load .env from the same directory as this script
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass  # python-dotenv is optional

try:
    import httpx
except ImportError:
    print("ERROR: httpx is required. Install with: pip install httpx", file=sys.stderr)
    sys.exit(1)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("ERROR: mcp SDK is required. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Initialize MCP server
mcp = FastMCP("qtest")

# Configuration from environment
QTEST_BASE_URL = os.environ.get("QTEST_BASE_URL", "")
QTEST_TOKEN = os.environ.get("QTEST_TOKEN", "")
QTEST_PROJECT_ID = os.environ.get("QTEST_PROJECT_ID", "")


def get_headers() -> dict:
    """Get authorization headers for qTest API calls."""
    return {
        "Authorization": f"bearer {QTEST_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def get_base_url() -> str:
    """Get the qTest API base URL."""
    return f"{QTEST_BASE_URL.rstrip('/')}/api/v3"


def resolve_project_id(project_id: Optional[str] = None) -> str:
    """Resolve project ID from parameter or environment."""
    pid = project_id or QTEST_PROJECT_ID
    if not pid:
        raise ValueError("project_id is required. Pass it as a parameter or set QTEST_PROJECT_ID env var.")
    return pid


# ============================================================
# PROJECT & CONFIGURATION TOOLS
# ============================================================

@mcp.tool()
async def list_projects() -> str:
    """List all qTest projects accessible to the authenticated user."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{get_base_url()}/projects", headers=get_headers())
        resp.raise_for_status()
        projects = resp.json()
        result = []
        for p in projects:
            result.append(f"- ID: {p['id']} | Name: {p['name']} | Status: {p.get('status_id', 'N/A')}")
        return "\n".join(result) if result else "No projects found."


@mcp.tool()
async def get_test_case_fields(project_id: Optional[str] = None) -> str:
    """Get all custom field definitions for test cases in a project.
    Use this to discover field IDs for Priority, Category, etc.

    Args:
        project_id: qTest project ID (uses QTEST_PROJECT_ID env var if not provided)
    """
    pid = resolve_project_id(project_id)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{get_base_url()}/projects/{pid}/settings/test-cases/fields",
            headers=get_headers()
        )
        resp.raise_for_status()
        fields = resp.json()
        result = []
        for f in fields:
            allowed = ""
            if f.get("allowed_values"):
                vals = [v.get("label", v.get("value", "")) for v in f["allowed_values"][:10]]
                allowed = f" | Values: {', '.join(vals)}"
            result.append(f"- ID: {f['id']} | Label: {f['label']} | Type: {f.get('attribute_type', 'N/A')} | Required: {f.get('required', False)}{allowed}")
        return "\n".join(result) if result else "No fields found."


# ============================================================
# MODULE (FOLDER) TOOLS
# ============================================================

@mcp.tool()
async def list_modules(project_id: Optional[str] = None, parent_id: Optional[str] = None) -> str:
    """List test case modules (folders) in a project.

    Args:
        project_id: qTest project ID
        parent_id: Parent module ID to list children of (omit for root modules)
    """
    pid = resolve_project_id(project_id)
    url = f"{get_base_url()}/projects/{pid}/modules"
    params = {}
    if parent_id:
        params["parentId"] = parent_id

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=get_headers(), params=params)
        resp.raise_for_status()
        modules = resp.json()
        if isinstance(modules, list):
            result = [f"- ID: {m['id']} | Name: {m['name']}" for m in modules]
        else:
            # Single module with children
            children = modules.get("children", [])
            result = [f"- ID: {m['id']} | Name: {m['name']}" for m in children]
        return "\n".join(result) if result else "No modules found."


@mcp.tool()
async def create_module(name: str, project_id: Optional[str] = None, parent_id: Optional[str] = None) -> str:
    """Create a new module (folder) for organizing test cases.

    Args:
        name: Name of the module/folder
        project_id: qTest project ID
        parent_id: Parent module ID (omit to create at root level)
    """
    pid = resolve_project_id(project_id)
    url = f"{get_base_url()}/projects/{pid}/modules"
    if parent_id:
        url += f"?parentId={parent_id}"

    payload = {"name": name}

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=get_headers(), json=payload)
        resp.raise_for_status()
        module = resp.json()
        return f"Created module: ID={module['id']}, Name={module['name']}"


# ============================================================
# TEST CASE TOOLS
# ============================================================

@mcp.tool()
async def get_test_cases(
    module_id: str,
    project_id: Optional[str] = None,
    page: int = 1,
    size: int = 50
) -> str:
    """Get test cases from a specific module/folder.

    Args:
        module_id: Module ID to get test cases from
        project_id: qTest project ID
        page: Page number (default 1)
        size: Page size (default 50, max 100)
    """
    pid = resolve_project_id(project_id)
    params = {"parentId": module_id, "page": page, "size": size}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{get_base_url()}/projects/{pid}/test-cases",
            headers=get_headers(),
            params=params
        )
        resp.raise_for_status()
        test_cases = resp.json()
        if not test_cases:
            return "No test cases found in this module."

        result = []
        for tc in test_cases:
            steps_count = len(tc.get("test_steps", []))
            result.append(
                f"- ID: {tc['id']} | PID: {tc.get('pid', 'N/A')} | Name: {tc.get('name', 'Untitled')} | Steps: {steps_count}"
            )
        return "\n".join(result)


@mcp.tool()
async def get_test_case_detail(test_case_id: str, project_id: Optional[str] = None) -> str:
    """Get full details of a specific test case including steps.

    Args:
        test_case_id: The test case ID
        project_id: qTest project ID
    """
    pid = resolve_project_id(project_id)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{get_base_url()}/projects/{pid}/test-cases/{test_case_id}",
            headers=get_headers()
        )
        resp.raise_for_status()
        tc = resp.json()

        steps_text = ""
        for step in tc.get("test_steps", []):
            steps_text += f"\n  Step {step.get('order', '?')}: {step.get('description', '')} → Expected: {step.get('expected', '')}"

        properties_text = ""
        for prop in tc.get("properties", []):
            properties_text += f"\n  {prop.get('field_name', 'Field')}: {prop.get('field_value_name', prop.get('field_value', ''))}"

        return (
            f"Test Case: {tc.get('name', 'Untitled')}\n"
            f"ID: {tc['id']} | PID: {tc.get('pid', 'N/A')}\n"
            f"Description: {tc.get('description', 'N/A')}\n"
            f"Precondition: {tc.get('precondition', 'N/A')}\n"
            f"Properties:{properties_text or ' None'}\n"
            f"Test Steps:{steps_text or ' None'}"
        )


@mcp.tool()
async def create_test_case(
    name: str,
    module_id: str,
    description: str = "",
    precondition: str = "",
    steps: Optional[list] = None,
    priority_field_id: Optional[str] = None,
    priority_value: Optional[str] = None,
    project_id: Optional[str] = None
) -> str:
    """Create a new test case in qTest.

    Args:
        name: Test case title/summary
        module_id: Module (folder) ID to create the test case in
        description: Test case description
        precondition: Preconditions text
        steps: Array of test steps. Each step: {"description": "...", "expected": "...", "order": 1}
        priority_field_id: Field ID for priority (get from get_test_case_fields)
        priority_value: Priority value (e.g., "High", "Medium", "Low")
        project_id: qTest project ID
    """
    pid = resolve_project_id(project_id)

    payload = {
        "name": name,
        "description": description,
        "precondition": precondition,
        "parent_id": int(module_id)
    }

    # Parse test steps - accept list or JSON string
    if steps:
        if isinstance(steps, str):
            try:
                payload["test_steps"] = json.loads(steps)
            except json.JSONDecodeError:
                return "ERROR: 'steps' must be a valid JSON array string."
        elif isinstance(steps, list):
            payload["test_steps"] = steps
        else:
            return "ERROR: 'steps' must be a list or JSON string."

    # Add priority property
    if priority_field_id and priority_value:
        payload["properties"] = [
            {"field_id": int(priority_field_id), "field_value": priority_value}
        ]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{get_base_url()}/projects/{pid}/test-cases",
            headers=get_headers(),
            json=payload
        )
        resp.raise_for_status()
        tc = resp.json()
        return f"Created test case: ID={tc['id']}, PID={tc.get('pid', 'N/A')}, Name={tc.get('name', name)}"


@mcp.tool()
async def bulk_create_test_cases(
    module_id: str,
    test_cases_json: str,
    project_id: Optional[str] = None
) -> str:
    """Create multiple test cases at once from a JSON array.

    Args:
        module_id: Module (folder) ID to create test cases in
        test_cases_json: JSON array string of test cases. Each item: {"name": "...", "description": "...", "precondition": "...", "test_steps": [{"description": "...", "expected": "...", "order": 1}]}
        project_id: qTest project ID
    """
    pid = resolve_project_id(project_id)

    try:
        test_cases = json.loads(test_cases_json)
    except json.JSONDecodeError:
        return "ERROR: test_cases_json must be a valid JSON array string."

    results = []
    async with httpx.AsyncClient() as client:
        for i, tc_data in enumerate(test_cases):
            payload = {
                "name": tc_data.get("name", f"Test Case {i+1}"),
                "description": tc_data.get("description", ""),
                "precondition": tc_data.get("precondition", ""),
                "parent_id": int(module_id),
                "test_steps": tc_data.get("test_steps", [])
            }
            if tc_data.get("properties"):
                payload["properties"] = tc_data["properties"]

            resp = await client.post(
                f"{get_base_url()}/projects/{pid}/test-cases",
                headers=get_headers(),
                json=payload
            )
            if resp.status_code in (200, 201):
                created = resp.json()
                results.append(f"✓ Created: ID={created['id']} | {payload['name']}")
            else:
                results.append(f"✗ Failed: {payload['name']} | Status: {resp.status_code} | {resp.text[:100]}")

    return "\n".join(results)


# ============================================================
# TEST EXECUTION TOOLS
# ============================================================

@mcp.tool()
async def create_test_cycle(
    name: str,
    project_id: Optional[str] = None,
    description: str = "",
    parent_id: Optional[str] = None
) -> str:
    """Create a test cycle (container for test suites/runs).

    Args:
        name: Test cycle name (e.g., "Sprint 5 Regression")
        project_id: qTest project ID
        description: Description of the test cycle
        parent_id: Parent test cycle ID for nesting (optional)
    """
    pid = resolve_project_id(project_id)
    url = f"{get_base_url()}/projects/{pid}/test-cycles"
    if parent_id:
        url += f"?parentId={parent_id}"

    payload = {"name": name, "description": description}

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=get_headers(), json=payload)
        resp.raise_for_status()
        cycle = resp.json()
        return f"Created test cycle: ID={cycle['id']}, Name={cycle['name']}"


@mcp.tool()
async def create_test_run(
    test_case_id: str,
    test_cycle_id: str,
    name: Optional[str] = None,
    project_id: Optional[str] = None
) -> str:
    """Create a test run (executable instance of a test case).

    Args:
        test_case_id: ID of the test case to create a run for
        test_cycle_id: ID of the test cycle to place the run in
        name: Optional name for the test run (defaults to test case name)
        project_id: qTest project ID
    """
    pid = resolve_project_id(project_id)

    payload = {
        "test_case": {"id": int(test_case_id)},
        "parent_id": int(test_cycle_id),
        "parent_type": "test-cycle"
    }
    if name:
        payload["name"] = name

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{get_base_url()}/projects/{pid}/test-runs",
            headers=get_headers(),
            json=payload
        )
        resp.raise_for_status()
        run = resp.json()
        return f"Created test run: ID={run['id']}, Name={run.get('name', 'N/A')}"


@mcp.tool()
async def submit_test_result(
    test_run_id: str,
    status: str,
    project_id: Optional[str] = None,
    note: str = "",
    step_results: Optional[str] = None
) -> str:
    """Submit a test execution result (test log) for a test run.

    Args:
        test_run_id: ID of the test run
        status: Execution status name (e.g., "Passed", "Failed", "Blocked", "Unexecuted")
        project_id: qTest project ID
        note: Execution notes/comments
        step_results: Optional JSON array of step results: [{"test_step_id": 123, "status": "Passed", "actual_result": "..."}]
    """
    pid = resolve_project_id(project_id)

    payload = {
        "status": {"name": status},
        "note": note
    }

    if step_results:
        try:
            payload["test_step_logs"] = json.loads(step_results)
        except json.JSONDecodeError:
            return "ERROR: step_results must be a valid JSON array string."

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{get_base_url()}/projects/{pid}/test-runs/{test_run_id}/test-logs",
            headers=get_headers(),
            json=payload
        )
        resp.raise_for_status()
        log = resp.json()
        return f"Submitted test result: Status={status}, Log ID={log.get('id', 'N/A')}"


# ============================================================
# REQUIREMENTS & TRACEABILITY TOOLS
# ============================================================

@mcp.tool()
async def create_requirement(
    name: str,
    project_id: Optional[str] = None,
    description: str = "",
    parent_id: Optional[str] = None
) -> str:
    """Create a requirement in qTest for traceability linking.

    Args:
        name: Requirement name/title
        project_id: qTest project ID
        description: Requirement description
        parent_id: Parent module ID for requirements tree
    """
    pid = resolve_project_id(project_id)
    url = f"{get_base_url()}/projects/{pid}/requirements"
    if parent_id:
        url += f"?parentId={parent_id}"

    payload = {"name": name, "description": description}

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=get_headers(), json=payload)
        resp.raise_for_status()
        req = resp.json()
        return f"Created requirement: ID={req['id']}, Name={req.get('name', name)}"


@mcp.tool()
async def link_requirement_to_test_case(
    requirement_id: str,
    test_case_id: str,
    project_id: Optional[str] = None
) -> str:
    """Link a requirement to a test case for traceability.

    Args:
        requirement_id: ID of the requirement
        test_case_id: ID of the test case to link
        project_id: qTest project ID
    """
    pid = resolve_project_id(project_id)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{get_base_url()}/projects/{pid}/requirements/{requirement_id}/test-cases/{test_case_id}",
            headers=get_headers()
        )
        resp.raise_for_status()
        return f"Linked requirement {requirement_id} ↔ test case {test_case_id}"


# ============================================================
# DEFECT TOOLS
# ============================================================

@mcp.tool()
async def search_defects(
    query: str,
    project_id: Optional[str] = None,
    page: int = 1,
    size: int = 50
) -> str:
    """Search for defects in a qTest project using a query string.

    Args:
        query: Search query (e.g., release name, version, keyword). Searches defect name and description.
        project_id: qTest project ID
        page: Page number (default 1)
        size: Page size (default 50)
    """
    pid = resolve_project_id(project_id)
    params = {"page": page, "size": size}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Try the search endpoint with AQL query
        search_payload = {
            "object_type": "defects",
            "fields": ["*"],
            "query": f"'Affected Release/Build' = '{query}'"
        }
        resp = await client.post(
            f"{get_base_url()}/projects/{pid}/search",
            headers=get_headers(),
            json=search_payload,
            params=params
        )

        if resp.status_code == 200:
            raw = resp.json()
            # Debug: return raw structure info if parsing fails
            try:
                if isinstance(raw, dict):
                    items = raw.get("items", [])
                elif isinstance(raw, list):
                    items = raw
                else:
                    return f"Unexpected response type: {type(raw)}"

                if not items:
                    return f"No defects found matching '{query}'."

                result = [f"Found {len(items)} defect(s) matching '{query}':\n"]
                for d in items:
                    if not isinstance(d, dict):
                        continue
                    props = {}
                    for p in d.get("properties", []):
                        if isinstance(p, dict):
                            props[p.get("field_name", "")] = p.get("field_value_name", p.get("field_value", ""))
                    result.append(
                        f"- ID: {d.get('id')} | PID: {d.get('pid', 'N/A')} | "
                        f"Name: {d.get('name', 'Untitled')} | "
                        f"Status: {props.get('Status', 'N/A')} | "
                        f"Severity: {props.get('Severity', 'N/A')}"
                    )
                return "\n".join(result) if len(result) > 1 else f"No defects found matching '{query}'."
            except Exception as e:
                return f"Error parsing response: {str(e)}\nRaw type: {type(raw)}\nFirst 500 chars: {str(raw)[:500]}"
        else:
            return f"Search failed with status {resp.status_code}: {resp.text[:300]}"


@mcp.tool()
async def get_defect_detail(
    defect_id: str,
    project_id: Optional[str] = None
) -> str:
    """Get full details of a specific defect.

    Args:
        defect_id: The defect ID
        project_id: qTest project ID
    """
    pid = resolve_project_id(project_id)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{get_base_url()}/projects/{pid}/defects/{defect_id}",
            headers=get_headers()
        )
        resp.raise_for_status()
        d = resp.json()

        properties_text = ""
        for prop in d.get("properties", []):
            field_name = prop.get("field_name", "Unknown")
            field_value = prop.get("field_value_name", prop.get("field_value", ""))
            if field_value:
                properties_text += f"\n  {field_name}: {field_value}"

        return (
            f"Defect: {d.get('name', 'Untitled')}\n"
            f"ID: {d.get('id')} | PID: {d.get('pid', 'N/A')}\n"
            f"Description: {d.get('description', 'N/A')}\n"
            f"Properties:{properties_text or ' None'}\n"
            f"Web URL: {d.get('web_url', 'N/A')}"
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    # Validate configuration
    if not QTEST_BASE_URL:
        print("WARNING: QTEST_BASE_URL environment variable not set", file=sys.stderr)
    if not QTEST_TOKEN:
        print("WARNING: QTEST_TOKEN environment variable not set", file=sys.stderr)

    mcp.run()
