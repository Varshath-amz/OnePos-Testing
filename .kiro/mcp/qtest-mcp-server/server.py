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
            field_id = prop.get('field_id', 'N/A')
            field_name = prop.get('field_name', 'Field')
            field_value = prop.get('field_value', '')
            field_value_name = prop.get('field_value_name', '')
            display = field_value_name or field_value or ''
            properties_text += f"\n  [ID:{field_id}] {field_name}: {display} (raw_value={field_value})"

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
    status: Optional[str] = None,
    test_type: Optional[str] = None,
    test_priority: Optional[str] = None,
    designer: Optional[str] = None,
    tc_type: Optional[str] = None,
    automation_status: Optional[str] = None,
    testing_area: Optional[str] = None,
    requirement_id: Optional[str] = None,
    reason_not_automating: Optional[str] = None,
    touch_point: Optional[str] = None,
    project_id: Optional[str] = None
) -> str:
    """Create a new test case in qTest with custom fields.

    Args:
        name: Test case title/summary
        module_id: Module (folder) ID to create the test case in
        description: Test case description
        precondition: Preconditions text
        steps: Array of test steps. Each step: {"description": "...", "expected": "...", "order": 1}
        status: Status value (e.g., "Draft", "Review", "Approved", "Delete", "Deferred", "Re-Run")
        test_type: Test Type value (e.g., "Functional", "Integration Progression", "Integration Regression", "Progression", "Regression", "Sanity")
        test_priority: Test Priority value (e.g., "1-Critical", "2-Major", "3-Moderate", "4-Minor")
        designer: Designer name (e.g., "Ana Castillo", "Cody Kelso", "Swati Kulkarni")
        tc_type: Type value - "Manual" or "Automation"
        automation_status: Automation Status (e.g., "Ready for Automation", "In Progress", "Automated", "Will Not Automate")
        testing_area: Testing Area value
        requirement_id: Requirement ID string
        reason_not_automating: Reason for not automating (free text)
        touch_point: Touch Point value (e.g., "POS", "SCO", "QSR")
        project_id: qTest project ID
    """
    pid = resolve_project_id(project_id)

    # Field ID mapping for project 96767
    FIELD_IDS = {
        "status": 8961694,
        "test_type": 8961695,
        "test_priority": 8961699,
        "designer": 8961741,
        "tc_type": 8961742,
        "automation_status": 8961743,
        "testing_area": 9198251,
        "requirement_id": 8961749,
        "reason_not_automating": 8961751,
        "touch_point": 9464923,
    }

    # Value mapping for constrained fields (label -> value)
    VALUE_MAP = {
        "status": {
            "Draft": 1342657, "Review": 1342658, "Approved": 1342659,
            "Delete": 1342660, "Deferred": 1342661, "Re-Run": 1342665
        },
        "test_type": {
            "Assembly": 1342666, "Functional": 1342667,
            "Integration Progression": 1379310, "Integration Regression": 1379309,
            "Non Functional-Other": 1342668, "Non Functional-Performance": 1342669,
            "Progression": 1342670, "Regression": 1342671, "Sanity": 1342672
        },
        "test_priority": {
            "1-Critical": 1342682, "2-Major": 1342683,
            "3-Moderate": 1342684, "4-Minor": 1342685
        },
        "designer": {
            "Ana Castillo": 179849, "Cody Kelso": 195656,
            "Gracian Benjamin": 528925, "Kristin Tanzillo": 139251,
            "Mark Brizendine": 163439, "Marshall Chappell": 99812,
            "Nerissa Bautista": 195663, "Peter Benvenuto": 121432,
            "QA Tools Support": 127726, "Sherwin Maher": 195657,
            "Swati Kulkarni": 506943, "Yves Well": 195668
        },
        "tc_type": {
            "Manual": 1, "Automation": 2
        },
        "automation_status": {
            "Ready for Automation": 1, "In Progress": 2,
            "Automated": 3, "Will Not Automate": 4,
            "Pending for Clarification": 5
        }
    }

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

    # Build properties array using field_id for project 96767
    # Values discovered from existing test cases in this project
    properties = []

    # Value mappings for project 96767 (correct field_value IDs)
    STATUS_VALUES = {"Draft": "1346476", "Review": "1346477", "Approved": "1346478", "Delete": "1346479", "Deferred": "1346480", "Re-Run": "1346484"}
    TEST_TYPE_VALUES = {
        "Assembly": "1346485", "Functional": "1346486",
        "Integration Progression": "1379304", "Integration Regression": "1379303",
        "Non Functional-Other": "1346487", "Non Functional-Performance": "1346488",
        "Progression": "1346489", "Regression": "1346490", "Sanity": "1346491"
    }
    PRIORITY_VALUES = {"1-Critical": "1346501", "2-Major": "1346502", "3-Moderate": "1346503", "4-Minor": "1346504"}
    DESIGNER_VALUES = {
        "Ana Castillo": "179849", "Anagha Joshi": "522433", "Andres Mijares": "394938",
        "Anup Jishnu": "137953", "Arun Rao": "573409", "Ashish Sharma": "332586",
        "Bharathi Maheedhara": "589579", "Brian Huff": "330851", "Chaitanya Bhat": "431515",
        "Chris Hanly": "622056", "Chris Kauffman": "586185", "Cody Graf": "121645",
        "Cody Kelso": "195656", "David Chaput": "113698", "Debdip Ghosh": "447582",
        "Dhaval Patel": "610360", "Ed Trudeau": "329497", "Eric Neher": "121423",
        "Fernando Duhart": "245973", "Gracian Benjamin": "528925",
        "Hemalatha Gollapalli": "481133", "Hunter Harris": "468463",
        "James Buschow": "415206", "Jimi Stitts": "262939", "Joe Alfano": "482326",
        "Joel Jensen": "188359", "John Vazquez": "593583", "Jordan Huss": "706356",
        "Jorge Cruz": "141658", "Josh Hammonds": "121586", "Joshua Williams": "438731",
        "Jyothi Tota": "180556", "Kristin Tanzillo": "139251", "Kyle Collins": "512876",
        "Lisa Livingston": "259852", "Mackenzie Dalglish": "262940",
        "Malvin Viego": "118327", "Mark Brizendine": "163439", "Marshall Chappell": "99812",
        "Michael Woodson": "418568", "Michelle Landes": "113593", "Nabeel Nasir": "587838",
        "Navina Shrestha": "113590", "NCR QA": "418580", "Nerissa Bautista": "195663",
        "Nhu Ly": "328911", "Nikhila Vats": "529798", "Nirdesh Parmar": "446860",
        "Nolan Wehe": "481980", "Pamela Champagne": "261543", "Peter Benvenuto": "121432",
        "Praveena Kollipara": "600941", "Priya Rj": "118332", "Priyanka Chaganti": "519087",
        "QA Tools Support": "127726", "Raymond Martinez": "201737", "Richard Freeman": "509143",
        "Ryan Sutherland": "664515", "Sai Keerthana Gajula": "578280",
        "Samantha Lilley": "588753", "Sampreet Hiremath": "314806",
        "Sarah Fleischmann": "361345", "Sergio Servat": "649747", "Shay Turjeman": "121631",
        "Sherwin Maher": "195657", "Smita Jagadal": "321461",
        "Sowmiya Balasubramaniam": "656971", "Sri Preethi Ms": "458564",
        "Sushmitha Kl": "723697", "Swati Kulkarni": "506943", "Tim Treadway": "128815",
        "Varshath Vivekanandhan": "271205", "Varuna Dharshini Ramesh": "430381",
        "Venkatesh G": "431514", "Vikas Gunaki": "118308", "Willie Escaba": "195257",
        "Yeshwanth Swamy": "118311", "Yves Well": "195668"
    }
    TYPE_VALUES = {"Manual": "1", "Automation": "2"}
    AUTO_STATUS_VALUES = {
        "Ready for Automation": "1", "In Progress": "2",
        "Automated": "3", "Will Not Automate": "4", "Pending for Clarification": "5"
    }
    TESTING_AREA_VALUES = {
        "365": "1", "ADA": "31", "Aloha Kitchen": "32", "Amazon": "2", "BRM": "33",
        "Cash Management": "46", "Cash Office": "3", "Client Office": "4",
        "Container Menu": "47", "CSAT": "37", "EOD": "38", "eWIC": "5",
        "General Sale": "6", "Gift Card": "7", "House Account": "8", "Eclipse": "44",
        "ICD": "41", "Integration - CCH": "9", "Integration - DW": "10",
        "Integration - ICON": "11", "Integration - INFOR": "12", "Integration - IRMA": "13",
        "Integration - Kit Builder": "14", "Integration - MARS": "15",
        "Integration - Sales Audit": "16", "Integration - Workday": "17",
        "Line Director": "18", "mPOS": "19", "Offline": "39", "Payments": "20",
        "Picklist": "42", "Price Checker": "21", "Price Query": "40", "Promotion": "22",
        "QSR": "23", "Receipt": "24", "Report": "43", "Returns": "25", "Roles": "48",
        "Save the Recall": "26", "Scanner": "45", "Side Card": "27",
        "Tab Functional": "34", "Tax": "28", "Tips": "35", "TM Intervention": "36",
        "Transaction Search by Card": "29", "User Interface": "30"
    }
    TOUCH_POINT_VALUES = {"POS": "[1]", "QSR": "[2]", "SCO": "[3]", "AO": "[4]"}

    if status:
        val = STATUS_VALUES.get(status)
        if val:
            properties.append({"field_id": FIELD_IDS["status"], "field_value": val})

    if test_type:
        val = TEST_TYPE_VALUES.get(test_type)
        if val:
            properties.append({"field_id": FIELD_IDS["test_type"], "field_value": val})

    if test_priority:
        val = PRIORITY_VALUES.get(test_priority)
        if val:
            properties.append({"field_id": FIELD_IDS["test_priority"], "field_value": val})

    if designer:
        val = DESIGNER_VALUES.get(designer)
        if val:
            properties.append({"field_id": FIELD_IDS["designer"], "field_value": val})

    if tc_type:
        val = TYPE_VALUES.get(tc_type)
        if val:
            properties.append({"field_id": FIELD_IDS["tc_type"], "field_value": val})

    if automation_status:
        val = AUTO_STATUS_VALUES.get(automation_status)
        if val:
            properties.append({"field_id": FIELD_IDS["automation_status"], "field_value": val})

    if requirement_id:
        properties.append({"field_id": FIELD_IDS["requirement_id"], "field_value": requirement_id})

    if reason_not_automating:
        properties.append({"field_id": FIELD_IDS["reason_not_automating"], "field_value": reason_not_automating})

    if testing_area:
        val = TESTING_AREA_VALUES.get(testing_area)
        if val:
            properties.append({"field_id": FIELD_IDS["testing_area"], "field_value": val})

    if touch_point:
        val = TOUCH_POINT_VALUES.get(touch_point)
        if val:
            properties.append({"field_id": FIELD_IDS["touch_point"], "field_value": val})

    if properties:
        payload["properties"] = properties

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{get_base_url()}/projects/{pid}/test-cases",
            headers=get_headers(),
            json=payload
        )
        if resp.status_code in (200, 201):
            tc = resp.json()
            return f"Created test case: ID={tc['id']}, PID={tc.get('pid', 'N/A')}, Name={tc.get('name', name)}"
        else:
            return f"Error {resp.status_code}: {resp.text[:500]}"


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
async def list_releases(project_id: Optional[str] = None) -> str:
    """List all releases in a project (from Test Plan).

    Args:
        project_id: qTest project ID
    """
    pid = resolve_project_id(project_id)
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{get_base_url()}/projects/{pid}/releases", headers=get_headers())
        resp.raise_for_status()
        releases = resp.json()
        if not releases:
            return "No releases found."
        result = []
        for r in releases:
            result.append(f"- ID: {r['id']} | Name: {r['name']} | PID: {r.get('pid', 'N/A')}")
        return "\n".join(result)


@mcp.tool()
async def list_test_cycles(project_id: Optional[str] = None, parent_id: Optional[str] = None) -> str:
    """List test cycles in a project. Returns all cycles at root level or children of a parent cycle.

    Args:
        project_id: qTest project ID
        parent_id: Parent test cycle ID to list children of (omit for root cycles)
    """
    pid = resolve_project_id(project_id)
    url = f"{get_base_url()}/projects/{pid}/test-cycles"
    if parent_id:
        url += f"?parentId={parent_id}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=get_headers())
        resp.raise_for_status()
        cycles = resp.json()
        if not cycles:
            return "No test cycles found."
        result = []
        for c in cycles:
            result.append(f"- ID: {c['id']} | Name: {c['name']} | PID: {c.get('pid', 'N/A')}")
        return "\n".join(result)


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
