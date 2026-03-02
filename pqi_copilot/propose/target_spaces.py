"""Curated target spaces for consultant-grade wedge mapping quality."""

from __future__ import annotations

from typing import Any

DENYLIST_PATH_PREFIXES = [
    "Observation.referenceRange.type",
    "Observation.referenceRange.appliesTo",
    "Observation.referenceRange.text",
    "Extension.value",
]

BATCH_LOT_TARGETS = [
    {
        "resourceType": "Medication",
        "elementPath": "Medication.batch.lotNumber",
        "types": ["string"],
        "profileHints": ["Medication-batch-information-drug-pq"],
        "description": "Primary batch/lot anchor",
    },
    {
        "resourceType": "Medication",
        "elementPath": "Medication.identifier.value",
        "types": ["Identifier", "string"],
        "profileHints": ["Medication-batch-information-drug-pq"],
        "description": "Batch identifier fallback",
    },
    {
        "resourceType": "Medication",
        "elementPath": "Medication.batch.expirationDate",
        "types": ["dateTime"],
        "profileHints": ["Medication-batch-information-drug-pq"],
        "description": "Batch timing fields when no PQI extension path is explicit",
    },
    {
        "resourceType": "Medication",
        "elementPath": "Medication.batch.extension",
        "types": ["Extension"],
        "profileHints": ["Medication-batch-information-drug-pq", "Extension-batch"],
        "description": "PQI batch extensions for release/retest/packaging/manufacturing details",
    },
    {
        "resourceType": "Medication",
        "elementPath": "Medication.code.coding.code",
        "types": ["code", "CodeableConcept"],
        "profileHints": ["Medication-batch-information-drug-pq"],
        "description": "Product/batch coded context",
    },
    {
        "resourceType": "Medication",
        "elementPath": "Medication.code.text",
        "types": ["string", "CodeableConcept"],
        "profileHints": ["Medication-batch-information-drug-pq"],
        "description": "Product text context",
    },
]

BATCH_ANALYSIS_TARGETS = [
    {
        "resourceType": "Observation",
        "elementPath": "Observation.code.coding.code",
        "types": ["code", "CodeableConcept"],
        "profileHints": ["Observation-test-result-drug-pq"],
        "description": "Analytical test code",
    },
    {
        "resourceType": "Observation",
        "elementPath": "Observation.code.coding.display",
        "types": ["string", "CodeableConcept"],
        "profileHints": ["Observation-test-result-drug-pq"],
        "description": "Analytical test display",
    },
    {
        "resourceType": "Observation",
        "elementPath": "Observation.code.text",
        "types": ["string", "CodeableConcept"],
        "profileHints": ["Observation-test-result-drug-pq"],
        "description": "Analytical test text",
    },
    {
        "resourceType": "Observation",
        "elementPath": "Observation.valueQuantity.value",
        "types": ["Quantity", "decimal"],
        "profileHints": ["Observation-test-result-drug-pq"],
        "description": "Numeric result value",
    },
    {
        "resourceType": "Observation",
        "elementPath": "Observation.valueQuantity.unit",
        "types": ["Quantity", "string"],
        "profileHints": ["Observation-test-result-drug-pq"],
        "description": "Result unit",
    },
    {
        "resourceType": "Observation",
        "elementPath": "Observation.valueCodeableConcept.text",
        "types": ["CodeableConcept", "string"],
        "profileHints": ["Observation-test-result-drug-pq"],
        "description": "Non-numeric coded result",
    },
    {
        "resourceType": "Observation",
        "elementPath": "Observation.effectiveDateTime",
        "types": ["dateTime"],
        "profileHints": ["Observation-test-result-drug-pq"],
        "description": "Result timestamp",
    },
    {
        "resourceType": "Observation",
        "elementPath": "Observation.method.text",
        "types": ["CodeableConcept", "string"],
        "profileHints": ["Observation-test-result-drug-pq", "ObservationDefinition-test-method-drug-pq"],
        "description": "Analytical method",
    },
    {
        "resourceType": "Observation",
        "elementPath": "Observation.subject.reference",
        "types": ["Reference"],
        "profileHints": ["Observation-test-result-drug-pq"],
        "description": "Reference to batch-level subject (Medication)",
    },
    {
        "resourceType": "Observation",
        "elementPath": "Observation.referenceRange.low.value",
        "types": ["Quantity", "decimal"],
        "profileHints": ["Observation-test-result-drug-pq"],
        "description": "Specification lower limit",
    },
    {
        "resourceType": "Observation",
        "elementPath": "Observation.referenceRange.high.value",
        "types": ["Quantity", "decimal"],
        "profileHints": ["Observation-test-result-drug-pq"],
        "description": "Specification upper limit",
    },
    {
        "resourceType": "DiagnosticReport",
        "elementPath": "DiagnosticReport.code.coding.code",
        "types": ["code", "CodeableConcept"],
        "profileHints": ["DiagnosticReport-analysis-drug-pq"],
        "description": "Analysis report type",
    },
    {
        "resourceType": "DiagnosticReport",
        "elementPath": "DiagnosticReport.result.reference",
        "types": ["Reference"],
        "profileHints": ["DiagnosticReport-analysis-drug-pq"],
        "description": "Report links to observations",
    },
    {
        "resourceType": "DiagnosticReport",
        "elementPath": "DiagnosticReport.effectiveDateTime",
        "types": ["dateTime"],
        "profileHints": ["DiagnosticReport-analysis-drug-pq"],
        "description": "Report effective date",
    },
]


