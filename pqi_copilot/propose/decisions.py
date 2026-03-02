"""Decision artifact generation for SME workshops."""

from __future__ import annotations

from typing import Any

from pqi_copilot.common import normalize_token
from pqi_copilot.propose.hard_rules import candidate_question_hint, matched_anchor
from pqi_copilot.propose.mapping import candidate_sort_key


def _source_id(source: dict[str, Any]) -> str:
    return f"{source.get('table')}.{source.get('column')}"


def _decision_reason(source: dict[str, Any], proposal: dict[str, Any], relationships: dict[str, Any]) -> str:
    col = normalize_token(str(source.get("column", "")))
    table = str(source.get("table", ""))
    inferred_type = str(
        (proposal.get("candidates", [{}])[0].get("evidence", {}) or {}).get("inferred_type", "unknown")
    ).lower()
    anchor = matched_anchor(str(source.get("column", "")), {"inferred_type": inferred_type})

    rel_hits = []
    for rel in relationships.get("relationship_proposals", []):
        join = str(rel.get("join", ""))
        if table in join:
            rel_hits.append(join)

    if anchor == "batch_lot_id":
        return (
            f"Field is a likely batch/lot join key; appears in {len(rel_hits)} cross-table join proposals."
        )
    if anchor == "test_code":
        return "Field appears code-like and likely identifies analytical test semantics."
    if anchor == "result_value_numeric":
        return "Field appears to carry analytical result payload that may require units and limits context."
    if anchor == "result_unit":
        return "Field appears to represent unit-of-measure semantics that need controlled coding/UOM treatment."
    if anchor == "process_event_date":
        return "Field appears to represent batch lifecycle timing (manufacturing/packaging/release) requiring extension semantics."
    if anchor == "expiration_date":
        return "Field appears to represent expiration/retest timing requiring regulatory confirmation."
    if anchor == "quantity_value":
        return "Field appears to represent quantitative batch context that should be bound to explicit units."
    if anchor == "material_id":
        return "Field appears to be a material/product identifier requiring business meaning confirmation."
    if "batch" in col or "lot" in col:
        return f"Field contains batch/lot semantics but lacks strong anchor confidence; appears in {len(rel_hits)} joins."
    return "Field has multiple plausible targets requiring SME choice for regulatory intent."


def build_decisions(
    run_id: str,
    mapping_proposals: dict[str, Any],
    relationships: dict[str, Any],
) -> dict[str, Any]:
    decisions = []

    for proposal in mapping_proposals.get("proposals", []):
        if proposal.get("disposition") == "OUT_OF_SCOPE":
            continue

        source = proposal.get("source", {})
        source_id = _source_id(source)
        candidates = sorted(
            proposal.get("candidates", []),
            key=candidate_sort_key,
        )

        top = candidates[0] if candidates else None
        second = candidates[1] if len(candidates) > 1 else None

        ambiguous = bool(top and second and abs(float(top.get("confidence", 0.0)) - float(second.get("confidence", 0.0))) <= 0.10)
        needs_decision = (
            top is None
            or top.get("status") == "REQUIRES_REVIEW"
            or float(top.get("confidence", 0.0)) < 0.65
            or ambiguous
        )

        if not needs_decision:
            continue

        options = []
        for cand in candidates[:3]:
            target = cand.get("target", {})
            options.append(
                {
                    "target": str(target.get("elementPath")),
                    "resourceType": str(target.get("resourceType", "UNKNOWN")),
                    "confidence": round(float(cand.get("confidence", 0.0)), 6),
                    "status": cand.get("status"),
                    "label": cand.get("label"),
                }
            )

        decisions.append(
            {
                "decision_id": "PENDING",
                "source": source_id,
                "why": _decision_reason(source, proposal, relationships),
                "proposed": options,
                "question_for_sme": candidate_question_hint(str(source.get("column", ""))),
            }
        )

    decisions.sort(key=lambda d: tuple(str(d.get("source", ".")).split(".", 1)))
    for idx, decision in enumerate(decisions, start=1):
        decision["decision_id"] = f"D-{idx:03d}"

    return {
        "run_id": run_id,
        "decisions": decisions,
        "summary": {
            "decision_count": len(decisions),
        },
    }
