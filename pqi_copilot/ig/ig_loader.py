"""PQI IG loader and catalog builder (local-first)."""

from __future__ import annotations

import io
import json
import os
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Iterable

from pqi_copilot.common import ensure_dir, stable_hash_obj, write_json

ENV_IG_SOURCE = "PQI_IG_SOURCE"
PRIMARY_PACKAGE = Path("ig/pqi-package.tgz")
SECONDARY_PACKAGE = Path("assets/pqi/package.tgz")
DEFAULT_IG_ZIP = Path("/mnt/data/full-ig.zip")
CATALOG_PATH = Path("artifacts/library/ig_catalog.json")


def _iter_json_from_tar_bytes(blob: bytes) -> Iterable[tuple[str, dict[str, Any]]]:
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        members = sorted((m for m in tf.getmembers() if m.isfile()), key=lambda m: m.name)
        for member in members:
            if not member.name.endswith(".json"):
                continue
            handle = tf.extractfile(member)
            if handle is None:
                continue
            try:
                data = json.loads(handle.read().decode("utf-8"))
            except Exception:
                continue
            if isinstance(data, dict):
                yield member.name, data


def _iter_json_from_tgz(path: Path) -> Iterable[tuple[str, dict[str, Any]]]:
    if not path.exists():
        return
    blob = path.read_bytes()
    yield from _iter_json_from_tar_bytes(blob)


def _iter_json_from_zip(path: Path) -> Iterable[tuple[str, dict[str, Any]]]:
    with zipfile.ZipFile(path, "r") as zf:
        names = sorted(zf.namelist())

        nested_tgzs = [
            name
            for name in names
            if name.endswith("package.tgz") or name.endswith("site/package.tgz")
        ]
        for tgz_name in nested_tgzs:
            try:
                blob = zf.read(tgz_name)
            except Exception:
                continue
            yield from _iter_json_from_tar_bytes(blob)

        for name in names:
            if not name.endswith(".json"):
                continue
            basename = Path(name).name
            if not (
                basename.startswith("StructureDefinition-")
                or basename.startswith("ValueSet-")
                or basename.startswith("CodeSystem-")
                or basename.startswith("ConceptMap-")
                or basename.startswith("ImplementationGuide-")
                or basename == "package.json"
            ):
                continue
            try:
                data = json.loads(zf.read(name).decode("utf-8"))
            except Exception:
                continue
            if isinstance(data, dict):
                yield name, data


def _extract_required_paths(sd: dict[str, Any]) -> list[str]:
    required: set[str] = set()
    for section in ("snapshot", "differential"):
        for element in sd.get(section, {}).get("element", []):
            path = element.get("path")
            min_val = element.get("min", 0)
            if not isinstance(path, str):
                continue
            try:
                min_int = int(min_val)
            except Exception:
                min_int = 0
            if min_int > 0:
                required.add(path)
    return sorted(required)


def _extract_must_support(sd: dict[str, Any]) -> list[str]:
    paths: set[str] = set()
    for section in ("snapshot", "differential"):
        for element in sd.get(section, {}).get("element", []):
            path = element.get("path")
            if element.get("mustSupport") is True and isinstance(path, str):
                paths.add(path)
    return sorted(paths)


def _extract_bindings(sd: dict[str, Any]) -> list[dict[str, str]]:
    out: dict[tuple[str, str, str], dict[str, str]] = {}
    for section in ("snapshot", "differential"):
        for element in sd.get(section, {}).get("element", []):
            path = element.get("path")
            binding = element.get("binding")
            if not isinstance(path, str) or not isinstance(binding, dict):
                continue
            valueset = str(binding.get("valueSet", ""))
            strength = str(binding.get("strength", ""))
            if not valueset:
                continue
            key = (path, valueset, strength)
            out[key] = {"path": path, "valueSetUrl": valueset, "strength": strength}
    return [out[k] for k in sorted(out.keys())]


def _extract_elements(sd: dict[str, Any]) -> list[dict[str, Any]]:
    dedup: dict[str, dict[str, Any]] = {}
    for section in ("snapshot", "differential"):
        for element in sd.get(section, {}).get("element", []):
            path = element.get("path")
            if not isinstance(path, str):
                continue
            if path in dedup:
                continue
            type_codes = [
                t.get("code") for t in element.get("type", []) if isinstance(t, dict) and t.get("code")
            ]
            dedup[path] = {
                "path": path,
                "min": int(element.get("min", 0)) if str(element.get("min", "0")).isdigit() else 0,
                "max": str(element.get("max", "")),
                "mustSupport": bool(element.get("mustSupport", False)),
                "types": sorted(set(str(c) for c in type_codes if c)),
                "short": str(element.get("short", "")),
                "definition": str(element.get("definition", "")),
            }
    return [dedup[k] for k in sorted(dedup.keys())]


