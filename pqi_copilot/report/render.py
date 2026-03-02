"""Stakeholder-friendly report rendering (Markdown + HTML)."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from pqi_copilot.common import read_json, write_text
from pqi_copilot.governance.store import run_dir


def _table_overview(profile: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for table in profile.get("tables", []):
        out.append(
            {
                "table": table.get("table"),
                "source_file": table.get("source_file"),
                "rows": table.get("row_count"),
                "columns": len(table.get("columns", {})),
            }
        )
    return out


def _classification_map(classification: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for table in classification.get("tables", []):
        out[str(table.get("table"))] = table
    return out


def _top_candidates(proposals: dict[str, Any], k: int = 1) -> list[dict[str, Any]]:
    out = []
    for p in proposals.get("proposals", []):
        candidates = sorted(
            p.get("candidates", []),
            key=lambda c: (-float(c.get("confidence", 0.0)), str(c.get("target", {}).get("elementPath", "")),),
        )
        out.append(
            {
                "source": p.get("source", {}),
                "domain": p.get("domain", {}),
                "candidates": candidates[:k],
            }
        )
    return out


def generate_markdown_report(run_id: str) -> str:
    base = run_dir(run_id)
    profile = read_json(base / "profile.json")
    classification = read_json(base / "domain_classification.json")
    proposals = read_json(base / "mapping_proposals.json")
    relationships = read_json(base / "relationship_proposals.json")

    class_map = _classification_map(classification)
    tops = _top_candidates(proposals, k=2)

    lines = [f"# PQI Mapping Copilot Report - {run_id}", ""]
    lines.append("## Dataset Overview")
    lines.append("")
    lines.append("| Table | Source File | Rows | Columns |")
    lines.append("|---|---|---:|---:|")
    for row in _table_overview(profile):
        lines.append(f"| {row['table']} | {row['source_file']} | {row['rows']} | {row['columns']} |")

    lines.append("")
    lines.append("## Domain Classification")
    lines.append("")
    lines.append("| Table | Primary Domain | Scores | Rationale (top) |")
    lines.append("|---|---|---|---|")
    for table in classification.get("tables", []):
        scores = table.get("domain_scores", {})
        score_text = ", ".join(f"{k}={v:.2f}" for k, v in sorted(scores.items()))
        rat = table.get("rationale", {})
        top = []
        for domain, reasons in rat.items():
            if reasons:
                top.append(f"{domain}:{reasons[0]}")
        lines.append(
            f"| {table.get('table')} | {table.get('primary_domain')} | {score_text} | {'; '.join(top[:2])} |"
        )

    lines.append("")
    lines.append("## Top Mapping Candidates")
    lines.append("")
    lines.append("| Source | Domain | Candidate Target | Confidence | Status | Evidence |")
    lines.append("|---|---|---|---:|---|---|")
    unresolved = []
    for item in tops:
        source = item.get("source", {})
        source_label = f"{source.get('table')}.{source.get('column')}"
        domain = item.get("domain", {}).get("primary")
        if not item.get("candidates"):
            unresolved.append(source_label)
            lines.append(f"| {source_label} | {domain} | (none) | 0.00 | REQUIRES_REVIEW | no candidates |")
            continue
        best = item["candidates"][0]
        target = best.get("target", {})
        evidence = best.get("evidence", {})
        rules = evidence.get("rules_fired", {})
        brief = "; ".join(
            [
                *(rules.get("name", [])[:1] if isinstance(rules.get("name"), list) else []),
                *(rules.get("datatype", [])[:1] if isinstance(rules.get("datatype"), list) else []),
            ]
        )
        lines.append(
            f"| {source_label} | {domain} | {target.get('resourceType')}::{target.get('elementPath')} | "
            f"{float(best.get('confidence', 0.0)):.2f} | {best.get('status')} | {brief} |"
        )
        if best.get("status") == "REQUIRES_REVIEW":
            unresolved.append(source_label)

    lines.append("")
    lines.append("## Relationship Suggestions")
    lines.append("")
    lines.append("| Join | Match Rate | Overlap |")
    lines.append("|---|---:|---:|")
    for rel in relationships.get("relationship_proposals", []):
        lines.append(
            f"| {rel.get('join')} | {100*float(rel.get('match_rate', 0.0)):.1f}% | {rel.get('overlap_count')} |"
        )

    lines.append("")
    lines.append("## Unresolved / Ambiguous Items")
    lines.append("")
    if unresolved:
        for u in sorted(set(unresolved)):
            lines.append(f"- {u}")
    else:
        lines.append("- None")

    lines.append("")
    lines.append("## Decisions Required From SMEs")
    lines.append("")
    if unresolved:
        lines.append("- Confirm target profile/element for unresolved columns listed above.")
        lines.append("- Confirm terminology mapping for code-like fields lacking ValueSet bindings.")
    else:
        lines.append("- Validate high-confidence mappings before approval.")

    return "\n".join(lines) + "\n"


def markdown_to_basic_html(md_text: str) -> str:
    lines = md_text.splitlines()
    html_lines = ["<html><head><meta charset='utf-8'><title>PQI Mapping Copilot Report</title>"]
    html_lines.append(
        "<style>body{font-family:Arial,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;}"
        "table{border-collapse:collapse;width:100%;margin:1rem 0;}"
        "th,td{border:1px solid #ccc;padding:.4rem;text-align:left;}"
        "h1,h2{color:#0b3a57;} code{background:#f3f4f6;padding:2px 4px;}</style>"
    )
    html_lines.append("</head><body>")

    in_table = False
    for line in lines:
        if line.startswith("# "):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("|") and line.endswith("|"):
            parts = [html.escape(p.strip()) for p in line.strip("|").split("|")]
            if all(set(p) <= {"-", ":"} for p in parts):
                continue
            if not in_table:
                html_lines.append("<table>")
                in_table = True
            tag = "th" if "---" not in line else "td"
            html_lines.append("<tr>" + "".join(f"<{tag}>{p}</{tag}>" for p in parts) + "</tr>")
        elif line.startswith("- "):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<p>&bull; {html.escape(line[2:])}</p>")
        elif line.strip() == "":
            if in_table:
                pass
            else:
                html_lines.append("<br/>")
        else:
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<p>{html.escape(line)}</p>")

    if in_table:
        html_lines.append("</table>")

    html_lines.append("</body></html>")
    return "\n".join(html_lines)


def render_report_files(run_id: str) -> dict[str, str]:
    base = run_dir(run_id)
    markdown = generate_markdown_report(run_id)
    md_path = base / "report.md"
    write_text(md_path, markdown)

    try:
        from jinja2 import Template  # type: ignore

        template = Template("<html><body><pre>{{ text }}</pre></body></html>")
        html_text = template.render(text=markdown)
    except Exception:
        html_text = markdown_to_basic_html(markdown)

    html_path = base / "report.html"
    write_text(html_path, html_text)

    return {"markdown": str(md_path), "html": str(html_path)}
