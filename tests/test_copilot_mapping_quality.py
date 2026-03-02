from __future__ import annotations

import json
from pathlib import Path

from pqi_copilot.pipeline import propose_run
from pqi_copilot.report.render import render_report_files


def _proposal_index(payload: dict) -> dict[tuple[str, str], dict]:
    out = {}
    for proposal in payload.get("proposals", []):
        source = proposal.get("source", {})
        out[(str(source.get("table")), str(source.get("column")))] = proposal
    return out


def test_anchor_batch_columns_do_not_drift_to_noise_targets() -> None:
    result = propose_run(Path("data/examples"))
    payload = json.loads((Path(result["run_dir"]) / "mapping_proposals.json").read_text(encoding="utf-8"))
    idx = _proposal_index(payload)

    sap_batch_id = idx[("sap_batch", "batch_id")]["candidates"][0]
    sap_lot = idx[("sap_batch", "lot_number")]["candidates"][0]
    mes_batch = idx[("mes_steps", "batch_id")]["candidates"][0]
    lims_batch = idx[("lims_results", "batch_id")]["candidates"][0]

    assert sap_batch_id["target"]["elementPath"] == "Medication.batch.lotNumber"
    assert sap_lot["target"]["elementPath"] == "Medication.batch.lotNumber"
    assert mes_batch["target"]["elementPath"] == "Medication.batch.lotNumber"

    # Nearest curated equivalent for analysis-table batch link.
    assert lims_batch["target"]["elementPath"] in {
        "Medication.batch.lotNumber",
        "Observation.subject.reference",
    }

    for proposal in payload.get("proposals", []):
        source_col = proposal.get("source", {}).get("column")
        if source_col not in {"batch_id", "lot_number"}:
            continue
        for candidate in proposal.get("candidates", []):
            assert candidate.get("target", {}).get("elementPath") != "Observation.referenceRange.type"


def test_batch_lifecycle_dates_and_quantities_require_extension_review() -> None:
    result = propose_run(Path("data/examples"))
    payload = json.loads((Path(result["run_dir"]) / "mapping_proposals.json").read_text(encoding="utf-8"))
    idx = _proposal_index(payload)

    for col in ("manufacturing_date", "packaging_date", "release_date"):
        cand = idx[("sap_batch", col)]["candidates"][0]
        assert cand["target"]["elementPath"] == "Medication.batch.extension"
        assert cand["status"] == "REQUIRES_REVIEW"

    qty = idx[("sap_batch", "batch_quantity")]["candidates"][0]
    assert qty["target"]["elementPath"] == "Medication.batch.extension"
    assert "date" not in qty["target"]["elementPath"].lower()


def test_analysis_time_prefers_observation_effective_datetime() -> None:
    result = propose_run(Path("data/examples"))
    payload = json.loads((Path(result["run_dir"]) / "mapping_proposals.json").read_text(encoding="utf-8"))
    idx = _proposal_index(payload)

    analysis_time = idx[("lims_results", "analysis_time")]["candidates"][0]
    assert analysis_time["target"]["elementPath"] == "Observation.effectiveDateTime"
    assert analysis_time["confidence"] >= 0.65


def test_out_of_scope_tables_emit_out_of_scope_non_anchor() -> None:
    result = propose_run(Path("data/examples"))
    payload = json.loads((Path(result["run_dir"]) / "mapping_proposals.json").read_text(encoding="utf-8"))

    target = None
    for proposal in payload.get("proposals", []):
        src = proposal.get("source", {})
        if src.get("table") == "qms_deviations" and src.get("column") == "status":
            target = proposal
            break

    assert target is not None
    assert target.get("disposition") == "OUT_OF_SCOPE"
    top = target["candidates"][0]
    assert top.get("label") == "OUT_OF_SCOPE"
    assert "out_of_scope_non_anchor" in top.get("flags", [])


def test_report_renders_out_of_scope_label() -> None:
    result = propose_run(Path("data/examples"))
    run_id = result["run_id"]
    report_paths = render_report_files(run_id)
    markdown = Path(report_paths["markdown"]).read_text(encoding="utf-8")
    assert "qms_deviations.status" in markdown
    assert "| OUT_OF_SCOPE | 0.00 | OUT_OF_SCOPE | REQUIRES_REVIEW | out_of_scope_non_anchor |" in markdown
