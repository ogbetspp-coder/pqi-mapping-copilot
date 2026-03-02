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
    "expiration_date": [
        re.compile(r"(^|_)(exp|expiry|expiration|expire|retest_date|retain_until)(_|$)", re.IGNORECASE),
    ],
    "process_event_date": [
        re.compile(r"(^|_)(manufacturing_date|mfg_date|packaging_date|release_date|pack_date)(_|$)", re.IGNORECASE),
    ],
    "analysis_event_date": [
        re.compile(r"(^|_)(analysis_time|analysis_date|test_date|tested_on)(_|$)", re.IGNORECASE),
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
    "quantity_value": [
        re.compile(r"(^|_)(qty|quantity|amount|volume|weight|mass)(_|$)", re.IGNORECASE),
    ],
    "material_id": [
        re.compile(r"(^|_)(material_id|product_id|item_id)(_|$)", re.IGNORECASE),
    ],
}


def matched_anchor(source_column: str, stats: dict[str, Any]) -> str | None:
    column = normalize_token(source_column)
    inferred_type = str(stats.get("inferred_type", "unknown")).lower()

    if _match(ANCHOR_PATTERNS["process_event_date"], column):
        return "process_event_date"
    if _match(ANCHOR_PATTERNS["expiration_date"], column):
        return "expiration_date"
    if _match(ANCHOR_PATTERNS["analysis_event_date"], column) and inferred_type in {"date", "datetime"}:
        return "analysis_event_date"
    if _match(ANCHOR_PATTERNS["batch_lot_id"], column):
        return "batch_lot_id"
    if _match(ANCHOR_PATTERNS["test_code"], column):
        return "test_code"
    if _match(ANCHOR_PATTERNS["result_unit"], column):
        return "result_unit"
    if _match(ANCHOR_PATTERNS["result_value_numeric"], column) and inferred_type == "number":
        return "result_value_numeric"
    if _match(ANCHOR_PATTERNS["quantity_value"], column):
        return "quantity_value"
    if _match(ANCHOR_PATTERNS["material_id"], column):
        return "material_id"
    return None


def is_anchor_column(source_column: str, stats: dict[str, Any]) -> bool:
    return matched_anchor(source_column, stats) is not None


def anchor_domain(source_column: str, stats: dict[str, Any]) -> str | None:
    anchor = matched_anchor(source_column, stats)
    if anchor in {"test_code", "result_unit", "result_value_numeric", "analysis_event_date"}:
        return "batch_analysis"
    if anchor in {"batch_lot_id", "expiration_date", "process_event_date", "quantity_value", "material_id"}:
        return "batch_lot_information"
    return None


def hard_rule_context(source_column: str, stats: dict[str, Any]) -> dict[str, Any]:
    column = normalize_token(source_column)
    anchor = matched_anchor(source_column, stats)

    context = {
        "anchor": anchor,
        "required_paths": set(),
        "boost_by_path": {},
        "ban_prefixes": ["Observation.referenceRange.type", "Extension.value"],
        "ban_contains": [],
        "ban_exact_paths": set(),
        "confidence_cap": None,
        "notes": [],
    }

    if anchor == "process_event_date":
        context["required_paths"] = {
            "Medication.batch.extension",
        }
        context["boost_by_path"] = {
            "Medication.batch.extension": 0.28,
        }
        context["ban_exact_paths"] = {"Medication.batch.expirationDate"}
        # Date semantics are ambiguous without SME semantics of extension code.
        context["confidence_cap"] = 0.59
        context["notes"].append("anchor:process_event_date")

    if anchor == "expiration_date":
        context["required_paths"] = {
            "Medication.batch.expirationDate",
            "Medication.batch.extension",
        }
        context["boost_by_path"] = {
            "Medication.batch.expirationDate": 0.25,
            "Medication.batch.extension": 0.05,
        }
        context["notes"].append("anchor:expiration_date")

    if anchor == "analysis_event_date":
        context["required_paths"] = {
            "Observation.effectiveDateTime",
            "DiagnosticReport.effectiveDateTime",
        }
        context["boost_by_path"] = {
            "Observation.effectiveDateTime": 0.24,
            "DiagnosticReport.effectiveDateTime": 0.12,
        }
        context["notes"].append("anchor:analysis_event_date")

    if anchor == "batch_lot_id":
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

    if anchor == "test_code":
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

    if anchor == "result_unit":
        context["required_paths"] = {
            "Observation.valueQuantity.unit",
        }
        context["boost_by_path"] = {
            "Observation.valueQuantity.unit": 0.24,
        }
        context["notes"].append("anchor:result_unit")

    if anchor == "result_value_numeric":
        context["required_paths"] = {
            "Observation.valueQuantity.value",
            "Observation.valueCodeableConcept.text",
        }
        context["boost_by_path"] = {
            "Observation.valueQuantity.value": 0.30,
            "Observation.valueCodeableConcept.text": 0.05,
        }
        context["notes"].append("anchor:result_value_numeric")

    if anchor == "quantity_value":
        context["required_paths"] = {
            "Medication.batch.extension",
            "Observation.valueQuantity.value",
            "Observation.valueQuantity.unit",
        }
        context["boost_by_path"] = {
            "Medication.batch.extension": 0.24,
            "Observation.valueQuantity.value": 0.10,
        }
        context["ban_contains"] = ["date", "time"]
        context["notes"].append("anchor:quantity_value")

    if anchor == "material_id":
        context["required_paths"] = {
            "Medication.code.coding.code",
            "Medication.code.text",
            "Medication.identifier.value",
        }
        context["boost_by_path"] = {
            "Medication.code.coding.code": 0.18,
            "Medication.identifier.value": 0.12,
        }
        context["notes"].append("anchor:material_id")

    return context


