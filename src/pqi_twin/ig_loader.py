"""Load and index HL7 FHIR IG package artifacts for PQI."""

from __future__ import annotations

import io
import json
import tarfile
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .constants import DOMAIN_KEYWORDS


JSONResource = dict[str, Any]


def _iter_json_from_tar_bytes(tar_bytes: bytes) -> Iterable[tuple[str, JSONResource]]:
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tf:
        members = sorted((m for m in tf.getmembers() if m.isfile()), key=lambda m: m.name)
        for member in members:
            if not member.name.endswith(".json"):
                continue
            handle = tf.extractfile(member)
            if handle is None:
                continue
            data = json.loads(handle.read().decode("utf-8"))
            yield member.name, data


def _iter_json_from_tgz(path: Path) -> Iterable[tuple[str, JSONResource]]:
    with path.open("rb") as f:
        data = f.read()
    yield from _iter_json_from_tar_bytes(data)


def _iter_json_from_zip(path: Path) -> Iterable[tuple[str, JSONResource]]:
    with zipfile.ZipFile(path, "r") as zf:
        names = sorted(zf.namelist())

        nested_tgz_name = None
        for name in names:
            if name.endswith("site/package.tgz"):
                nested_tgz_name = name
                break

        if nested_tgz_name is not None:
            tar_bytes = zf.read(nested_tgz_name)
            yield from _iter_json_from_tar_bytes(tar_bytes)
            return

        for name in names:
            if not name.endswith(".json"):
                continue
            data = json.loads(zf.read(name).decode("utf-8"))
            yield name, data


def _iter_json_resources(asset_path: Path) -> Iterable[tuple[str, JSONResource]]:
    suffix = asset_path.suffix.lower()
    if suffix in {".tgz", ".gz"}:
        yield from _iter_json_from_tgz(asset_path)
        return
    if suffix == ".zip":
        yield from _iter_json_from_zip(asset_path)
        return
    raise ValueError(f"Unsupported IG asset path: {asset_path}")


def _extract_required_elements(structure_definition: JSONResource) -> list[str]:
    def _read(elements: list[dict[str, Any]]) -> set[str]:
        required: set[str] = set()
        for element in elements:
            path = element.get("path")
            min_val = element.get("min", 0)
            if not isinstance(path, str) or "." not in path:
                continue
            try:
                min_int = int(min_val)
            except (TypeError, ValueError):
                min_int = 0
            if min_int > 0:
                required.add(path)
        return required

    differential = structure_definition.get("differential", {}).get("element", [])
    snapshot = structure_definition.get("snapshot", {}).get("element", [])
    required = _read(differential) | _read(snapshot)
    return sorted(required)


def _extract_bindings(structure_definition: JSONResource) -> list[dict[str, Any]]:
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    for section in ("differential", "snapshot"):
        elements = structure_definition.get(section, {}).get("element", [])
        for element in elements:
            binding = element.get("binding")
            path = element.get("path")
            if not isinstance(binding, dict) or not isinstance(path, str):
                continue
            strength = binding.get("strength", "")
            valueset = binding.get("valueSet", "")
            key = (path, str(strength), str(valueset))
            seen[key] = {
                "path": path,
                "strength": strength,
                "valueSet": valueset,
            }
    return [seen[k] for k in sorted(seen.keys())]


def _infer_domains(text: str) -> list[str]:
    lowered = text.lower()
    scored: list[tuple[str, int]] = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in lowered)
        if score > 0:
            scored.append((domain, score))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return [domain for domain, _ in scored[:3]]


