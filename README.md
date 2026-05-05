# OnePos Testing - AI-Powered QA Agent

An AI-powered test case generation, gap analysis, and defect analysis workspace built with [Kiro](https://kiro.dev). This project uses Kiro's agent capabilities to help QA engineers generate comprehensive test cases from Jira user stories, compare them against existing test suites, and identify coverage gaps.

## What This Project Does

- **Generate Test Cases** — From Jira DoD/acceptance criteria, produces structured test cases covering positive, negative, boundary, integration, regression, and security scenarios
- **Compare & Gap Analysis** — Imports existing test cases (Excel/CSV/qTest) and identifies missing coverage
- **Defect Analysis** — Analyzes defect patterns, root causes, and correlates them with test coverage gaps
- **Export** — Outputs results as CSV files with traceability matrices

---

## Prerequisites

Before you start, make sure you have:

1. **Kiro IDE** — Download and install from [kiro.dev](https://kiro.dev)
2. **Git** — For cloning the repository
3. **Python 3.9+** (optional) — If you want to run Excel parsing scripts locally
4. **qTest Access** (optional) — If integrating with Tricentis qTest for import/export

---

## Getting Started

### 1. Clone the Repository

```bash
git clone git@github.com:Varshath-amz/OnePos-Testing.git
cd OnePos-Testing
```

### 2. Open in Kiro

Open the `OnePos-Testing` folder directly in Kiro IDE:

- Launch Kiro
- **File → Open Folder** → select the `OnePos-Testing` directory
- Kiro will automatically detect the `.kiro/` configuration

### 3. Verify Setup

Once opened in Kiro, you should see:
- The agents listed in Kiro's agent panel (`onepos-testing` and `onepos-testing-qa`)
- The workflows available for execution
- The prompts loaded from `.kiro/prompts/`

---

## Project Structure

```
OnePos-Testing/
├── .kiro/
│   ├── agents/
│   │   ├── onepos-testing.md          # Test case generation & gap analysis agent
│   │   └── onepos-testing-qa.md       # QA export agent (generate, compare, defect analysis)
│   ├── config/
│   │   └── settings.json              # Agent configuration & defaults
│   ├── mcp/
│   │   └── mcp.json                   # MCP server configuration (for extensions)
│   ├── prompts/
│   │   ├── generate_testcases.txt     # Prompt template for test case generation
│   │   ├── compare_testcases.txt      # Prompt template for gap analysis
│   │   └── defect_analysis.txt        # Prompt template for defect analysis
│   └── workflows/
│       ├── testcase_generation.json   # Workflow: generate test cases from requirements
│       ├── testcase_comparison.json   # Workflow: compare generated vs existing tests
│       └── defect_analysis.json       # Workflow: analyze defect patterns
├── test-scripts/                      # Output directory for generated test scripts
│   ├── *.csv                          # Generated test case CSV files
│   └── *.md                           # Summary reports
└── README.md
```

---

## How to Use

### Generate Test Cases

1. Open Kiro chat
2. Invoke the agent: type `@onepos-testing-qa` or select it from the agent panel
3. Provide your input:
   - Paste the **Jira user story** or feature description
   - Paste the **acceptance criteria / Definition of Done**
   - Optionally add extra context
4. The agent will generate structured test cases and export them as CSV

**Example prompt:**
```
Generate test cases for this user story:

As a cashier, I want to verify customer age for alcohol purchases so that we comply with legal requirements.

Acceptance Criteria:
- System prompts for age verification when alcohol item is scanned
- Cashier can approve or deny based on ID check
- Transaction is blocked if age verification is denied
- Age verification prompt can be removed by manager override
```

### Compare Against Existing Tests

1. Place your existing test case file (Excel/CSV) in the workspace
2. Invoke the agent and ask it to compare:
   ```
   Compare the generated test cases against the existing tests in test-scripts/existing_tests.csv
   ```
3. The agent produces a gap analysis report with coverage metrics

### Defect Analysis

1. Provide defect data (paste from Jira/qTest or point to a CSV file)
2. The agent classifies defects, detects patterns, and recommends targeted test cases

---

## Configuration

### Agent Settings (``.kiro/config/settings.json``)

| Setting | Description | Default |
|---------|-------------|---------|
| `defaultAgent` | Which agent responds by default | `onepos-testing-qa` |
| `defaultWorkflow` | Default workflow to execute | `testcase_generation` |
| `outputDirectory` | Where generated files are saved | `./output` |
| `output_format` | Default export format | `csv` |
| `default_priority` | Default priority for generated test cases | `Medium` |

### Adding MCP Servers (Optional)

If you want to extend the agents with external tools (e.g., Jira API, qTest API), configure them in `.kiro/mcp/mcp.json`:

```json
{
  "mcpServers": {
    "your-server-name": {
      "command": "uvx",
      "args": ["your-mcp-server-package@latest"],
      "env": {},
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

---

## qTest Integration (Optional)

If your team uses Tricentis qTest, the agents can import/export test cases via the qTest REST API.

### Setup

1. Get your qTest API token from qTest Manager → Download Resources page
2. Set environment variables:
   ```bash
   export QTEST_BASE_URL="https://yoursite.qtestnet.com"
   export QTEST_API_TOKEN="your-bearer-token"
   export QTEST_PROJECT_ID="12345"
   ```
3. The agent can then pull existing test cases from qTest for comparison and push generated test cases back

---

## Customization

### Modifying Prompts

Edit files in `.kiro/prompts/` to adjust how test cases are generated:
- `generate_testcases.txt` — Controls test case structure, categories, and coverage types
- `compare_testcases.txt` — Controls gap analysis logic and output format
- `defect_analysis.txt` — Controls defect classification and root cause analysis

### Adding New Workflows

Create a new JSON file in `.kiro/workflows/` following the existing pattern. Register it in `settings.json` if you want it as a default.

### Creating Custom Agents

Add a new `.md` file in `.kiro/agents/` with the agent definition (frontmatter + system prompt), then register it in `settings.json`.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Agent not appearing in Kiro | Ensure `.kiro/agents/` files have valid frontmatter with `name` field |
| Workflows not loading | Check JSON syntax in `.kiro/workflows/` files |
| Excel parsing fails | Install Python dependencies: `pip install openpyxl pandas` |
| qTest API returns 401 | Verify your API token hasn't been revoked |
| qTest API returns 402 | Your qTest edition may not support API access |

---

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Test by running the agent in Kiro
4. Commit with a descriptive message
5. Push and create a PR

---

## Team

Maintained by the OnePos QA team. For questions, reach out via the team Slack channel or create an issue in this repository.
