"""
Full Pipeline Script: Taskei → Generate Test Cases → qTest
Triggered by the Kiro hook when request.json is saved.

This script:
1. Reads request.json
2. Calls Taskei API via builder-mcp (or uses cached data)
3. Parses DoD from the task description
4. Creates test cases in qTest via REST API
"""

import json
import os
import sys
import re
import subprocess

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REQUEST_FILE = os.path.join(SCRIPT_DIR, "request.json")

# qTest config
QTEST_BASE_URL = os.environ.get("QTEST_BASE_URL", "https://wfm.qtestnet.com")
QTEST_TOKEN = os.environ.get("QTEST_TOKEN", "82cd172c-a5c9-4ea7-b6e0-6d197e8f8d85")
QTEST_PROJECT_ID = os.environ.get("QTEST_PROJECT_ID", "96767")


def get_headers():
    return {
        "Authorization": f"bearer {QTEST_TOKEN}",
        "Content-Type": "application/json"
    }


def parse_dod_from_description(description):
    """Extract DOD items from Taskei task description."""
    dods = []
    # Match **DOD X: ...** patterns
    pattern = r'\*\*DOD\s*(\d+)[^*]*\*\*'
    parts = re.split(pattern, description)
    
    # parts will be: [before, dod_num, content, dod_num, content, ...]
    i = 1
    while i < len(parts) - 1:
        dod_num = parts[i]
        content = parts[i + 1].strip()
        
        # Extract steps (numbered lines)
        steps = []
        order = 1
        for line in content.split('\n'):
            line = line.strip()
            # Match numbered steps like "1. ..." or "1\t..."
            step_match = re.match(r'^\d+[\.\)\t]\s*(.+)', line)
            if step_match:
                steps.append({
                    "description": step_match.group(1),
                    "expected": "Verify expected behavior",
                    "order": order
                })
                order += 1
            # Match sub-items like "a) ..."
            sub_match = re.match(r'^[a-z]\)\s*(.+)', line)
            if sub_match:
                steps.append({
                    "description": f"Verify: {sub_match.group(1)}",
                    "expected": sub_match.group(1),
                    "order": order
                })
                order += 1
        
        dods.append({
            "dod_num": dod_num,
            "label": f"DOD{dod_num}",
            "content": content[:200],
            "precondition": "Terminal is powered on and operational",
            "steps": steps if steps else [{"description": "Execute test scenario", "expected": "Expected behavior observed", "order": 1}]
        })
        i += 2
    
    return dods


