"""Table-to-resource classifier for wedge domains."""

from __future__ import annotations

from typing import Any

from pqi_copilot.common import normalize_token

RESOURCE_SIGNAL_WEIGHTS = {
    "Medication": {
        "keywords": {
            "batch": 1.3,
            "lot": 1.3,
            "release": 0.8,
            "manufacturing": 0.8,
            "packaging": 0.7,
            "yield": 0.6,
            "material": 0.6,
            "quantity": 0.5,
        },
        "domain_boost": {"batch_lot_information": 0.9},
    },
    "Observation": {
        "keywords": {
            "test": 1.2,
            "result": 1.3,
            "assay": 1.1,
            "analysis": 1.1,
            "method": 0.9,
            "spec": 0.8,
            "limit": 0.8,
            "value": 0.8,
            "unit": 0.6,
            "sample": 0.8,
            "specimen": 0.8,
        },
        "domain_boost": {"batch_analysis": 1.0},
    },
    "DiagnosticReport": {
        "keywords": {
            "report": 1.4,
            "summary": 0.9,
            "conclusion": 0.8,
            "analysis": 0.6,
        },
        "domain_boost": {"batch_analysis": 0.4},
    },
    "Specimen": {
        "keywords": {
            "specimen": 1.4,
            "sample": 1.2,
            "aliquot": 0.8,
            "container": 0.5,
        },
        "domain_boost": {"batch_analysis": 0.3},
    },
}


def classify_table_resources(profile: dict[str, Any], domain_classification: dict[str, Any]) -> dict[str, Any]:
    domain_by_table = {
        str(t.get("table")): str(t.get("primary_domain", "REQUIRES_REVIEW"))
        for t in domain_classification.get("tables", [])
    }

    out_tables: list[dict[str, Any]] = []

    for table in profile.get("tables", []):
        table_name = str(table.get("table", ""))
        domain = domain_by_table.get(table_name, "REQUIRES_REVIEW")

        scores = {r: 0.0 for r in RESOURCE_SIGNAL_WEIGHTS.keys()}
        rationale: dict[str, list[str]] = {r: [] for r in RESOURCE_SIGNAL_WEIGHTS.keys()}

        table_tokens = normalize_token(table_name)
        column_names = sorted(table.get("columns", {}).keys())

        for resource, cfg in RESOURCE_SIGNAL_WEIGHTS.items():
            for keyword, weight in cfg["keywords"].items():
                if keyword in table_tokens:
                    scores[resource] += weight * 0.75
                    rationale[resource].append(f"table-keyword:{keyword}(+{weight * 0.75:.2f})")

            domain_boost = float(cfg.get("domain_boost", {}).get(domain, 0.0))
            if domain_boost:
                scores[resource] += domain_boost
                rationale[resource].append(f"domain-boost:{domain}(+{domain_boost:.2f})")

        for col in column_names:
            token = normalize_token(col)
            for resource, cfg in RESOURCE_SIGNAL_WEIGHTS.items():
                for keyword, weight in cfg["keywords"].items():
                    if keyword in token:
                        scores[resource] += weight
                        rationale[resource].append(f"column:{col}:keyword:{keyword}(+{weight:.2f})")

        # Co-occurrence signal for Observation-centric analysis tables.
        cols = set(column_names)
        if {"test_code", "result_value"} & cols and "batch_id" in cols:
            scores["Observation"] += 0.8
            rationale["Observation"].append("cooccurrence:batch_id+test/result(+0.80)")

        if "batch_id" in cols and not ({"test_code", "result_value", "assay"} & cols):
            scores["Medication"] += 0.4
            rationale["Medication"].append("cooccurrence:batch_id_without_test(+0.40)")

        total = sum(max(v, 0.0) for v in scores.values())
        if total <= 0:
            normalized = {k: 0.0 for k in scores.keys()}
            primary = "REQUIRES_REVIEW"
        else:
            normalized = {k: round(max(v, 0.0) / total, 6) for k, v in scores.items()}
            ranked = sorted(normalized.items(), key=lambda item: (-item[1], item[0]))
            primary = ranked[0][0]

        out_tables.append(
            {
                "table": table_name,
                "source_file": table.get("source_file"),
                "domain_primary": domain,
                "primary_resource": primary,
                "resource_scores": normalized,
                "rationale": {k: v[:20] for k, v in rationale.items()},
            }
        )

    return {
        "tables": out_tables,
        "summary": {
            "classified_tables": len(out_tables),
            "requires_review": sum(1 for t in out_tables if t.get("primary_resource") == "REQUIRES_REVIEW"),
        },
    }
