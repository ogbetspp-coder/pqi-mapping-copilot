"""Hard mapping constraints for consultant credibility anchors."""

from __future__ import annotations

import re
from typing import Any

from pqi_copilot.common import normalize_token
from pqi_copilot.propose.target_spaces import is_denied_target_path


def _match(patterns: list[re.Pattern[str]], value: str) -> bool:
    return any(p.search(value) for p in patterns)


ANCHOR_PATTERNS = {
    "batch_lot_id": [
        re.compile(r"(^|_)(batch_id|lot|lot_number)(_|$)", re.IGNORECASE),
    ],
    "test_code": [
        re.compile(r"(^|_)(test_code|assay_code|analysis_code|test|assay)(_|$)", re.IGNORECASE),
    ],
    "result_value_numeric": [
        re.compile(r"(^|_)(result_value|value|result)(_|$)", re.IGNORECASE),
    ],
    "result_unit": [
        re.compile(r"(^|_)(result_unit|unit|uom|units)(_|$)", re.IGNORECASE),
    ],
}


def hard_rule_context(source_column: str, stats: dict[str, Any]) -> dict[str, Any]:
    column = normalize_token(source_column)
    inferred_type = str(stats.get("inferred_type", "unknown")).lower()

    context = {
        "anchor": None,
        "required_paths": set(),
        "boost_by_path": {},
        "ban_prefixes": ["Observation.referenceRange.type", "Extension.value"],
        "notes": [],
    }

    if _match(ANCHOR_PATTERNS["batch_lot_id"], column):
        context["anchor"] = "batch_lot_id"
        context["required_paths"] = {
            "Medication.batch.lotNumber",
            "Medication.identifier.value",
            "Observation.subject.reference",
        }
        context["boost_by_path"] = {
            "Medication.batch.lotNumber": 0.28,
            "Observation.subject.reference": 0.14,
            "Medication.identifier.value": 0.10,
        }
        context["notes"].append("anchor:batch_lot_id")

    if _match(ANCHOR_PATTERNS["test_code"], column):
        context["anchor"] = "test_code"
        context["required_paths"] = {
            "Observation.code.coding.code",
            "Observation.code.text",
            "DiagnosticReport.code.coding.code",
        }
        context["boost_by_path"] = {
            "Observation.code.coding.code": 0.25,
            "Observation.code.text": 0.12,
        }
        context["notes"].append("anchor:test_code")

    if _match(ANCHOR_PATTERNS["result_unit"], column):
        context["anchor"] = "result_unit"
        context["required_paths"] = {
            "Observation.valueQuantity.unit",
        }
        context["boost_by_path"] = {
            "Observation.valueQuantity.unit": 0.24,
        }
        context["notes"].append("anchor:result_unit")

    if _match(ANCHOR_PATTERNS["result_value_numeric"], column) and inferred_type == "number":
        context["anchor"] = "result_value_numeric"
        context["required_paths"] = {
            "Observation.valueQuantity.value",
            "Observation.valueCodeableConcept.text",
        }
        context["boost_by_path"] = {
            "Observation.valueQuantity.value": 0.30,
            "Observation.valueCodeableConcept.text": 0.05,
        }
        context["notes"].append("anchor:result_value_numeric")

    return context


def apply_hard_rules(
    source_column: str,
    stats: dict[str, Any],
    candidate: dict[str, Any],
    confidence: float,
) -> tuple[float, list[str], bool, bool]:
    """Returns (confidence, notes, banned, filtered_by_required)."""
    context = hard_rule_context(source_column, stats)
    path = str(candidate.get("elementPath", ""))

    notes: list[str] = []

    if is_denied_target_path(path):
        notes.append("denylist:structural_noise")
        return 0.0, notes, True, False

    for prefix in context.get("ban_prefixes", []):
        if path.startswith(prefix):
            notes.append(f"ban_prefix:{prefix}")
            return 0.0, notes, True, False

    required_paths = context.get("required_paths", set())
    if required_paths and path not in required_paths:
        notes.append("filtered_by_required_anchor_set")
        return confidence, notes, False, True

    boost = float(context.get("boost_by_path", {}).get(path, 0.0))
    if boost > 0:
        confidence = min(1.0, round(confidence + boost, 6))
        notes.append(f"boost:{path}(+{boost})")

    if context.get("anchor"):
        notes.append(f"anchor_applied:{context['anchor']}")

    return confidence, notes, False, False


def candidate_question_hint(source_column: str) -> str:
    col = normalize_token(source_column)
    if _match(ANCHOR_PATTERNS["batch_lot_id"], col):
        return "Is this the regulatory lot number or an internal batch surrogate?"
    if _match(ANCHOR_PATTERNS["test_code"], col):
        return "Which controlled code system should represent this test code?"
    if _match(ANCHOR_PATTERNS["result_unit"], col):
        return "Should this be represented as UCUM-compatible Observation.valueQuantity.unit?"
    if _match(ANCHOR_PATTERNS["result_value_numeric"], col):
        return "Should this value always be numeric Quantity with explicit unit?"
    return "Which target path best matches regulatory intent for this field?"
