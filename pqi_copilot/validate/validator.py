"""Minimal structural validation interfaces (local-only)."""

from __future__ import annotations

from typing import Any

from pqi_copilot.models import validate_mapping_proposal_payload


def validate_mapping_proposals(payload: dict[str, Any]) -> dict[str, Any]:
    validated = validate_mapping_proposal_payload(payload)
    return {
        "status": "PASS",
        "validated_proposal_count": len(validated.get("proposals", [])),
    }


def validate_bundle_minimal(bundle: dict[str, Any]) -> dict[str, Any]:
    issues = []
    if bundle.get("resourceType") != "Bundle":
        issues.append("resourceType must be Bundle")
    if bundle.get("type") != "collection":
        issues.append("Bundle.type must be collection")
    if not isinstance(bundle.get("entry"), list):
        issues.append("Bundle.entry must be list")

    for idx, entry in enumerate(bundle.get("entry", [])):
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(resource, dict):
            issues.append(f"entry[{idx}] missing resource")
            continue
        if "resourceType" not in resource:
            issues.append(f"entry[{idx}] resource missing resourceType")

    return {
        "status": "PASS" if not issues else "FAIL",
        "issues": issues,
    }