def is_denied_target_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in DENYLIST_PATH_PREFIXES)


def _find_profile_for_target(catalog: dict[str, Any], resource_type: str, profile_hints: list[str]) -> dict[str, Any] | None:
    hints = [h.lower() for h in profile_hints]
    profiles = [
        p
        for p in catalog.get("profiles", [])
        if str(p.get("resourceType", "")).lower() == resource_type.lower()
    ]

    scored: list[tuple[int, dict[str, Any]]] = []
    for profile in profiles:
        haystack = " ".join(str(profile.get(k, "")).lower() for k in ("url", "name", "description"))
        score = sum(1 for hint in hints if hint in haystack)
        if score > 0:
            scored.append((score, profile))

    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], str(item[1].get("url", ""))))
    return scored[0][1]


def curated_targets_for_domain(
    domain: str,
    catalog: dict[str, Any],
    preferred_resource_type: str | None = None,
) -> list[dict[str, Any]]:
    if domain == "batch_lot_information":
        templates = BATCH_LOT_TARGETS
    elif domain == "batch_analysis":
        templates = BATCH_ANALYSIS_TARGETS
    else:
        templates = BATCH_LOT_TARGETS + BATCH_ANALYSIS_TARGETS

    if preferred_resource_type and preferred_resource_type != "REQUIRES_REVIEW":
        filtered = [t for t in templates if t["resourceType"] == preferred_resource_type]
        if filtered:
            templates = filtered

    out: list[dict[str, Any]] = []
    for template in templates:
        path = str(template["elementPath"])
        if is_denied_target_path(path):
            continue

        profile = _find_profile_for_target(
            catalog,
            resource_type=str(template["resourceType"]),
            profile_hints=[str(h) for h in template.get("profileHints", [])],
        )

        binding_url = None
        resolved_types = list(template.get("types", []))
        path_exists_in_profile = False

        if profile:
            elements = {str(e.get("path")): e for e in profile.get("elements", [])}
            path_exists_in_profile = path in elements
            if path_exists_in_profile and elements[path].get("types"):
                resolved_types = [str(t) for t in elements[path].get("types", [])]

            for binding in profile.get("bindings", []):
                if str(binding.get("path")) == path and binding.get("valueSetUrl"):
                    binding_url = str(binding.get("valueSetUrl"))
                    break

        out.append(
            {
                "profileUrl": profile.get("url") if profile and path_exists_in_profile else "BASE_FHIR_R5",
                "resourceType": template["resourceType"],
                "elementPath": path,
                "types": resolved_types,
                "bindingValueSetUrl": binding_url,
                "description": template.get("description", ""),
                "from_curated_target_space": True,
                "path_exists_in_profile": path_exists_in_profile,
            }
        )

    out.sort(key=lambda t: (str(t["resourceType"]), str(t["elementPath"]), str(t["profileUrl"])))
    return out