def generate_qa_scenarios(dods, description):
    """Generate additional QA consideration and negative test scenarios."""
    scenarios = []
    
    # Detect context from description
    has_config = "configuration" in description.lower() or "config" in description.lower()
    has_toggle = "toggle" in description.lower() or "filter" in description.lower()
    has_ui = "ui" in description.lower() or "display" in description.lower() or "screen" in description.lower()
    has_search = "search" in description.lower()
    has_payment = "payment" in description.lower() or "pay" in description.lower()
    has_transaction = "transaction" in description.lower()
    
    scenario_num = len(dods) + 1
    
    # Negative: Invalid/missing configuration
    if has_config:
        scenarios.append({
            "dod_num": str(scenario_num),
            "label": "NEG",
            "content": "Negative - Verify behavior when configuration value is invalid or missing",
            "precondition": "Terminal is powered on. Configuration is set to an invalid/empty value.",
            "steps": [
                {"description": "Set the configuration to an invalid or empty value", "expected": "System handles gracefully without crash", "order": 1},
                {"description": "Navigate to the affected screen/feature", "expected": "Feature defaults to safe state or shows appropriate error", "order": 2},
                {"description": "Verify no error messages or crashes occur", "expected": "System remains stable and functional", "order": 3}
            ]
        })
        scenario_num += 1
    
    # Negative: Rapid toggling / state changes
    if has_toggle:
        scenarios.append({
            "dod_num": str(scenario_num),
            "label": "NEG",
            "content": "Negative - Verify rapid toggle/state changes do not cause UI issues",
            "precondition": "Terminal is powered on. Feature toggle is visible.",
            "steps": [
                {"description": "Rapidly toggle the feature on and off multiple times", "expected": "UI responds correctly to each toggle without lag or glitch", "order": 1},
                {"description": "Verify final state matches the last toggle position", "expected": "Toggle state is accurate", "order": 2},
                {"description": "Verify no visual artifacts or frozen UI elements", "expected": "UI is clean and responsive", "order": 3}
            ]
        })
        scenario_num += 1
    
    # QA: UI consistency across screen transitions
    if has_ui:
        scenarios.append({
            "dod_num": str(scenario_num),
            "label": "QA",
            "content": "QA Consideration - Verify UI consistency when navigating away and returning",
            "precondition": "Terminal is powered on. Feature is active/visible.",
            "steps": [
                {"description": "Navigate to the screen with the feature", "expected": "Feature displays correctly", "order": 1},
                {"description": "Navigate away to a different screen", "expected": "Navigation is smooth", "order": 2},
                {"description": "Return to the original screen", "expected": "Feature state is preserved or reset correctly per requirements", "order": 3},
                {"description": "Verify no visual glitches or missing elements", "expected": "UI renders correctly on return", "order": 4}
            ]
        })
        scenario_num += 1
    
    # QA: Multi-transaction persistence
    if has_transaction or has_toggle:
        scenarios.append({
            "dod_num": str(scenario_num),
            "label": "QA",
            "content": "QA Consideration - Verify feature state resets correctly between transactions",
            "precondition": "Terminal is powered on. Previous transaction completed.",
            "steps": [
                {"description": "Complete a transaction with the feature in a non-default state", "expected": "Transaction completes successfully", "order": 1},
                {"description": "Start a new transaction", "expected": "New transaction begins", "order": 2},
                {"description": "Verify the feature resets to its default/configured state", "expected": "Feature is in default state for new customer", "order": 3}
            ]
        })
        scenario_num += 1
    
    # Negative: Interruption during feature use
    scenarios.append({
        "dod_num": str(scenario_num),
        "label": "NEG",
        "content": "Negative - Verify behavior when operation is interrupted (power cycle/timeout)",
        "precondition": "Terminal is powered on. Feature is in use.",
        "steps": [
            {"description": "Begin using the feature (mid-operation)", "expected": "Feature is active", "order": 1},
            {"description": "Simulate interruption (timeout, cancel, or navigate away)", "expected": "System handles interruption gracefully", "order": 2},
            {"description": "Return to the feature", "expected": "Feature is in a valid state (default or last saved)", "order": 3},
            {"description": "Verify no data corruption or stuck states", "expected": "System is fully functional", "order": 4}
        ]
    })
    scenario_num += 1
    
    # QA: Accessibility / usability
    if has_ui:
        scenarios.append({
            "dod_num": str(scenario_num),
            "label": "QA",
            "content": "QA Consideration - Verify UI elements are properly sized and accessible",
            "precondition": "Terminal is powered on. Feature UI is visible.",
            "steps": [
                {"description": "Verify all UI elements (buttons, toggles, text) are properly sized for touch interaction", "expected": "Elements meet minimum touch target size", "order": 1},
                {"description": "Verify text is readable and labels are clear", "expected": "Text is legible at normal viewing distance", "order": 2},
                {"description": "Verify color contrast meets accessibility standards", "expected": "Sufficient contrast between text and background", "order": 3}
            ]
        })
    
    return scenarios


