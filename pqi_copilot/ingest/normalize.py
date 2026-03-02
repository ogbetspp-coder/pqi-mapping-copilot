"""Ingestion and normalization for CSV/JSON/XML extracts."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from pqi_copilot.common import file_sha256, normalize_token, read_csv_rows


def _flatten_dict(data: dict[str, Any], prefix: str = "", depth: int = 0, max_depth: int = 2) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        k = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict) and depth < max_depth:
            out.update(_flatten_dict(value, k, depth + 1, max_depth=max_depth))
        elif isinstance(value, list):
            # Keep small scalar lists as joined text for row context.
            if all(not isinstance(x, (dict, list)) for x in value):
                out[k] = "|".join(str(x) for x in value)
            else:
                out[k] = "[complex-list]"
        else:
            out[k] = value
    return out


def _normalize_row(row: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in row.items():
        normalized = normalize_token(str(key))
        out[normalized] = "" if value is None else str(value)
    return out


def _ingest_csv(path: Path) -> list[dict[str, Any]]:
    try:
        import pandas as pd  # type: ignore

        df = pd.read_csv(path)
        rows = [
            {str(col): ("" if value is None else str(value)) for col, value in row.items()}
            for row in df.to_dict(orient="records")
        ]
    except Exception:
        rows = read_csv_rows(path)

    return [
        {
            "table": path.stem,
            "source_file": str(path),
            "format": "csv",
            "rows": [_normalize_row(r) for r in rows],
            "row_count": len(rows),
            "hash": file_sha256(path),
            "notes": "CSV loaded as tabular rows",
        }
    ]


def _ingest_json(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tables: list[dict[str, Any]] = []

    if isinstance(payload, list) and all(isinstance(x, dict) for x in payload):
        rows = [_normalize_row(item) for item in payload]
        tables.append(
            {
                "table": path.stem,
                "source_file": str(path),
                "format": "json",
                "rows": rows,
                "row_count": len(rows),
                "hash": file_sha256(path),
                "notes": "JSON list-of-objects ingested as one table",
            }
        )
        return tables

    if isinstance(payload, dict):
        list_keys = [k for k, v in payload.items() if isinstance(v, list) and all(isinstance(x, dict) for x in v)]
        if list_keys:
            for key in sorted(list_keys):
                rows = [_normalize_row(item) for item in payload[key]]
                tables.append(
                    {
                        "table": f"{path.stem}_{normalize_token(key)}",
                        "source_file": str(path),
                        "format": "json",
                        "rows": rows,
                        "row_count": len(rows),
                        "hash": file_sha256(path),
                        "notes": f"Extracted list-of-objects from root key '{key}'",
                    }
                )
            return tables

        flattened = _normalize_row(_flatten_dict(payload, max_depth=2))
        tables.append(
            {
                "table": path.stem,
                "source_file": str(path),
                "format": "json",
                "rows": [flattened],
                "row_count": 1,
                "hash": file_sha256(path),
                "notes": "Single JSON object flattened to one row (depth<=2)",
            }
        )
        return tables

    tables.append(
        {
            "table": path.stem,
            "source_file": str(path),
            "format": "json",
            "rows": [],
            "row_count": 0,
            "hash": file_sha256(path),
            "notes": "Unsupported JSON top-level type",
            "unsupported": True,
            "guidance": "Provide list-of-objects or object with list fields.",
        }
    )
    return tables


def _xml_rows_from_repeated_children(root: ET.Element) -> tuple[list[dict[str, str]], str]:
    children = list(root)
    if not children:
        return [], "XML root has no child nodes"

    tags = [child.tag for child in children]
    repeated_tag = None
    for tag in sorted(set(tags)):
        if tags.count(tag) > 1:
            repeated_tag = tag
            break

    if repeated_tag is None and len(children) == 1 and len(list(children[0])) > 1:
        grandkids = list(children[0])
        gt = [g.tag for g in grandkids]
        for tag in sorted(set(gt)):
            if gt.count(tag) > 1:
                repeated_tag = tag
                children = grandkids
                break

    if repeated_tag is None:
        if all(len(list(c)) == 0 for c in children):
            row = {normalize_token(c.tag): ("" if c.text is None else c.text.strip()) for c in children}
            return [row], "Single-row XML interpreted from direct child elements"
        return [], "No repeated row-like nodes detected"

    rows = []
    for child in children:
        if child.tag != repeated_tag:
            continue
        row: dict[str, str] = {}
        for node in list(child):
            row[normalize_token(node.tag)] = "" if node.text is None else node.text.strip()
        if row:
            rows.append(row)

    return rows, f"Repeated XML nodes '{repeated_tag}' extracted as rows"


def _ingest_xml(path: Path) -> list[dict[str, Any]]:
    try:
        root = ET.parse(path).getroot()
    except Exception as exc:
        return [
            {
                "table": path.stem,
                "source_file": str(path),
                "format": "xml",
                "rows": [],
                "row_count": 0,
                "hash": file_sha256(path),
                "unsupported": True,
                "guidance": f"XML parse error: {exc}",
            }
        ]

    rows, note = _xml_rows_from_repeated_children(root)
    unsupported = len(rows) == 0
    guidance = (
        "Use repeated row-like nodes (e.g., <record>...</record>) for best results."
        if unsupported
        else ""
    )

    return [
        {
            "table": path.stem,
            "source_file": str(path),
            "format": "xml",
            "rows": rows,
            "row_count": len(rows),
            "hash": file_sha256(path),
            "notes": note,
            "unsupported": unsupported,
            "guidance": guidance,
        }
    ]


def ingest_folder(input_dir: Path) -> dict[str, Any]:
    tables: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []

    for path in sorted(input_dir.rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        result_tables: list[dict[str, Any]] = []
        if ext == ".csv":
            result_tables = _ingest_csv(path)
        elif ext == ".json":
            result_tables = _ingest_json(path)
        elif ext == ".xml":
            result_tables = _ingest_xml(path)
        else:
            continue

        for table in result_tables:
            if table.get("unsupported"):
                unsupported.append(
                    {
                        "source_file": table.get("source_file"),
                        "format": table.get("format"),
                        "guidance": table.get("guidance", ""),
                    }
                )
            tables.append(table)

    return {
        "tables": tables,
        "unsupported": unsupported,
        "stats": {
            "table_count": len(tables),
            "unsupported_count": len(unsupported),
            "row_count": sum(int(t.get("row_count", 0)) for t in tables),
        },
    }
