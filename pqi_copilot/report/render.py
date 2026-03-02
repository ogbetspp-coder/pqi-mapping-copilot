"""Stakeholder-friendly report rendering (Markdown + HTML)."""

from __future__ import annotations

import html
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


def _top_candidates(proposals: dict[str, Any], k: int = 1) -> list[dict[str, Any]]:
    out = []
    for p in proposals.get("proposals", []):
        candidates = sorted(
            p.get("candidates", []),
            key=lambda c: (
                -float(c.get("confidence", 0.0)),
                str(c.get("target", {}).get("resourceType", "")),
                str(c.get("target", {}).get("elementPath", "")),
            ),
        )
        out.append(
            {
                "source": p.get("source", {}),
                "domain": p.get("domain", {}),
                "table_model": p.get("table_model", {}),
                "disposition": p.get("disposition", "IN_SCOPE"),
                "candidates": candidates[:k],
            }
        )
    return out


def generate_markdown_report(run_id: str) -> str:
    base = run_dir(run_id)
    profile = read_json(base / "profile.json")
    classification = read_json(base / "domain_classification.json")
    resource_classification = read_json(base / "resource_classification.json")
    proposals = read_json(base / "mapping_proposals.json")
    relationships = read_json(base / "relationship_proposals.json")
    decisions = read_json(base / "decisions.json")

    tops = _top_candidates(proposals, k=3)
    top_labels: dict[str, int] = {}
    out_of_scope_fields = 0
    for item in tops:
        if item.get("disposition") == "OUT_OF_SCOPE":
            out_of_scope_fields += 1
            continue
        candidates = item.get("candidates", [])
        if not candidates:
            continue
        label = str(candidates[0].get("label", "REQUIRES_SME"))
        top_labels[label] = top_labels.get(label, 0) + 1

    lines = [f"# PQI Mapping Copilot Report - {run_id}", ""]
    lines.append("## Workshop Summary")
    lines.append("")
    lines.append(f"- Auto-approve candidates: {top_labels.get('AUTO_APPROVE_CANDIDATE', 0)}")
    lines.append(f"- Good candidates: {top_labels.get('GOOD_CANDIDATE', 0)}")
    lines.append(f"- SME decisions required: {int(decisions.get('summary', {}).get('decision_count', 0))}")
    lines.append(f"- Out-of-scope fields: {out_of_scope_fields}")
    lines.append("")
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
    lines.append("## Table-to-Resource Model")
    lines.append("")
    lines.append("| Table | Primary Resource | Resource Scores | Rationale (top) |")
    lines.append("|---|---|---|---|")
    for table in resource_classification.get("tables", []):
        scores = table.get("resource_scores", {})
        score_text = ", ".join(f"{k}={v:.2f}" for k, v in sorted(scores.items()))
        rat = table.get("rationale", {})
        top = []
        for resource, reasons in rat.items():
            if reasons:
                top.append(f"{resource}:{reasons[0]}")
        lines.append(
            f"| {table.get('table')} | {table.get('primary_resource')} | {score_text} | {'; '.join(top[:2])} |"
        )

    lines.append("")
    lines.append("## Out-of-Scope Tables")
    lines.append("")
    lines.append("| Table | Reason (top) |")
    lines.append("|---|---|")
    out_tables = [t for t in classification.get("tables", []) if t.get("primary_domain") == "out_of_scope"]
    if out_tables:
        for table in out_tables:
            reasons = table.get("rationale", {}).get("out_of_scope", [])
            lines.append(f"| {table.get('table')} | {('; '.join(reasons[:2]) if reasons else 'n/a')} |")
    else:
        lines.append("| (none) | - |")

    lines.append("")
    lines.append("## Decisions Required From SMEs")
    lines.append("")
    lines.append("| Decision | Source | Why | Top Option | Question |")
    lines.append("|---|---|---|---|---|")
    if decisions.get("decisions"):
        for d in decisions.get("decisions", []):
            options = d.get("proposed", [])
            if options:
                top_opt = options[0]
                option_text = f"{top_opt.get('target')} ({float(top_opt.get('confidence', 0.0)):.2f})"
            else:
                option_text = "(none)"
            lines.append(
                f"| {d.get('decision_id')} | {d.get('source')} | {d.get('why')} | {option_text} | {d.get('question_for_sme')} |"
            )
    else:
        lines.append("| - | - | No SME decisions required | - | - |")

    lines.append("")
    lines.append("## Top Mapping Candidates")
    lines.append("")
    lines.append("| Source | Domain | Table Resource | Candidate Target | Confidence | Label | Status | Evidence |")
    lines.append("|---|---|---|---|---:|---|---|---|")
    unresolved = []
    for item in tops:
        source = item.get("source", {})
        source_label = f"{source.get('table')}.{source.get('column')}"
        domain = item.get("domain", {}).get("primary")
        table_resource = item.get("table_model", {}).get("primary_resource")
        disposition = str(item.get("disposition", "IN_SCOPE"))

        if disposition == "OUT_OF_SCOPE":
            lines.append(
                f"| {source_label} | {domain} | {table_resource} | OUT_OF_SCOPE | 0.00 | REQUIRES_SME | REQUIRES_REVIEW | out_of_scope_non_anchor |"
            )
            continue

        if not item.get("candidates"):
            unresolved.append(source_label)
            lines.append(
                f"| {source_label} | {domain} | {table_resource} | (none) | 0.00 | REQUIRES_SME | REQUIRES_REVIEW | no candidates |"
            )
            continue

        best = item["candidates"][0]
        target = best.get("target", {})
        evidence = best.get("evidence", {})
        rules = evidence.get("rules_fired", {})
        brief = "; ".join(
            [
                *(rules.get("name", [])[:1] if isinstance(rules.get("name"), list) else []),
                *(rules.get("datatype", [])[:1] if isinstance(rules.get("datatype"), list) else []),
                *(rules.get("hard_rules", [])[:1] if isinstance(rules.get("hard_rules"), list) else []),
            ]
        )

        lines.append(
            f"| {source_label} | {domain} | {table_resource} | {target.get('resourceType')}::{target.get('elementPath')} | "
            f"{float(best.get('confidence', 0.0)):.2f} | {best.get('label')} | {best.get('status')} | {brief} |"
        )
        if best.get("status") == "REQUIRES_REVIEW" or best.get("label") == "REQUIRES_SME":
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
