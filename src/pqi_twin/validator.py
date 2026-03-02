"""Validation runner: structural, terminology, and business-rule checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _known_profiles(catalog: dict[str, Any]) -> set[str]:
    return {
        str(profile.get("url"))
        for profile in catalog.get("profiles", [])
        if isinstance(profile.get("url"), str)
    }


def _resource_profile(resource: dict[str, Any]) -> list[str]:
    profiles = resource.get("meta", {}).get("profile", [])
    if isinstance(profiles, list):
        return [str(x) for x in profiles if isinstance(x, str)]
    return []


def _find_codings(node: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if "coding" in node and isinstance(node["coding"], list):
            for coding in node["coding"]:
                if isinstance(coding, dict):
                    found.append(coding)
        for value in node.values():
            found.extend(_find_codings(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_find_codings(item))
    return found


def _check_required_profile_elements(
    resource: dict[str, Any],
    profile_url: str,
    catalog: dict[str, Any],
) -> list[str]:
    required_paths: list[str] = []
    for profile in catalog.get("profiles", []):
        if profile.get("url") == profile_url:
            required_paths = profile.get("requiredElements", [])
            break

    missing: list[str] = []
    resource_type = resource.get("resourceType", "")

    for path in required_paths:
        if not path.startswith(f"{resource_type}."):
            continue
        segments = path.split(".")[1:3]
        if not segments:
            continue
        key = segments[0]
        if key.endswith("[x]"):
            prefix = key.replace("[x]", "")
            if not any(k.startswith(prefix) for k in resource.keys()):
                missing.append(path)
            continue
        if key not in resource:
            missing.append(path)

    return sorted(set(missing))


def _business_rule_issues(resource: dict[str, Any], bundle_id: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    rtype = resource.get("resourceType")
    rid = resource.get("id", "UNKNOWN")

    if rtype == "Medication":
        if not resource.get("batch", {}).get("lotNumber"):
            issues.append(
                {
                    "severity": "error",
                    "type": "business-rule",
                    "bundleId": bundle_id,
                    "resource": f"Medication/{rid}",
                    "message": "Medication batch.lotNumber is required for PQ5 batch/lot traceability.",
                }
            )

    if rtype == "Observation":
        if not resource.get("subject", {}).get("reference"):
            issues.append(
                {
                    "severity": "error",
                    "type": "business-rule",
                    "bundleId": bundle_id,
                    "resource": f"Observation/{rid}",
                    "message": "Observation.subject.reference missing for batch linkage.",
                }
            )
        if "valueQuantity" not in resource and "valueCodeableConcept" not in resource:
            issues.append(
                {
                    "severity": "error",
                    "type": "business-rule",
                    "bundleId": bundle_id,
                    "resource": f"Observation/{rid}",
                    "message": "Observation requires value[x] for analytical result payload.",
                }
            )

    if rtype == "DiagnosticReport":
        if not resource.get("result"):
            issues.append(
                {
                    "severity": "error",
                    "type": "business-rule",
                    "bundleId": bundle_id,
                    "resource": f"DiagnosticReport/{rid}",
                    "message": "DiagnosticReport.result must reference one or more Observation resources.",
                }
            )

    return issues


def run_external_validator_stub(bundle_files: list[Path]) -> dict[str, Any]:
    return {
        "status": "SKIPPED",
        "validatorId": "external-fhir-validator-stub",
        "validatorVersion": "TODO",
        "message": "Hook provided; integrate with Java validator_cli.jar in production.",
        "bundleFiles": [str(path) for path in bundle_files],
    }


def run_validations(
    catalog: dict[str, Any],
    bundle_set: dict[str, Any],
    terminology_set: dict[str, Any],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    known_profile_urls = _known_profiles(catalog)

    for domain, bundle in sorted(bundle_set.get("bundles", {}).items()):
        bundle_id = str(bundle.get("id", f"bundle-{domain}"))

        if bundle.get("resourceType") != "Bundle":
            issues.append(
                {
                    "severity": "error",
                    "type": "structural",
                    "bundleId": bundle_id,
                    "resource": "Bundle",
                    "message": "resourceType must be 'Bundle'.",
                }
            )

        if bundle.get("type") != "collection":
            issues.append(
                {
                    "severity": "error",
                    "type": "structural",
                    "bundleId": bundle_id,
                    "resource": "Bundle",
                    "message": "Bundle.type must be 'collection' for PQI exchange bundles.",
                }
            )

        for profile in _resource_profile(bundle):
            if profile not in known_profile_urls:
                issues.append(
                    {
                        "severity": "warning",
                        "type": "structural",
                        "bundleId": bundle_id,
                        "resource": "Bundle",
                        "message": f"Bundle profile not found in local IG catalog: {profile}",
                    }
                )

        entry = bundle.get("entry", [])
        if not isinstance(entry, list) or not entry:
            issues.append(
                {
                    "severity": "error",
                    "type": "structural",
                    "bundleId": bundle_id,
                    "resource": "Bundle",
                    "message": "Bundle.entry must contain at least one resource.",
                }
            )
            continue

        for idx, item in enumerate(entry):
            resource = item.get("resource") if isinstance(item, dict) else None
            if not isinstance(resource, dict):
                issues.append(
                    {
                        "severity": "error",
                        "type": "structural",
                        "bundleId": bundle_id,
                        "resource": f"Bundle.entry[{idx}]",
                        "message": "Bundle.entry item missing resource object.",
                    }
                )
                continue

            resource_type = resource.get("resourceType")
            rid = resource.get("id", "UNKNOWN")
            if not resource_type:
                issues.append(
                    {
                        "severity": "error",
                        "type": "structural",
                        "bundleId": bundle_id,
                        "resource": f"Bundle.entry[{idx}]",
                        "message": "Resource missing resourceType.",
                    }
                )
                continue

            for profile in _resource_profile(resource):
                if profile not in known_profile_urls:
                    issues.append(
                        {
                            "severity": "warning",
                            "type": "structural",
                            "bundleId": bundle_id,
                            "resource": f"{resource_type}/{rid}",
                            "message": f"Resource profile not found in local IG catalog: {profile}",
                        }
                    )
                missing_required = _check_required_profile_elements(resource, profile, catalog)
                if missing_required:
                    issues.append(
                        {
                            "severity": "warning",
                            "type": "structural",
                            "bundleId": bundle_id,
                            "resource": f"{resource_type}/{rid}",
                            "message": f"Missing required profile elements (MVP check): {missing_required[:5]}",
                        }
                    )

            for coding in _find_codings(resource):
                for field in ("system", "code", "display"):
                    if field not in coding or coding[field] in (None, ""):
                        issues.append(
                            {
                                "severity": "error",
                                "type": "terminology",
                                "bundleId": bundle_id,
                                "resource": f"{resource_type}/{rid}",
                                "message": f"Coding missing required '{field}' for explicit CodeableConcept semantics.",
                            }
                        )

            issues.extend(_business_rule_issues(resource, bundle_id))

    binding_suggestions = terminology_set.get("bindingSuggestions", [])
    for binding in binding_suggestions:
        if binding.get("suggestedValueSet") == "UNKNOWN":
            issues.append(
                {
                    "severity": "warning",
                    "type": "terminology",
                    "bundleId": "N/A",
                    "resource": binding.get("profileUrl", "UNKNOWN"),
                    "message": f"Binding unresolved for element {binding.get('elementPath', 'UNKNOWN')}; REQUIRES_REVIEW.",
                }
            )

    issues.sort(key=lambda i: (i["severity"], i["type"], i["bundleId"], i["resource"], i["message"]))

    summary = {
        "validatorId": "local-minimal-fhir-r5-validator",
        "validatorVersion": "0.1.0",
        "issueCount": len(issues),
        "errors": sum(1 for issue in issues if issue["severity"] == "error"),
        "warnings": sum(1 for issue in issues if issue["severity"] == "warning"),
        "status": "PASS" if all(issue["severity"] != "error" for issue in issues) else "FAIL",
    }

    return {
        "summary": summary,
        "issues": issues,
        "externalValidator": run_external_validator_stub([]),
    }
