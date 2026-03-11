"""Unit tests for the SOP rules engine."""

import pytest
from kyc_automation.rules.engine import SOPRulesEngine


@pytest.fixture
def engine():
    return SOPRulesEngine()


def test_load_rules(engine):
    assert "Identity" in engine.raw
    assert "AddressProof" in engine.raw
    assert "NNS" in engine.raw


def test_get_identity_decline_flow(engine):
    flow = engine.get_flow("Identity", "DeclineFlow")
    assert len(flow) > 0
    assert flow[0]["step"] == 1


def test_get_identity_refer_flow(engine):
    flow = engine.get_flow("Identity", "ReferFlow")
    assert len(flow) == 1
    assert "Not Required" in flow[0]["action"]


def test_acceptable_identity_documents(engine):
    docs = engine.get_acceptable_documents("Identity")
    assert "passport" in docs
    assert "national_id" in docs


def test_acceptable_address_documents(engine):
    docs = engine.get_acceptable_documents("AddressProof")
    assert "utility_bill" in docs
    assert "bank_statement" in docs


def test_nns_routing_apac(engine):
    assert engine.get_nns_routing_team("Japan") == "APAC"
    assert engine.get_nns_routing_team("India") == "APAC"


def test_nns_routing_emea(engine):
    assert engine.get_nns_routing_team("United Kingdom") == "EMEA"
    assert engine.get_nns_routing_team("Germany") == "EMEA"


def test_nns_routing_americas(engine):
    assert engine.get_nns_routing_team("United States") == "AMERICAS"
    assert engine.get_nns_routing_team("Brazil") == "AMERICAS"


def test_nns_routing_unknown_country(engine):
    assert engine.get_nns_routing_team("Atlantis") == "GLOBAL"


def test_describe_flow_returns_text(engine):
    desc = engine.describe_flow("Identity", "DeclineFlow")
    assert "Step 1" in desc
    assert "Verify" in desc
