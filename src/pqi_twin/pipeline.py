"""End-to-end deterministic PQI MVP pipeline orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .domain_classifier import classify_domains
from .evidence import build_evidence_manifest, hash_output_files
from .generator import generate_bundles
from .governance import govern_and_store
from .ig_loader import load_ig_catalog
from .mapping_recommender import recommend_mappings
from .profiler import profile_input_extracts
from .terminology import build_terminology_scaffold
from .validator import run_validations


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


def run_pipeline(
    ig_asset_path: Path,
    input_dir: Path,
    output_dir: Path,
    governance_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    governance_dir.mkdir(parents=True, exist_ok=True)

    catalog = load_ig_catalog(ig_asset_path)
    _write_json(output_dir / "ig_catalog.json", catalog)

    profile_report = profile_input_extracts(input_dir)
    _write_json(output_dir / "profiling_report.json", profile_report)

    domain_report = classify_domains(profile_report)
    _write_json(output_dir / "domain_classification.json", domain_report)

    mapping_set = recommend_mappings(catalog, profile_report, domain_report)
    _write_json(output_dir / "mapping_proposals.json", mapping_set)

    terminology_set = build_terminology_scaffold(mapping_set, catalog)
    _write_json(output_dir / "terminology_scaffold.json", terminology_set)

    governance_result = govern_and_store(governance_dir, mapping_set, terminology_set)

    mapping_approved_record = governance_result["mapping"]["versions"][-1]
    terminology_approved_record = governance_result["terminology"]["versions"][-1]

    mapping_version_id = (
        f"{mapping_approved_record['artifactId']}@"
        f"{str(mapping_approved_record['contentHash'])[:12]}"
    )
    terminology_version_id = (
        f"{terminology_approved_record['artifactId']}@"
        f"{str(terminology_approved_record['contentHash'])[:12]}"
    )

    input_hashes = {
        table["sourceFile"]: table["fileHash"]
        for table in profile_report.get("tables", [])
        if table.get("sourceFile") and table.get("fileHash")
    }

    generated = generate_bundles(
        input_dir=input_dir,
        catalog=catalog,
        approved_mapping_set=mapping_approved_record["content"],
        mapping_version_id=mapping_version_id,
        terminology_version_id=terminology_version_id,
        input_hashes=input_hashes,
    )

    bundle_dir = output_dir / "bundles"
    bundle_paths: list[Path] = []
    for domain, bundle in sorted(generated["bundles"].items()):
        bundle_path = bundle_dir / f"bundle-{domain.lower()}.json"
        _write_json(bundle_path, bundle)
        bundle_paths.append(bundle_path)

    _write_json(output_dir / "generated_resources.json", generated["resources"])

    validator_report = run_validations(
        catalog=catalog,
        bundle_set=generated,
        terminology_set=terminology_set,
    )
    _write_json(output_dir / "validation_report.json", validator_report)

    bundle_hashes = hash_output_files(bundle_paths)

    evidence_manifest = build_evidence_manifest(
        input_hashes=input_hashes,
        mapping_version=mapping_approved_record,
        terminology_version=terminology_approved_record,
        validator_report=validator_report,
        bundle_hashes=bundle_hashes,
        ig_catalog=catalog,
    )
    _write_json(output_dir / "evidence_manifest.json", evidence_manifest)

    summary = {
        "catalog": output_dir / "ig_catalog.json",
        "profile": output_dir / "profiling_report.json",
        "domains": output_dir / "domain_classification.json",
        "mappings": output_dir / "mapping_proposals.json",
        "terminology": output_dir / "terminology_scaffold.json",
        "validation": output_dir / "validation_report.json",
        "evidence": output_dir / "evidence_manifest.json",
        "bundles": bundle_paths,
        "governance": governance_dir,
    }

    _write_json(
        output_dir / "run_summary.json",
        {k: [str(p) for p in v] if isinstance(v, list) else str(v) for k, v in summary.items()},
    )

    return {
        "paths": summary,
        "mappingVersion": mapping_version_id,
        "terminologyVersion": terminology_version_id,
        "validator": validator_report.get("summary", {}),
    }