def _build_catalog(resources: list[tuple[str, dict[str, Any]]], source: str) -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    value_sets: dict[str, dict[str, Any]] = {}
    code_systems: dict[str, dict[str, Any]] = {}
    concept_maps: dict[str, dict[str, Any]] = {}
    implementation_guide = None
    package_json = None

    for path, res in resources:
        rt = res.get("resourceType")
        if path.endswith("package/package.json") or path.endswith("package.json"):
            package_json = res
            continue
        if rt == "ImplementationGuide":
            implementation_guide = res
            continue
        if rt == "StructureDefinition":
            profiles.append(
                {
                    "url": res.get("url"),
                    "name": res.get("name") or res.get("id"),
                    "resourceType": res.get("type") or "UNKNOWN",
                    "mustSupport": _extract_must_support(res),
                    "requiredPaths": _extract_required_paths(res),
                    "bindings": _extract_bindings(res),
                    "description": res.get("description") or res.get("purpose") or "",
                    "elements": _extract_elements(res),
                    "source": path,
                }
            )
            continue
        if rt == "ValueSet" and isinstance(res.get("url"), str):
            value_sets[res["url"]] = {
                "url": res.get("url"),
                "name": res.get("name") or res.get("id"),
                "status": res.get("status"),
                "source": path,
            }
            continue
        if rt == "CodeSystem" and isinstance(res.get("url"), str):
            code_systems[res["url"]] = {
                "url": res.get("url"),
                "name": res.get("name") or res.get("id"),
                "status": res.get("status"),
                "source": path,
            }
            continue
        if rt == "ConceptMap" and isinstance(res.get("url"), str):
            concept_maps[res["url"]] = {
                "url": res.get("url"),
                "name": res.get("name") or res.get("id"),
                "status": res.get("status"),
                "source": path,
            }

    profiles.sort(key=lambda p: str(p.get("url") or p.get("name") or ""))

    catalog = {
        "catalog_version": "0.1.0",
        "source": source,
        "package": (package_json or {}).get("name", "UNKNOWN"),
        "package_version": (package_json or {}).get("version", "UNKNOWN"),
        "fhir_version": ((package_json or {}).get("fhirVersions") or ["UNKNOWN"])[0],
        "ig_canonical": (implementation_guide or {}).get("url")
        or (package_json or {}).get("canonical")
        or "UNKNOWN",
        "profiles": profiles,
        "valueSets": {k: value_sets[k] for k in sorted(value_sets.keys())},
        "codeSystems": {k: code_systems[k] for k in sorted(code_systems.keys())},
        "conceptMaps": {k: concept_maps[k] for k in sorted(concept_maps.keys())},
    }
    catalog["hash"] = stable_hash_obj(catalog)
    return catalog


def _load_from_path(path: Path) -> tuple[list[tuple[str, dict[str, Any]]], str]:
    resources: list[tuple[str, dict[str, Any]]] = []
    if not path.exists():
        return [], "NOT_FOUND"

    suffixes = {s.lower() for s in path.suffixes}
    if ".zip" in suffixes:
        resources = list(_iter_json_from_zip(path))
    elif ".tgz" in suffixes or (".tar" in suffixes and ".gz" in suffixes):
        resources = list(_iter_json_from_tgz(path))
    else:
        # best-effort fallback
        try:
            resources = list(_iter_json_from_tgz(path))
        except Exception:
            try:
                resources = list(_iter_json_from_zip(path))
            except Exception:
                resources = []

    if any(r[1].get("resourceType") == "StructureDefinition" for r in resources):
        return resources, str(path)
    return [], str(path)


def discover_ig_resources(
    ig_override: Path | None = None,
    primary_package: Path = PRIMARY_PACKAGE,
    secondary_package: Path = SECONDARY_PACKAGE,
    fallback_zip: Path = DEFAULT_IG_ZIP,
) -> tuple[list[tuple[str, dict[str, Any]]], str]:
    candidates: list[Path] = []

    if ig_override is not None:
        candidates.append(ig_override)

    env_override = os.environ.get(ENV_IG_SOURCE, "").strip()
    if env_override:
        candidates.append(Path(env_override))

    candidates.extend([primary_package, secondary_package, fallback_zip])

    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        resources, source = _load_from_path(path)
        if resources:
            return resources, source

    return [], "NOT_FOUND"


def build_and_save_catalog(
    ig_override: Path | None = None,
    primary_package: Path = PRIMARY_PACKAGE,
    secondary_package: Path = SECONDARY_PACKAGE,
    fallback_zip: Path = DEFAULT_IG_ZIP,
    output_path: Path = CATALOG_PATH,
) -> dict[str, Any]:
    resources, source = discover_ig_resources(
        ig_override=ig_override,
        primary_package=primary_package,
        secondary_package=secondary_package,
        fallback_zip=fallback_zip,
    )
    if not resources:
        raise FileNotFoundError(
            "No machine-readable PQI artifacts found. "
            "Set PQI_IG_SOURCE or provide ig/pqi-package.tgz "
            "or assets/pqi/package.tgz or /mnt/data/full-ig.zip."
        )
    catalog = _build_catalog(resources, source)
    ensure_dir(output_path.parent)
    write_json(output_path, catalog)
    return catalog


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    if not path.exists():
        return build_and_save_catalog(output_path=path)
    return json.loads(path.read_text(encoding="utf-8"))


def list_profiles(catalog: dict[str, Any], contains: str = "") -> list[dict[str, Any]]:
    needle = contains.lower().strip()
    out = []
    for profile in catalog.get("profiles", []):
        haystack = " ".join(
            str(profile.get(k, "")).lower() for k in ("url", "name", "resourceType", "description")
        )
        if needle and needle not in haystack:
            continue
        out.append(profile)
    return out


def show_profile(catalog: dict[str, Any], profile_url: str) -> dict[str, Any] | None:
    for profile in catalog.get("profiles", []):
        if str(profile.get("url")) == profile_url:
            return profile
    return None
