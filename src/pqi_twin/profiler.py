"""Profiling for raw source extracts (CSV/JSON/XML)."""

from __future__ import annotations

import csv
import json
import math
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import file_sha256, normalize_label


UNIT_PATTERN = re.compile(r"^\s*[-+]?\d+(?:\.\d+)?\s*([A-Za-z%\u00b0/]+)\s*$")


@dataclass(frozen=True)
class LoadedTable:
    file_path: Path
    table_name: str
    rows: list[dict[str, Any]]


ALIASES = {
    "batch": {"batch_id", "lot", "lot_number", "batch_number"},
    "material": {"material_id", "product_id", "item_id"},
    "organization": {"organization_id", "site_id", "manufacturer_id"},
}


def _infer_scalar(value: str) -> str:
    text = value.strip()
    if not text:
        return "null"
    lowered = text.lower()
    if lowered in {"true", "false", "yes", "no"}:
        return "boolean"
    if re.fullmatch(r"[-+]?\d+", text):
        return "integer"
    if re.fullmatch(r"[-+]?\d+\.\d+", text):
        return "number"
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y/%m/%d"):
        try:
            datetime.strptime(text, fmt)
            return "date"
        except ValueError:
            pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            datetime.strptime(text, fmt)
            return "datetime"
        except ValueError:
            pass
    return "string"


def _dominant_type(values: list[str]) -> str:
    if not values:
        return "unknown"
    counts = Counter(_infer_scalar(v) for v in values if v.strip())
    if not counts:
        return "unknown"
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _detect_units(column_name: str, values: list[str]) -> list[str]:
    detected: Counter[str] = Counter()
    lower_col = column_name.lower()

    if "unit" in lower_col and values:
        for value in values:
            text = str(value).strip()
            if text:
                detected[text] += 1

    for value in values:
        match = UNIT_PATTERN.match(str(value))
        if match:
            detected[match.group(1)] += 1

    return [u for u, _ in sorted(detected.items(), key=lambda item: (-item[1], item[0]))[:5]]


def _load_csv(path: Path) -> LoadedTable:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k: ("" if v is None else str(v)) for k, v in row.items()})
    return LoadedTable(file_path=path, table_name=path.stem, rows=rows)


def _load_json(path: Path) -> LoadedTable:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, list):
        rows = [dict(item) for item in payload if isinstance(item, dict)]
    elif isinstance(payload, dict):
        if isinstance(payload.get("records"), list):
            rows = [dict(item) for item in payload["records"] if isinstance(item, dict)]
        else:
            rows = [dict(payload)]
    else:
        rows = []

    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        normalized_rows.append({str(k): "" if v is None else str(v) for k, v in row.items()})
    return LoadedTable(file_path=path, table_name=path.stem, rows=normalized_rows)


def _load_xml(path: Path) -> LoadedTable:
    root = ET.parse(path).getroot()
    children = list(root)

    rows: list[dict[str, Any]] = []
    if children and all(len(list(child)) > 0 for child in children):
        for child in children:
            row: dict[str, Any] = {}
            for node in child:
                row[node.tag] = "" if node.text is None else node.text
            rows.append(row)
    else:
        row = {child.tag: "" if child.text is None else child.text for child in children}
        if row:
            rows.append(row)

    return LoadedTable(file_path=path, table_name=path.stem, rows=rows)


