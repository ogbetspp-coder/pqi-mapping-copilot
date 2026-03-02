"""Optional terminology scaffolding for local mapping packs."""

from __future__ import annotations

from typing import Any

from pqi_copilot.common import normalize_token, stable_hash_obj


def build_terminology_scaffold(run_id: str, proposals: dict[str, Any]) -> dict[str, Any]:
    concepts: dict[str, dict[str, Any]] = {}
    mappings: list[dict[str, Any]] = []

    for proposal in proposals.get("proposals", []):
        source = proposal.get("source", {})
        for candidate in proposal.get("candidates", []):
            if candidate.get("status") != "PROPOSED":
                continue
            terminology = candidate.get("terminology", {})
            if not terminology.get("conceptMapSuggested"):
                continue
            samples = candidate.get("evidence", {}).get("samples", [])
            for sample in samples[:3]:
                code = normalize_token(str(sample)) or "unknown"
                if code not in concepts:
                    concepts[code] = {
                        "code": code,
                        "display": str(sample),
                        "definition": f"Derived from {source.get('table')}.{source.get('column')}",
                    }
                mappings.append(
                    {
                        "source_code": code,
                        "target_profile": candidate.get("target", {}).get("profileUrl"),
                        "target_path": candidate.get("target", {}).get("elementPath"),
                        "binding_valueset": terminology.get("bindingValueSetUrl"),
                    }
                )

    code_system = {
        "resourceType": "CodeSystem",
        "id": f"local-cmc-{run_id}",
        "url": f"http://example.org/fhir/CodeSystem/local-cmc-{run_id}",
        "status": "draft",
        "content": "complete",
        "concept": [concepts[k] for k in sorted(concepts.keys())],
    }

    value_set = {
        "resourceType": "ValueSet",
        "id": f"local-cmc-{run_id}",
        "url": f"http://example.org/fhir/ValueSet/local-cmc-{run_id}",
        "status": "draft",
        "compose": {
            "include": [
                {
                    "system": code_system["url"],
                    "concept": [{"code": c["code"], "display": c["display"]} for c in code_system["concept"]],
                }
            ]
        },
    }

    concept_map = {
        "resourceType": "ConceptMap",
        "id": f"local-to-pqi-{run_id}",
        "url": f"http://example.org/fhir/ConceptMap/local-to-pqi-{run_id}",
        "status": "draft",
        "group": [
            {
                "source": code_system["url"],
                "target": "http://hl7.org/fhir/uv/pharm-quality",
                "element": [
                    {
                        "code": m["source_code"],
                        "target": [
                            {
                                "code": "REQUIRES_REVIEW",
                                "equivalence": "relatedto",
                                "comment": f"Candidate mapping to {m['target_path']}",
                            }
                        ],
                    }
                    for m in mappings
                ],
            }
        ],
    }

    bundle = {
        "run_id": run_id,
        "codeSystem": code_system,
        "valueSet": value_set,
        "conceptMap": concept_map,
        "mappingHints": mappings,
    }
    bundle["terminology_hash"] = stable_hash_obj(bundle)
    return bundle
