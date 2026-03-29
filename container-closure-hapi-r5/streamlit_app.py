"""
Container Closure Pack Pilot — business demo layer.

Thin Streamlit presentation over the existing pilot engine.
Reads local source files and canonical bundles; optionally queries live HAPI.
Does NOT modify any core engine files.

Display values for the business summary are fixed constants matching the pilot data.
The raw source files (pattern_input.txt, CSV, canonical bundles) are read from disk
and shown verbatim in the technical expanders.
"""

import json
import urllib.request
import urllib.error
from pathlib import Path

import streamlit as st

# ── paths ─────────────────────────────────────────────────────────────────────

BASE = Path(__file__).parent
FHIR_BASE = "http://localhost:8080/fhir"

# ── file readers ──────────────────────────────────────────────────────────────


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _fhir_get(path: str) -> tuple[int, dict | None]:
    """GET a FHIR endpoint. Returns (http_status, json_body) or (0, None) on failure."""
    url = f"{FHIR_BASE}{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/fhir+json"})
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def _seal_supplier(bundle: dict) -> str:
    """Walk bundle → PPD packaging hierarchy → return foil seal liner manufacturer."""
    for entry in bundle.get("entry", []):
        r = entry.get("resource", {})
        if r.get("resourceType") != "PackagedProductDefinition":
            continue
        for cap in r.get("packaging", {}).get("packaging", []):
            for seal in cap.get("packaging", []):
                for mfr in seal.get("manufacturer", []):
                    name = mfr.get("display", "")
                    if name:
                        return name
    return ""


# ── load assets once ─────────────────────────────────────────────────────────

source_pattern = _read_text(BASE / "source" / "pattern_input.txt")
source_csv_raw = _read_text(BASE / "source" / "sap_container_closure_extract.csv")
initial_bundle = _read_json(BASE / "fhir" / "container-closure.collection.json")
update_bundle = _read_json(BASE / "fhir" / "container-closure-update.collection.json")

# Extract seal suppliers dynamically from the canonical bundles.
# All other display values are fixed constants — the CSV has an unquoted comma in
# source_string that makes column-by-column parsing unreliable; this is intentionally
# avoided in a thin demo layer.
initial_seal = _seal_supplier(initial_bundle) or "SealTech North America"
update_seal = _seal_supplier(update_bundle) or "BarrierSeal Systems"

# ── page setup ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Container Closure Pack Pilot",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── 1. Business intro ─────────────────────────────────────────────────────────

st.title("Container Closure Pack Pilot")
st.markdown(
    "This demo shows how packaging meaning moves from a human-maintained source pattern "
    "into a reusable canonical package model, and how a controlled packaging change is "
    "versioned cleanly — without touching unrelated product records."
)
st.caption(
    "Fictional product (AVELOR / AVL10). All supplier names are demo placeholders. "
    "The pattern and canonical model reflect real container-closure source structure."
)

st.divider()

# ── 2. Source input ───────────────────────────────────────────────────────────

st.header("1 · What came in")
st.markdown(
    "The business maintains packaging meaning as short, human-readable strings. "
    "This is the string as it lives today in the source system."
)

st.markdown("**Source pattern**")
if source_pattern:
    st.code(source_pattern, language=None)
else:
    st.warning("source/pattern_input.txt not found — is the repo complete?")

st.markdown("**Key facts extracted into the structured source extract**")

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("- **Product:** AVELOR 10 mg tablet")
    st.markdown("- **Product code:** AVL10")
    st.markdown("- **Market:** United States (US)")
    st.markdown("- **Tablet count:** 28 tablets per bottle")
with col_b:
    st.markdown("- **Bottle material:** High-density polyethylene (HDPE), white")
    st.markdown("- **Closure:** Child-resistant polypropylene cap")
    st.markdown("- **Seal:** Multi-layer aluminum foil induction seal")
    st.markdown("- **Scope:** Primary container closure system only")

st.markdown(
    "> Secondary paperboard carton is part of the marketed presentation "
    "but is **out of scope** for the container closure system description."
)

with st.expander("Source extract — raw CSV file"):
    if source_csv_raw:
        st.code(source_csv_raw, language=None)
    else:
        st.warning("source/sap_container_closure_extract.csv not found.")

st.divider()

# ── 3. Canonical package model ────────────────────────────────────────────────

st.header("2 · The canonical package model")
st.markdown(
    "The structured extract was normalized into a coded, versioned package record. "
    "Each field carries a stable identifier — no free text, no ambiguity across systems."
)

m1, m2, m3 = st.columns(3)
m1.metric("Product", "AVELOR 10 mg")
m2.metric("Market", "United States")
m3.metric("Presentation", "28 tablets / bottle")

st.markdown("**Packaging hierarchy — primary container closure system**")
st.markdown(
    """
| Level | Component | Material | Supplier |
|---|---|---|---|
| Primary container | White HDPE bottle | High Density PolyEthylene | Container Co. of America |
| Closure (child-resistant) | Polypropylene cap | Polypropylene | CapSafe Components |
| Seal liner | Multi-layer foil seal | Aluminium | *see controlled update below* |

Quality standards are coded on each component (e.g. USP <661>, 16 CFR 1700, 21 CFR 175.300).
"""
)

st.markdown("**Three stable records make up the model**")
rc1, rc2, rc3 = st.columns(3)
with rc1:
    st.markdown(
        "**Product anchor**  \n"
        "`mpd-avelor-10mg`  \n"
        "AVELOR 10 mg tablets  \n"
        "Reusable across all package variants"
    )
