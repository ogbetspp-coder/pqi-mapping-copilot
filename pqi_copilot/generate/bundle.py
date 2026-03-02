"""Optional minimal bundle generator for wedge scope."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pqi_copilot.common import normalize_token, stable_hash_text
from pqi_copilot.governance.store import latest_approved_mapping, run_dir


def _rid(prefix: str, value: str) -> str:
    return f"{prefix}-{stable_hash_text(value)[:14]}"


def _extract_profiles(approved: dict[str, Any], resource_type: str) -> list[str]:
    urls = []
    for entry in approved.get("entries", []):
        selected = entry.get("selected")
        if not selected:
            continue
        target = selected.get("target", {})
        if target.get("resourceType") != resource_type:
            continue
        url = target.get("profileUrl")
        if isinstance(url, str) and url and url != "BASE_FHIR_R5":
            urls.append(url)
    return sorted(set(urls))


def _find_table_with_columns(ingested: dict[str, Any], required_any: set[str]) -> dict[str, Any] | None:
    best = None
    best_score = -1
    for table in ingested.get("tables", []):
        cols = set()
        for row in table.get("rows", []):
            cols.update(row.keys())
        score = len(required_any & cols)
        if score > best_score:
            best_score = score
            best = table
    return best


def generate_minimal_bundle(run_id: str, mapping_name: str = "batch-lot-analysis") -> dict[str, Any]:
    approved = latest_approved_mapping(mapping_name)
    if not approved:
        raise FileNotFoundError(f"No approved mapping found for '{mapping_name}'")

    ingest_path = run_dir(run_id) / "ingest.json"
    if not ingest_path.exists():
        raise FileNotFoundError(f"Run ingest artifact missing: {ingest_path}")
    import json

    ingested = json.loads(ingest_path.read_text(encoding="utf-8"))

    batch_table = _find_table_with_columns(ingested, {"batch_id", "lot_number", "lot", "batch"})
    analysis_table = _find_table_with_columns(
        ingested,
        {"result", "result_value", "result_code", "test", "test_code", "assay", "batch_id"},
    )

    medications: dict[str, dict[str, Any]] = {}
    observations: list[dict[str, Any]] = []

    for row in (batch_table or {}).get("rows", []):
        batch = row.get("batch_id") or row.get("lot_number") or row.get("lot")
        if not batch:
            continue
        rid = _rid("med", str(batch))
        med = {
            "resourceType": "Medication",
            "id": rid,
            "batch": {"lotNumber": str(batch)},
        }
        profiles = _extract_profiles(approved, "Medication")
        if profiles:
            med["meta"] = {"profile": profiles}
        medications[str(batch)] = med

    for row in (analysis_table or {}).get("rows", []):
        batch = row.get("batch_id") or row.get("lot_number") or row.get("lot") or "UNKNOWN"
        code = row.get("result_code") or row.get("test_code") or row.get("test") or row.get("assay") or "UNKNOWN"
        display = row.get("result") or row.get("result_display") or str(code)
        rid = _rid("obs", f"{batch}|{code}|{display}")

        obs: dict[str, Any] = {
            "resourceType": "Observation",
            "id": rid,
            "status": "final",
            "code": {
                "coding": [
                    {
                        "system": "http://example.org/fhir/CodeSystem/local-cmc-pqi",
                        "code": normalize_token(str(code)) or "unknown",
                        "display": str(display),
                    }
                ],
                "text": str(display),
            },
        }

        if batch in medications:
            obs["subject"] = {"reference": f"Medication/{medications[batch]['id']}"}

        raw_value = row.get("result_value") or row.get("value") or row.get("result")
        unit = row.get("result_unit") or row.get("unit") or row.get("uom")
        try:
            num = float(str(raw_value))
            obs["valueQuantity"] = {"value": num, "unit": unit or "1"}
        except Exception:
            obs["valueCodeableConcept"] = {
                "coding": [
                    {
                        "system": "http://example.org/fhir/CodeSystem/local-cmc-pqi",
                        "code": normalize_token(str(raw_value)) or "unknown",
                        "display": str(raw_value) if raw_value is not None else "UNKNOWN",
                    }
                ],
                "text": str(raw_value) if raw_value is not None else "UNKNOWN",
            }

        when = row.get("analysis_time") or row.get("test_date")
        if when:
            obs["effectiveDateTime"] = str(when)

        profiles = _extract_profiles(approved, "Observation")
        if profiles:
            obs["meta"] = {"profile": profiles}

        observations.append(obs)

    entries = []
    for med in sorted(medications.values(), key=lambda r: r["id"]):
        entries.append({"resource": med})
    for obs in sorted(observations, key=lambda r: r["id"]):
        entries.append({"resource": obs})

    profile_missing = not (_extract_profiles(approved, "Medication") or _extract_profiles(approved, "Observation"))

    bundle = {
        "resourceType": "Bundle",
        "id": _rid("bundle", run_id + mapping_name),
        "type": "collection",
        "entry": entries,
    }

    return {
        "bundle": bundle,
        "generation_manifest": {
            "run_id": run_id,
            "mapping_name": mapping_name,
            "mapping_version": approved.get("version_id") or approved.get("version"),
            "profileMissing": profile_missing,
            "resource_counts": {
                "Medication": len(medications),
                "Observation": len(observations),
            },
        },
    }