def load_ig_catalog(asset_path: Path) -> dict[str, Any]:
    package_json: dict[str, Any] = {}
    implementation_guide: dict[str, Any] = {}

    profiles: list[dict[str, Any]] = []
    value_sets: list[dict[str, Any]] = []
    code_systems: list[dict[str, Any]] = []
    concept_maps: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    domain_map: dict[str, list[str]] = defaultdict(list)

    for source_name, resource in _iter_json_resources(asset_path):
        if source_name.endswith("package/package.json"):
            package_json = resource
            continue

        resource_type = resource.get("resourceType")
        if source_name.endswith("ImplementationGuide-hl7.fhir.uv.pharm-quality.json"):
            implementation_guide = resource

        if resource_type == "StructureDefinition":
            profile_info = {
                "url": resource.get("url"),
                "name": resource.get("name"),
                "id": resource.get("id"),
                "title": resource.get("title"),
                "type": resource.get("type"),
                "kind": resource.get("kind"),
                "derivation": resource.get("derivation"),
                "requiredElements": _extract_required_elements(resource),
                "bindings": _extract_bindings(resource),
                "source": source_name,
                "domains": _infer_domains(
                    " ".join(
                        str(x)
                        for x in [
                            resource.get("id", ""),
                            resource.get("name", ""),
                            resource.get("title", ""),
                            resource.get("type", ""),
                        ]
                    )
                ),
            }
            profiles.append(profile_info)
            for domain in profile_info["domains"]:
                url = profile_info.get("url")
                if isinstance(url, str):
                    domain_map[domain].append(url)
            continue

        if resource_type == "ValueSet":
            value_sets.append(
                {
                    "url": resource.get("url"),
                    "name": resource.get("name"),
                    "id": resource.get("id"),
                    "status": resource.get("status"),
                    "source": source_name,
                }
            )
            continue

        if resource_type == "CodeSystem":
            code_systems.append(
                {
                    "url": resource.get("url"),
                    "name": resource.get("name"),
                    "id": resource.get("id"),
                    "status": resource.get("status"),
                    "source": source_name,
                }
            )
            continue

        if resource_type == "ConceptMap":
            concept_maps.append(
                {
                    "url": resource.get("url"),
                    "name": resource.get("name"),
                    "id": resource.get("id"),
                    "status": resource.get("status"),
                    "source": source_name,
                }
            )
            continue

        if resource_type == "Bundle" and "/example/" in source_name:
            examples.append(
                {
                    "id": resource.get("id"),
                    "url": resource.get("url"),
                    "profile": (
                        resource.get("meta", {}).get("profile", [None])[0]
                        if isinstance(resource.get("meta", {}).get("profile"), list)
                        else None
                    ),
                    "source": source_name,
                }
            )

    profiles.sort(key=lambda p: str(p.get("url") or p.get("name") or ""))
    value_sets.sort(key=lambda r: str(r.get("url") or ""))
    code_systems.sort(key=lambda r: str(r.get("url") or ""))
    concept_maps.sort(key=lambda r: str(r.get("url") or ""))
    examples.sort(key=lambda r: str(r.get("id") or ""))

    domain_profile_map = {domain: sorted(set(urls)) for domain, urls in sorted(domain_map.items())}

    return {
        "igCanonical": implementation_guide.get("url")
        or package_json.get("canonical")
        or "UNKNOWN",
        "implementationGuideId": implementation_guide.get("id", "UNKNOWN"),
        "package": package_json.get("name", "UNKNOWN"),
        "packageVersion": package_json.get("version", "UNKNOWN"),
        "fhirVersion": (package_json.get("fhirVersions") or ["UNKNOWN"])[0],
        "generatedFrom": str(asset_path),
        "profiles": profiles,
        "valueSets": value_sets,
        "codeSystems": code_systems,
        "conceptMaps": concept_maps,
        "exampleBundles": examples,
        "domainProfileMap": domain_profile_map,
    }


def find_profile_url(catalog: dict[str, Any], profile_name_fragment: str) -> str | None:
    target = profile_name_fragment.lower()
    for profile in catalog.get("profiles", []):
        url = profile.get("url")
        id_value = str(profile.get("id", "")).lower()
        name = str(profile.get("name", "")).lower()
        if target in id_value or target in name:
            return str(url) if isinstance(url, str) else None
    return None
