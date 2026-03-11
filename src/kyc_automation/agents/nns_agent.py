"""Negative News Screening (NNS) Agent — executes SOP-defined steps for
NNS exception handling and routes to regional teams."""

from __future__ import annotations

import json

from agent_framework import Agent, tool

from kyc_automation.models.case import (
    AgentResult,
    ExceptionType,
    KYCCase,
    RemediationStatus,
)
from kyc_automation.rules.engine import SOPRulesEngine

_engine = SOPRulesEngine()

# ---------------------------------------------------------------------------
# Tools the NNS Agent can call
# ---------------------------------------------------------------------------

@tool(approval_mode="never_require")
def run_nns_screening(case_json: str, identity_resolved: bool, address_resolved: bool) -> str:
    """Run Negative News Screening against the applicant per SOP rules.

    Args:
        case_json: The KYC case as a JSON string.
        identity_resolved: Whether the identity exception has been resolved.
        address_resolved: Whether the address exception has been resolved.

    Returns:
        JSON AgentResult with screening outcome.
    """
    case = KYCCase.model_validate_json(case_json)
    steps_executed: list[str] = []

    # Step 1: Check if Identity and Address are resolved first
    steps_executed.append("Step 1: Check if Identity and Address exceptions are resolved")
    if case.identity_exception and not identity_resolved:
        steps_executed.append("  FAIL — Identity exception still unresolved; deferring NNS")
        return AgentResult(
            exception_type=ExceptionType.NNS,
            status=RemediationStatus.PENDING,
            steps_executed=steps_executed,
            remediation_action="Defer NNS — resolve Identity exception first",
        ).model_dump_json()
    if case.address_exception and not address_resolved:
        steps_executed.append("  FAIL — Address exception still unresolved; deferring NNS")
        return AgentResult(
            exception_type=ExceptionType.NNS,
            status=RemediationStatus.PENDING,
            steps_executed=steps_executed,
            remediation_action="Defer NNS — resolve Address exception first",
        ).model_dump_json()
    steps_executed.append("  PASS — Prerequisites resolved")

    # Step 2: Run screening
    nns = case.nns_result
    steps_executed.append("Step 2: Run Negative News Screening against applicant name")

    if not nns or not nns.has_potential_match:
        # Branch 3A — no match
        steps_executed.append("  Branch 3A: No potential match found")
        steps_executed.append("Step 3: Update Remediation_Status = Completed")
        return AgentResult(
            exception_type=ExceptionType.NNS,
            status=RemediationStatus.COMPLETED,
            steps_executed=steps_executed,
        ).model_dump_json()

    # Branch 3B — potential match found → route to regional team
    region = _engine.get_nns_routing_team(case.country)
    steps_executed.append(f"  Branch 3B: Potential match found — '{nns.match_details}'")
    steps_executed.append(f"  Routing to regional team: {region} (country: {case.country})")
    return AgentResult(
        exception_type=ExceptionType.NNS,
        status=RemediationStatus.INVESTIGATION_REQUIRED,
        steps_executed=steps_executed,
        remediation_action=f"Route to {region} regional investigation team",
        escalation_team=region,
    ).model_dump_json()


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

NNS_AGENT_INSTRUCTIONS = f"""You are the Negative News Screening (NNS) Agent for the KYC onboarding system.

Your job is to execute the SOP-defined NNS steps DETERMINISTICALLY.
You MUST use the run_nns_screening tool with the case data and the resolution
status of Identity and Address exceptions.

SOP NNS Rules:
{_engine.describe_flow("NNS", "DeclineFlow")}

Country-to-team routing is handled automatically by the tool.
After calling the tool, relay the result faithfully.
"""


def create_nns_agent(client) -> Agent:
    """Create and return the NNS Agent."""
    return Agent(
        name="nns_agent",
        client=client,
        instructions=NNS_AGENT_INSTRUCTIONS,
        tools=[run_nns_screening],
    )
