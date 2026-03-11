"""Pydantic models for KYC case data and agent responses."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ExceptionType(str, Enum):
    IDENTITY = "Identity"
    ADDRESS = "AddressProof"
    NNS = "NNS"


class RemediationStatus(str, Enum):
    COMPLETED = "Completed"
    SUPPLEMENT_REQUIRED = "SupplementRequired"
    INVESTIGATION_REQUIRED = "InvestigationRequired"
    NOT_REQUIRED = "NotRequired"
    PENDING = "Pending"


class FlowType(str, Enum):
    DECLINE = "DeclineFlow"
    REFER = "ReferFlow"


# ---------------------------------------------------------------------------
# Applicant / Case models
# ---------------------------------------------------------------------------

class ApplicantIdentity(BaseModel):
    """Identity document details submitted by the applicant."""
    document_type: str = Field(description="Type of ID document (e.g. passport, national_id)")
    full_name: str = Field(description="Name as it appears on the ID document")
    date_of_birth: str = Field(description="Date of birth on the ID (YYYY-MM-DD)")
    country_of_issue: str = Field(description="Country that issued the document")


class ApplicantAddress(BaseModel):
    """Address proof document details submitted by the applicant."""
    document_type: str = Field(description="Type of address document (e.g. utility_bill, bank_statement)")
    full_name: str = Field(description="Name on the address document")
    address: str = Field(description="Address on the document")


class SupportingDocument(BaseModel):
    """A supporting document reference submitted with the application."""
    name_on_document: str
    date_of_birth_on_document: Optional[str] = None
    address_on_document: Optional[str] = None


class NNSResult(BaseModel):
    """Result from a negative news screening service."""
    has_potential_match: bool = False
    match_details: Optional[str] = None


class KYCCase(BaseModel):
    """A single KYC onboarding case with exception flags."""
    case_id: str
    applicant_name: str
    applicant_dob: str = Field(description="Applicant date of birth (YYYY-MM-DD)")
    country: str = Field(description="Country of the identity document")

    # Exception flags — True means this exception is present on the case
    identity_exception: bool = False
    address_exception: bool = False
    nns_exception: bool = False

    # Document data
    identity_doc: Optional[ApplicantIdentity] = None
    address_doc: Optional[ApplicantAddress] = None
    supporting_doc: Optional[SupportingDocument] = None
    nns_result: Optional[NNSResult] = None

    # Flow type for each exception
    identity_flow: FlowType = FlowType.DECLINE
    address_flow: FlowType = FlowType.DECLINE


# ---------------------------------------------------------------------------
# Agent response models
# ---------------------------------------------------------------------------

class AgentResult(BaseModel):
    """Standard result returned by each specialist agent."""
    exception_type: ExceptionType
    status: RemediationStatus
    steps_executed: list[str] = Field(default_factory=list)
    remediation_action: Optional[str] = None
    escalation_team: Optional[str] = None


class OrchestratorReport(BaseModel):
    """Aggregated report produced by the orchestrator."""
    case_id: str
    results: list[AgentResult] = Field(default_factory=list)
    overall_status: str = "Pending"
    customer_notification: Optional[str] = None
