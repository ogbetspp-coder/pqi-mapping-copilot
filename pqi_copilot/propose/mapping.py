"""Evidence-driven mapping proposer constrained by PQI catalog."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pqi_copilot.common import normalize_token, similarity, split_identifier, stable_hash_obj
from pqi_copilot.models import validate_mapping_proposal_payload

TRANSFORM_WHITELIST = {
    "identity",
    "trim_string",
    "parse_date",
    "to_quantity",
    "normalize_codeable_concept",
    "to_reference",
    "join_lookup",
}

SYNONYMS = {
    "batch": {"lot", "batch", "batchid"},
    "lot": {"batch", "lot"},
    "test": {"assay", "test", "method", "analysis"},
    "result": {"value", "result", "outcome"},
    "unit": {"uom", "unit", "units"},
    "spec": {"limit", "criteria", "specification", "spec"},
    "method": {"procedure", "method", "protocol"},
}

WEDGE_KEYWORDS = {
    "batch",
    "lot",
    "analysis",
    "observation",
    "spec",
    "test",
    "result",
}

BASE_FHIR_FALLBACK = [
    {
        "profileUrl": "BASE_FHIR_R5",
        "resourceType": "Medication",
        "elementPath": "Medication.batch.lotNumber",
        "types": ["string"],
        "bindingValueSetUrl": None,
        "description": "Base fallback for batch/lot",
    },
    {
        "profileUrl": "BASE_FHIR_R5",
        "resourceType": "Observation",
        "elementPath": "Observation.valueQuantity.value",
        "types": ["Quantity"],
        "bindingValueSetUrl": None,
        "description": "Base fallback for analytical result value",
    },
    {
        "profileUrl": "BASE_FHIR_R5",
        "resourceType": "Observation",
        "elementPath": "Observation.code.coding.code",
        "types": ["code"],
        "bindingValueSetUrl": None,
        "description": "Base fallback for analytical test code",
    },
]


def _expand_tokens(text: str) -> set[str]:
    tokens = {normalize_token(tok) for tok in split_identifier(text)}
    expanded = set(tokens)
    for token in list(tokens):
        for key, syns in SYNONYMS.items():
            if token == key or token in syns:
                expanded.update(syns)
                expanded.add(key)
    return {t for t in expanded if t}


def _element_candidates(catalog: dict[str, Any], domain: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    domain_keywords = set(WEDGE_KEYWORDS)
    if domain == "batch_lot_information":
        domain_keywords.update({"release", "packaging", "yield", "medication"})
    if domain == "batch_analysis":
        domain_keywords.update({"diagnostic", "report", "specimen", "method"})

    for profile in catalog.get("profiles", []):
        profile_text = " ".join(
            str(profile.get(k, "")).lower() for k in ("url", "name", "description", "resourceType")
        )
        if not any(k in profile_text for k in domain_keywords):
            continue

        bindings = {b.get("path"): b for b in profile.get("bindings", []) if isinstance(b, dict)}
        for element in profile.get("elements", []):
            path = element.get("path")
            if not isinstance(path, str):
                continue
            if path.count(".") < 1:
                continue
            if path.endswith(".id") or path.endswith(".meta"):
                continue

            candidates.append(
                {
                    "profileUrl": profile.get("url"),
                    "resourceType": profile.get("resourceType", "UNKNOWN"),
                    "elementPath": path,
                    "types": element.get("types", []),
                    "bindingValueSetUrl": (bindings.get(path) or {}).get("valueSetUrl"),
                    "description": element.get("short") or element.get("definition") or profile.get("description") or "",
                }
            )

    if not candidates:
        return list(BASE_FHIR_FALLBACK)
    return candidates


def _code_like(stats: dict[str, Any]) -> bool:
    samples = stats.get("sample_values", [])
    if not samples:
        return False
    uppercase_short = [s for s in samples if isinstance(s, str) and s.isupper() and len(s) <= 16]
    return len(uppercase_short) >= max(1, len(samples) // 3)


def _name_similarity(source_col: str, target_path: str, description: str) -> tuple[float, list[str]]:
    source_tokens = _expand_tokens(source_col)
    target_tokens = _expand_tokens(target_path + " " + description)

    overlap = source_tokens & target_tokens
    overlap_score = len(overlap) / max(1, len(source_tokens | target_tokens))
    sim_score = similarity(" ".join(sorted(source_tokens)), " ".join(sorted(target_tokens)))
    score = max(overlap_score, sim_score)
    rationale = [f"token_overlap={sorted(overlap)}", f"text_similarity={round(sim_score, 4)}"]
    return min(1.0, round(score, 6)), rationale


def _datatype_fit(source_type: str, target_types: list[str], target_path: str) -> tuple[float, str]:
    source = (source_type or "").lower()
    targets = {t.lower() for t in target_types}

    if not targets:
        if "date" in target_path.lower():
            targets = {"date", "datetime"}
        elif "quantity" in target_path.lower() or "value" in target_path.lower():
            targets = {"quantity", "decimal", "integer", "codeableconcept"}
        else:
            targets = {"string", "code", "codeableconcept"}

    if source in {"date", "datetime"} and ("date" in targets or "datetime" in targets):
        return 1.0, "date/datetime compatible"
    if source == "number" and ({"quantity", "decimal", "integer"} & targets):
        return 1.0, "numeric compatible"
    if source == "string" and ("string" in targets or "code" in targets or "codeableconcept" in targets):
        return 0.8, "string compatible"
    if source == "unknown":
        return 0.3, "unknown source type"
    return 0.2, "weak type fit"


def _value_pattern_fit(source_col: str, stats: dict[str, Any], target_path: str, target_types: list[str]) -> tuple[float, list[str]]:
    score = 0.0
    fired: list[str] = []
    lower_path = target_path.lower()

    if stats.get("units") and ("quantity" in lower_path or "unit" in lower_path):
        score += 0.5
        fired.append("units->quantity")

    if stats.get("regex_hits", {}).get("batch_like", 0) > 0 and ("batch" in lower_path or "lot" in lower_path):
        score += 0.5
        fired.append("batch_pattern->batch_path")

    if stats.get("inferred_type") in {"date", "datetime"} and ("date" in lower_path or "time" in lower_path):
        score += 0.5
        fired.append("date_type->date_path")

    if _code_like(stats) and (
        "code" in lower_path or "coding" in lower_path or "codeableconcept" in " ".join(target_types).lower()
    ):
        score += 0.5
        fired.append("code_like_values->coded_target")

    if normalize_token(source_col).endswith("id") and ("reference" in lower_path or "identifier" in lower_path):
        score += 0.4
        fired.append("id_column->identifier_or_reference")

    return min(1.0, round(score, 6)), fired


def _binding_fit(stats: dict[str, Any], binding_valueset: str | None, target_path: str) -> tuple[float, str]:
    if binding_valueset:
        if _code_like(stats) or "code" in target_path.lower() or "coding" in target_path.lower():
            return 1.0, "binding available and source appears code-like"
        return 0.6, "binding available but source not clearly code-like"

    if _code_like(stats):
        return 0.4, "code-like source without explicit binding"
    return 0.5, "no binding"


def _select_transform(stats: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    target_path = str(target.get("elementPath", "")).lower()
    source_type = str(stats.get("inferred_type", "unknown"))

    if source_type in {"date", "datetime"}:
        name = "parse_date"
        params = {"accepted_formats": ["YYYY-MM-DD", "YYYY-MM", "ISO-8601"]}
    elif stats.get("units") or "quantity" in target_path:
        name = "to_quantity"
        params = {"units_detected": stats.get("units", [])}
    elif "code" in target_path or "coding" in target_path or "codeableconcept" in target_path:
        name = "normalize_codeable_concept"
        params = {"system_required": True}
    elif "reference" in target_path:
        name = "to_reference"
        params = {"lookup": "REQUIRES_REVIEW"}
    elif source_type == "string":
        name = "trim_string"
        params = {}
    else:
        name = "identity"
        params = {}

    if name not in TRANSFORM_WHITELIST:
        name = "identity"
        params = {}

    return {"name": name, "params": params}


def _domain_lookup(classification: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for table in classification.get("tables", []):
        out[str(table.get("table"))] = {
            "primary": table.get("primary_domain", "REQUIRES_REVIEW"),
            "scores": table.get("domain_scores", {}),
        }
    return out


def build_mapping_proposals(
    run_id: str,
    profile: dict[str, Any],
    classification: dict[str, Any],
    catalog: dict[str, Any],
    top_k: int = 3,
) -> dict[str, Any]:
    domain_by_table = _domain_lookup(classification)
    proposals = []

    for table in sorted(profile.get("tables", []), key=lambda t: str(t.get("table", ""))):
        table_name = str(table.get("table"))
        domain_info = domain_by_table.get(table_name, {"primary": "REQUIRES_REVIEW", "scores": {}})
        primary_domain = domain_info["primary"]
        element_candidates = _element_candidates(catalog, primary_domain)

        for column, stats in sorted(table.get("columns", {}).items()):
            scored_candidates = []

            for target in element_candidates:
                name_score, name_rationale = _name_similarity(
                    column,
                    str(target.get("elementPath", "")),
                    str(target.get("description", "")),
                )
                dtype_score, dtype_reason = _datatype_fit(
                    str(stats.get("inferred_type", "unknown")),
                    [str(t) for t in target.get("types", [])],
                    str(target.get("elementPath", "")),
                )
                value_score, value_reason = _value_pattern_fit(
                    column,
                    stats,
                    str(target.get("elementPath", "")),
                    [str(t) for t in target.get("types", [])],
                )
                binding_score, binding_reason = _binding_fit(
                    stats,
                    target.get("bindingValueSetUrl"),
                    str(target.get("elementPath", "")),
                )

                confidence = round(
                    0.35 * name_score
                    + 0.25 * dtype_score
                    + 0.20 * value_score
                    + 0.20 * binding_score,
                    6,
                )
                status = "PROPOSED" if confidence >= 0.6 else "REQUIRES_REVIEW"

                evidence = {
                    "samples": stats.get("sample_values", [])[:5],
                    "top_values": stats.get("top_values", [])[:5],
                    "inferred_type": stats.get("inferred_type"),
                    "units": stats.get("units", []),
                    "rules_fired": {
                        "name": name_rationale,
                        "datatype": [dtype_reason],
                        "value_pattern": value_reason,
                        "binding": [binding_reason],
                    },
                    "component_scores": {
                        "name_similarity": name_score,
                        "datatype_fit": dtype_score,
                        "value_pattern_fit": value_score,
                        "binding_fit": binding_score,
                    },
                }

                scored_candidates.append(
                    {
                        "target": {
                            "profileUrl": target.get("profileUrl") or "BASE_FHIR_R5",
                            "resourceType": target.get("resourceType", "UNKNOWN"),
                            "elementPath": target.get("elementPath", "UNKNOWN"),
                        },
                        "transform": _select_transform(stats, target),
                        "terminology": {
                            "bindingValueSetUrl": target.get("bindingValueSetUrl"),
                            "conceptMapSuggested": "LOCAL_TO_PQI_REQUIRES_REVIEW"
                            if _code_like(stats)
                            else None,
                        },
                        "confidence": confidence,
                        "evidence": evidence,
                        "status": status,
                    }
                )

            scored_candidates.sort(
                key=lambda c: (
                    -float(c["confidence"]),
                    str(c["target"]["profileUrl"]),
                    str(c["target"]["elementPath"]),
                )
            )

            proposal = {
                "run_id": run_id,
                "source": {
                    "file": str(table.get("source_file")),
                    "table": table_name,
                    "column": column,
                },
                "domain": {
                    "primary": primary_domain,
                    "scores": domain_info.get("scores", {}),
                },
                "candidates": scored_candidates[:top_k],
            }
            proposals.append(proposal)

    payload = {"proposals": proposals}
    payload = validate_mapping_proposal_payload(payload)

    payload["summary"] = {
        "proposal_count": len(payload["proposals"]),
        "requires_review": sum(
            1
            for p in payload["proposals"]
            for c in p.get("candidates", [])
            if c.get("status") == "REQUIRES_REVIEW"
        ),
    }
    payload["hash"] = stable_hash_obj(payload)
    return payload


def proposals_by_source(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for proposal in payload.get("proposals", []):
        table = proposal.get("source", {}).get("table", "")
        column = proposal.get("source", {}).get("column", "")
        index[(str(table), str(column))] = proposal
    return index
