"""SOP rules engine — loads the structured JSON rules and provides
deterministic step-by-step execution for each exception type."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Default path to the bundled rules file
_DEFAULT_RULES_PATH = Path(__file__).resolve().parents[3] / "data" / "sop_rules" / "sop_rules.json"


class SOPRulesEngine:
    """Loads SOP rules from JSON and exposes helpers for agents."""

    def __init__(self, rules_path: str | Path | None = None) -> None:
        path = Path(rules_path) if rules_path else _DEFAULT_RULES_PATH
        with open(path, encoding="utf-8") as f:
            self._rules: dict[str, Any] = json.load(f)

    # -- accessors ----------------------------------------------------------

    @property
    def raw(self) -> dict[str, Any]:
        return self._rules

    def get_flow(self, exception_type: str, flow_type: str) -> list[dict[str, Any]]:
        """Return the list of steps for a given exception type and flow."""
        return self._rules.get(exception_type, {}).get(flow_type, [])

    def get_acceptable_documents(self, exception_type: str) -> list[str]:
        """Return the acceptable document types for an exception category."""
        return self._rules.get("AcceptableDocuments", {}).get(exception_type, [])

    def get_nns_routing_team(self, country: str) -> str:
        """Look up the regional investigation team for a country."""
        routing = self._rules.get("NNS_CountryRouting", {})
        return routing.get(country, "GLOBAL")

    # -- rule descriptions (for agent instructions) -------------------------

    def describe_flow(self, exception_type: str, flow_type: str) -> str:
        """Return a human-readable description of a flow's steps."""
        steps = self.get_flow(exception_type, flow_type)
        if not steps:
            return f"No rules defined for {exception_type}/{flow_type}."
        lines: list[str] = []
        for entry in steps:
            branch = entry.get("branch", "")
            step_num = entry.get("step", "")
            prefix = f"Branch {branch}" if branch else f"Step {step_num}"
            cond = f" [{entry['condition']}]" if "condition" in entry else ""
            action = entry.get("action", "")
            lines.append(f"  {prefix}{cond}: {action}")
            if "if_pass" in entry:
                lines.append(f"    → Pass: go to {entry['if_pass']}")
            if "if_fail" in entry:
                lines.append(f"    → Fail: {entry['if_fail']}")
            if "status" in entry:
                lines.append(f"    → Final status: {entry['status']}")
        return "\n".join(lines)
