"""Profiling engine for normalized tables."""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from typing import Any

from pqi_copilot.common import parse_date_like

ID_NAME_HINTS = {
    "id",
    "batch_id",
    "lot",
    "lot_number",
    "material_id",
    "product_id",
    "sample_id",
    "specimen_id",
    "test_id",
    "result_id",
}

UCUMISH_UNITS = {
    "mg",
    "g",
    "kg",
    "ug",
    "ml",
    "l",
    "%",
    "ppm",
    "ppb",
    "c",
    "degc",
    "h",
    "hr",
    "day",
}

REGEX_PATTERNS = {
    "batch_like": re.compile(r"(?i)^(batch|lot)[-_]?[a-z0-9]+$"),
    "date_iso": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "datetime_iso": re.compile(r"^\d{4}-\d{2}-\d{2}[tT ]\d{2}:\d{2}(:\d{2})?([zZ]|[+-]\d{2}:?\d{2})?$"),
    "numeric": re.compile(r"^[+-]?\d+(\.\d+)?$"),
    "unit_suffix": re.compile(r"^[+-]?\d+(\.\d+)?\s*([A-Za-z%/]+)$"),
}


def infer_type(values: list[str]) -> str:
    non_empty = [v.strip() for v in values if str(v).strip()]
    if not non_empty:
        return "unknown"

    if all(v.lower() in {"true", "false", "yes", "no"} for v in non_empty):
        return "boolean"
    if all(REGEX_PATTERNS["numeric"].match(v) for v in non_empty):
        return "number"

    parsed_dates = sum(1 for v in non_empty if parse_date_like(v) is not None)
    if parsed_dates / len(non_empty) >= 0.8:
        if any("t" in v.lower() or ":" in v for v in non_empty):
            return "datetime"
        return "date"
    return "string"


def _numeric_stats(values: list[str]) -> dict[str, Any]:
    nums = []
    for v in values:
        try:
            nums.append(float(v))
        except Exception:
            continue
    if not nums:
        return {}
    return {
        "min": min(nums),
        "max": max(nums),
        "mean": round(sum(nums) / len(nums), 6),
    }


def _date_stats(values: list[str]) -> dict[str, Any]:
    dates: list[datetime] = []
    for v in values:
        parsed = parse_date_like(v)
        if parsed is not None:
            dates.append(parsed)
    if not dates:
        return {}
    dates.sort()
    return {
        "min": dates[0].isoformat(),
        "max": dates[-1].isoformat(),
    }


def detect_units(values: list[str], column_name: str) -> list[str]:
    found: Counter[str] = Counter()
    col = column_name.lower()

    if "unit" in col or "uom" in col:
        for v in values:
            token = v.strip().lower()
            if token:
                found[token] += 1

    for v in values:
        m = REGEX_PATTERNS["unit_suffix"].match(v.strip())
        if m:
            found[m.group(2).lower()] += 1

    filtered = [(u, c) for u, c in found.items() if u in UCUMISH_UNITS or len(u) <= 8]
    filtered.sort(key=lambda t: (-t[1], t[0]))
    return [u for u, _ in filtered[:5]]


def regex_hits(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for name, pattern in REGEX_PATTERNS.items():
        out[name] = sum(1 for v in values if pattern.match(v.strip()))
    return out


def id_likelihood(column_name: str, values: list[str], unique_ratio: float, inferred_type: str) -> float:
    score = 0.0
    name = column_name.lower()
    if name in ID_NAME_HINTS or name.endswith("_id"):
        score += 0.5
    if unique_ratio >= 0.95:
        score += 0.3
    if inferred_type == "string" and all(len(v) <= 64 for v in values if v.strip()):
        score += 0.1
    if inferred_type in {"number", "datetime", "date"}:
        score -= 0.1
    return max(0.0, min(1.0, round(score, 6)))


def profile_normalized(ingested: dict[str, Any]) -> dict[str, Any]:
    tables_out: list[dict[str, Any]] = []

    for table in sorted(ingested.get("tables", []), key=lambda t: str(t.get("table", ""))):
        rows = table.get("rows", [])
        row_count = len(rows)
        columns = sorted({key for row in rows for key in row.keys()})

        by_col: dict[str, list[str]] = {c: [] for c in columns}
        for row in rows:
            for col in columns:
                by_col[col].append(str(row.get(col, "")))

        profile_cols: dict[str, Any] = {}
        for col in columns:
            values = by_col[col]
            non_empty = [v for v in values if v.strip()]
            distinct = set(non_empty)
            freq = Counter(non_empty)

            inferred = infer_type(values)
            null_pct = round((1 - (len(non_empty) / max(1, row_count))) * 100, 6)
            unique_pct = round((len(distinct) / max(1, len(non_empty))) * 100, 6)

            top_values = [
                {"value": v, "count": c}
                for v, c in sorted(freq.items(), key=lambda item: (-item[1], item[0]))[:8]
            ]

            col_profile = {
                "inferred_type": inferred,
                "null_pct": null_pct,
                "unique_pct": unique_pct,
                "top_values": top_values,
                "sample_values": sorted(distinct)[:8],
                "regex_hits": regex_hits(non_empty),
                "units": detect_units(non_empty, col),
                "id_likelihood": id_likelihood(col, non_empty, unique_pct / 100.0, inferred),
            }
            if inferred == "number":
                col_profile["numeric_stats"] = _numeric_stats(non_empty)
            if inferred in {"date", "datetime"}:
                col_profile["date_stats"] = _date_stats(non_empty)

            profile_cols[col] = col_profile

        table_out = {
            "table": table.get("table"),
            "source_file": table.get("source_file"),
            "format": table.get("format"),
            "row_count": row_count,
            "columns": profile_cols,
            "notes": table.get("notes", ""),
            "hash": table.get("hash"),
        }
        if table.get("unsupported"):
            table_out["unsupported"] = True
            table_out["guidance"] = table.get("guidance", "")

        tables_out.append(table_out)

    return {
        "tables": tables_out,
        "summary": {
            "table_count": len(tables_out),
            "row_count": sum(t["row_count"] for t in tables_out),
            "unsupported_count": sum(1 for t in tables_out if t.get("unsupported")),
        },
    }


def profile_markdown(profile: dict[str, Any]) -> str:
    lines = ["# Data Profile", ""]
    lines.append(f"Tables: {profile.get('summary', {}).get('table_count', 0)}")
    lines.append(f"Rows: {profile.get('summary', {}).get('row_count', 0)}")
    lines.append("")

    for table in profile.get("tables", []):
        lines.append(f"## Table: {table.get('table')}")
        lines.append(f"- Source: {table.get('source_file')}")
        lines.append(f"- Rows: {table.get('row_count')}")
        if table.get("unsupported"):
            lines.append(f"- Unsupported: {table.get('guidance', '')}")
        lines.append("")
        lines.append("| Column | Type | Null% | Unique% | ID Score | Units |")
        lines.append("|---|---:|---:|---:|---:|---|")
        for col, stat in sorted(table.get("columns", {}).items()):
            lines.append(
                "| {c} | {t} | {n:.2f} | {u:.2f} | {i:.2f} | {units} |".format(
                    c=col,
                    t=stat.get("inferred_type", ""),
                    n=stat.get("null_pct", 0.0),
                    u=stat.get("unique_pct", 0.0),
                    i=stat.get("id_likelihood", 0.0),
                    units=", ".join(stat.get("units", [])),
                )
            )
        lines.append("")

    return "\n".join(lines) + "\n"