def load_tables(input_dir: Path) -> list[LoadedTable]:
    tables: list[LoadedTable] = []
    for path in sorted(input_dir.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix == ".csv":
            tables.append(_load_csv(path))
        elif suffix == ".json":
            tables.append(_load_json(path))
        elif suffix == ".xml":
            tables.append(_load_xml(path))
    return tables


def _profile_column(values: list[str], row_count: int, column_name: str) -> dict[str, Any]:
    non_null = [v for v in values if str(v).strip()]
    distinct_values = set(non_null)

    freq = Counter(non_null)
    top_values = [
        {"value": value, "count": count}
        for value, count in sorted(freq.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]

    null_ratio = 0.0 if row_count == 0 else (row_count - len(non_null)) / row_count
    unique_ratio = 0.0 if len(non_null) == 0 else len(distinct_values) / len(non_null)

    samples = sorted(distinct_values)[:5]

    return {
        "inferredType": _dominant_type([str(v) for v in non_null]),
        "nullRatio": round(null_ratio, 6),
        "distinctCount": len(distinct_values),
        "uniqueRatio": round(unique_ratio, 6),
        "topValues": top_values,
        "sampleValues": samples,
        "detectedUnits": _detect_units(column_name, [str(v) for v in non_null]),
    }


def _canonical_join_key(column_name: str) -> str:
    normalized = normalize_label(column_name)
    for alias_key, alias_values in ALIASES.items():
        if normalized in alias_values:
            return alias_key
    return normalized


def _compute_joins(tables: list[LoadedTable]) -> list[dict[str, Any]]:
    column_index: dict[str, list[tuple[str, str, set[str]]]] = defaultdict(list)

    for table in tables:
        columns = sorted({col for row in table.rows for col in row.keys()})
        for column in columns:
            values = {
                str(row.get(column, "")).strip()
                for row in table.rows
                if str(row.get(column, "")).strip()
            }
            if not values:
                continue
            canonical = _canonical_join_key(column)
            column_index[canonical].append((table.table_name, column, values))

    joins: list[dict[str, Any]] = []
    for canonical, refs in sorted(column_index.items()):
        if len(refs) < 2:
            continue
        for i in range(len(refs)):
            left_table, left_column, left_values = refs[i]
            for j in range(i + 1, len(refs)):
                right_table, right_column, right_values = refs[j]
                overlap = left_values & right_values
                if not overlap:
                    continue
                overlap_ratio = len(overlap) / max(1, min(len(left_values), len(right_values)))
                if overlap_ratio < 0.25:
                    continue
                joins.append(
                    {
                        "left": {"table": left_table, "column": left_column},
                        "right": {"table": right_table, "column": right_column},
                        "canonicalKey": canonical,
                        "overlapCount": len(overlap),
                        "overlapRatio": round(overlap_ratio, 6),
                        "sampleOverlapValues": sorted(overlap)[:5],
                    }
                )

    joins.sort(
        key=lambda j: (
            -j["overlapRatio"],
            -j["overlapCount"],
            j["left"]["table"],
            j["right"]["table"],
            j["canonicalKey"],
        )
    )
    return joins


def profile_input_extracts(input_dir: Path) -> dict[str, Any]:
    tables = load_tables(input_dir)
    input_dir_resolved = input_dir.resolve()

    table_reports: list[dict[str, Any]] = []
    for table in sorted(tables, key=lambda t: t.table_name):
        row_count = len(table.rows)
        columns = sorted({column for row in table.rows for column in row.keys()})

        by_column: dict[str, list[str]] = {column: [] for column in columns}
        for row in table.rows:
            for column in columns:
                by_column[column].append(str(row.get(column, "")))

        column_profiles = {
            column: _profile_column(values, row_count, column)
            for column, values in sorted(by_column.items())
        }

        candidate_keys = [
            column
            for column, profile in column_profiles.items()
            if profile["uniqueRatio"] >= 0.95 and profile["nullRatio"] <= 0.05
        ]

        table_reports.append(
            {
                "table": table.table_name,
                "sourceFile": str(
                    table.file_path.resolve().relative_to(input_dir_resolved)
                    if table.file_path.resolve().is_relative_to(input_dir_resolved)
                    else table.file_path
                ),
                "fileHash": file_sha256(table.file_path),
                "rowCount": row_count,
                "columns": column_profiles,
                "candidateKeys": sorted(candidate_keys),
            }
        )

    joins = _compute_joins(tables)

    return {
        "tables": table_reports,
        "candidateJoins": joins,
        "profileStats": {
            "tableCount": len(table_reports),
            "joinCount": len(joins),
            "totalRows": sum(t["rowCount"] for t in table_reports),
            "containsMixedFormats": True,
        },
    }