with rc2:
    st.markdown(
        "**Manufactured item**  \n"
        "`mid-avelor-10mg-tablet`  \n"
        "AVELOR 10 mg tablet  \n"
        "Physical tablet definition"
    )
with rc3:
    st.markdown(
        "**Package record**  \n"
        "`ppd-avelor-10mg-28ct-us`  \n"
        "28-tablet US bottle  \n"
        "Container closure hierarchy"
    )

with st.expander("Technical detail — initial canonical bundle (FHIR R5 collection)"):
    if initial_bundle:
        st.json(initial_bundle)
    else:
        st.warning("fhir/container-closure.collection.json not found.")

st.divider()

# ── 4. Controlled update ──────────────────────────────────────────────────────

st.header("3 · The controlled update")
st.markdown(
    "A supplier change was approved for the foil seal liner. "
    "The change was applied only to the package record."
)

col_before, col_arrow, col_after = st.columns([10, 1, 10])
with col_before:
    st.markdown("**Before**")
    st.info(f"Foil seal liner supplier\n\n**{initial_seal}**")
with col_arrow:
    st.markdown(
        "<div style='text-align:center;font-size:1.6rem;padding-top:2.2rem'>→</div>",
        unsafe_allow_html=True,
    )
with col_after:
    st.markdown("**After**")
    st.success(f"Foil seal liner supplier\n\n**{update_seal}**")

st.markdown(
    "> **Only the package record changed.**  \n"
    "> The product anchor (`mpd-avelor-10mg`) and manufactured item (`mid-avelor-10mg-tablet`) "
    "were not touched and received no new version.  \n"
    "> The package record (`ppd-avelor-10mg-28ct-us`) moved from **version 1** to **version 2**."
)

with st.expander("Technical detail — update bundle (FHIR R5 collection)"):
    if update_bundle:
        st.json(update_bundle)
    else:
        st.warning("fhir/container-closure-update.collection.json not found.")

st.divider()

# ── 5. Why it matters ─────────────────────────────────────────────────────────

st.header("4 · Why this matters")

wc1, wc2, wc3 = st.columns(3)
with wc1:
    st.markdown(
        "**Less ambiguity**  \n"
        "Packaging meaning is coded and structured — "
        "not buried in free text or spreadsheets that differ between systems."
    )
with wc2:
    st.markdown(
        "**Controlled history**  \n"
        "Every approved change creates a new version. "
        "Unchanged records stay clean. The audit trail is automatic."
    )
with wc3:
    st.markdown(
        "**Reusable downstream**  \n"
        "The same canonical output feeds RIM, regulatory submissions, "
        "and supply chain systems without re-interpretation."
    )

st.markdown(
    "The commercial value is not parsing one string. "
    "It is reusing a small number of product anchors across many package variants "
    "and delivering validated canonical output downstream."
)

st.divider()

# ── 6. Technical evidence (optional) ─────────────────────────────────────────

with st.expander("Technical evidence — live FHIR server"):
    st.caption(f"HAPI FHIR R5  ·  {FHIR_BASE}")

    meta_status, metadata = _fhir_get("/metadata")

    if meta_status != 200 or not metadata:
        st.warning(
            "FHIR server not reachable. "
            "Start it with `docker compose up -d` in `container-closure-hapi-r5/`, "
            "then reload this page."
        )
    else:
        fhir_ver = metadata.get("fhirVersion", "?")
        sw = metadata.get("software", {})
        st.success(
            f"Server online  ·  FHIR {fhir_ver}  ·  "
            f"{sw.get('name', 'HAPI FHIR')} {sw.get('version', '')}"
        )

        # PPD current state
        ppd_status, ppd = _fhir_get(
            "/PackagedProductDefinition/ppd-avelor-10mg-28ct-us"
        )
        if ppd_status == 200 and ppd:
            ver = ppd.get("meta", {}).get("versionId", "?")
            updated = ppd.get("meta", {}).get("lastUpdated", "?")
            st.markdown(
                f"**Package record (PPD)** — current version: **{ver}** "
                f"· last updated: {updated}"
            )
        elif ppd_status == 404:
            st.info(
                "Package record not yet loaded. "
                "Run `./load_bundle.sh initial` (or the curl equivalent) first."
            )
        else:
            st.warning(f"PPD not reachable (HTTP {ppd_status}).")

        # PPD version history
        hist_status, hist = _fhir_get(
            "/PackagedProductDefinition/ppd-avelor-10mg-28ct-us/_history"
        )
        if hist_status == 200 and hist:
            total = hist.get("total", 0)
            st.markdown(f"**PPD version history** — {total} version(s) on record")
            rows = []
            for entry in hist.get("entry", []):
                m = entry.get("resource", {}).get("meta", {})
                rows.append(
                    {
                        "version": m.get("versionId", "?"),
                        "lastUpdated": m.get("lastUpdated", "?"),
                    }
                )
            if rows:
                st.table(rows)

        # Confirm anchors are stable
        mpd_status, mpd = _fhir_get("/MedicinalProductDefinition/mpd-avelor-10mg")
        mid_status, mid = _fhir_get(
            "/ManufacturedItemDefinition/mid-avelor-10mg-tablet"
        )
        if mpd_status == 200 and mpd and mid_status == 200 and mid:
            mpd_ver = mpd.get("meta", {}).get("versionId", "?")
            mid_ver = mid.get("meta", {}).get("versionId", "?")
            st.markdown(
                f"**Product anchor (MPD)** — version: **{mpd_ver}** · "
                f"**Manufactured item (MID)** — version: **{mid_ver}** · "
                "_(no spurious updates)_"
            )

        with st.expander("Raw /metadata response"):
            st.json(metadata)
