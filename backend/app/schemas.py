from pydantic import BaseModel, Field, EmailStr
from typing import Literal
from uuid import UUID
from datetime import date

Employer = Literal["NATIONAL", "VILLE_SAINT_ETIENNE", "SAINT_ETIENNE_METROPOLE"]

class AskRequest(BaseModel):
    employer: Employer
    # Legacy exact date remains supported for existing clients.
    facts_date: str | None = None
    facts_start_date: str | None = None
    facts_end_date: str | None = None
    situation_ongoing: bool = False
    question: str = Field(min_length=8, max_length=5000)
    conversation_id: UUID | None = None

class AskResponse(BaseModel):
    request_id: str
    conversation_id: UUID | None = None
    verification_status: Literal["VERIFIE", "PARTIELLEMENT_VERIFIE", "NON_VERIFIE"]
    answer: str
    clarification_question: str | None = None
    sources: list[dict] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    disclaimer: str = "Information juridique assistée, à valider humainement."
    # Internal metering data; excluded from every public API serialization.
    ai_usage: dict | None = Field(default=None, exclude=True)

class InvitationCreate(BaseModel):
    email: EmailStr
    role: Literal["ORG_ADMIN", "LEGAL_EDITOR", "MEMBER"] = "MEMBER"

class InvitationAccept(BaseModel):
    token: str = Field(min_length=40, max_length=200)

class OrganizationCreate(BaseModel):
    slug: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    legal_name: str = Field(min_length=2, max_length=250)
    display_name: str = Field(min_length=2, max_length=160)


class CollectivityCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=180)

class DocumentMetadata(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    document_type: str = Field(min_length=2, max_length=80)
    collectivity_id: str
    official_number: str | None = Field(default=None, max_length=120)
    official_url: str | None = Field(default=None, max_length=1000)
    adopted_at: date | None = None
    published_at: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None

class DocumentValidationUpdate(BaseModel):
    validation_status: Literal[
        "COLLECTED_UNVERIFIED", "VERIFIED_APPLICABLE",
        "VERIFIED_HISTORICAL", "REPEALED", "REPLACED", "INCOMPLETE"
    ]
    validation_note: str | None = Field(default=None, max_length=2000)

class DocumentMetadataUpdate(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    document_type: str = Field(min_length=2, max_length=80)
    collectivity_id: str
    official_number: str | None = Field(default=None, max_length=120)
    official_url: str | None = Field(default=None, max_length=1000)
    adopted_at: date | None = None
    published_at: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class MemberRoleUpdate(BaseModel):
    role: Literal["ORG_ADMIN", "LEGAL_EDITOR", "MEMBER"]
