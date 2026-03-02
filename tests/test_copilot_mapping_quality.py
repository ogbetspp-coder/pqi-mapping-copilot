from __future__ import annotations

import json
from pathlib import Path

from pqi_copilot.pipeline import propose_run


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
