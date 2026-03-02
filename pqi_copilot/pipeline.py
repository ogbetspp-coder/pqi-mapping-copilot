"""End-to-end local pipeline for propose/report/approve workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pqi_copilot.classify.domain_classifier import classify_domains
from pqi_copilot.classify.resource_classifier import classify_table_resources
from pqi_copilot.common import normalize_token, stable_hash_obj, write_json, write_yaml
from pqi_copilot.governance.store import (
    compute_input_hashes,
    compute_run_id,
    run_dir,
    run_manifest,
    write_run_artifact,
    write_run_text,
)
from pqi_copilot.ig.ig_loader import build_and_save_catalog, load_catalog
from pqi_copilot.ingest.normalize import ingest_folder
from pqi_copilot.profiler.stats import profile_markdown, profile_normalized
from pqi_copilot.propose.decisions import build_decisions
from pqi_copilot.propose.mapping import build_mapping_proposals
from pqi_copilot.propose.relationships import propose_relationships
from pqi_copilot.terminology.scaffold import build_terminology_scaffold
from pqi_copilot.validate.validator import validate_mapping_proposals


def _proposal_filename(proposal: dict[str, Any]) -> str:
    source = proposal.get("source", {})
    table = normalize_token(str(source.get("table", "unknown")))
    column = normalize_token(str(source.get("column", "unknown")))
    return f"{table}__{column}.yaml"


def propose_run(input_dir: Path) -> dict[str, Any]:
    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    catalog = load_catalog()
    input_hashes = compute_input_hashes(input_dir)
    run_id = compute_run_id(input_hashes, str(catalog.get("hash", "")))

    ingested = ingest_folder(input_dir)
    profile = profile_normalized(ingested)
    classification = classify_domains(profile)
    resource_classification = classify_table_resources(profile, classification)
    proposals = build_mapping_proposals(
        run_id,
        profile,
        classification,
        catalog,
        top_k=3,
        resource_classification=resource_classification,
    )
    relationships = propose_relationships(ingested, profile)
    decisions = build_decisions(run_id, proposals, relationships)
    validation = validate_mapping_proposals(proposals)
    terminology = build_terminology_scaffold(run_id, proposals)

    write_run_artifact(run_id, "ingest.json", ingested)
    write_run_artifact(run_id, "profile.json", profile)
    write_run_text(run_id, "profile.md", profile_markdown(profile))
    write_run_artifact(run_id, "domain_classification.json", classification)
    write_run_artifact(run_id, "resource_classification.json", resource_classification)
    write_run_artifact(run_id, "mapping_proposals.json", proposals)
    write_run_artifact(run_id, "relationship_proposals.json", relationships)
    write_run_artifact(run_id, "decisions.json", decisions)
    write_run_artifact(run_id, "validation.json", validation)
    write_run_artifact(run_id, "terminology_scaffold.json", terminology)

    map_dir = run_dir(run_id) / "mapping_proposals"
    for proposal in proposals.get("proposals", []):
        write_yaml(map_dir / _proposal_filename(proposal), proposal)

    manifest = run_manifest(
        run_id=run_id,
        input_hashes=input_hashes,
        ig_catalog_hash=str(catalog.get("hash", "")),
        mapping_proposal_hash=str(proposals.get("hash", stable_hash_obj(proposals))),
    )
    write_run_artifact(run_id, "manifest.json", manifest)

    return {
        "run_id": run_id,
        "run_dir": str(run_dir(run_id)),
        "proposal_count": len(proposals.get("proposals", [])),
        "requires_review": proposals.get("summary", {}).get("requires_review", 0),
        "manifest_hash": manifest.get("manifest_hash"),
    }


def update_manifest_with_outputs(
    run_id: str,
    approved_mapping_version_id: str | None = None,
    terminology_version_id: str | None = None,
    output_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    base = run_dir(run_id)
    manifest_path = base / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    old = manifest_path.read_text(encoding="utf-8")
    import json

    manifest = json.loads(old)
    manifest["approved_mapping_version_id"] = approved_mapping_version_id
    manifest["terminology_version_id"] = terminology_version_id
    manifest["output_hashes"] = dict(sorted((output_hashes or {}).items()))
    manifest["manifest_hash"] = stable_hash_obj({k: v for k, v in manifest.items() if k != "manifest_hash"})
    write_json(manifest_path, manifest)
    return manifest


def ensure_catalog(ig_source: Path | None = None) -> dict[str, Any]:
    return build_and_save_catalog(ig_override=ig_source)
