"""Domain classification for PQI domain framing."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .constants import DOMAIN_KEYWORDS, PQ_DOMAINS
from .utils import normalize_label


def _score_text(text: str) -> dict[str, float]:
    normalized = normalize_label(text)
    scores: dict[str, float] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        hits = [kw for kw in keywords if kw in normalized]
        if not hits:
            continue
        score = len(hits) / max(1, len(set(keywords)))
        scores[domain] = score
    return scores


def _merge_scores(*score_maps: dict[str, float]) -> dict[str, float]:
    merged: dict[str, float] = defaultdict(float)
    for score_map in score_maps:
        for domain, score in score_map.items():
            merged[domain] += score
    return dict(merged)


def classify_domains(profile_report: dict[str, Any]) -> dict[str, Any]:
    table_results: list[dict[str, Any]] = []

    for table in profile_report.get("tables", []):
        table_name = table.get("table", "")
        table_scores = _score_text(table_name)

        column_results: list[dict[str, Any]] = []
        aggregate_column_scores: dict[str, float] = defaultdict(float)

        for column_name, column_profile in sorted(table.get("columns", {}).items()):
            column_score = _score_text(column_name)

            sample_text = " ".join(str(v) for v in column_profile.get("sampleValues", []))
            sample_score = _score_text(sample_text)

            merged = _merge_scores(column_score, sample_score)
            if not merged:
                column_results.append(
                    {
                        "column": column_name,
                        "domains": ["UNKNOWN"],
                        "confidence": 0.0,
                        "evidence": ["No domain keywords matched"],
                    }
                )
                continue

            ranked = sorted(merged.items(), key=lambda item: (-item[1], item[0]))
            top_domain, top_score = ranked[0]
            confidence = min(1.0, round(top_score * 2.5, 6))
            if confidence < 0.35:
                domains = ["REQUIRES_REVIEW"] + [d for d, _ in ranked[:2]]
            else:
                domains = [d for d, _ in ranked[:2]]

            for domain, score in ranked[:3]:
                aggregate_column_scores[domain] += score

            evidence = [
                f"column='{column_name}'",
                f"sampleValues={column_profile.get('sampleValues', [])[:3]}",
            ]

            column_results.append(
                {
                    "column": column_name,
                    "domains": domains,
                    "confidence": confidence,
                    "evidence": evidence,
                }
            )

        merged_table_scores = _merge_scores(table_scores, dict(aggregate_column_scores))
        if merged_table_scores:
            ranked_table = sorted(merged_table_scores.items(), key=lambda item: (-item[1], item[0]))
            primary_domain, primary_score = ranked_table[0]
            table_confidence = min(1.0, round(primary_score / 1.2, 6))
            table_domains = [d for d, _ in ranked_table[:3]]
            if table_confidence < 0.35:
                table_domains = ["REQUIRES_REVIEW"] + table_domains
        else:
            table_domains = ["UNKNOWN"]
            table_confidence = 0.0

        table_results.append(
            {
                "table": table_name,
                "sourceFile": table.get("sourceFile"),
                "domains": table_domains,
                "confidence": table_confidence,
                "domainLabels": {d: PQ_DOMAINS.get(d, d) for d in table_domains if d in PQ_DOMAINS},
                "columns": column_results,
            }
        )

    return {
        "tables": table_results,
        "summary": {
            "classifiedTables": len(table_results),
            "reviewRequired": sum(1 for t in table_results if "REQUIRES_REVIEW" in t["domains"]),
            "unknown": sum(1 for t in table_results if t["domains"][0] == "UNKNOWN"),
        },
    }
