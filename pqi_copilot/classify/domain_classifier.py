"""Explainable domain classifier for wedge domains."""

from __future__ import annotations

from typing import Any

from pqi_copilot.common import normalize_token

DOMAINS = {
    "batch_lot_information": "Batch/Lot Information",
    "batch_analysis": "Batch Analysis",
}

DOMAIN_SIGNALS = {
    "batch_lot_information": {
        "keywords": {
            "batch": 1.2,
            "lot": 1.2,
            "release": 0.8,
            "retest": 0.6,
            "manufacturing": 0.6,
            "packaging": 0.5,
            "yield": 0.4,
            "shelf": 0.4,
            "material": 0.3,
        },
        "value_hints": {
            "batch-like-token": 0.5,
        },
    },
    "batch_analysis": {
        "keywords": {
            "test": 1.1,
            "result": 1.2,
            "assay": 0.9,
            "spec": 0.8,
            "limit": 0.8,
            "method": 0.8,
            "analysis": 1.0,
            "sample": 0.8,
            "specimen": 0.8,
            "unit": 0.4,
        },
        "value_hints": {
            "has-units": 0.4,
            "has-test-codes": 0.5,
        },
    },
}


def _column_score(column_name: str, column_profile: dict[str, Any], domain: str) -> tuple[float, list[str]]:
    score = 0.0
    rationale: list[str] = []

    tokens = normalize_token(column_name)
    keyword_weights = DOMAIN_SIGNALS[domain]["keywords"]
    for keyword, weight in keyword_weights.items():
        if keyword in tokens:
            score += weight
            rationale.append(f"keyword:{keyword}(+{weight})")

    regex_hits = column_profile.get("regex_hits", {})
    top_values = [tv.get("value", "") for tv in column_profile.get("top_values", [])]

    if domain == "batch_lot_information" and regex_hits.get("batch_like", 0) > 0:
        score += 0.5
        rationale.append("value-pattern:batch_like(+0.5)")

    if domain == "batch_analysis":
        if column_profile.get("units"):
            score += 0.4
            rationale.append("value-pattern:has_units(+0.4)")
        if any(v.isupper() and len(v) <= 12 for v in top_values if isinstance(v, str)):
            score += 0.3
            rationale.append("value-pattern:test_code_like(+0.3)")

    return score, rationale


def classify_domains(profile: dict[str, Any]) -> dict[str, Any]:
    tables_out: list[dict[str, Any]] = []

    for table in profile.get("tables", []):
        by_domain: dict[str, float] = {d: 0.0 for d in DOMAINS.keys()}
        rationale: dict[str, list[str]] = {d: [] for d in DOMAINS.keys()}

        table_name = normalize_token(str(table.get("table", "")))
        for domain in DOMAINS.keys():
            for keyword, weight in DOMAIN_SIGNALS[domain]["keywords"].items():
                if keyword in table_name:
                    by_domain[domain] += weight * 0.75
                    rationale[domain].append(f"table-keyword:{keyword}(+{weight * 0.75:.2f})")

        for column_name, stats in sorted(table.get("columns", {}).items()):
            for domain in DOMAINS.keys():
                col_score, col_reason = _column_score(column_name, stats, domain)
                by_domain[domain] += col_score
                for reason in col_reason:
                    rationale[domain].append(f"{column_name}:{reason}")

        total = sum(max(v, 0.0) for v in by_domain.values())
        if total <= 0:
            domain_scores = {d: 0.0 for d in DOMAINS.keys()}
            primary = "REQUIRES_REVIEW"
        else:
            domain_scores = {d: round(max(v, 0.0) / total, 6) for d, v in by_domain.items()}
            ranked = sorted(domain_scores.items(), key=lambda item: (-item[1], item[0]))
            primary = ranked[0][0]

        tables_out.append(
            {
                "table": table.get("table"),
                "source_file": table.get("source_file"),
                "domain_scores": domain_scores,
                "primary_domain": primary,
                "rationale": {
                    d: rationale[d][:20] for d in DOMAINS.keys()
                },
            }
        )

    return {
        "domains": DOMAINS,
        "tables": tables_out,
        "summary": {
            "classified_tables": len(tables_out),
            "requires_review": sum(1 for t in tables_out if t.get("primary_domain") == "REQUIRES_REVIEW"),
        },
    }
