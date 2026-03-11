"""Unit tests for the deterministic tool functions (no LLM needed)."""

import json
import pytest

from kyc_automation.models.case import KYCCase, RemediationStatus
from kyc_automation.agents.identity_agent import verify_identity_document as _id_tool
from kyc_automation.agents.address_agent import verify_address_document as _addr_tool
from kyc_automation.agents.nns_agent import run_nns_screening as _nns_tool

# Unwrap the underlying functions from FunctionTool
_verify_identity = _id_tool.func
_verify_address = _addr_tool.func
_run_nns = _nns_tool.func


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_case(**overrides) -> str:
    """Build a minimal KYCCase JSON string."""
    defaults = {
        "case_id": "TEST-001",
        "applicant_name": "Test User",
        "applicant_dob": "1990-01-01",
        "country": "Japan",
        "identity_exception": True,
        "address_exception": True,
        "nns_exception": True,
        "identity_doc": {
            "document_type": "passport",
            "full_name": "Test User",
            "date_of_birth": "1990-01-01",
            "country_of_issue": "Japan",
        },
        "address_doc": {
            "document_type": "utility_bill",
            "full_name": "Test User",
            "address": "123 Test St",
        },
        "supporting_doc": {
            "name_on_document": "Test User",
            "date_of_birth_on_document": "1990-01-01",
            "address_on_document": "123 Test St",
        },
        "nns_result": {"has_potential_match": False},
        "identity_flow": "DeclineFlow",
        "address_flow": "DeclineFlow",
    }
    defaults.update(overrides)
    return json.dumps(defaults)


# ---------------------------------------------------------------------------
# Identity Agent tool tests
# ---------------------------------------------------------------------------

def test_identity_all_pass():
    result = json.loads(_verify_identity(_make_case()))
    assert result["status"] == RemediationStatus.COMPLETED.value


def test_identity_bad_doc_type():
    case = _make_case(identity_doc={
        "document_type": "library_card",
        "full_name": "Test User",
        "date_of_birth": "1990-01-01",
        "country_of_issue": "Japan",
    })
    result = json.loads(_verify_identity(case))
    assert result["status"] == RemediationStatus.SUPPLEMENT_REQUIRED.value


def test_identity_name_mismatch():
    case = _make_case(supporting_doc={
        "name_on_document": "Wrong Name",
        "date_of_birth_on_document": "1990-01-01",
    })
    result = json.loads(_verify_identity(case))
    assert result["status"] == RemediationStatus.SUPPLEMENT_REQUIRED.value
    assert "name mismatch" in result["remediation_action"].lower()


def test_identity_dob_mismatch():
    case = _make_case(supporting_doc={
        "name_on_document": "Test User",
        "date_of_birth_on_document": "1999-12-31",
    })
    result = json.loads(_verify_identity(case))
    assert result["status"] == RemediationStatus.SUPPLEMENT_REQUIRED.value
    assert "DOB" in result["remediation_action"]


# ---------------------------------------------------------------------------
# Address Agent tool tests
# ---------------------------------------------------------------------------

def test_address_all_pass():
    result = json.loads(_verify_address(_make_case()))
    assert result["status"] == RemediationStatus.COMPLETED.value


def test_address_name_mismatch():
    case = _make_case(supporting_doc={
        "name_on_document": "Different Person",
        "address_on_document": "123 Test St",
    })
    result = json.loads(_verify_address(case))
    assert result["status"] == RemediationStatus.SUPPLEMENT_REQUIRED.value


def test_address_mismatch():
    case = _make_case(supporting_doc={
        "name_on_document": "Test User",
        "address_on_document": "999 Other Ave",
    })
    result = json.loads(_verify_address(case))
    assert result["status"] == RemediationStatus.SUPPLEMENT_REQUIRED.value


# ---------------------------------------------------------------------------
# NNS Agent tool tests
# ---------------------------------------------------------------------------

def test_nns_no_match():
    result = json.loads(_run_nns(_make_case(), True, True))
    assert result["status"] == RemediationStatus.COMPLETED.value


def test_nns_potential_match():
    case = _make_case(nns_result={
        "has_potential_match": True,
        "match_details": "Partial match with sanctioned entity",
    })
    result = json.loads(_run_nns(case, True, True))
    assert result["status"] == RemediationStatus.INVESTIGATION_REQUIRED.value
    assert result["escalation_team"] == "APAC"


def test_nns_deferred_identity_unresolved():
    result = json.loads(_run_nns(_make_case(), False, True))
    assert result["status"] == RemediationStatus.PENDING.value
    assert "Identity" in result["remediation_action"]
