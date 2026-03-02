from __future__ import annotations

import json
import os
import shutil
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from pqi_copilot.common import ensure_dir, read_json, write_json, write_yaml
from pqi_copilot.governance.store import approve_run, run_dir
from pqi_copilot.pipeline import ensure_catalog, propose_run
from pqi_copilot.report.render import render_report_files

WORKSPACES_ROOT = Path(".workspaces")


def _new_session_id() -> str:
    return f"s-{uuid.uuid4().hex[:10]}"


def _workspace_paths(session_id: str) -> dict[str, Path]:
    root = WORKSPACES_ROOT / session_id
    paths = {
        "root": root,
        "inputs": root / "inputs",
        "artifacts": root / "artifacts",
        "exports": root / "exports",
    }
    for p in paths.values():
        ensure_dir(p)
    return paths


def _set_runtime_env(artifacts_dir: Path, ig_source: str) -> None:
    os.environ["PQI_ARTIFACTS_ROOT"] = str(artifacts_dir)
    if ig_source.strip():
        os.environ["PQI_IG_SOURCE"] = ig_source.strip()
    else:
        os.environ.pop("PQI_IG_SOURCE", None)


def _copy_examples(inputs_dir: Path) -> int:
    src = Path("data/examples")
    copied = 0
    if not src.exists():
        return copied
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".csv", ".json", ".xml"}:
            continue
        target = inputs_dir / path.name
        shutil.copy2(path, target)
        copied += 1
    return copied


def _source_id(proposal: dict[str, Any]) -> str:
    source = proposal.get("source", {})
    return f"{source.get('table')}.{source.get('column')}"


