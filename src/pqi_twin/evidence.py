"""Evidence manifest generation for deterministic audit trail."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import file_sha256, stable_hash_obj, stable_json_dumps


def hash_output_files(paths: list[Path]) -> dict[str, str]:
    return {str(path): file_sha256(path) for path in sorted(paths, key=lambda p: str(p))}


def build_evidence_manifest(
    input_hashes: dict[str, str],
    mapping_version: dict[str, Any],
    terminology_version: dict[str, Any],
    validator_report: dict[str, Any],
    bundle_hashes: dict[str, str],
    ig_catalog: dict[str, Any],
) -> dict[str, Any]:
    manifest = {
        "manifestType": "PQI-EvidenceManifest",
        "manifestVersion": "0.1.0",
        "ig": {
            "canonical": ig_catalog.get("igCanonical", "UNKNOWN"),
            "package": ig_catalog.get("package", "UNKNOWN"),
            "packageVersion": ig_catalog.get("packageVersion", "UNKNOWN"),
            "fhirVersion": ig_catalog.get("fhirVersion", "UNKNOWN"),
        },
        "inputs": {
            "fileHashes": dict(sorted(input_hashes.items())),
        },
        "governance": {
            "mapping": {
                "artifactId": mapping_version.get("artifactId"),
                "version": mapping_version.get("version"),
                "status": mapping_version.get("status"),
                "contentHash": mapping_version.get("contentHash"),
            },
            "terminology": {
                "artifactId": terminology_version.get("artifactId"),
                "version": terminology_version.get("version"),
                "status": terminology_version.get("status"),
                "contentHash": terminology_version.get("contentHash"),
            },
        },
        "validator": validator_report.get("summary", {}),
        "outputs": {
            "bundleHashes": dict(sorted(bundle_hashes.items())),
        },
        "determinismContract": {
            "statement": "Same inputs + mapping version + terminology version + validator version => identical outputs.",
            "canonicalization": "JSON canonical form with sorted keys and deterministic ordering",
        },
    }

    canonical_manifest = stable_json_dumps(manifest)
    manifest_hash = stable_hash_obj(manifest)

    manifest["canonicalManifestSha256"] = manifest_hash
    manifest["runId"] = f"run-{manifest_hash[:16]}"
    manifest["signatureHooks"] = {
        "algorithm": "SHA-256",
        "canonicalJson": canonical_manifest,
        "signature": None,
        "note": "PKI signing intentionally out-of-scope for MVP; hook provided.",
    }

    return manifest
