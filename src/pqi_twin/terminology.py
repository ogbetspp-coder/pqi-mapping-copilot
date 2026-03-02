"""Terminology scaffolding: CodeSystem/ValueSet/ConceptMap recommendations."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .utils import normalize_label, stable_hash_obj


def build_terminology_scaffold(
    mapping_set: dict[str, Any],
    catalog: dict[str, Any],
    namespace: str = "http://example.org/fhir",
) -> dict[str, Any]:
    code_system_url = f"{namespace}/CodeSystem/local-cmc-pqi"
    value_set_url = f"{namespace}/ValueSet/local-cmc-pqi"
    concept_map_url = f"{namespace}/ConceptMap/local-to-pqi"

    concepts_by_code: dict[str, dict[str, Any]] = {}
    mappings: list[dict[str, Any]] = []
    binding_suggestions: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []

    for proposal in mapping_set.get("proposals", []):
        source = proposal.get("source", {})
        column_name = str(source.get("column", ""))
        target = proposal.get("target", {})
        terminology = proposal.get("terminology", {})

        if target.get("resourceType") in {"UNKNOWN", "REQUIRES_REVIEW"}:
            continue

        for suggestion in terminology.get("codingSuggestions", []):
            local_code = normalize_label(suggestion.get("code", "")) or "unknown"
            display = str(suggestion.get("display", "UNKNOWN"))
            system = str(suggestion.get("system", "UNKNOWN"))

            if local_code not in concepts_by_code:
                concepts_by_code[local_code] = {
                    "code": local_code,
                    "display": display,
                    "definition": f"Derived from source column {column_name}",
                    "property": [{"code": "source-column", "valueString": column_name}],
                }

            mappings.append(
                {
                    "code": local_code,
                    "display": display,
                    "targetSystem": system,
                    "targetCode": suggestion.get("code", "UNKNOWN"),
                    "targetDisplay": suggestion.get("display", "UNKNOWN"),
                    "equivalence": "relatedto" if system == "UNKNOWN" else "equivalent",
                }
            )

            recommendations.append(
                {
                    "source": source,
                    "target": {
                        "resourceType": target.get("resourceType"),
                        "elementPath": target.get("elementPath"),
                    },
                    "codeableConcept": {
                        "coding": [
                            {
                                "system": system,
                                "code": suggestion.get("code", "UNKNOWN"),
                                "display": suggestion.get("display", "UNKNOWN"),
                            }
                        ],
                        "text": suggestion.get("display", "UNKNOWN"),
                    },
                    "confidence": proposal.get("confidence", 0.0),
                    "status": "proposed" if proposal.get("needsReview") else "reviewed",
                }
            )

        binding_suggestions.append(
            {
                "profileUrl": target.get("profileUrl", "UNKNOWN"),
                "elementPath": target.get("elementPath", "UNKNOWN"),
                "suggestedValueSet": terminology.get("valueSet", "UNKNOWN"),
                "strength": "required" if proposal.get("confidence", 0.0) >= 0.85 else "preferred",
                "status": "REQUIRES_REVIEW"
                if proposal.get("needsReview")
                else "CANDIDATE",
            }
        )

    concepts = [concepts_by_code[k] for k in sorted(concepts_by_code.keys())]

    code_system = {
        "resourceType": "CodeSystem",
        "id": "local-cmc-pqi",
        "url": code_system_url,
        "version": "0.1.0",
        "status": "draft",
        "content": "complete",
        "name": "LocalCmcPqiCodes",
        "title": "Local CMC to PQI Codes",
        "concept": concepts,
    }

    value_set = {
        "resourceType": "ValueSet",
        "id": "local-cmc-pqi",
        "url": value_set_url,
        "version": "0.1.0",
        "status": "draft",
        "name": "LocalCmcPqiValueSet",
        "compose": {
            "include": [
                {
                    "system": code_system_url,
                    "concept": [{"code": concept["code"], "display": concept["display"]} for concept in concepts],
                }
            ]
        },
    }

    grouped_mappings: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in mappings:
        grouped_mappings[item["code"]].append(item)

    concept_map_elements: list[dict[str, Any]] = []
    for code in sorted(grouped_mappings.keys()):
        targets = grouped_mappings[code]
        grouped_targets: list[dict[str, Any]] = []
        for target in sorted(
            targets,
            key=lambda t: (t["targetSystem"], str(t["targetCode"]), str(t["targetDisplay"])),
        ):
            grouped_targets.append(
                {
                    "code": str(target["targetCode"]),
                    "display": str(target["targetDisplay"]),
                    "equivalence": target["equivalence"],
                    "comment": f"Mapped from local code '{code}'",
                }
            )

        concept_map_elements.append(
            {
                "code": code,
                "target": grouped_targets,
            }
        )

    concept_map = {
        "resourceType": "ConceptMap",
        "id": "local-to-pqi",
        "url": concept_map_url,
        "version": "0.1.0",
        "status": "draft",
        "name": "LocalToPqiConceptMap",
        "group": [
            {
                "source": code_system_url,
                "target": "http://hl7.org/fhir/uv/pharm-quality",
                "element": concept_map_elements,
            }
        ],
    }

    bundle = {
        "codeSystem": code_system,
        "valueSet": value_set,
        "conceptMap": concept_map,
        "bindingSuggestions": sorted(
            binding_suggestions,
            key=lambda b: (b["profileUrl"], b["elementPath"], b["suggestedValueSet"]),
        ),
        "codeableConceptRecommendations": sorted(
            recommendations,
            key=lambda r: (
                str(r["source"].get("table", "")),
                str(r["source"].get("column", "")),
            ),
        ),
    }

    bundle["terminologyVersionId"] = f"term-{stable_hash_obj(bundle)[:12]}"

    catalog_value_sets = [v.get("url") for v in catalog.get("valueSets", []) if isinstance(v.get("url"), str)]
    bundle["knownValueSetsFromPqi"] = sorted(catalog_value_sets)

    return bundle
