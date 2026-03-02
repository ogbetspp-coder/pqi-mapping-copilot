"""Generate PQI-aligned FHIR R5 resources and collection bundles from approved mappings."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .constants import BUNDLE_PROFILE_BY_DOMAIN
from .ig_loader import find_profile_url
from .profiler import load_tables
from .utils import normalize_label, slugify, stable_hash_text


def _resource_id(prefix: str, *parts: str) -> str:
    key = "|".join(str(p) for p in parts)
    digest = stable_hash_text(key)[:14]
    return f"{slugify(prefix)}-{digest}"


def _full_url(resource_type: str, resource_id: str) -> str:
    return f"urn:uuid:{stable_hash_text(f'{resource_type}/{resource_id}')[:32]}"


def _as_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _profile_url(catalog: dict[str, Any], fragment: str) -> str | None:
    return find_profile_url(catalog, fragment)


def _medicinal_product_from_row(row: dict[str, str], catalog: dict[str, Any]) -> dict[str, Any]:
    material_id = row.get("material_id", "UNKNOWN")
    resource_id = _resource_id("mpd", material_id)

    profile = _profile_url(catalog, "MedicinalProductDefinition-drug-product-pq")
    resource: dict[str, Any] = {
        "resourceType": "MedicinalProductDefinition",
        "id": resource_id,
        "identifier": [{"system": "urn:example:sap:material", "value": material_id}],
        "name": [{"productName": row.get("product_name", "UNKNOWN")}],
    }

    dose_code = row.get("dosage_form_code", "")
    dose_display = row.get("dosage_form_display", "")
    if dose_code or dose_display:
        resource["combinedPharmaceuticalDoseForm"] = {
            "coding": [
                {
                    "system": "http://standardterms.edqm.eu",
                    "code": dose_code or "UNKNOWN",
                    "display": dose_display or "UNKNOWN",
                }
            ]
        }

    route_code = row.get("route_code", "")
    route_display = row.get("route_display", "")
    if route_code or route_display:
        resource["route"] = [
            {
                "coding": [
                    {
                        "system": "http://standardterms.edqm.eu",
                        "code": route_code or "UNKNOWN",
                        "display": route_display or "UNKNOWN",
                    }
                ]
            }
        ]

    if profile:
        resource["meta"] = {"profile": [profile]}

    return resource


def _organization_from_row(row: dict[str, str], catalog: dict[str, Any]) -> dict[str, Any]:
    org_key = row.get("manufacturer_org_id") or row.get("lab_org_id") or row.get("organization_id") or "UNKNOWN"
    resource_id = _resource_id("org", org_key)
    profile = _profile_url(catalog, "Organization-drug-pq")

    code = row.get("organization_type") or row.get("manufacturer_type") or "UNKNOWN"
    display = row.get("organization_type_display") or row.get("manufacturer_type_display") or code

    resource: dict[str, Any] = {
        "resourceType": "Organization",
        "id": resource_id,
        "identifier": [{"system": "urn:example:org", "value": org_key}],
        "active": True,
        "name": row.get("manufacturer_name") or row.get("lab_org_name") or row.get("organization_name") or "UNKNOWN",
        "type": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/pharmaceutical-organization-type",
                        "code": code,
                        "display": display,
                    }
                ]
            }
        ],
    }
    if profile:
        resource["meta"] = {"profile": [profile]}
    return resource


def _medication_from_row(
    row: dict[str, str],
    catalog: dict[str, Any],
    product_id_by_material: dict[str, str],
    org_id_by_key: dict[str, str],
) -> dict[str, Any]:
    batch_id = row.get("batch_id") or row.get("lot_number") or "UNKNOWN"
    resource_id = _resource_id("med", batch_id)

    profile = _profile_url(catalog, "Medication-batch-information-drug-pq")
    med: dict[str, Any] = {
        "resourceType": "Medication",
        "id": resource_id,
        "code": {
            "extension": [
                {
                    "url": "http://hl7.org/fhir/uv/pharm-quality/StructureDefinition/Extension-medication-definition-pq",
                    "valueReference": {
                        "reference": f"MedicinalProductDefinition/{product_id_by_material.get(row.get('material_id', ''), 'UNKNOWN')}"
                    },
                }
            ]
        },
        "batch": {
            "lotNumber": batch_id,
            "extension": [],
        },
    }

    manufacturing_extensions: list[dict[str, Any]] = []

    mfg_date = row.get("manufacturing_date", "")
    if mfg_date:
        manufacturing_extensions.append({"url": "manufacturingDate", "valueDateTime": mfg_date})

    quantity = _as_float(row.get("batch_quantity", ""))
    if quantity is not None:
        manufacturing_extensions.append(
            {
                "url": "batchQuantity",
                "valueQuantity": {
                    "value": quantity,
                    "unit": row.get("batch_quantity_unit") or "UNKNOWN",
                },
            }
        )

    manufacturer_key = row.get("manufacturer_org_id", "")
    if manufacturer_key and manufacturer_key in org_id_by_key:
        manufacturing_extensions.append(
            {
                "url": "assignedManufacturer",
                "valueReference": {
                    "reference": f"Organization/{org_id_by_key[manufacturer_key]}"
                },
            }
        )

    if manufacturing_extensions:
        med["batch"]["extension"].append(
            {
                "url": "http://hl7.org/fhir/StructureDefinition/medication-manufacturingBatch",
                "extension": manufacturing_extensions,
            }
        )

    release_date = row.get("release_date", "")
    if release_date:
        med["batch"]["extension"].append(
            {
                "url": "http://hl7.org/fhir/uv/pharm-quality/StructureDefinition/Extension-batch-release-date-pq",
                "valueDateTime": release_date,
            }
        )

    packaging_date = row.get("packaging_date", "")
    if packaging_date:
        med["batch"]["extension"].append(
            {
                "url": "http://hl7.org/fhir/uv/pharm-quality/StructureDefinition/Extension-packaging-date-pq",
                "valueDateTime": packaging_date,
            }
        )

    actual_yield = _as_float(row.get("actual_yield", ""))
    if actual_yield is not None:
        med["batch"]["extension"].append(
            {
                "url": "http://hl7.org/fhir/uv/pharm-quality/StructureDefinition/Extension-actual-yield-pq",
                "valueQuantity": {
                    "value": actual_yield,
                    "unit": row.get("actual_yield_unit") or "UNKNOWN",
                },
            }
        )

    if profile:
        med["meta"] = {"profile": [profile]}

    return med


def _observation_definition_from_row(row: dict[str, str], catalog: dict[str, Any]) -> dict[str, Any]:
    code = row.get("result_code") or row.get("method_code") or "UNKNOWN"
    resource_id = _resource_id("obsdef", code)
    profile = _profile_url(catalog, "ObservationDefinition-test-method-drug-pq")

    resource: dict[str, Any] = {
        "resourceType": "ObservationDefinition",
        "id": resource_id,
        "status": "active",
        "code": {
            "coding": [
                {
                    "system": "http://hl7.org/fhir/uv/pharm-quality/CodeSystem/cs-local-codes-drug-pq-example",
                    "code": code,
                    "display": row.get("result_display") or row.get("method_display") or code,
                }
            ]
        },
    }
    if profile:
        resource["meta"] = {"profile": [profile]}
    return resource


def _specimen_from_row(row: dict[str, str], catalog: dict[str, Any]) -> dict[str, Any]:
    specimen_key = row.get("specimen_id") or f"specimen-{row.get('batch_id', 'unknown')}"
    resource_id = _resource_id("specimen", specimen_key)
    profile = _profile_url(catalog, "Specimen-drug-pq")

    resource: dict[str, Any] = {
        "resourceType": "Specimen",
        "id": resource_id,
        "collection": {},
    }
    collected = row.get("sample_collection_date", "")
    if collected:
        resource["collection"]["collectedDateTime"] = collected
    if row.get("storage_condition"):
        resource["processing"] = [{"description": row["storage_condition"]}]
    if profile:
        resource["meta"] = {"profile": [profile]}
    return resource


def _observation_from_row(
    row: dict[str, str],
    catalog: dict[str, Any],
    medication_id_by_batch: dict[str, str],
    observation_definition_id_by_code: dict[str, str],
    specimen_id_by_key: dict[str, str],
    org_id_by_key: dict[str, str],
) -> dict[str, Any]:
    batch_id = row.get("batch_id", "UNKNOWN")
    code = row.get("result_code", "UNKNOWN")
    analysis_time = row.get("analysis_time", "")
    resource_id = _resource_id("obs", batch_id, code, analysis_time)

    profile = _profile_url(catalog, "Observation-test-result-drug-pq")

    obs: dict[str, Any] = {
        "resourceType": "Observation",
        "id": resource_id,
        "status": "final",
        "instantiatesReference": {
            "reference": f"ObservationDefinition/{observation_definition_id_by_code.get(code, 'UNKNOWN')}"
        },
        "code": {
            "coding": [
                {
                    "system": "http://hl7.org/fhir/uv/pharm-quality/CodeSystem/cs-local-codes-drug-pq-example",
                    "code": code,
                    "display": row.get("result_display") or code,
                }
            ]
        },
        "subject": {
            "reference": f"Medication/{medication_id_by_batch.get(batch_id, 'UNKNOWN')}"
        },
    }

    if analysis_time:
        obs["effectiveDateTime"] = analysis_time

    result_value = row.get("result_value", "")
    value_number = _as_float(result_value)
    if value_number is not None:
        obs["valueQuantity"] = {
            "value": value_number,
            "unit": row.get("result_unit") or "UNKNOWN",
        }
    else:
        obs["valueCodeableConcept"] = {
            "coding": [
                {
                    "system": "http://example.org/fhir/CodeSystem/local-cmc-pqi",
                    "code": normalize_label(result_value or "unknown"),
                    "display": result_value or "UNKNOWN",
                }
            ],
            "text": result_value or "UNKNOWN",
        }

    specimen_key = row.get("specimen_id", "")
    if specimen_key in specimen_id_by_key:
        obs["specimen"] = {"reference": f"Specimen/{specimen_id_by_key[specimen_key]}"}

    lab_org_key = row.get("lab_org_id", "")
    if lab_org_key in org_id_by_key:
        obs["performer"] = [{"reference": f"Organization/{org_id_by_key[lab_org_key]}"}]

    if profile:
        obs["meta"] = {"profile": [profile]}

    return obs


def _diagnostic_report(
    batch_id: str,
    observation_ids: list[str],
    catalog: dict[str, Any],
    org_ref: str | None,
    effective_time: str,
) -> dict[str, Any]:
    resource_id = _resource_id("dr", batch_id)
    profile = _profile_url(catalog, "DiagnosticReport-analysis-drug-pq")

    report: dict[str, Any] = {
        "resourceType": "DiagnosticReport",
        "id": resource_id,
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/pharmaceutical-report-type",
                    "code": "Batch Analysis Report",
                    "display": "Batch Analysis Report",
                }
            ]
        },
        "result": [{"reference": f"Observation/{obs_id}"} for obs_id in sorted(observation_ids)],
    }

    if effective_time:
        report["effectiveDateTime"] = effective_time
    if org_ref:
        report["performer"] = [{"reference": org_ref}]
    if profile:
        report["meta"] = {"profile": [profile]}

    return report


def _bundle(
    catalog: dict[str, Any],
    domain: str,
    resources: list[dict[str, Any]],
    mapping_version_id: str,
    terminology_version_id: str,
    input_hashes: dict[str, str],
) -> dict[str, Any]:
    profile_fragment = BUNDLE_PROFILE_BY_DOMAIN.get(domain)
    profile_url = find_profile_url(catalog, profile_fragment) if profile_fragment else None

    bundle_id = _resource_id("bundle", domain, mapping_version_id, terminology_version_id)

    entry = []
    for resource in sorted(resources, key=lambda r: (r.get("resourceType", ""), r.get("id", ""))):
        entry.append(
            {
                "fullUrl": _full_url(resource["resourceType"], resource["id"]),
                "resource": resource,
            }
        )

    bundle: dict[str, Any] = {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": "collection",
        "entry": entry,
        "extension": [
            {
                "url": "http://example.org/fhir/StructureDefinition/mapping-version-id",
                "valueString": mapping_version_id,
            },
            {
                "url": "http://example.org/fhir/StructureDefinition/terminology-version-id",
                "valueString": terminology_version_id,
            },
            {
                "url": "http://example.org/fhir/StructureDefinition/input-hashes",
                "valueString": ",".join(f"{k}:{v}" for k, v in sorted(input_hashes.items())),
            },
        ],
    }

    if profile_url:
        bundle["meta"] = {"profile": [profile_url]}

    return bundle


def generate_bundles(
    input_dir: Path,
    catalog: dict[str, Any],
    approved_mapping_set: dict[str, Any],
    mapping_version_id: str,
    terminology_version_id: str,
    input_hashes: dict[str, str],
) -> dict[str, Any]:
    tables = load_tables(input_dir)
    by_name = {table.table_name: table.rows for table in tables}

    product_rows = by_name.get("product_master", [])
    batch_rows = by_name.get("batch_record", [])
    lims_rows = by_name.get("lims_results", [])

    products: list[dict[str, Any]] = []
    organizations_by_key: dict[str, dict[str, Any]] = {}
    medications: list[dict[str, Any]] = []
    observation_definitions_by_code: dict[str, dict[str, Any]] = {}
    specimens_by_key: dict[str, dict[str, Any]] = {}
    observations: list[dict[str, Any]] = []

    product_id_by_material: dict[str, str] = {}
    org_id_by_key: dict[str, str] = {}

    for row in product_rows:
        resource = _medicinal_product_from_row(row, catalog)
        products.append(resource)
        material = row.get("material_id", "")
        if material:
            product_id_by_material[material] = resource["id"]

    for row in batch_rows + lims_rows:
        org_key = row.get("manufacturer_org_id") or row.get("lab_org_id") or row.get("organization_id")
        if not org_key:
            continue
        if org_key in organizations_by_key:
            continue
        org = _organization_from_row(row, catalog)
        organizations_by_key[org_key] = org
        org_id_by_key[org_key] = org["id"]

    medication_id_by_batch: dict[str, str] = {}
    for row in batch_rows:
        med = _medication_from_row(row, catalog, product_id_by_material, org_id_by_key)
        medications.append(med)
        batch_id = row.get("batch_id") or row.get("lot_number")
        if batch_id:
            medication_id_by_batch[batch_id] = med["id"]

    for row in lims_rows:
        code = row.get("result_code") or row.get("method_code") or "UNKNOWN"
        if code not in observation_definitions_by_code:
            obs_def = _observation_definition_from_row(row, catalog)
            observation_definitions_by_code[code] = obs_def

        specimen_key = row.get("specimen_id") or f"specimen-{row.get('batch_id', 'unknown')}"
        if specimen_key not in specimens_by_key:
            specimens_by_key[specimen_key] = _specimen_from_row(row, catalog)

    specimen_id_by_key = {k: v["id"] for k, v in specimens_by_key.items()}
    observation_definition_id_by_code = {k: v["id"] for k, v in observation_definitions_by_code.items()}

    for row in lims_rows:
        observation = _observation_from_row(
            row,
            catalog,
            medication_id_by_batch,
            observation_definition_id_by_code,
            specimen_id_by_key,
            org_id_by_key,
        )
        observations.append(observation)

    diagnostics: list[dict[str, Any]] = []
    obs_by_batch: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row, obs in zip(lims_rows, observations):
        batch_id = row.get("batch_id", "UNKNOWN")
        obs_by_batch[batch_id].append(obs)

    for batch_id in sorted(obs_by_batch.keys()):
        obs_items = obs_by_batch[batch_id]
        obs_ids = [obs["id"] for obs in obs_items]
        effective_time = sorted(
            [str(obs.get("effectiveDateTime", "")) for obs in obs_items if obs.get("effectiveDateTime")]
        )[-1] if any(obs.get("effectiveDateTime") for obs in obs_items) else ""

        performer_ref = None
        for obs in obs_items:
            performers = obs.get("performer", [])
            if performers:
                performer_ref = performers[0].get("reference")
                break

        diagnostics.append(_diagnostic_report(batch_id, obs_ids, catalog, performer_ref, effective_time))

    approved_proposals = [
        p for p in approved_mapping_set.get("proposals", []) if p.get("status") == "approved"
    ]
    if not approved_proposals:
        raise ValueError("No approved mappings available for generation.")

    bundle_pq5_resources = products + medications + list(organizations_by_key.values())
    bundle_pq6_resources = (
        list(observation_definitions_by_code.values())
        + list(specimens_by_key.values())
        + observations
        + diagnostics
        + medications
        + list(organizations_by_key.values())
    )

    bundles = {
        "PQ5": _bundle(
            catalog,
            "PQ5",
            bundle_pq5_resources,
            mapping_version_id,
            terminology_version_id,
            input_hashes,
        ),
        "PQ6": _bundle(
            catalog,
            "PQ6",
            bundle_pq6_resources,
            mapping_version_id,
            terminology_version_id,
            input_hashes,
        ),
    }

    return {
        "bundles": bundles,
        "resources": {
            "MedicinalProductDefinition": products,
            "Medication": medications,
            "Organization": list(organizations_by_key.values()),
            "ObservationDefinition": list(observation_definitions_by_code.values()),
            "Specimen": list(specimens_by_key.values()),
            "Observation": observations,
            "DiagnosticReport": diagnostics,
        },
        "generationSummary": {
            "approvedMappingCount": len(approved_proposals),
            "bundleCount": len(bundles),
            "generatedAt": "deterministic",
        },
    }
