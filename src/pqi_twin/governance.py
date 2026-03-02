"""Versioned governance store with immutable approved artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import LIFECYCLE_ORDER
from .utils import ensure_dir, stable_hash_obj


def _lifecycle_index(status: str) -> int:
    if status not in LIFECYCLE_ORDER:
        raise ValueError(f"Unsupported lifecycle state: {status}")
    return LIFECYCLE_ORDER.index(status)


def _artifact_id(kind: str, content: dict[str, Any]) -> str:
    if kind == "mappings":
        seed = [
            {
                "source": p.get("source"),
                "target": p.get("target"),
            }
            for p in content.get("proposals", [])
        ]
    elif kind == "terminology":
        seed = {
            "codeSystem": content.get("codeSystem", {}).get("url"),
            "valueSet": content.get("valueSet", {}).get("url"),
            "conceptMap": content.get("conceptMap", {}).get("url"),
        }
    else:
        seed = content
    digest = stable_hash_obj(seed)[:12]
    return f"{kind}-{digest}"


def _artifact_dir(root: Path, kind: str, artifact_id: str) -> Path:
    return ensure_dir(root / kind / artifact_id)


def _load_versions(artifact_dir: Path) -> list[dict[str, Any]]:
    versions: list[dict[str, Any]] = []
    for file_path in sorted(artifact_dir.glob("v*.json")):
        with file_path.open("r", encoding="utf-8") as f:
            versions.append(json.load(f))
    versions.sort(key=lambda item: int(str(item["version"]).lstrip("v")))
    return versions


def _write_version(artifact_dir: Path, record: dict[str, Any]) -> None:
    version = record["version"]
    path = artifact_dir / f"{version}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, sort_keys=True)


def create_or_reuse_version(
    root: Path,
    kind: str,
    content: dict[str, Any],
    status: str,
    changelog: str,
    approvals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if status not in LIFECYCLE_ORDER:
        raise ValueError(f"Invalid status: {status}")

    artifact_id = _artifact_id(kind, content)
    a_dir = _artifact_dir(root, kind, artifact_id)
    existing = _load_versions(a_dir)
    content_hash = stable_hash_obj(content)

    for version in existing:
        if version["contentHash"] == content_hash and version["status"] == status:
            return version

    if existing:
        latest = existing[-1]
        latest_status = latest["status"]
        if latest_status == "approved" and content_hash != latest["contentHash"]:
            next_version_num = int(str(latest["version"]).lstrip("v")) + 1
        elif _lifecycle_index(status) < _lifecycle_index(latest_status):
            next_version_num = int(str(latest["version"]).lstrip("v")) + 1
        else:
            next_version_num = int(str(latest["version"]).lstrip("v")) + 1
        previous_version = latest["version"]
    else:
        next_version_num = 1
        previous_version = None

    record = {
        "artifactId": artifact_id,
        "artifactKind": kind,
        "version": f"v{next_version_num}",
        "previousVersion": previous_version,
        "status": status,
        "contentHash": content_hash,
        "content": content,
        "changelog": changelog,
        "approvals": approvals or [],
    }

    _write_version(a_dir, record)
    return record


def apply_mapping_governance(
    mapping_set: dict[str, Any],
    approve_threshold: float = 0.8,
    review_threshold: float = 0.4,
) -> dict[str, Any]:
    governed = json.loads(json.dumps(mapping_set))

    for proposal in governed.get("proposals", []):
        confidence = float(proposal.get("confidence", 0.0))
        needs_review = bool(proposal.get("needsReview", True))

        if confidence >= approve_threshold and not needs_review:
            proposal["status"] = "approved"
        elif confidence >= review_threshold:
            proposal["status"] = "reviewed"
        else:
            proposal["status"] = "proposed"

    summary = {
        "proposed": 0,
        "reviewed": 0,
        "approved": 0,
        "deprecated": 0,
    }
    for proposal in governed.get("proposals", []):
        summary[proposal["status"]] += 1

    governed["summary"]["lifecycleCounts"] = summary
    return governed


def deprecate_mapping(
    mapping_set: dict[str, Any],
    proposal_id: str,
    reason: str,
) -> dict[str, Any]:
    governed = json.loads(json.dumps(mapping_set))
    for proposal in governed.get("proposals", []):
        if proposal.get("proposalId") == proposal_id:
            proposal["status"] = "deprecated"
            proposal.setdefault("deprecation", {})["reason"] = reason
            break
    return governed


def govern_and_store(
    root: Path,
    mapping_set: dict[str, Any],
    terminology_set: dict[str, Any],
) -> dict[str, Any]:
    governed_mappings = apply_mapping_governance(mapping_set)

    mapping_proposed = create_or_reuse_version(
        root,
        "mappings",
        mapping_set,
        status="proposed",
        changelog="Initial mapping recommendation import",
    )
    mapping_reviewed = create_or_reuse_version(
        root,
        "mappings",
        governed_mappings,
        status="reviewed",
        changelog="Automated triage: proposed->reviewed/approved by confidence",
    )
    mapping_approved = create_or_reuse_version(
        root,
        "mappings",
        governed_mappings,
        status="approved",
        changelog="Approved snapshot for bundle generation",
        approvals=[{"by": "MVP-AUTOMATION", "decision": "approved"}],
    )

    terminology_proposed = create_or_reuse_version(
        root,
        "terminology",
        terminology_set,
        status="proposed",
        changelog="Initial terminology scaffolding",
    )
    terminology_reviewed = create_or_reuse_version(
        root,
        "terminology",
        terminology_set,
        status="reviewed",
        changelog="Terminology reviewed for explicit coding.system/code/display",
    )
    terminology_approved = create_or_reuse_version(
        root,
        "terminology",
        terminology_set,
        status="approved",
        changelog="Approved terminology baseline",
        approvals=[{"by": "MVP-AUTOMATION", "decision": "approved"}],
    )

    return {
        "mapping": {
            "governed": governed_mappings,
            "versions": [mapping_proposed, mapping_reviewed, mapping_approved],
        },
        "terminology": {
            "governed": terminology_set,
            "versions": [terminology_proposed, terminology_reviewed, terminology_approved],
        },
    }
