"""Static constants for the PQI digital twin MVP."""

from __future__ import annotations

PQ_DOMAINS = {
    "PQ1": "Identification",
    "PQ2": "Composition",
    "PQ3": "Impurities",
    "PQ4": "Organizations",
    "PQ5": "Batch/Lot Information",
    "PQ6": "Batch Analysis",
    "PQ7": "Batch Formula",
    "PQ8": "Manufacturing Process",
    "PQ9": "Process Validation",
    "PQ10": "Analytical Procedures",
    "PQ11": "Container Closure System",
    "PQ12": "Stability Study",
    "PQ13": "Drug Specifications",
    "PQ14": "Compatibility",
}

DOMAIN_KEYWORDS = {
    "PQ1": ["ident", "product", "material", "name", "mpd", "item", "id"],
    "PQ2": ["composition", "ingredient", "strength", "component", "excipient"],
    "PQ3": ["impurity", "degradation", "contaminant"],
    "PQ4": ["organization", "site", "manufacturer", "supplier", "company"],
    "PQ5": ["batch", "lot", "release", "retest", "shelf", "vial"],
    "PQ6": ["analysis", "result", "assay", "micro", "test", "sample"],
    "PQ7": ["formula", "recipe", "blend", "charge"],
    "PQ8": ["manufacturing", "process", "step", "equipment", "parameter"],
    "PQ9": ["validation", "protocol", "ppq", "cpv"],
    "PQ10": ["analytical", "method", "procedure", "instrument"],
    "PQ11": ["container", "closure", "packaging", "stopper"],
    "PQ12": ["stability", "timepoint", "temperature", "humidity"],
    "PQ13": ["specification", "criteria", "limit", "acceptance"],
    "PQ14": ["compatibility", "interaction", "diluent"],
}

PROFILE_HINTS = {
    "MedicinalProductDefinition": {
        "profile_match": "MedicinalProductDefinition-drug-product-pq",
        "domain": "PQ1",
    },
    "Medication": {
        "profile_match": "Medication-batch-information-drug-pq",
        "domain": "PQ5",
    },
    "Observation": {
        "profile_match": "Observation-test-result-drug-pq",
        "domain": "PQ6",
    },
    "ObservationDefinition": {
        "profile_match": "ObservationDefinition-test-method-drug-pq",
        "domain": "PQ10",
    },
    "DiagnosticReport": {
        "profile_match": "DiagnosticReport-analysis-drug-pq",
        "domain": "PQ6",
    },
    "Specimen": {
        "profile_match": "Specimen-drug-pq",
        "domain": "PQ6",
    },
    "Organization": {
        "profile_match": "Organization-drug-pq",
        "domain": "PQ4",
    },
    "Ingredient": {
        "profile_match": "Ingredient-drug-pq",
        "domain": "PQ2",
    },
}

FIELD_TO_TARGETS = {
    "material_id": ("MedicinalProductDefinition", "identifier[0].value", "PQ1"),
    "product_name": ("MedicinalProductDefinition", "name[0].productName", "PQ1"),
    "dosage_form_code": (
        "MedicinalProductDefinition",
        "combinedPharmaceuticalDoseForm.coding[0].code",
        "PQ1",
    ),
    "dosage_form_display": (
        "MedicinalProductDefinition",
        "combinedPharmaceuticalDoseForm.coding[0].display",
        "PQ1",
    ),
    "route_code": ("MedicinalProductDefinition", "route[0].coding[0].code", "PQ1"),
    "route_display": (
        "MedicinalProductDefinition",
        "route[0].coding[0].display",
        "PQ1",
    ),
    "batch_id": ("Medication", "batch.lotNumber", "PQ5"),
    "lot_number": ("Medication", "batch.lotNumber", "PQ5"),
    "manufacturing_date": (
        "Medication",
        "batch.extension[medication-manufacturingBatch].manufacturingDate",
        "PQ5",
    ),
    "release_date": ("Medication", "batch.extension[Extension-batch-release-date-pq]", "PQ5"),
    "packaging_date": ("Medication", "batch.extension[Extension-packaging-date-pq]", "PQ11"),
    "actual_yield": ("Medication", "batch.extension[Extension-actual-yield-pq]", "PQ5"),
    "result_code": ("Observation", "code.coding[0].code", "PQ6"),
    "result_display": ("Observation", "code.coding[0].display", "PQ6"),
    "result_value": ("Observation", "value[x]", "PQ6"),
    "result_unit": ("Observation", "valueQuantity.unit", "PQ6"),
    "analysis_time": ("Observation", "effectiveDateTime", "PQ6"),
    "specimen_id": ("Specimen", "id", "PQ6"),
    "organization_name": ("Organization", "name", "PQ4"),
    "organization_type": ("Organization", "type[0].coding[0].code", "PQ4"),
    "stability_timepoint": (
        "DiagnosticReport",
        "effectiveDateTime",
        "PQ12",
    ),
    "method_code": (
        "ObservationDefinition",
        "code.coding[0].code",
        "PQ10",
    ),
}

DEFAULT_CODE_SYSTEMS = {
    "dose_form": "http://standardterms.edqm.eu",
    "route": "http://standardterms.edqm.eu",
    "test_code": "http://hl7.org/fhir/uv/pharm-quality/CodeSystem/cs-local-codes-drug-pq-example",
    "organization_type": "http://terminology.hl7.org/CodeSystem/pharmaceutical-organization-type",
}

BUNDLE_PROFILE_BY_DOMAIN = {
    "PQ5": "Bundle-drug-product-batch-info-pq",
    "PQ6": "Bundle-batch-analysis-pq",
    "PQ12": "Bundle-drug-stability-pq",
    "PQ10": "Bundle-analytical-procedure-pq",
    "PQ4": "Bundle-organizations-pq",
    "PQ2": "Bundle-drug-product-composition-pq",
}

LIFECYCLE_ORDER = ["proposed", "reviewed", "approved", "deprecated"]
