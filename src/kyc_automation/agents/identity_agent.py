"""Identity Verification Agent — executes SOP-defined steps for identity
exception handling using MAF tools and the rules engine."""

from __future__ import annotations

import json

from agent_framework import Agent, tool

from kyc_automation.models.case import (
    AgentResult,
    ExceptionType,
    FlowType,
    KYCCase,
    RemediationStatus,
)
from kyc_automation.rules.engine import SOPRulesEngine

_engine = SOPRulesEngine()

# ---------------------------------------------------------------------------
# Tools the Identity Agent can call
# ---------------------------------------------------------------------------

@tool(approval_mode="never_require")
def verify_identity_document(case_json: str) -> str:
    """Verify the applicant's identity document against SOP rules.

    Executes the full Identity DeclineFlow or ReferFlow step-by-step
    and returns a JSON AgentResult.
    """
    case = KYCCase.model_validate_json(case_json)
    flow_type = case.identity_flow.value
    acceptable = _engine.get_acceptable_documents("Identity")
    steps_executed: list[str] = []

    # Refer flow — skip verification
    if flow_type == FlowType.REFER.value:
        steps_executed.append("Step 1: Identity check not required (Refer flow)")
        return AgentResult(
            exception_type=ExceptionType.IDENTITY,
            status=RemediationStatus.NOT_REQUIRED,
            steps_executed=steps_executed,
        ).model_dump_json()

    # Decline flow
    doc = case.identity_doc
    if not doc:
        return AgentResult(
            exception_type=ExceptionType.IDENTITY,
            status=RemediationStatus.SUPPLEMENT_REQUIRED,
            steps_executed=["No identity document provided"],
            remediation_action="Request identity document from applicant",
        ).model_dump_json()

    # Step 1: Document type check
    steps_executed.append(f"Step 1: Verify document type '{doc.document_type}'")
    if doc.document_type.lower() not in acceptable:
        steps_executed.append(f"  FAIL — '{doc.document_type}' not in acceptable list: {acceptable}")
        return AgentResult(
            exception_type=ExceptionType.IDENTITY,
            status=RemediationStatus.SUPPLEMENT_REQUIRED,
            steps_executed=steps_executed,
            remediation_action="Request supplementary identity document — unacceptable document type",
        ).model_dump_json()
    steps_executed.append("  PASS — document type is acceptable")

    # Step 2: Name match
    supporting_name = case.supporting_doc.name_on_document if case.supporting_doc else ""
    name_match = doc.full_name.strip().lower() == supporting_name.strip().lower()
    steps_executed.append(f"Step 2: Verify name match — ID='{doc.full_name}' vs supporting='{supporting_name}'")

    if not name_match:
        # Branch 3B
        steps_executed.append("  FAIL — Branch 3B: Name NOT matched")
        return AgentResult(
            exception_type=ExceptionType.IDENTITY,
            status=RemediationStatus.SUPPLEMENT_REQUIRED,
            steps_executed=steps_executed,
            remediation_action="Invoke Supplement Identity Document process — name mismatch",
        ).model_dump_json()
    steps_executed.append("  PASS — Branch 3A: Name matched")

    # Step 3 (Branch 3A): DOB match
    supporting_dob = case.supporting_doc.date_of_birth_on_document if case.supporting_doc else ""
    dob_match = doc.date_of_birth.strip() == (supporting_dob or "").strip()
    steps_executed.append(f"Step 3: Verify DOB — ID='{doc.date_of_birth}' vs supporting='{supporting_dob}'")

    if not dob_match:
        # Branch 4B
        steps_executed.append("  FAIL — Branch 4B: DOB NOT matched")
        return AgentResult(
            exception_type=ExceptionType.IDENTITY,
            status=RemediationStatus.SUPPLEMENT_REQUIRED,
            steps_executed=steps_executed,
            remediation_action="Invoke Supplement Identity Document process — DOB mismatch",
        ).model_dump_json()

    # Branch 4A: All passed
    steps_executed.append("  PASS — Branch 4A: DOB matched")
    steps_executed.append("Step 4: Update Remediation_Status = Completed")
    return AgentResult(
        exception_type=ExceptionType.IDENTITY,
        status=RemediationStatus.COMPLETED,
        steps_executed=steps_executed,
    ).model_dump_json()


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

IDENTITY_AGENT_INSTRUCTIONS = f"""You are the Identity Verification Agent for the KYC onboarding system.

Your job is to execute the SOP-defined identity verification steps DETERMINISTICALLY.
You MUST use the verify_identity_document tool with the case data provided to you.
Do NOT improvise or skip steps — follow the SOP rules exactly.

SOP Identity Rules:
{_engine.describe_flow("Identity", "DeclineFlow")}

After calling the tool, relay the result faithfully — include every step executed
and the final remediation status.
"""


def create_identity_agent(client) -> Agent:
    """Create and return the Identity Verification Agent."""
    return Agent(
        name="identity_agent",
        client=client,
        instructions=IDENTITY_AGENT_INSTRUCTIONS,
        tools=[verify_identity_document],
    )
