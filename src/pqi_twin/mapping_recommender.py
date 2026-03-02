"""Generate MappingProposal artifacts from profiling + domain evidence."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from .constants import DEFAULT_CODE_SYSTEMS, FIELD_TO_TARGETS, PROFILE_HINTS
from .ig_loader import find_profile_url
from .utils import normalize_label, stable_hash_obj


def _match_valueset(catalog: dict[str, Any], fragments: list[str]) -> str:
    candidates: list[tuple[int, str]] = []
    for value_set in catalog.get("valueSets", []):
        url = value_set.get("url")
        if not isinstance(url, str):
            continue
        text = " ".join(
            str(value_set.get(k, "")).lower() for k in ("url", "name", "id", "source")
        )
        score = sum(1 for fragment in fragments if fragment.lower() in text)
        if score > 0:
            candidates.append((score, url))
    if not candidates:
        return "UNKNOWN"
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][1]


def _infer_transform(element_path: str, column_profile: dict[str, Any], join_hint: dict[str, Any] | None) -> dict[str, Any]:
    inferred_type = column_profile.get("inferredType", "unknown")
    units = column_profile.get("detectedUnits", [])

    if "Date" in element_path or "date" in element_path:
        return {"function": "parse_date", "params": {"acceptedFormats": ["YYYY-MM-DD", "YYYY-MM"]}}
    if "valueQuantity" in element_path or units:
        return {
            "function": "normalize_quantity",
            "params": {
                "detectedUnits": units,
                "defaultUnit": units[0] if units else "UNKNOWN",
            },
        }
    if join_hint:
        return {
            "function": "join_lookup",
            "params": {
                "left": join_hint["left"],
                "right": join_hint["right"],
                "canonicalKey": join_hint["canonicalKey"],
            },
        }
    if inferred_type in {"integer", "number"}:
        return {"function": "cast_number", "params": {"type": inferred_type}}
    return {"function": "identity", "params": {}}


def _build_coding_suggestions(column_name: str, column_profile: dict[str, Any], domain: str) -> list[dict[str, Any]]:
    normalized = normalize_label(column_name)
    sample_values = column_profile.get("sampleValues", [])

    if "dose" in normalized or "form" in normalized:
        system = DEFAULT_CODE_SYSTEMS["dose_form"]
    elif "route" in normalized:
        system = DEFAULT_CODE_SYSTEMS["route"]
    elif "organization" in normalized or "site" in normalized:
        system = DEFAULT_CODE_SYSTEMS["organization_type"]
    elif "result" in normalized or "test" in normalized or domain == "PQ6":
        system = DEFAULT_CODE_SYSTEMS["test_code"]
    else:
        system = "UNKNOWN"

    suggestions: list[dict[str, Any]] = []
    for value in sample_values[:3]:
        suggestions.append(
            {
                "system": system,
                "code": value if value else "UNKNOWN",
                "display": value if value else "UNKNOWN",
            }
        )
    if not suggestions:
        suggestions.append({"system": system, "code": "UNKNOWN", "display": "UNKNOWN"})
    return suggestions


def _table_domains(domain_report: dict[str, Any]) -> dict[str, list[str]]:
    table_to_domains: dict[str, list[str]] = {}
    for table in domain_report.get("tables", []):
        table_to_domains[str(table.get("table"))] = [str(d) for d in table.get("domains", [])]
    return table_to_domains


def _resource_for_table(table_name: str, table_domains: list[str]) -> str | None:
    normalized = normalize_label(table_name)
    if "product" in normalized or "material" in normalized:
        return "MedicinalProductDefinition"
    if "batch" in normalized:
        return "Medication"
    if "lims" in normalized or "analysis" in normalized or "result" in normalized:
        return "Observation"
    if "organization" in normalized or "site" in normalized:
        return "Organization"

    for _, hint in PROFILE_HINTS.items():
        if hint["domain"] in table_domains:
            for resource_type, resource_hint in PROFILE_HINTS.items():
                if resource_hint == hint:
                    return resource_type
    return None


def _collect_relationships(
    proposals: list[dict[str, Any]],
    joins: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_table_resource: dict[str, set[str]] = defaultdict(set)
    for proposal in proposals:
        if proposal.get("needsReview", True):
            continue
        if float(proposal.get("confidence", 0.0)) < 0.6:
            continue
        table = proposal["source"]["table"]
        resource_type = proposal["target"]["resourceType"]
        if resource_type not in {"UNKNOWN", "REQUIRES_REVIEW"}:
            by_table_resource[table].add(resource_type)

    relationships: list[dict[str, Any]] = []

    for join in joins:
        left_table = join["left"]["table"]
        right_table = join["right"]["table"]

        left_resources = by_table_resource.get(left_table, set())
        right_resources = by_table_resource.get(right_table, set())

        if "Observation" in left_resources and "Medication" in right_resources:
            relationships.append(
                {
                    "fromResource": "Observation",
                    "toResource": "Medication",
                    "referencePath": "Observation.subject.reference",
                    "joinEvidence": deepcopy(join),
                }
            )
        if "Medication" in left_resources and "MedicinalProductDefinition" in right_resources:
            relationships.append(
                {
                    "fromResource": "Medication",
                    "toResource": "MedicinalProductDefinition",
                    "referencePath": "Medication.code.extension[Extension-medication-definition-pq].valueReference",
                    "joinEvidence": deepcopy(join),
                }
            )
        if "Medication" in right_resources and "MedicinalProductDefinition" in left_resources:
            relationships.append(
                {
                    "fromResource": "Medication",
                    "toResource": "MedicinalProductDefinition",
                    "referencePath": "Medication.code.extension[Extension-medication-definition-pq].valueReference",
                    "joinEvidence": deepcopy(join),
                }
            )

    relationships.append(
        {
            "fromResource": "DiagnosticReport",
            "toResource": "Observation",
            "referencePath": "DiagnosticReport.result.reference",
            "joinEvidence": {"reason": "PQI batch analysis/stability pattern"},
        }
    )

    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for rel in relationships:
        key = (rel["fromResource"], rel["toResource"], rel["referencePath"])
        if key not in grouped:
            grouped[key] = {
                "fromResource": rel["fromResource"],
                "toResource": rel["toResource"],
                "referencePath": rel["referencePath"],
                "joinEvidence": [],
            }
        grouped[key]["joinEvidence"].append(rel["joinEvidence"])

    collapsed = []
    for key in sorted(grouped.keys()):
        item = grouped[key]
        item["joinEvidence"] = sorted(
            item["joinEvidence"],
            key=lambda e: stable_hash_obj(e),
        )
        collapsed.append(item)

    return collapsed


def recommend_mappings(
    catalog: dict[str, Any],
    profile_report: dict[str, Any],
    domain_report: dict[str, Any],
) -> dict[str, Any]:
    proposals: list[dict[str, Any]] = []
    joins = profile_report.get("candidateJoins", [])
    table_domain_map = _table_domains(domain_report)

    for table in sorted(profile_report.get("tables", []), key=lambda t: str(t.get("table", ""))):
        table_name = str(table.get("table", ""))
        table_domains = table_domain_map.get(table_name, ["UNKNOWN"])
        fallback_resource = _resource_for_table(table_name, table_domains)

        for column_name, column_profile in sorted(table.get("columns", {}).items()):
            normalized = normalize_label(column_name)
            mapping_rule = FIELD_TO_TARGETS.get(normalized)

            if mapping_rule:
                resource_type, element_path, mapped_domain = mapping_rule
                profile_url = find_profile_url(
                    catalog,
                    PROFILE_HINTS.get(resource_type, {}).get("profile_match", resource_type),
                )
                base_confidence = 0.9
                needs_review = mapped_domain not in table_domains
                domain = [mapped_domain]
            else:
                resource_type = fallback_resource or "UNKNOWN"
                element_path = "UNKNOWN"
                mapped_domain = table_domains[0] if table_domains else "UNKNOWN"
                domain = [mapped_domain]
                profile_url = (
                    find_profile_url(
                        catalog,
                        PROFILE_HINTS.get(resource_type, {}).get("profile_match", resource_type),
                    )
                    if resource_type not in {"UNKNOWN", None}
                    else None
                )
                base_confidence = 0.25 if resource_type != "UNKNOWN" else 0.05
                needs_review = True

            related_joins = [
                join
                for join in joins
                if (
                    join.get("left", {}).get("table") == table_name
                    and join.get("left", {}).get("column") == column_name
                )
                or (
                    join.get("right", {}).get("table") == table_name
                    and join.get("right", {}).get("column") == column_name
                )
            ]

            confidence = base_confidence
            if related_joins:
                confidence += 0.05
            if needs_review:
                confidence -= 0.25
            confidence = round(max(0.0, min(1.0, confidence)), 6)

            value_set = _match_valueset(catalog, [column_name, mapped_domain, resource_type or ""])
            concept_map_url = (
                f"http://example.org/fhir/ConceptMap/local-to-{resource_type.lower()}-{normalized}"
                if resource_type not in {"UNKNOWN", None}
                else "UNKNOWN"
            )

            proposal = {
                "source": {
                    "file": table.get("sourceFile"),
                    "table": table_name,
                    "column": column_name,
                },
                "domain": domain,
                "target": {
                    "profileUrl": profile_url or "UNKNOWN",
                    "resourceType": resource_type or "UNKNOWN",
                    "elementPath": element_path,
                },
                "transform": _infer_transform(
                    element_path,
                    column_profile,
                    related_joins[0] if related_joins else None,
                ),
                "terminology": {
                    "valueSet": value_set,
                    "conceptMap": concept_map_url,
                    "codingSuggestions": _build_coding_suggestions(column_name, column_profile, domain[0]),
                },
                "relationships": [],
                "evidence": {
                    "fileHash": table.get("fileHash"),
                    "profiling": column_profile,
                    "sampleValues": column_profile.get("sampleValues", []),
                    "candidateJoins": related_joins,
                    "provenance": {
                        "source": table.get("sourceFile"),
                        "table": table_name,
                        "column": column_name,
                    },
                },
                "confidence": confidence,
                "status": "proposed",
                "needsReview": needs_review,
            }

            proposal_id = stable_hash_obj(
                {
                    "source": proposal["source"],
                    "target": proposal["target"],
                    "transform": proposal["transform"],
                }
            )[:16]
            proposal["proposalId"] = f"mp-{proposal_id}"
            proposals.append(proposal)

    relationships = _collect_relationships(proposals, joins)

    for proposal in proposals:
        resource_type = proposal["target"]["resourceType"]
        related = [
            rel
            for rel in relationships
            if rel["fromResource"] == resource_type or rel["toResource"] == resource_type
        ]
        proposal["relationships"] = related

    proposals.sort(key=lambda p: (p["source"]["table"], p["source"]["column"], p["proposalId"]))

    return {
        "artifactType": "MappingProposalSet",
        "version": "0.1.0",
        "status": "proposed",
        "proposals": proposals,
        "relationshipGraph": relationships,
        "summary": {
            "proposalCount": len(proposals),
            "needsReviewCount": sum(1 for p in proposals if p.get("needsReview")),
            "highConfidenceCount": sum(1 for p in proposals if p.get("confidence", 0.0) >= 0.8),
        },
    }
