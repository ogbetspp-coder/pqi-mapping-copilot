"""Lightweight relationship proposer based on key match rates."""

from __future__ import annotations

from typing import Any


def _candidate_key_columns(table_profile: dict[str, Any]) -> list[str]:
    out = []
    for col, stats in table_profile.get("columns", {}).items():
        unique_pct = float(stats.get("unique_pct", 0.0))
        id_score = float(stats.get("id_likelihood", 0.0))
        null_pct = float(stats.get("null_pct", 100.0))
        if (id_score >= 0.6 or unique_pct >= 90.0) and null_pct <= 30.0:
            out.append(col)
    return sorted(out)


def _table_rows_by_name(ingested: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    return {str(t.get("table")): t.get("rows", []) for t in ingested.get("tables", [])}


def _non_empty_values(rows: list[dict[str, str]], column: str) -> list[str]:
    vals = []
    for row in rows:
        value = str(row.get(column, "")).strip()
        if value:
            vals.append(value)
    return vals


def propose_relationships(ingested: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    rows_by_table = _table_rows_by_name(ingested)
    table_profiles = {str(t.get("table")): t for t in profile.get("tables", [])}

    proposals: list[dict[str, Any]] = []
    tables = sorted(table_profiles.keys())

    for i in range(len(tables)):
        left = tables[i]
        left_keys = _candidate_key_columns(table_profiles[left])
        left_rows = rows_by_table.get(left, [])

        for j in range(i + 1, len(tables)):
            right = tables[j]
            right_keys = _candidate_key_columns(table_profiles[right])
            right_rows = rows_by_table.get(right, [])

            for lk in left_keys:
                left_vals = _non_empty_values(left_rows, lk)
                left_set = set(left_vals)
                if not left_set:
                    continue

                for rk in right_keys:
                    right_vals = _non_empty_values(right_rows, rk)
                    right_set = set(right_vals)
                    if not right_set:
                        continue

                    overlap = left_set & right_set
                    if not overlap:
                        continue

                    left_unique = len(left_set) / max(1, len(left_vals))
                    right_unique = len(right_set) / max(1, len(right_vals))

                    if left_unique >= right_unique:
                        parent_table, parent_col = left, lk
                        child_table, child_col = right, rk
                        parent_vals, child_vals = left_set, right_vals
                    else:
                        parent_table, parent_col = right, rk
                        child_table, child_col = left, lk
                        parent_vals, child_vals = right_set, left_vals

                    match_rate = sum(1 for v in child_vals if v in parent_vals) / max(1, len(child_vals))
                    if match_rate < 0.6:
                        continue

                    proposals.append(
                        {
                            "parent": {"table": parent_table, "column": parent_col},
                            "child": {"table": child_table, "column": child_col},
                            "join": f"{child_table}.{child_col} -> {parent_table}.{parent_col}",
                            "match_rate": round(match_rate, 6),
                            "overlap_count": len(overlap),
                            "sample_overlap": sorted(overlap)[:10],
                        }
                    )

    proposals.sort(
        key=lambda p: (
            -float(p["match_rate"]),
            -int(p["overlap_count"]),
            str(p["child"]["table"]),
            str(p["parent"]["table"]),
        )
    )

    return {
        "relationship_proposals": proposals,
        "summary": {
            "proposal_count": len(proposals),
            "high_confidence": sum(1 for p in proposals if p["match_rate"] >= 0.9),
        },
    }
