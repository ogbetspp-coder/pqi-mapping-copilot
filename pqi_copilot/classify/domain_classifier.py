"""Explainable domain classifier for wedge domains."""

from __future__ import annotations

from typing import Any

from pqi_copilot.common import normalize_token

DOMAINS = {
    "batch_lot_information": "Batch/Lot Information",
    "batch_analysis": "Batch Analysis",
    "out_of_scope": "Out of Scope (Wedge)",
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

ADMIN_KEYWORDS = {
    "deviation",
    "status",
    "category",
    "workflow",
    "owner",
    "equipment",
    "step",
    "action",
}

ANALYSIS_KEYWORDS = {"test", "result", "assay", "analysis", "spec", "limit"}


def _looks_out_of_scope(table_name: str, columns: list[str]) -> tuple[bool, list[str]]:
    table_token = normalize_token(table_name)
    column_tokens = [normalize_token(c) for c in columns]
    all_tokens = [table_token, *column_tokens]

    admin_hits = 0
    analysis_hits = 0
    rationale: list[str] = []

    for token in all_tokens:
        if any(k in token for k in ADMIN_KEYWORDS):
            admin_hits += 1
        if any(k in token for k in ANALYSIS_KEYWORDS):
            analysis_hits += 1

    ratio = admin_hits / max(1, len(all_tokens))
    if ratio >= 0.35 and analysis_hits == 0:
        rationale.append(f"admin_signal_ratio={ratio:.2f} and no analysis keywords")
        return True, rationale
    return False, rationale


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
    wedge_domains = [d for d in DOMAINS.keys() if d != "out_of_scope"]

    for table in profile.get("tables", []):
        by_domain: dict[str, float] = {d: 0.0 for d in wedge_domains}
        rationale: dict[str, list[str]] = {d: [] for d in DOMAINS.keys()}

        table_name = normalize_token(str(table.get("table", "")))
        for domain in wedge_domains:
            for keyword, weight in DOMAIN_SIGNALS[domain]["keywords"].items():
                if keyword in table_name:
                    by_domain[domain] += weight * 0.75
                    rationale[domain].append(f"table-keyword:{keyword}(+{weight * 0.75:.2f})")

        columns = sorted(table.get("columns", {}).keys())
        for column_name, stats in sorted(table.get("columns", {}).items()):
            for domain in wedge_domains:
                col_score, col_reason = _column_score(column_name, stats, domain)
                by_domain[domain] += col_score
                for reason in col_reason:
                    rationale[domain].append(f"{column_name}:{reason}")

        total = sum(max(v, 0.0) for v in by_domain.values())
        if total <= 0:
            domain_scores = {d: 0.0 for d in wedge_domains}
            domain_scores["out_of_scope"] = 1.0
            primary = "out_of_scope"
            rationale["out_of_scope"].append("no_domain_signals_detected")
        else:
            domain_scores = {d: round(max(v, 0.0) / total, 6) for d, v in by_domain.items()}
            ranked = sorted(domain_scores.items(), key=lambda item: (-item[1], item[0]))
            primary = ranked[0][0]
            top_score = float(ranked[0][1])
            second_score = float(ranked[1][1]) if len(ranked) > 1 else 0.0
            margin = top_score - second_score
            out_of_scope, oo_rationale = _looks_out_of_scope(str(table.get("table", "")), columns)
            rationale["out_of_scope"].extend(oo_rationale)

            if top_score < 0.55:
                out_of_scope = True
                rationale["out_of_scope"].append(f"top_score_below_threshold({top_score:.2f}<0.55)")
            if margin < 0.15:
                out_of_scope = True
                rationale["out_of_scope"].append(f"domain_margin_low({margin:.2f}<0.15)")

            if out_of_scope:
                primary = "out_of_scope"
                domain_scores["out_of_scope"] = round(max(0.65, 1.0 - top_score), 6)
            else:
                domain_scores["out_of_scope"] = round(max(0.0, 1.0 - top_score), 6)

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
            "out_of_scope": sum(1 for t in tables_out if t.get("primary_domain") == "out_of_scope"),
        },
    }
