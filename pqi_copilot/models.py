"""Core models with pydantic when available, dataclass fallback otherwise."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from pydantic import BaseModel, ConfigDict, Field, field_validator  # type: ignore

    class _Base(BaseModel):
        model_config = ConfigDict(extra="allow")

    class MappingCandidate(_Base):
        target: dict[str, Any]
        transform: dict[str, Any]
        terminology: dict[str, Any]
        confidence: float = Field(ge=0.0, le=1.0)
        evidence: dict[str, Any]
        status: str
        flags: list[str] = Field(default_factory=list)
        label: str | None = None

        @field_validator("status")
        @classmethod
        def check_status(cls, value: str) -> str:
            allowed = {"PROPOSED", "REQUIRES_REVIEW", "APPROVED", "DEPRECATED"}
            if value not in allowed:
                raise ValueError(f"Invalid status: {value}")
            return value

    class MappingProposal(_Base):
        run_id: str
        source: dict[str, str]
        domain: dict[str, Any]
        table_model: dict[str, Any] = Field(default_factory=dict)
        candidates: list[MappingCandidate]

    class MappingProposalSet(_Base):
        proposals: list[MappingProposal]
        summary: dict[str, Any] = Field(default_factory=dict)
        hash: str | None = None

    PYDANTIC_AVAILABLE = True

except Exception:

    @dataclass
    class MappingCandidate:
        target: dict[str, Any]
        transform: dict[str, Any]
        terminology: dict[str, Any]
        confidence: float
        evidence: dict[str, Any]
        status: str
        flags: list[str] = field(default_factory=list)
        label: str | None = None

        def model_dump(self) -> dict[str, Any]:
            return {
                "target": self.target,
                "transform": self.transform,
                "terminology": self.terminology,
                "confidence": self.confidence,
                "evidence": self.evidence,
                "status": self.status,
                "flags": self.flags,
                "label": self.label,
            }

    @dataclass
    class MappingProposal:
        run_id: str
        source: dict[str, str]
        domain: dict[str, Any]
        table_model: dict[str, Any] = field(default_factory=dict)
        candidates: list[MappingCandidate] = field(default_factory=list)

        def model_dump(self) -> dict[str, Any]:
            return {
                "run_id": self.run_id,
                "source": self.source,
                "domain": self.domain,
                "table_model": self.table_model,
                "candidates": [c.model_dump() for c in self.candidates],
            }

    @dataclass
    class MappingProposalSet:
        proposals: list[MappingProposal] = field(default_factory=list)
        summary: dict[str, Any] = field(default_factory=dict)
        hash: str | None = None

        def model_dump(self) -> dict[str, Any]:
            return {
                "proposals": [p.model_dump() for p in self.proposals],
                "summary": self.summary,
                "hash": self.hash,
            }

    PYDANTIC_AVAILABLE = False


def validate_mapping_proposal_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate mapping proposal payload with pydantic if available."""
    if PYDANTIC_AVAILABLE:
        validated = MappingProposalSet.model_validate(payload)
        return validated.model_dump()

    # lightweight fallback
    proposals = payload.get("proposals", [])
    if not isinstance(proposals, list):
        raise ValueError("proposals must be a list")
    for proposal in proposals:
        for key in ("run_id", "source", "domain", "candidates"):
            if key not in proposal:
                raise ValueError(f"proposal missing key: {key}")
        if not isinstance(proposal["candidates"], list):
            raise ValueError("candidates must be a list")
        for candidate in proposal["candidates"]:
            conf = candidate.get("confidence", -1)
            if not isinstance(conf, (int, float)) or conf < 0 or conf > 1:
                raise ValueError("candidate confidence must be between 0 and 1")
            if candidate.get("status") not in {"PROPOSED", "REQUIRES_REVIEW", "APPROVED", "DEPRECATED"}:
                raise ValueError("candidate has invalid status")
    return payload