def apply_hard_rules(
    source_column: str,
    stats: dict[str, Any],
    candidate: dict[str, Any],
    confidence: float,
) -> tuple[float, list[str], bool, bool, float | None]:
    """Returns (confidence, notes, banned, filtered_by_required, confidence_cap)."""
    context = hard_rule_context(source_column, stats)
    path = str(candidate.get("elementPath", ""))
    lower_path = path.lower()

    notes: list[str] = []

    if is_denied_target_path(path):
        notes.append("denylist:structural_noise")
        return 0.0, notes, True, False, None

    for prefix in context.get("ban_prefixes", []):
        if path.startswith(prefix):
            notes.append(f"ban_prefix:{prefix}")
            return 0.0, notes, True, False, None

    for exact in context.get("ban_exact_paths", set()):
        if path == exact:
            notes.append(f"ban_exact:{exact}")
            return 0.0, notes, True, False, None

    for token in context.get("ban_contains", []):
        if token in lower_path:
            notes.append(f"ban_contains:{token}")
            return 0.0, notes, True, False, None

    required_paths = context.get("required_paths", set())
    if required_paths and path not in required_paths:
        notes.append("filtered_by_required_anchor_set")
        return confidence, notes, False, True, None

    boost = float(context.get("boost_by_path", {}).get(path, 0.0))
    if boost > 0:
        confidence = min(1.0, round(confidence + boost, 6))
        notes.append(f"boost:{path}(+{boost})")

    if context.get("anchor"):
        notes.append(f"anchor_applied:{context['anchor']}")

    cap = context.get("confidence_cap")
    return confidence, notes, False, False, float(cap) if cap is not None else None


def candidate_question_hint(source_column: str) -> str:
    col = normalize_token(source_column)
    if _match(ANCHOR_PATTERNS["process_event_date"], col):
        return "Is this manufacturing, packaging, or release timing and which PQI batch extension should capture it?"
    if _match(ANCHOR_PATTERNS["expiration_date"], col):
        return "Does this represent formal expiration/retest date for regulatory batch disposition?"
    if _match(ANCHOR_PATTERNS["analysis_event_date"], col):
        return "Should this timestamp be the observation effective time or report-level effective time?"
    if _match(ANCHOR_PATTERNS["batch_lot_id"], col):
        return "Is this the regulatory lot number or an internal batch surrogate?"
    if _match(ANCHOR_PATTERNS["quantity_value"], col):
        return "Should this quantity be represented in a PQI batch extension with explicit UOM linkage?"
    if _match(ANCHOR_PATTERNS["material_id"], col):
        return "Is this a product code, material master code, or an internal identifier?"
    if _match(ANCHOR_PATTERNS["test_code"], col):
        return "Which controlled code system should represent this test code?"
    if _match(ANCHOR_PATTERNS["result_unit"], col):
        return "Should this be represented as UCUM-compatible Observation.valueQuantity.unit?"
    if _match(ANCHOR_PATTERNS["result_value_numeric"], col):
        return "Should this value always be numeric Quantity with explicit unit?"
    return "Which target path best matches regulatory intent for this field?"
