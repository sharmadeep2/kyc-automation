"""Orchestrator Agent — coordinates the KYC exception handling workflow.

Uses MAF's Agent-as-Tool pattern: wraps the three specialist agents as
tools so the orchestrator can delegate deterministically based on which
exceptions are flagged on the case.
"""

from __future__ import annotations

import json

from agent_framework import Agent

from kyc_automation.agents.identity_agent import create_identity_agent
from kyc_automation.agents.address_agent import create_address_agent
from kyc_automation.agents.nns_agent import create_nns_agent

# ---------------------------------------------------------------------------
# Instructions
# ---------------------------------------------------------------------------

ORCHESTRATOR_INSTRUCTIONS = """\
You are the KYC Orchestrator Agent. You coordinate exception handling for
international customer onboarding cases.

WORKFLOW (follow this exactly):
1. Receive a KYC case (JSON).
2. Check which exceptions are flagged: identity_exception, address_exception, nns_exception.
3. For Identity and Address exceptions, delegate to the respective agents IN PARALLEL
   by calling consult_identity_agent and/or consult_address_agent with the full case JSON.
4. After Identity and Address are resolved, if nns_exception is True, delegate to the
   NNS agent by calling consult_nns_agent. Include whether identity and address were resolved.
5. Aggregate all agent results into a final report.
6. Compose a SINGLE customer notification summarizing all required actions.

RULES:
- Always pass the FULL case JSON to each agent tool.
- Do NOT skip any flagged exception.
- For NNS, pass identity_resolved and address_resolved based on prior results.
- End your response with a structured summary: case_id, each exception result, overall status,
  and the customer notification text.
"""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_orchestrator(client) -> Agent:
    """Create the orchestrator agent with specialist agents wrapped as tools."""
    identity_agent = create_identity_agent(client)
    address_agent = create_address_agent(client)
    nns_agent = create_nns_agent(client)

    identity_tool = identity_agent.as_tool(
        name="consult_identity_agent",
        description=(
            "Delegates identity verification to the Identity Agent. "
            "Pass the full KYC case JSON. Returns identity verification result."
        ),
    )
    address_tool = address_agent.as_tool(
        name="consult_address_agent",
        description=(
            "Delegates address proof verification to the Address Agent. "
            "Pass the full KYC case JSON. Returns address verification result."
        ),
    )
    nns_tool = nns_agent.as_tool(
        name="consult_nns_agent",
        description=(
            "Delegates Negative News Screening to the NNS Agent. "
            "Pass the full KYC case JSON and include whether identity and "
            "address exceptions have been resolved."
        ),
    )

    return Agent(
        name="orchestrator",
        client=client,
        instructions=ORCHESTRATOR_INSTRUCTIONS,
        tools=[identity_tool, address_tool, nns_tool],
    )
