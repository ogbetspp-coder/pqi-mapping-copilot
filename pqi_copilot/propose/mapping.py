"""Evidence-driven mapping proposer with constrained target spaces and hard rules."""

from __future__ import annotations

from typing import Any

from pqi_copilot.common import normalize_token, similarity, split_identifier, stable_hash_obj
from pqi_copilot.models import validate_mapping_proposal_payload
from pqi_copilot.propose.hard_rules import anchor_domain, apply_hard_rules
from pqi_copilot.propose.target_spaces import curated_targets_for_domain, is_denied_target_path

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
        "from_curated_target_space": False,
    },
    {
        "profileUrl": "BASE_FHIR_R5",
        "resourceType": "Observation",
        "elementPath": "Observation.valueQuantity.value",
        "types": ["Quantity"],
        "bindingValueSetUrl": None,
        "description": "Base fallback for analytical result value",
        "from_curated_target_space": False,
    },
    {
        "profileUrl": "BASE_FHIR_R5",
        "resourceType": "Observation",
        "elementPath": "Observation.code.coding.code",
        "types": ["code"],
        "bindingValueSetUrl": None,
        "description": "Base fallback for analytical test code",
        "from_curated_target_space": False,
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


def _catalog_fallback_candidates(
    catalog: dict[str, Any],
    domain: str,
    preferred_resource_type: str | None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    domain_keywords = set(WEDGE_KEYWORDS)
    if domain == "batch_lot_information":
        domain_keywords.update({"release", "packaging", "yield", "medication"})
    if domain == "batch_analysis":
        domain_keywords.update({"diagnostic", "report", "specimen", "method"})

    for profile in catalog.get("profiles", []):
        resource_type = str(profile.get("resourceType", ""))
        if preferred_resource_type and preferred_resource_type != "REQUIRES_REVIEW":
            if resource_type != preferred_resource_type:
                continue

        profile_text = " ".join(
            str(profile.get(k, "")).lower() for k in ("url", "name", "description", "resourceType")
        )
        if not any(k in profile_text for k in domain_keywords):
            continue

        bindings = {b.get("path"): b for b in profile.get("bindings", []) if isinstance(b, dict)}
        for element in profile.get("elements", []):
            path = str(element.get("path", ""))
            if not path or path.count(".") < 1:
                continue
            if path.endswith(".id") or path.endswith(".meta"):
                continue
            if is_denied_target_path(path):
                continue

            candidates.append(
                {
                    "profileUrl": profile.get("url"),
                    "resourceType": resource_type,
                    "elementPath": path,
                    "types": [str(t) for t in element.get("types", [])],
                    "bindingValueSetUrl": (bindings.get(path) or {}).get("valueSetUrl"),
                    "description": element.get("short")
                    or element.get("definition")
                    or profile.get("description")
                    or "",
                    "from_curated_target_space": False,
                }
            )

    if not candidates:
        return list(BASE_FHIR_FALLBACK)

    candidates.sort(key=lambda c: (str(c.get("resourceType", "")), str(c.get("elementPath", "")), str(c.get("profileUrl", ""))))
    return candidates


def _element_candidates(
    catalog: dict[str, Any],
    domain: str,
    preferred_resource_type: str | None,
) -> list[dict[str, Any]]:
    curated = curated_targets_for_domain(domain, catalog, preferred_resource_type=preferred_resource_type)
    if curated:
        return curated

    fallback = _catalog_fallback_candidates(catalog, domain, preferred_resource_type)
    if fallback:
        return fallback

    return list(BASE_FHIR_FALLBACK)


def _code_like(stats: dict[str, Any]) -> bool:
    samples = stats.get("sample_values", [])
    if not samples:
        return False
    uppercase_short = [s for s in samples if isinstance(s, str) and s.isupper() and len(s) <= 16]
    return len(uppercase_short) >= max(1, len(samples) // 3)


def _name_similarity(source_col: str, target_path: str, description: str) -> tuple[float, list[str], float]:
    source_tokens = _expand_tokens(source_col)
    target_tokens = _expand_tokens(target_path + " " + description)

    overlap = sorted(source_tokens & target_tokens)
    overlap_score = len(overlap) / max(1, len(source_tokens | target_tokens))
    sim_score = similarity(" ".join(sorted(source_tokens)), " ".join(sorted(target_tokens)))
    score = max(overlap_score, sim_score)
    return min(1.0, round(score, 6)), overlap, round(sim_score, 6)


def _datatype_fit(source_type: str, target_types: list[str], target_path: str) -> tuple[float, str]:
    source = (source_type or "").lower()
    targets = {t.lower() for t in target_types}

    if not targets:
        if "date" in target_path.lower() or "time" in target_path.lower():
            targets = {"date", "datetime", "instant"}
        elif "quantity" in target_path.lower() or "value" in target_path.lower():
            targets = {"quantity", "decimal", "integer", "codeableconcept"}
        elif "reference" in target_path.lower():
            targets = {"reference"}
        else:
            targets = {"string", "code", "codeableconcept"}

    if source in {"date", "datetime"} and ("date" in targets or "datetime" in targets or "instant" in targets):
        return 1.0, "date/datetime compatible"
    if source == "number" and ({"quantity", "decimal", "integer"} & targets):
        return 1.0, "numeric compatible"
    if source == "string" and ("string" in targets or "code" in targets or "codeableconcept" in targets):
        return 0.8, "string compatible"
    if source == "string" and "reference" in targets and source.endswith("id"):
        return 0.6, "string id -> reference weak fit"
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


def _resource_lookup(resource_classification: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not resource_classification:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for table in resource_classification.get("tables", []):
        out[str(table.get("table"))] = {
            "primary_resource": table.get("primary_resource", "REQUIRES_REVIEW"),
            "scores": table.get("resource_scores", {}),
            "rationale": table.get("rationale", {}),
        }
    return out


def _calibration_label(confidence: float, status: str, flags: list[str]) -> str:
    if status == "PROPOSED" and confidence >= 0.80 and not flags:
        return "AUTO_APPROVE_CANDIDATE"
    if status == "PROPOSED" and confidence >= 0.65:
        return "GOOD_CANDIDATE"
    return "REQUIRES_SME"


def _unknown_candidate(
    reason: str,
    flags: list[str] | None = None,
    label: str = "REQUIRES_SME",
) -> dict[str, Any]:
    return {
        "target": {
            "profileUrl": "UNKNOWN",
            "resourceType": "UNKNOWN",
            "elementPath": "UNKNOWN",
        },
        "transform": {"name": "identity", "params": {}},
        "terminology": {
            "bindingValueSetUrl": None,
            "conceptMapSuggested": None,
        },
        "confidence": 0.3,
        "evidence": {
            "reason": reason,
            "rules_fired": {},
            "component_scores": {},
        },
        "flags": flags or ["no_viable_candidate"],
        "label": label,
        "status": "REQUIRES_REVIEW",
    }


def build_mapping_proposals(
    run_id: str,
    profile: dict[str, Any],
    classification: dict[str, Any],
    catalog: dict[str, Any],
    top_k: int = 3,
    resource_classification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    domain_by_table = _domain_lookup(classification)
    resource_by_table = _resource_lookup(resource_classification)
    proposals = []

    for table in sorted(profile.get("tables", []), key=lambda t: str(t.get("table", ""))):
        table_name = str(table.get("table"))
        domain_info = domain_by_table.get(table_name, {"primary": "REQUIRES_REVIEW", "scores": {}})
        primary_domain = domain_info["primary"]

        resource_info = resource_by_table.get(
            table_name,
            {
                "primary_resource": "REQUIRES_REVIEW",
                "scores": {},
                "rationale": {},
            },
        )
        primary_resource = str(resource_info.get("primary_resource", "REQUIRES_REVIEW"))

        for column, stats in sorted(table.get("columns", {}).items()):
            effective_domain = primary_domain
            if primary_domain == "out_of_scope":
                inferred_domain = anchor_domain(column, stats)
                if inferred_domain:
                    effective_domain = inferred_domain
                else:
                    proposals.append(
                        {
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
                            "table_model": {
                                "primary_resource": primary_resource,
                                "resource_scores": resource_info.get("scores", {}),
                            },
                            "disposition": "OUT_OF_SCOPE",
                            "candidates": [
                                _unknown_candidate(
                                    reason="Table classified out_of_scope and column has no wedge anchor",
                                    flags=["out_of_scope_non_anchor"],
                                    label="OUT_OF_SCOPE",
                                )
                            ],
                        }
                    )
                    continue

            element_candidates = _element_candidates(catalog, effective_domain, primary_resource)
            scored_candidates = []

            for target in element_candidates:
                target_path = str(target.get("elementPath", ""))
                target_types = [str(t) for t in target.get("types", [])]

                name_score, overlap_tokens, text_similarity = _name_similarity(
                    column,
                    target_path,
                    str(target.get("description", "")),
                )
                dtype_score, dtype_reason = _datatype_fit(
                    str(stats.get("inferred_type", "unknown")),
                    target_types,
                    target_path,
                )
                value_score, value_reason = _value_pattern_fit(
                    column,
                    stats,
                    target_path,
                    target_types,
                )
                binding_score, binding_reason = _binding_fit(
                    stats,
                    target.get("bindingValueSetUrl"),
                    target_path,
                )

                confidence = round(
                    0.35 * name_score
                    + 0.25 * dtype_score
                    + 0.20 * value_score
                    + 0.20 * binding_score,
                    6,
                )

                confidence, hard_notes, hard_banned, filtered_by_required, hard_cap = apply_hard_rules(
                    source_column=column,
                    stats=stats,
                    candidate={
                        "elementPath": target_path,
                        "resourceType": target.get("resourceType"),
                    },
                    confidence=confidence,
                )

                if hard_banned or filtered_by_required:
                    continue

                flags: list[str] = []

                if not bool(target.get("from_curated_target_space", False)):
                    confidence = min(confidence, 0.45)
                    flags.append("outside_curated_target_space_cap_0_45")

                if not overlap_tokens and dtype_score <= 0.4:
                    confidence = min(confidence, 0.55)
                    flags.append("no_token_overlap_and_weak_datatype_cap_0_55")

                if is_denied_target_path(target_path):
                    confidence = min(confidence, 0.30)
                    flags.append("structural_noise_cap_0_30")

                if hard_cap is not None:
                    confidence = min(confidence, hard_cap)
                    flags.append(f"hard_rule_confidence_cap_{hard_cap}")

                confidence = round(max(0.0, min(1.0, confidence)), 6)
                status = "PROPOSED" if confidence >= 0.6 else "REQUIRES_REVIEW"
                label = _calibration_label(confidence, status, flags)

                evidence = {
                    "samples": stats.get("sample_values", [])[:5],
                    "top_values": stats.get("top_values", [])[:5],
                    "inferred_type": stats.get("inferred_type"),
                    "units": stats.get("units", []),
                    "rules_fired": {
                        "name": [
                            f"token_overlap={overlap_tokens}",
                            f"text_similarity={text_similarity}",
                        ],
                        "datatype": [dtype_reason],
                        "value_pattern": value_reason,
                        "binding": [binding_reason],
                        "hard_rules": hard_notes,
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
                            "elementPath": target_path,
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
                        "flags": flags,
                        "label": label,
                        "status": status,
                    }
                )

            scored_candidates.sort(
                key=lambda c: (
                    -float(c["confidence"]),
                    str(c["target"]["resourceType"]),
                    str(c["target"]["elementPath"]),
                    str(c["target"]["profileUrl"]),
                )
            )

            if not scored_candidates:
                scored_candidates = [_unknown_candidate("No candidate remained after hard-rule filtering")]

            proposal = {
                "run_id": run_id,
                "source": {
                    "file": str(table.get("source_file")),
                    "table": table_name,
                    "column": column,
                },
                "domain": {
                    "primary": effective_domain,
                    "scores": domain_info.get("scores", {}),
                },
                "table_model": {
                    "primary_resource": primary_resource,
                    "resource_scores": resource_info.get("scores", {}),
                },
                "disposition": "IN_SCOPE" if primary_domain != "out_of_scope" else "ANCHOR_MAPPED_FROM_OUT_OF_SCOPE",
                "candidates": scored_candidates[:top_k],
            }
            proposals.append(proposal)

    proposals.sort(
        key=lambda p: (
            str(p.get("source", {}).get("table", "")),
            str(p.get("source", {}).get("column", "")),
        )
    )

    payload = {"proposals": proposals}
    payload = validate_mapping_proposal_payload(payload)

    labels = {}
    requires_review = 0
    out_of_scope = 0
    for proposal in payload.get("proposals", []):
        if proposal.get("disposition") == "OUT_OF_SCOPE":
            out_of_scope += 1
        for candidate in proposal.get("candidates", []):
            label = candidate.get("label", "REQUIRES_SME")
            labels[label] = labels.get(label, 0) + 1
            if candidate.get("status") == "REQUIRES_REVIEW":
                requires_review += 1

    payload["summary"] = {
        "proposal_count": len(payload["proposals"]),
        "requires_review": requires_review,
        "label_counts": labels,
        "out_of_scope": out_of_scope,
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
