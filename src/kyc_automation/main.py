"""KYC Automation — Main entry point.

Runs the Orchestrator agent against sample KYC cases via the DevUI,
or processes a single case from the CLI.

Usage:
    python -m kyc_automation.main                  # DevUI on port 8080
    python -m kyc_automation.main --case 0         # Process sample case #0 in CLI
    python -m kyc_automation.main --case-file X.json  # Process a custom case file
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from kyc_automation.utils.client import create_client
from kyc_automation.agents.orchestrator import create_orchestrator
from kyc_automation.models.case import KYCCase

_SAMPLE_CASES_PATH = Path(__file__).resolve().parents[2] / "data" / "sample_cases" / "sample_cases.json"


def _load_sample_cases() -> list[dict]:
    with open(_SAMPLE_CASES_PATH, encoding="utf-8") as f:
        return json.load(f)


async def run_case_cli(orchestrator, case_data: dict) -> None:
    """Process a single KYC case through the orchestrator in the CLI."""
    case = KYCCase.model_validate(case_data)
    prompt = (
        f"Process this KYC case. Execute all flagged exceptions per SOP rules.\n\n"
        f"Case JSON:\n```json\n{case.model_dump_json(indent=2)}\n```"
    )
    print(f"\n{'='*70}")
    print(f"  Processing Case: {case.case_id} — {case.applicant_name}")
    print(f"  Exceptions: identity={case.identity_exception}, "
          f"address={case.address_exception}, nns={case.nns_exception}")
    print(f"{'='*70}\n")

    response = await orchestrator.run(prompt)
    print(response.text)
    print(f"\n{'='*70}\n")


def run_devui(orchestrator) -> None:
    """Launch the DevUI for interactive testing."""
    from agent_framework.devui import serve

    print("Starting KYC Automation DevUI on http://localhost:8080 ...")
    serve(entities=[orchestrator], port=8080, auto_open=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="KYC Automation — Multi-Agent System")
    parser.add_argument("--case", type=int, default=None,
                        help="Index of the sample case to process (0-based)")
    parser.add_argument("--case-file", type=str, default=None,
                        help="Path to a custom case JSON file")
    parser.add_argument("--devui", action="store_true", default=False,
                        help="Launch DevUI for interactive testing (default if no --case)")
    args = parser.parse_args()

    client = create_client()
    orchestrator = create_orchestrator(client)

    if args.case is not None:
        cases = _load_sample_cases()
        if args.case < 0 or args.case >= len(cases):
            print(f"Error: case index {args.case} out of range (0-{len(cases)-1})")
            sys.exit(1)
        asyncio.run(run_case_cli(orchestrator, cases[args.case]))
    elif args.case_file:
        with open(args.case_file, encoding="utf-8") as f:
            case_data = json.load(f)
        asyncio.run(run_case_cli(orchestrator, case_data))
    else:
        run_devui(orchestrator)


if __name__ == "__main__":
    main()
