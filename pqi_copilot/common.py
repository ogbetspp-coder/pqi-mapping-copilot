"""Shared utilities with deterministic serialization and optional dependency adapters."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


def stable_json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_hash_obj(value: Any) -> str:
    return hashlib.sha256(stable_json_dumps(value).encode("utf-8")).hexdigest()


def stable_hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "unknown"


def normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def split_identifier(value: str) -> list[str]:
    value = re.sub(r"([a-z])([A-Z])", r"\1_\2", value)
    return [t for t in re.split(r"[^A-Za-z0-9]+", value) if t]


def parse_date_like(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None

    # dateutil preferred; fallback to known formats
    try:
        from dateutil import parser as date_parser  # type: ignore

        return date_parser.parse(value)
    except Exception:
        pass

    for fmt in (
        "%Y-%m-%d",
        "%Y-%m",
        "%Y/%m/%d",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def obj_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    serializable = obj_to_dict(payload)
    with path.open("w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, sort_keys=True)


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "" or any(c in text for c in ":#\n{}[]") or text.strip() != text:
        return json.dumps(text, ensure_ascii=True)
    return text


def to_yaml(value: Any, indent: int = 0) -> str:
    pad = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key in sorted(value.keys()):
            v = value[key]
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}{key}:")
                lines.append(to_yaml(v, indent + 2))
            else:
                lines.append(f"{pad}{key}: {yaml_scalar(v)}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}-")
                lines.append(to_yaml(item, indent + 2))
            else:
                lines.append(f"{pad}- {yaml_scalar(item)}")
        return "\n".join(lines)
    return f"{pad}{yaml_scalar(value)}"


def write_yaml(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(to_yaml(obj_to_dict(payload)) + "\n", encoding="utf-8")


def read_simple_yaml(path: Path) -> dict[str, Any]:
    """Very small YAML parser for key: value pairs used in approval config."""
    out: dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, raw = stripped.split(":", 1)
        key = key.strip()
        raw = raw.strip()
        if raw.lower() in {"true", "false"}:
            out[key] = raw.lower() == "true"
            continue
        try:
            if "." in raw:
                out[key] = float(raw)
            else:
                out[key] = int(raw)
            continue
        except ValueError:
            pass
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        out[key] = raw
    return out


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [{k: "" if v is None else str(v) for k, v in row.items()} for row in reader]


def similarity(a: str, b: str) -> float:
    a = a or ""
    b = b or ""
    try:
        from rapidfuzz.fuzz import token_set_ratio  # type: ignore

        return float(token_set_ratio(a, b)) / 100.0
    except Exception:
        from difflib import SequenceMatcher

        return SequenceMatcher(None, a, b).ratio()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pqi-copilot")
    sub = parser.add_subparsers(dest="command", required=True)

    ig_parser = sub.add_parser("ig", help="IG catalog utilities")
    ig_sub = ig_parser.add_subparsers(dest="ig_command", required=True)

    ig_sub.add_parser("index", help="Build IG catalog")
    p = ig_sub.add_parser("list-profiles", help="List indexed profiles")
    p.add_argument("--contains", default="", help="Case-insensitive filter")
    p = ig_sub.add_parser("show-profile", help="Show one profile")
    p.add_argument("profile_url", help="Profile canonical URL")

    p = sub.add_parser("propose", help="Run ingest/profile/classify/propose")
    p.add_argument("input_dir", help="Folder containing CSV/JSON/XML extracts")

    p = sub.add_parser("report", help="Render report for run")
    p.add_argument("run_id", help="Run ID")

    p = sub.add_parser("approve", help="Approve proposals from run")
    p.add_argument("run_id", help="Run ID")
    p.add_argument("--rules", required=True, help="Path to approval config YAML")
    p.add_argument("--overrides", default=None, help="Optional path to manual approval overrides YAML")
    p.add_argument("--mapping-name", default="batch-lot-analysis", help="Library mapping name")

    lib = sub.add_parser("library", help="Library operations")
    lib_sub = lib.add_subparsers(dest="library_command", required=True)
    lib_sub.add_parser("list", help="List library artifacts")

    p = sub.add_parser("generate", help="Generate minimal bundle from approved mappings")
    p.add_argument("run_id", help="Run ID")
    p.add_argument("--mapping-name", default="batch-lot-analysis", help="Library mapping name")

    return parser