def fetch_from_taskei(ticket_id):
    """Fetch task details from Taskei via builder-mcp using MCP protocol over stdio."""
    builder_mcp_path = r"C:\Users\vaviveka\AppData\Local\Toolbox\bin\builder-mcp.exe"
    
    if not os.path.exists(builder_mcp_path):
        print(f"[ERROR] builder-mcp not found at {builder_mcp_path}")
        return None
    
    # MCP protocol: send initialize, then call the tool
    initialize_msg = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "pipeline-script", "version": "1.0.0"}
        }
    })
    
    initialized_msg = json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {}
    })
    
    tool_call_msg = json.dumps({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "TaskeiGetTask",
            "arguments": {
                "taskId": ticket_id,
                "includeCustomAttributes": False
            }
        }
    })
    
    try:
        # Start builder-mcp process
        proc = subprocess.Popen(
            [builder_mcp_path, "--include-tools", "*Taskei*"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        # Send MCP messages
        input_data = f"{initialize_msg}\n{initialized_msg}\n{tool_call_msg}\n"
        stdout, stderr = proc.communicate(input=input_data, timeout=30)
        
        # Parse response - look for the tool result
        for line in stdout.split('\n'):
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                if msg.get("id") == 2 and "result" in msg:
                    # Extract task data from MCP response
                    content = msg["result"].get("content", [])
                    for item in content:
                        if item.get("type") == "text":
                            task_data = json.loads(item["text"])
                            if "task" in task_data:
                                return task_data["task"]
                            return task_data
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        
        if stderr:
            print(f"[WARN] builder-mcp stderr: {stderr[:200]}")
        
        return None
        
    except subprocess.TimeoutExpired:
        proc.kill()
        print("[ERROR] builder-mcp timed out (30s). Is mwinit fresh?")
        return None
    except Exception as e:
        print(f"[ERROR] Error calling builder-mcp: {e}")
        return None


def create_submodule_in_qtest(name, parent_module_id):
    """Create a sub-module (folder) inside a parent module in qTest."""
    url = f"{QTEST_BASE_URL}/api/v3/projects/{QTEST_PROJECT_ID}/modules?parentId={parent_module_id}"
    payload = {"name": name}
    
    with httpx.Client() as client:
        resp = client.post(url, headers=get_headers(), json=payload)
        if resp.status_code in (200, 201):
            module = resp.json()
            return str(module.get("id"))
        else:
            print(f"   Error creating sub-module: {resp.status_code} - {resp.text[:100]}")
            return None


def create_test_case(name, description, precondition, steps, module_id, settings=None):
    """Create a test case in qTest with custom fields."""
    payload = {
        "name": name,
        "description": description,
        "precondition": precondition,
        "parent_id": int(module_id),
        "test_steps": steps
    }

    # Add custom field properties if settings provided
    if settings:
        properties = build_properties(settings)
        if properties:
            payload["properties"] = properties
    
    url = f"{QTEST_BASE_URL}/api/v3/projects/{QTEST_PROJECT_ID}/test-cases"
    
    with httpx.Client() as client:
        resp = client.post(url, headers=get_headers(), json=payload)
        if resp.status_code in (200, 201):
            tc = resp.json()
            return f"[CREATED] {tc.get('pid', 'N/A')} | {name}"
        else:
            return f"[FAILED] {name} | {resp.status_code}: {resp.text[:200]}"


def build_properties(settings):
    """Build qTest properties array from settings dict."""
    # Field IDs for project 96767
    FIELD_IDS = {
        "status": 8961694, "test_type": 8961695, "test_priority": 8961699,
        "designer": 8961741, "tc_type": 8961742, "automation_status": 8961743,
        "testing_area": 9198251, "requirement_id": 8961749,
        "reason_not_automating": 8961751, "touch_point": 9464923
    }

    STATUS_VALUES = {"Draft": "1346476", "Review": "1346477", "Approved": "1346478", "Delete": "1346479", "Deferred": "1346480", "Re-Run": "1346484"}
    TEST_TYPE_VALUES = {
        "Assembly": "1346485", "Functional": "1346486",
        "Integration Progression": "1379304", "Integration Regression": "1379303",
        "Non Functional-Other": "1346487", "Non Functional-Performance": "1346488",
        "Progression": "1346489", "Regression": "1346490", "Sanity": "1346491"
    }
    PRIORITY_VALUES = {"1-Critical": "1346501", "2-Major": "1346502", "3-Moderate": "1346503", "4-Minor": "1346504"}
    DESIGNER_VALUES = {
        "Ana Castillo": "179849", "Andres Mijares": "394938", "Arun Rao": "573409",
        "Cody Kelso": "195656", "Gracian Benjamin": "528925", "Kristin Tanzillo": "139251",
        "Mark Brizendine": "163439", "Nerissa Bautista": "195663", "Nhu Ly": "328911",
        "Pamela Champagne": "261543", "QA Tools Support": "127726", "Sherwin Maher": "195657",
        "Sri Preethi Ms": "458564", "Sushmitha Kl": "723697", "Swati Kulkarni": "506943",
        "Varshath Vivekanandhan": "271205", "Varuna Dharshini Ramesh": "430381",
        "Jordan Huss": "706356", "Sai Keerthana Gajula": "578280",
        "Sampreet Hiremath": "314806", "Praveena Kollipara": "600941",
        "Nabeel Nasir": "587838", "Chris Hanly": "622056", "Bharathi Maheedhara": "589579",
        "Hemalatha Gollapalli": "481133", "Anagha Joshi": "522433"
    }
    TYPE_VALUES = {"Manual": "1", "Automation": "2"}
    AUTO_STATUS_VALUES = {"Ready for Automation": "1", "In Progress": "2", "Automated": "3", "Will Not Automate": "4", "Pending for Clarification": "5"}
    TESTING_AREA_VALUES = {
        "General Sale": "6", "Payments": "20", "Gift Card": "7", "QSR": "23",
        "Receipt": "24", "Returns": "25", "Promotion": "22", "Tax": "28",
        "User Interface": "30", "eWIC": "5", "House Account": "8", "Cash Office": "3",
        "Cash Management": "46", "Amazon": "2", "Picklist": "42", "Offline": "39",
        "mPOS": "19", "Integration - DW": "10", "Integration - Sales Audit": "16",
        "Integration - IRMA": "13", "Side Card": "27", "Scanner": "45", "Eclipse": "44",
        "ICD": "41", "Tips": "35", "TM Intervention": "36", "Roles": "48"
    }
    TOUCH_POINT_VALUES = {"POS": "[1]", "QSR": "[2]", "SCO": "[3]", "AO": "[4]"}

    properties = []

    # Status - default to Draft
    val = STATUS_VALUES.get("Draft")
    properties.append({"field_id": FIELD_IDS["status"], "field_value": val})

    # Test Type
    tt = settings.get("test_type", "")
    val = TEST_TYPE_VALUES.get(tt)
    if val:
        properties.append({"field_id": FIELD_IDS["test_type"], "field_value": val})

    # Test Priority
    tp = settings.get("test_priority", "")
    val = PRIORITY_VALUES.get(tp)
    if val:
        properties.append({"field_id": FIELD_IDS["test_priority"], "field_value": val})

    # Designer
    d = settings.get("designer", "")
    val = DESIGNER_VALUES.get(d)
    if val:
        properties.append({"field_id": FIELD_IDS["designer"], "field_value": val})

    # Type (Manual/Automation)
    t = settings.get("type", "")
    val = TYPE_VALUES.get(t)
    if val:
        properties.append({"field_id": FIELD_IDS["tc_type"], "field_value": val})

    # Automation Status
    aus = settings.get("automation_status", "")
    val = AUTO_STATUS_VALUES.get(aus)
    if val:
        properties.append({"field_id": FIELD_IDS["automation_status"], "field_value": val})

    # Testing Area
    ta = settings.get("testing_area", "")
    val = TESTING_AREA_VALUES.get(ta)
    if val:
        properties.append({"field_id": FIELD_IDS["testing_area"], "field_value": val})

    # Requirement ID
    rid = settings.get("requirement_id", "")
    if rid:
        properties.append({"field_id": FIELD_IDS["requirement_id"], "field_value": rid})

    # Reason for not automating
    rna = settings.get("reason_not_automating", "")
    if rna:
        properties.append({"field_id": FIELD_IDS["reason_not_automating"], "field_value": rna})

    # Touch Point
    tp = settings.get("touch_point", "")
    val = TOUCH_POINT_VALUES.get(tp)
    if val:
        properties.append({"field_id": FIELD_IDS["touch_point"], "field_value": val})

    return properties


def main():
    # Read request
    if not os.path.exists(REQUEST_FILE):
        print("No request.json found")
        return
    
    with open(REQUEST_FILE, 'r') as f:
        request = json.load(f)
    
    if request.get("action") not in ("full_pipeline", "manual_pipeline"):
        print(f"Unknown action: {request.get('action')}")
        return
    
    ticket_id = request.get("ticket_id")
    module_id = request.get("target_module_id", "56002030")
    settings = request.get("settings", {})
    prefix = settings.get("prefix", "POS-")
    create_submodule = request.get("create_submodule", False)
    submodule_name = request.get("submodule_name", "")
    action = request.get("action")
    
    print(f"[PIPELINE] Started - Mode: {action}")
    print(f"   Target module: {request.get('target_module_name', module_id)}")
    if create_submodule:
        print(f"   Sub-module: {submodule_name}")
    print(f"   Prefix: {prefix}")
    print()
    
    # Get description based on mode
    if action == "manual_pipeline":
        # Use manually entered DoD
        manual_dod = request.get("manual_dod", "")
        manual_story = request.get("manual_story", "")
        description = manual_dod if manual_dod else manual_story
        if not description:
            print("[ERROR] No manual DoD/requirements provided")
            return
        print(f"[INFO] Using manual input ({len(description)} chars)")
    else:
        # Fetch from Taskei
        cache_file = os.path.join(SCRIPT_DIR, f"taskei_cache_{ticket_id}.json")
        
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                task = json.load(f)
            description = task.get("description", "")
            print(f"[CACHED] Using cached Taskei data for {ticket_id}")
        else:
            print(f"[FETCH] Fetching {ticket_id} from Taskei via builder-mcp...")
            task = fetch_from_taskei(ticket_id)
            if task:
                description = task.get("description", "")
                with open(cache_file, 'w') as f:
                    json.dump(task, f, indent=2)
                print(f"[OK] Fetched and cached Taskei data")
            else:
                print(f"[ERROR] Failed to fetch from Taskei. Ensure mwinit is fresh.")
                return
    
    # Parse DODs
    dods = parse_dod_from_description(description)
    
    if not dods:
        print("[ERROR] No DOD items found in the task description")
        return
    
    # Generate additional QA and negative scenarios
    qa_scenarios = generate_qa_scenarios(dods, description)
    
    # Create sub-module if requested
    if create_submodule and submodule_name:
        print(f"[MODULE] Creating sub-module: {submodule_name}...")
        new_module_id = create_submodule_in_qtest(submodule_name, module_id)
        if new_module_id:
            module_id = new_module_id
            print(f"[OK] Sub-module created (ID: {module_id})")
        else:
            print("[WARN] Failed to create sub-module, using parent module instead")
    
    all_test_cases = dods + qa_scenarios
    print(f"\n[INFO] Found {len(dods)} DOD items + {len(qa_scenarios)} QA/Negative scenarios = {len(all_test_cases)} total test cases\n")
    
    # Create test cases
    results = []
    for tc in all_test_cases:
        tc_name = f"{prefix} {tc.get('label', 'DOD' + tc.get('dod_num', '?'))} - {tc['content'][:60]}"
        tc_desc = tc['content']
        tc_precondition = tc.get('precondition', 'Terminal is powered on and operational')
        
        result = create_test_case(tc_name, tc_desc, tc_precondition, tc['steps'], module_id, settings)
        results.append(result)
        print(result)
    
    print(f"\n{'='*50}")
    print(f"Done! {sum(1 for r in results if '[CREATED]' in r)}/{len(results)} test cases created.")


if __name__ == "__main__":
    main()
