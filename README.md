# KYC Automation — Multi-Agent Exception Handling

A Proof of Concept for automating international customer onboarding exception handling using **Microsoft Agent Framework (MAF)** in Python.

## Problem

Manual exception handling during KYC onboarding is time-consuming, error-prone, and hard to scale. The current SOP document contains nested decision logic for three exception types — Identity Verification, Address Proof, and Negative News Screening (NNS) — that operations teams follow manually.

## Solution

A multi-agent system that parses the SOP into structured rules and executes them deterministically:

```
                    ┌─────────────────┐
                    │  Orchestrator   │
                    │     Agent       │
                    └───────┬─────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
     ┌────────▼──────┐ ┌───▼──────────┐ ┌▼────────────┐
     │  Identity     │ │  Address     │ │  NNS        │
     │  Agent        │ │  Agent       │ │  Agent      │
     └───────────────┘ └──────────────┘ └─────────────┘
```

- **Orchestrator Agent**: Coordinates the workflow, delegates to specialists, aggregates results
- **Identity Agent**: Verifies ID document type, name match, DOB match per SOP
- **Address Agent**: Verifies address doc type, name match, address match per SOP
- **NNS Agent**: Runs negative news screening, routes to regional teams (APAC/EMEA/AMERICAS)

## Project Structure

```
kyc-automation/
├── data/
│   ├── sample_cases/          # Test KYC cases
│   │   └── sample_cases.json
│   └── sop_rules/             # Machine-readable SOP rules
│       └── sop_rules.json
├── src/kyc_automation/
│   ├── agents/                # MAF agents
│   │   ├── identity_agent.py
│   │   ├── address_agent.py
│   │   ├── nns_agent.py
│   │   └── orchestrator.py
│   ├── models/                # Pydantic models
│   │   └── case.py
│   ├── parser/                # Azure Document Intelligence SOP parser
│   │   └── sop_parser.py
│   ├── rules/                 # Rules engine
│   │   └── engine.py
│   ├── utils/                 # Client factory
│   │   └── client.py
│   └── main.py                # Entry point
├── tests/
│   ├── test_rules_engine.py
│   └── test_agents_tools.py
├── pyproject.toml
└── .env.example
```

## Setup

1. **Clone and install:**
   ```bash
   git clone https://github.com/sharmadeep2/kyc-automation.git
   cd kyc-automation
   pip install -e ".[dev]"
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Fill in your Azure AI Project endpoint and deployment name
   ```

3. **Run tests (no Azure credentials needed):**
   ```bash
   pytest tests/ -v
   ```

## Usage

### DevUI (interactive)
```bash
python -m kyc_automation.main
```
Opens http://localhost:8080 — paste a KYC case JSON and chat with the orchestrator.

### CLI (single case)
```bash
python -m kyc_automation.main --case 0    # Process sample case #0
python -m kyc_automation.main --case 1    # Process sample case #1
```

### Sample Cases

| Case | Applicant | Exceptions | Expected Outcome |
|------|-----------|------------|-----------------|
| 0 | Takeshi Yamamoto (Japan) | Identity + Address + NNS | All Completed (all docs match, no NNS hit) |
| 1 | Maria Schmidt (Germany) | Identity + NNS | Identity: Supplement Required (name mismatch), NNS: Investigation Required (EMEA) |
| 2 | John Carter (USA) | Identity + Address | All Completed (all docs match) |

## SOP Parsing (Optional)

To parse a new SOP document via Azure Document Intelligence:

```python
from kyc_automation.parser.sop_parser import parse_sop_document, save_extracted

extracted = parse_sop_document("path/to/SOP.docx")
save_extracted(extracted, "data/sop_rules/extracted_raw.json")
```

Requires `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` and `AZURE_DOCUMENT_INTELLIGENCE_KEY` in `.env`.

## Implementation Stack

- **Microsoft Agent Framework (MAF)** — Agent orchestration with Agent-as-Tool pattern
- **Azure OpenAI** — LLM backbone for agent reasoning
- **Azure Document Intelligence** — SOP document parsing (setup phase)
- **Pydantic** — Typed models for cases, results, and rules
- **Python 3.11+**
