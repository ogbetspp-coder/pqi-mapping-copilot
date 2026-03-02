"""File-based governance store and run artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pqi_copilot.common import (
    artifacts_root,
    ensure_dir,
    file_sha256,
    read_json,
    read_simple_yaml,
    stable_hash_obj,
    stable_hash_text,
    write_json,
    write_text,
    write_yaml,
)


def runs_root() -> Path:
    return artifacts_root() / "runs"


def library_root() -> Path:
    return artifacts_root() / "library"


def mappings_root() -> Path:
    return library_root() / "mappings"


def terminology_root() -> Path:
    return library_root() / "terminology"


def changelog_path() -> Path:
    return library_root() / "CHANGELOG.md"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_run_id(input_hashes: dict[str, str], ig_catalog_hash: str) -> str:
    seed = {"inputs": dict(sorted(input_hashes.items())), "ig": ig_catalog_hash}
    return f"run-{stable_hash_obj(seed)[:16]}"


def run_dir(run_id: str) -> Path:
    return runs_root() / run_id


def write_run_artifact(run_id: str, name: str, payload: Any) -> Path:
    out = run_dir(run_id) / name
    write_json(out, payload)
    return out


def write_run_text(run_id: str, name: str, text: str) -> Path:
    out = run_dir(run_id) / name
    write_text(out, text)
    return out


def run_manifest(
    run_id: str,
    input_hashes: dict[str, str],
    ig_catalog_hash: str,
    mapping_proposal_hash: str,
    approved_mapping_version_id: str | None = None,
    terminology_version_id: str | None = None,
    output_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    manifest = {
        "run_id": run_id,
        "generated_at_utc": "deterministic",
        "input_hashes": dict(sorted(input_hashes.items())),
        "ig_catalog_hash": ig_catalog_hash,
        "mapping_proposal_hash": mapping_proposal_hash,
        "approved_mapping_version_id": approved_mapping_version_id,
        "terminology_version_id": terminology_version_id,
        "output_hashes": dict(sorted((output_hashes or {}).items())),
        "determinism_contract": "Same inputs + same approved mapping version + same terminology version => identical outputs.",
    }
    manifest["manifest_hash"] = stable_hash_obj(manifest)
    return manifest


def _load_versions(mapping_name: str) -> list[str]:
    base = mappings_root() / mapping_name
    if not base.exists():
        return []
    versions = []
    for child in sorted(base.iterdir()):
        if child.is_dir() and child.name.startswith("v"):
            versions.append(child.name[1:])
    return versions


def _parse_semver(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3:
        return (0, 0, 0)
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        return (0, 0, 0)


def _next_patch_version(existing: list[str]) -> str:
    if not existing:
        return "1.0.0"
    highest = sorted(existing, key=_parse_semver)[-1]
    major, minor, patch = _parse_semver(highest)
    return f"{major}.{minor}.{patch + 1}"


def _proposal_id(proposal: dict[str, Any]) -> str:
    source = proposal.get("source", {})
    return f"{source.get('table', 'unknown')}.{source.get('column', 'unknown')}"


def _load_overrides(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        raise FileNotFoundError(f"Overrides file not found: {path}")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}

    try:
        payload = json.loads(text)
        return payload.get("overrides", {}) if isinstance(payload, dict) else {}
    except Exception:
        pass

    overrides: dict[str, Any] = {}
    current_source: str | None = None
    in_select = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if "#" in raw_line:
            raw_line = raw_line.split("#", 1)[0]
        if not raw_line.strip():
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if line == "overrides:":
            continue

        if indent == 2 and line.endswith(":"):
            current_source = line[:-1].strip().strip("'\"")
            overrides[current_source] = {}
            in_select = False
            continue

        if indent == 4 and line.startswith("select:") and current_source:
            overrides[current_source]["select"] = {}
            in_select = True
            continue

        if indent == 4 and current_source and ":" in line and not line.startswith("select:"):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            overrides[current_source][key] = value
            continue

        if indent >= 6 and in_select and current_source and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            overrides[current_source]["select"][key] = value

    return overrides


def approve_run(
    run_id: str,
    rules_path: Path,
    mapping_name: str,
    overrides_path: Path | None = None,
) -> dict[str, Any]:
    run_path = run_dir(run_id)
    proposals_path = run_path / "mapping_proposals.json"
    if not proposals_path.exists():
        raise FileNotFoundError(f"No mapping proposals found at {proposals_path}")

    rules = read_simple_yaml(rules_path)
    threshold = float(rules.get("confidence_threshold", 0.75))
    require_proposed = bool(rules.get("require_status_proposed", True))
    overrides = _load_overrides(overrides_path)

    proposals_payload = read_json(proposals_path)
    approved_entries = []
    decisions_required = []
    overrides_applied = []

    for proposal in sorted(
        proposals_payload.get("proposals", []),
        key=lambda p: (
            str(p.get("source", {}).get("table", "")),
            str(p.get("source", {}).get("column", "")),
        ),
    ):
        source_id = _proposal_id(proposal)
        candidates = proposal.get("candidates", [])

        override = overrides.get(source_id, {})
        if isinstance(override, dict):
            action = str(override.get("action", "")).upper()
            if action == "UNMAPPED":
                reason = str(override.get("reason", "Manual override marked as UNMAPPED"))
                overrides_applied.append({"source": source_id, "action": "UNMAPPED", "reason": reason})
                decisions_required.append(
                    {
                        "source": proposal.get("source"),
                        "reason": reason,
                        "status": "UNMAPPED",
                    }
                )
                approved_entries.append(
                    {
                        "source": proposal.get("source"),
                        "status": "UNMAPPED",
                        "selected": None,
                        "override_reason": reason,
                    }
                )
                continue

        select_target = override.get("select", {}) if isinstance(override, dict) else {}
        if select_target:
            selected = None
            for candidate in candidates:
                target = candidate.get("target", {})
                if (
                    str(target.get("resourceType")) == str(select_target.get("resourceType"))
                    and str(target.get("elementPath")) == str(select_target.get("elementPath"))
                ):
                    selected = candidate
                    break

            if selected is None:
                selected = {
                    "target": {
                        "profileUrl": str(select_target.get("profileUrl", "MANUAL_OVERRIDE")),
                        "resourceType": str(select_target.get("resourceType", "UNKNOWN")),
                        "elementPath": str(select_target.get("elementPath", "UNKNOWN")),
                    },
                    "transform": {"name": "identity", "params": {"manual_override": True}},
                    "terminology": {},
                    "confidence": 1.0,
                    "status": "PROPOSED",
                    "label": "MANUAL_OVERRIDE",
                    "evidence": {"reason": "Selected via approval override"},
                    "flags": ["manual_override_not_in_candidates"],
                }

            overrides_applied.append({"source": source_id, "select": select_target})
            approved_entries.append(
                {
                    "source": proposal.get("source"),
                    "status": "APPROVED_OVERRIDE",
                    "selected": selected,
                }
            )
            continue

        best = None
        for candidate in sorted(candidates, key=lambda c: (-float(c.get("confidence", 0.0)), str(c.get("target")))):
            if require_proposed and candidate.get("status") != "PROPOSED":
                continue
            if float(candidate.get("confidence", 0.0)) < threshold:
                continue
            best = candidate
            break

        if best is None:
            decisions_required.append(
                {
                    "source": proposal.get("source"),
                    "reason": "No candidate meets approval threshold",
                    "status": "UNMAPPED",
                }
            )
            approved_entries.append(
                {
                    "source": proposal.get("source"),
                    "status": "UNMAPPED",
                    "selected": None,
                }
            )
        else:
            approved_entries.append(
                {
                    "source": proposal.get("source"),
                    "status": "APPROVED",
                    "selected": best,
                }
            )

    approved_payload = {
        "lifecycle": "APPROVED",
        "run_id": run_id,
        "mapping_name": mapping_name,
        "approval_rules": rules,
        "overrides_file": str(overrides_path) if overrides_path else None,
        "overrides_applied": overrides_applied,
        "entries": approved_entries,
        "decisions_required": decisions_required,
        "created_at_utc": "deterministic",
    }
    approved_payload["content_hash"] = stable_hash_obj(approved_payload)

    existing_versions = _load_versions(mapping_name)
    # If identical content exists, reuse version id
    for version in existing_versions:
        candidate_path = mappings_root() / mapping_name / f"v{version}" / "approved.yaml"
        if candidate_path.exists():
            raw = candidate_path.read_text(encoding="utf-8")
            if approved_payload["content_hash"] in raw:
                version_id = f"{mapping_name}:v{version}"
                return {
                    "version": version,
                    "version_id": version_id,
                    "path": str(candidate_path),
                    "reused": True,
                    "approved": approved_payload,
                }

    next_version = _next_patch_version(existing_versions)
    version_dir = mappings_root() / mapping_name / f"v{next_version}"
    ensure_dir(version_dir)
    approved_payload["version"] = f"v{next_version}"
    approved_payload["version_id"] = f"{mapping_name}:v{next_version}"
    approved_payload["deterministic_id"] = stable_hash_text(approved_payload["content_hash"] + approved_payload["version"])[:16]

    out_path = version_dir / "approved.yaml"
    if out_path.exists():
        raise FileExistsError(f"Immutable target already exists: {out_path}")
    write_yaml(out_path, approved_payload)
    write_json(version_dir / "approved.json", approved_payload)

    changelog = changelog_path()
    ensure_dir(changelog.parent)
    if not changelog.exists():
        changelog.write_text("# Artifact Library Changelog\n\n", encoding="utf-8")
    with changelog.open("a", encoding="utf-8") as f:
        f.write(
            f"- { _utc_now() }: approved mapping `{mapping_name}` version `v{next_version}` "
            f"from run `{run_id}` (entries={len(approved_entries)}).\n"
        )

    return {
        "version": next_version,
        "version_id": approved_payload["version_id"],
        "path": str(out_path),
        "reused": False,
        "approved": approved_payload,
    }


def list_library() -> dict[str, Any]:
    mappings = []
    map_root = mappings_root()
    if map_root.exists():
        for mapping_name in sorted(p.name for p in map_root.iterdir() if p.is_dir()):
            versions = _load_versions(mapping_name)
            mappings.append({"mapping_name": mapping_name, "versions": [f"v{v}" for v in versions]})

    terminology = []
    term_root = terminology_root()
    if term_root.exists():
        for pack in sorted(p.name for p in term_root.iterdir() if p.is_dir()):
            versions = [p.name for p in sorted((term_root / pack).iterdir()) if p.is_dir()]
            terminology.append({"package": pack, "versions": versions})

    return {
        "mappings": mappings,
        "terminology": terminology,
        "changelog": str(changelog_path()),
    }


def latest_approved_mapping(mapping_name: str) -> dict[str, Any] | None:
    versions = _load_versions(mapping_name)
    if not versions:
        return None
    latest = sorted(versions, key=_parse_semver)[-1]
    json_path = mappings_root() / mapping_name / f"v{latest}" / "approved.json"
    if json_path.exists():
        return read_json(json_path)
    yaml_path = mappings_root() / mapping_name / f"v{latest}" / "approved.yaml"
    if not yaml_path.exists():
        return None
    # Fallback: best-effort tiny YAML parse for top-level keys only.
    return read_simple_yaml(yaml_path)


def compute_input_hashes(input_dir: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(input_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".csv", ".json", ".xml"}:
            continue
        out[str(path.relative_to(input_dir))] = file_sha256(path)
    return out
