"""Address Proof Verification Agent — executes SOP-defined steps for
address exception handling."""

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
# Tools the Address Agent can call
# ---------------------------------------------------------------------------

@tool(approval_mode="never_require")
def verify_address_document(case_json: str) -> str:
    """Verify the applicant's address proof document against SOP rules.

    Executes the full AddressProof DeclineFlow or ReferFlow step-by-step
    and returns a JSON AgentResult.
    """
    case = KYCCase.model_validate_json(case_json)
    flow_type = case.address_flow.value if hasattr(case, "address_flow") else "DeclineFlow"
    acceptable = _engine.get_acceptable_documents("AddressProof")
    steps_executed: list[str] = []

    # Refer flow — skip verification
    if flow_type == FlowType.REFER.value:
        steps_executed.append("Step 1: Address check not required (Refer flow)")
        return AgentResult(
            exception_type=ExceptionType.ADDRESS,
            status=RemediationStatus.NOT_REQUIRED,
            steps_executed=steps_executed,
        ).model_dump_json()

    # Decline flow
    doc = case.address_doc
    if not doc:
        return AgentResult(
            exception_type=ExceptionType.ADDRESS,
            status=RemediationStatus.SUPPLEMENT_REQUIRED,
            steps_executed=["No address document provided"],
            remediation_action="Request address proof document from applicant",
        ).model_dump_json()

    # Step 1: Document type check
    steps_executed.append(f"Step 1: Verify document type '{doc.document_type}'")
    if doc.document_type.lower() not in acceptable:
        steps_executed.append(f"  FAIL — '{doc.document_type}' not in acceptable list: {acceptable}")
        return AgentResult(
            exception_type=ExceptionType.ADDRESS,
            status=RemediationStatus.SUPPLEMENT_REQUIRED,
            steps_executed=steps_executed,
            remediation_action="Request supplementary address document — unacceptable document type",
        ).model_dump_json()
    steps_executed.append("  PASS — document type is acceptable")

    # Step 2: Name match
    supporting_name = case.supporting_doc.name_on_document if case.supporting_doc else ""
    name_match = doc.full_name.strip().lower() == supporting_name.strip().lower()
    steps_executed.append(f"Step 2: Verify name match — address doc='{doc.full_name}' vs supporting='{supporting_name}'")

    if not name_match:
        # Branch 3B
        steps_executed.append("  FAIL — Branch 3B: Name NOT matched")
        return AgentResult(
            exception_type=ExceptionType.ADDRESS,
            status=RemediationStatus.SUPPLEMENT_REQUIRED,
            steps_executed=steps_executed,
            remediation_action="Invoke Supplement Address Document process — name mismatch",
        ).model_dump_json()
    steps_executed.append("  PASS — Branch 3A: Name matched")

    # Step 3 (Branch 3A): Address match
    supporting_address = case.supporting_doc.address_on_document if case.supporting_doc else ""
    address_match = doc.address.strip().lower() == (supporting_address or "").strip().lower()
    steps_executed.append(f"Step 3: Verify address match — doc='{doc.address}' vs supporting='{supporting_address}'")

    if not address_match:
        # Branch 4B
        steps_executed.append("  FAIL — Branch 4B: Address NOT matched")
        return AgentResult(
            exception_type=ExceptionType.ADDRESS,
            status=RemediationStatus.SUPPLEMENT_REQUIRED,
            steps_executed=steps_executed,
            remediation_action="Invoke Supplement Address Document process — address mismatch",
        ).model_dump_json()

    # Branch 4A: All passed
    steps_executed.append("  PASS — Branch 4A: Address matched")
    steps_executed.append("Step 4: Update Remediation_Status = Completed")
    return AgentResult(
        exception_type=ExceptionType.ADDRESS,
        status=RemediationStatus.COMPLETED,
        steps_executed=steps_executed,
    ).model_dump_json()


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

ADDRESS_AGENT_INSTRUCTIONS = f"""You are the Address Proof Verification Agent for the KYC onboarding system.

Your job is to execute the SOP-defined address verification steps DETERMINISTICALLY.
You MUST use the verify_address_document tool with the case data provided to you.
Do NOT improvise or skip steps — follow the SOP rules exactly.

SOP Address Proof Rules:
{_engine.describe_flow("AddressProof", "DeclineFlow")}

After calling the tool, relay the result faithfully — include every step executed
and the final remediation status.
"""


def create_address_agent(client) -> Agent:
    """Create and return the Address Proof Verification Agent."""
    return Agent(
        name="address_agent",
        client=client,
        instructions=ADDRESS_AGENT_INSTRUCTIONS,
        tools=[verify_address_document],
    )