def _table_rows_from_proposals(proposals: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for proposal in proposals.get("proposals", []):
        source = proposal.get("source", {})
        for idx, candidate in enumerate(proposal.get("candidates", [])[:3], start=1):
            target = candidate.get("target", {})
            rows.append(
                {
                    "source": f"{source.get('table')}.{source.get('column')}",
                    "domain": proposal.get("domain", {}).get("primary"),
                    "disposition": proposal.get("disposition"),
                    "rank": idx,
                    "resourceType": target.get("resourceType"),
                    "elementPath": target.get("elementPath"),
                    "confidence": float(candidate.get("confidence", 0.0)),
                    "label": candidate.get("label"),
                    "status": candidate.get("status"),
                    "flags": ",".join(candidate.get("flags", [])),
                }
            )
    return rows


def _build_overrides(
    proposals: dict[str, Any],
    decisions: dict[str, Any],
    threshold: float,
    require_proposed: bool,
    mapping_name: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    overrides: dict[str, Any] = {}
    choice_map: dict[str, str] = {}

    # Auto selections.
    for proposal in proposals.get("proposals", []):
        source_id = _source_id(proposal)
        candidates = proposal.get("candidates", [])
        if not candidates:
            continue
        top = candidates[0]
        if require_proposed and top.get("status") != "PROPOSED":
            continue
        conf = float(top.get("confidence", 0.0))
        label = str(top.get("label", ""))
        if label == "AUTO_APPROVE_CANDIDATE" or conf >= threshold:
            target = top.get("target", {})
            overrides[source_id] = {
                "select": {
                    "profileUrl": str(target.get("profileUrl", "")),
                    "resourceType": str(target.get("resourceType", "")),
                    "elementPath": str(target.get("elementPath", "")),
                }
            }

    # Manual picks for decision rows.
    for decision in decisions.get("decisions", []):
        source = str(decision.get("source", ""))
        options = decision.get("proposed", [])
        labels = [
            f"{idx+1}. {o.get('resourceType')}::{o.get('target')} ({float(o.get('confidence', 0.0)):.2f})"
            for idx, o in enumerate(options)
        ]
        labels.append("DEFER/UNMAPPED")
        current = st.session_state.get(f"manual_choice::{source}", labels[0] if labels else "DEFER/UNMAPPED")
        choice = st.selectbox(
            f"{source}",
            options=labels,
            index=max(0, labels.index(current) if current in labels else 0),
            key=f"manual_choice::{source}",
        )
        choice_map[source] = choice

        if choice == "DEFER/UNMAPPED":
            overrides[source] = {"action": "UNMAPPED", "reason": "Deferred by SME in Streamlit review"}
            continue
        if not options:
            continue
        idx = labels.index(choice)
        selected = options[idx]
        overrides[source] = {
            "select": {
                "resourceType": str(selected.get("resourceType", "")),
                "elementPath": str(selected.get("target", "")),
            }
        }

    rules = {
        "confidence_threshold": round(float(threshold), 6),
        "require_status_proposed": bool(require_proposed),
    }
    metadata = {"mapping_name": mapping_name}
    return overrides, rules, choice_map


def _zip_workspace(workspace: Path, run_id: str, mapping_name: str) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        include_roots = [
            workspace / "inputs",
            workspace / "exports",
            workspace / "artifacts" / "runs" / run_id,
            workspace / "artifacts" / "library" / "mappings" / mapping_name,
        ]
        for root in include_roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file():
                    continue
                arcname = str(path.relative_to(workspace))
                zf.write(path, arcname=arcname)
    return buf.getvalue()


st.set_page_config(page_title="PQI Mapping Copilot", layout="wide")
st.title("PQI Mapping Copilot (Local Streamlit Demo)")

if "session_id" not in st.session_state:
    st.session_state["session_id"] = _new_session_id()

with st.sidebar:
    st.header("Session")
    st.code(st.session_state["session_id"])
    if st.button("New session"):
        st.session_state["session_id"] = _new_session_id()
        st.session_state.pop("run_id", None)
        st.rerun()

    st.header("Controls")
    ig_source = st.text_input("IG source override path", value="")
    threshold = st.slider("Auto-approve threshold", min_value=0.0, max_value=1.0, value=0.80, step=0.01)
    require_proposed = st.checkbox("Require PROPOSED for auto-approval", value=True)
    mapping_name = st.text_input("Mapping name", value="demo-batch-lot-analysis")

paths = _workspace_paths(st.session_state["session_id"])
_set_runtime_env(paths["artifacts"], ig_source)

tabs = st.tabs(["Upload", "Run", "Review", "Approve", "Export"])

with tabs[0]:
    st.subheader("Upload Extracts")
    uploads = st.file_uploader("Upload CSV/JSON/XML files", type=["csv", "json", "xml"], accept_multiple_files=True)
    if uploads:
        for uploaded in uploads:
            target = paths["inputs"] / uploaded.name
            target.write_bytes(uploaded.read())
        st.success(f"Saved {len(uploads)} file(s) to {paths['inputs']}")

    if st.button("Load Example Dataset"):
        copied = _copy_examples(paths["inputs"])
        st.success(f"Copied {copied} example file(s) into {paths['inputs']}")

    files = sorted(p.name for p in paths["inputs"].glob("*") if p.is_file())
    st.caption(f"Input folder: {paths['inputs']}")
    st.write(files if files else ["(no files yet)"])

with tabs[1]:
    st.subheader("Run Pipeline")
    if st.button("Build/refresh IG catalog"):
        src = Path(ig_source) if ig_source.strip() else None
        catalog = ensure_catalog(ig_source=src)
        st.json(
            {
                "source": catalog.get("source"),
                "profiles": len(catalog.get("profiles", [])),
                "valueSets": len(catalog.get("valueSets", {})),
            }
        )

    if st.button("Run propose"):
        src = Path(ig_source) if ig_source.strip() else None
        result = propose_run(paths["inputs"], ig_source=src)
        st.session_state["run_id"] = result["run_id"]
        st.success(f"Run complete: {result['run_id']}")
        st.json(result)

    run_id = st.session_state.get("run_id")
    if run_id and st.button("Generate report"):
        out = render_report_files(run_id)
        st.success("Report generated")
        st.json(out)

with tabs[2]:
    st.subheader("Review")
    run_id = st.session_state.get("run_id")
    if not run_id:
        st.info("Run propose first.")
    else:
        base = run_dir(run_id)
        required = {
            "proposals": base / "mapping_proposals.json",
            "decisions": base / "decisions.json",
            "relationships": base / "relationship_proposals.json",
            "domain": base / "domain_classification.json",
            "resource": base / "resource_classification.json",
        }
        if not all(p.exists() for p in required.values()):
            st.warning(f"Missing run artifacts under {base}")
        else:
            proposals = read_json(required["proposals"])
            decisions = read_json(required["decisions"])
            relationships = read_json(required["relationships"])

            label_counts = proposals.get("summary", {}).get("label_counts", {})
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("AUTO_APPROVE", int(label_counts.get("AUTO_APPROVE_CANDIDATE", 0)))
            c2.metric("GOOD", int(label_counts.get("GOOD_CANDIDATE", 0)))
            c3.metric("REQUIRES_SME", int(label_counts.get("REQUIRES_SME", 0)))
            c4.metric("OUT_OF_SCOPE", int(label_counts.get("OUT_OF_SCOPE", 0)))

            rows = _table_rows_from_proposals(proposals)
            table_opts = sorted({r["source"].split(".", 1)[0] for r in rows})
            domain_opts = sorted({str(r["domain"]) for r in rows})
            label_opts = sorted({str(r["label"]) for r in rows})

            fc1, fc2, fc3, fc4 = st.columns(4)
            table_filter = fc1.selectbox("Table filter", ["ALL", *table_opts])
            domain_filter = fc2.selectbox("Domain filter", ["ALL", *domain_opts])
            label_filter = fc3.selectbox("Label filter", ["ALL", *label_opts])
            conf_min, conf_max = fc4.slider("Confidence range", 0.0, 1.0, (0.0, 1.0), 0.01)

            filtered = []
            for row in rows:
                if table_filter != "ALL" and not row["source"].startswith(f"{table_filter}."):
                    continue
                if domain_filter != "ALL" and str(row["domain"]) != domain_filter:
                    continue
                if label_filter != "ALL" and str(row["label"]) != label_filter:
                    continue
                if not (conf_min <= float(row["confidence"]) <= conf_max):
                    continue
                filtered.append(row)
            st.dataframe(filtered, use_container_width=True, hide_index=True)

            st.markdown("### Decisions")
            st.dataframe(decisions.get("decisions", []), use_container_width=True, hide_index=True)

            st.markdown("### Relationships")
            st.dataframe(relationships.get("relationship_proposals", []), use_container_width=True, hide_index=True)

            report_html = base / "report.html"
            if report_html.exists():
                st.markdown("### Report Preview")
                components.html(report_html.read_text(encoding="utf-8"), height=500, scrolling=True)

with tabs[3]:
    st.subheader("Approve")
    run_id = st.session_state.get("run_id")
    if not run_id:
        st.info("Run propose first.")
    else:
        base = run_dir(run_id)
        proposals_path = base / "mapping_proposals.json"
        decisions_path = base / "decisions.json"
        if not proposals_path.exists() or not decisions_path.exists():
            st.warning("Generate proposals first.")
        else:
            proposals = read_json(proposals_path)
            decisions = read_json(decisions_path)
            st.caption("Manual selections for decision rows:")
            overrides, rules, _ = _build_overrides(
                proposals=proposals,
                decisions=decisions,
                threshold=threshold,
                require_proposed=require_proposed,
                mapping_name=mapping_name,
            )

            if st.button("Run approve"):
                overrides_json = paths["exports"] / "approval_overrides.json"
                overrides_yaml = paths["exports"] / "approval_overrides.yaml"
                rules_yaml = paths["exports"] / "approval_rules.yaml"

                write_json(overrides_json, {"overrides": overrides})
                write_yaml(overrides_yaml, {"overrides": overrides})
                write_yaml(rules_yaml, rules)

                approved = approve_run(
                    run_id=run_id,
                    rules_path=rules_yaml,
                    mapping_name=mapping_name,
                    overrides_path=overrides_json,
                )
                st.success("Approval completed")
                st.json(
                    {
                        "version_id": approved.get("version_id"),
                        "path": approved.get("path"),
                        "reused": approved.get("reused"),
                        "overrides": len(overrides),
                    }
                )

with tabs[4]:
    st.subheader("Export")
    run_id = st.session_state.get("run_id")
    if not run_id:
        st.info("Run propose first.")
    else:
        zip_bytes = _zip_workspace(paths["root"], run_id, mapping_name)
        st.download_button(
            label="Download ZIP",
            data=zip_bytes,
            file_name=f"pqi-copilot-{run_id}.zip",
            mime="application/zip",
        )
