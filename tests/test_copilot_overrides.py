from __future__ import annotations

from pathlib import Path

from pqi_copilot.governance.store import approve_run
from pqi_copilot.pipeline import propose_run


def test_manual_overrides_select_explicit_candidate(tmp_path: Path) -> None:
    result = propose_run(Path("data/examples"))
    run_id = result["run_id"]

    rules = tmp_path / "rules.yaml"
    rules.write_text("confidence_threshold: 0.95\nrequire_status_proposed: true\n", encoding="utf-8")

    overrides = tmp_path / "overrides.yaml"
    overrides.write_text(
        "\n".join(
            [
                "overrides:",
                "  lims_results.result_unit:",
                "    select:",
                "      resourceType: Observation",
                "      elementPath: Observation.valueQuantity.unit",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    approved = approve_run(
        run_id=run_id,
        rules_path=rules,
        mapping_name="test-overrides",
        overrides_path=overrides,
    )

    entries = approved["approved"]["entries"]
    target_entry = None
    for entry in entries:
        source = entry.get("source", {})
        if source.get("table") == "lims_results" and source.get("column") == "result_unit":
            target_entry = entry
            break

    assert target_entry is not None
    assert target_entry["status"] == "APPROVED_OVERRIDE"
    assert target_entry["selected"]["target"]["resourceType"] == "Observation"
    assert target_entry["selected"]["target"]["elementPath"] == "Observation.valueQuantity.unit"


def test_unmapped_override_wins_over_auto_approval(tmp_path: Path) -> None:
    result = propose_run(Path("data/examples"))
    run_id = result["run_id"]

    rules = tmp_path / "rules.yaml"
    rules.write_text("confidence_threshold: 0.10\nrequire_status_proposed: true\n", encoding="utf-8")

    overrides = tmp_path / "overrides.yaml"
    overrides.write_text(
        "\n".join(
            [
                "overrides:",
                "  lims_results.test_code:",
                "    action: UNMAPPED",
                "    reason: Deferred until controlled code system selected",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    approved = approve_run(
        run_id=run_id,
        rules_path=rules,
        mapping_name="test-overrides",
        overrides_path=overrides,
    )

    entries = approved["approved"]["entries"]
    target_entry = None
    for entry in entries:
        source = entry.get("source", {})
        if source.get("table") == "lims_results" and source.get("column") == "test_code":
            target_entry = entry
            break

    assert target_entry is not None
    assert target_entry["status"] == "UNMAPPED"
    assert target_entry["selected"] is None
    assert "Deferred until controlled code system selected" in str(target_entry.get("override_reason", ""))
