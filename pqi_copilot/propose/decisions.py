"""Decision artifact generation for SME workshops."""

from __future__ import annotations

from typing import Any

from pqi_copilot.common import normalize_token
from pqi_copilot.propose.hard_rules import candidate_question_hint


def _source_id(source: dict[str, Any]) -> str:
    return f"{source.get('table')}.{source.get('column')}"


def _decision_reason(source: dict[str, Any], proposal: dict[str, Any], relationships: dict[str, Any]) -> str:
    source_id = _source_id(source)
    col = normalize_token(str(source.get("column", "")))
    table = str(source.get("table", ""))

    rel_hits = []
    for rel in relationships.get("relationship_proposals", []):
        join = str(rel.get("join", ""))
        if table in join:
            rel_hits.append(join)

    if "batch" in col or "lot" in col:
        return (
            f"Field appears to be batch identifier; participates in {len(rel_hits)} candidate joins across tables."
        )
    if "test" in col or "assay" in col or "code" in col:
        return "Field appears code-like and likely identifies analytical test semantics."
    if "result" in col or "value" in col:
        return "Field appears to carry analytical result payload that may require units and limits context."
    return "Field has multiple plausible targets requiring SME choice for regulatory intent."


def build_decisions(
    run_id: str,
    mapping_proposals: dict[str, Any],
    relationships: dict[str, Any],
) -> dict[str, Any]:
    decisions = []
    decision_counter = 1

    for proposal in mapping_proposals.get("proposals", []):
        source = proposal.get("source", {})
        source_id = _source_id(source)
        candidates = sorted(
            proposal.get("candidates", []),
            key=lambda c: (-float(c.get("confidence", 0.0)), str(c.get("target", {}).get("elementPath", ""))),
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
                    "confidence": float(cand.get("confidence", 0.0)),
                    "status": cand.get("status"),
                    "label": cand.get("label"),
                }
            )

        decisions.append(
            {
                "decision_id": f"D-{decision_counter:03d}",
                "source": source_id,
                "why": _decision_reason(source, proposal, relationships),
                "proposed": options,
                "question_for_sme": candidate_question_hint(str(source.get("column", ""))),
            }
        )
        decision_counter += 1

    return {
        "run_id": run_id,
        "decisions": decisions,
        "summary": {
            "decision_count": len(decisions),
        },
    }
