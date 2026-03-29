# Container-Closure HAPI R5 Demo

This folder is the smallest credible local demo of a bottle-first PQI container-closure flow:

`source pattern -> structured extract -> canonical FHIR collection bundle -> HAPI repository -> controlled update/history -> downstream-ready reuse`

This is not a generic packaging demo and not a general free-text parsing claim. It is a canonical SAP-to-RIM MVP designed to show why a reusable canonical model matters.

This demo does not prove free text is solved generally. It proves that a small, patternable portfolio can be normalized into a reusable canonical model and versioned for downstream use.

## What This Proves

- One human-readable source pattern can be converted into a deterministic, auditable structured extract.
- That extract can be normalized into a canonical PQI-aligned FHIR R5 model.
- HAPI can persist that canonical model, expose it directly, and show version history for controlled package-state changes.
- The commercial value is not parsing one string. The commercial value is reusing a small number of product anchors across many package variants and sending validated canonical output downstream to RIM.

## Why This Is Commercially Credible

The demo implements one `MedicinalProductDefinition` anchor, one `ManufacturedItemDefinition`, and one `PackagedProductDefinition`.

The broader delivery pattern is the real point:

- roughly `2` reusable `MedicinalProductDefinition` anchors across the portfolio
- roughly `30` package-level records hanging off those anchors
- roughly `5 to 6` repeatable source-pattern families
- minor remediation for outliers
- validated canonical output sent downstream to RIM

The money is in canonical reuse and downstream RIM delivery, not in parsing one string.

## Source Truth Vs Placeholders

Source-supported bottle facts carried into this demo:

- HDPE bottle
- child-resistant closure
- pulp liner
- aluminum foil induction seal
- 28 tablets
- secondary paperboard carton described in the `PackagedProductDefinition.description` narrative but excluded from the structured packaging hierarchy (secondary packaging is out of scope for a container closure system description)

Fictional demo placeholders:

- product name `AVELOR`
- product code `AVL10`
- all supplier/manufacturer names used as operational master-data examples, including `Container Co. of America`, `CapSafe Components`, `FiberSeal Labs`, `SealTech North America`, `BarrierSeal Systems`, and `CartonPrint Co.`

## Why The Canonical Is Intentionally Lean

The PQI container-closure profile is flexible enough for a lean MVP:

- `MedicinalProductDefinition` is optional in the bundle slice model but included here because the product anchor is commercially important.
- `PackagedProductDefinition` is the required center of gravity for the package/closure story.
- `ManufacturedItemDefinition` is included so the bottle can point to the physical tablet item.

This means the MVP canonical is intentionally partial, not deficient. It is structurally correct now and can expand later without redesigning the model.

Earlier FHIR-dev work already proved the in-scope source elements can be parsed into discrete fields for this demo. This folder keeps that pattern, tightens it, and aligns it to the correct container-closure profile instead of reinventing it.

## Folder Structure

```text
container-closure-hapi-r5/
├── compose.yaml
├── source/
│   ├── pattern_input.txt
│   └── sap_container_closure_extract.csv
├── fhir/
│   ├── container-closure.collection.json
│   ├── container-closure.transaction.json
│   ├── container-closure-update.collection.json
│   └── container-closure-update.transaction.json
├── ig/
│   ├── hl7.fhir.uv.pharm-quality-1.0.0.tgz
│   └── BASELINE.md
├── load_bundle.sh
└── README.md
```

## Every File In Plain English

- [compose.yaml](compose.yaml)
  Starts one local HAPI FHIR server on port `8080`.
- [source/pattern_input.txt](source/pattern_input.txt)
  The exact human-readable source pattern string that reflects the real family grammar.
- [source/sap_container_closure_extract.csv](source/sap_container_closure_extract.csv)
  The deterministic structured input used for canonical mapping. This is the real MVP input, not the raw string.
- [fhir/container-closure.collection.json](fhir/container-closure.collection.json)
  The canonical PQI-aligned bundle for the initial package state. This is the reusable downstream artifact.
- [fhir/container-closure.transaction.json](fhir/container-closure.transaction.json)
  The prebuilt HAPI load bundle for the initial state. This exists only to lower live-demo risk.
- [fhir/container-closure-update.collection.json](fhir/container-closure-update.collection.json)
  The canonical PQI-aligned bundle for the controlled update state.
- [fhir/container-closure-update.transaction.json](fhir/container-closure-update.transaction.json)
  The prebuilt HAPI load bundle for the update state.
- [ig/hl7.fhir.uv.pharm-quality-1.0.0.tgz](ig/hl7.fhir.uv.pharm-quality-1.0.0.tgz)
  Vendored IG NPM package. Used as the frozen validation baseline in CI. Do not replace without an explicit version bump.
- [ig/BASELINE.md](ig/BASELINE.md)
  Records the package ID, version, SHA-256, adoption date, and conformance statement.
- [load_bundle.sh](load_bundle.sh)
  A tiny helper that posts either the initial or update transaction bundle to HAPI.
- [README.md](README.md)
  The exact runbook, architecture notes, and business talk track.

## Pinned Runtime And Profiles

- HAPI image: `hapiproject/hapi:v8.6.5-1`
- REST base URL: `http://localhost:8080/fhir`
- FHIR version: `5.0.0 / R5`
- Bundle profile: `http://hl7.org/fhir/uv/pharm-quality/StructureDefinition/Bundle-container-closure-system-pq`
- Product profile: `http://hl7.org/fhir/uv/pharm-quality/StructureDefinition/MedicinalProductDefinition-drug-product-pq`
- Package profile: `http://hl7.org/fhir/uv/pharm-quality/StructureDefinition/PackagedProductDefinition-drug-pq`
- Manufactured item profile: `http://hl7.org/fhir/uv/pharm-quality/StructureDefinition/ManufacturedItemDefinition-drug-pq`

> **Conformance statement:** This service is validated against an internally frozen implementation baseline: `hl7.fhir.uv.pharm-quality#1.0.0` (FHIR R5), vendored in `ig/` with recorded SHA-256 and adoption date, with pinned validation dependencies matching the IG-declared package versions. It is used as an internal canonical exchange contract and is not represented as formal conformance to an HL7 authorized publication. The upstream package carries `"notForPublication": true`. Upstream changes are assessed and adopted deliberately — see [ig/BASELINE.md](ig/BASELINE.md).

## Resource Ownership

- `MedicinalProductDefinition`
  Owns product identity, product code, strength at product naming level, and the product-level dose-form expression.
- `ManufacturedItemDefinition`
  Owns the physical tablet/item view, manufactured dose form, and unit of presentation.
- `PackagedProductDefinition`
  Owns the package presentation, count, market, closure hierarchy, materials, suppliers, and governance markers.

## Packaging Hierarchy

```text
Bottle (HDPE)                         ← PPD.packaging root
  └─ Child Proof Cap (PP)             ← componentPart: true
       └─ Multi-layer Foil Seal Liner ← componentPart: true
            (Aluminium)
```

The packaging root is the Bottle itself — there is no neutral wrapper. The closure sub-hierarchy uses the two available codes from the `container-closure-type` CodeSystem.

The source design has separate pulp liner and aluminum foil induction seal components. The IG `container-closure-type` CodeSystem does not define distinct codes for these elements. They are collapsed into `Multi-layer Foil Seal Liner`, which is the closest available coded concept, and the physical detail is preserved in the `PackagedProductDefinition.description` narrative.

The secondary paperboard carton is out of scope for the structured closure hierarchy. It is described in the PPD narrative.

## Property Encoding

Packaging properties use coded values from the PQI IG CodeSystems, matching the bottle-first IG example pattern:

- **Bottle:** Color (`white`) and Quality Standard (`USP <661>`, `PhEur 3.1.3 Polyolefins`)
- **Child Proof Cap:** Quality Standard (`16 CFR 1700`)
- **Multi-layer Foil Seal Liner:** Quality Standard (`21 CFR 175.300`, `EU 94/62/EC`)

The earlier free-text governance markers (`regulatory-relevant`, `change-controlled`, `reference-only`) have been removed. The container closure scope boundary — primary packaging in, secondary carton out — is now expressed structurally (carton absent from hierarchy) and narratively (PPD `description`).

## Exact Source Inputs

Human-facing family pattern:

```text
BOTTLE AVELOR 10MG 28 TABS, US
```

Deterministic structured input:

See [source/sap_container_closure_extract.csv](source/sap_container_closure_extract.csv).

## Exact Run Steps

From the repo root:

```bash
cd container-closure-hapi-r5
docker compose up -d
```

Wait until HAPI is responding:

```bash
curl -s http://localhost:8080/fhir/metadata
```

Load the initial state:

```bash
./load_bundle.sh initial
```

Apply the controlled update:

```bash
./load_bundle.sh update
```

## Raw Curl Equivalents

Initial load:

```bash
curl -s -X POST "http://localhost:8080/fhir" \
  -H "Content-Type: application/fhir+json" \
  --data-binary @fhir/container-closure.transaction.json
```

Update load:

```bash
curl -s -X POST "http://localhost:8080/fhir" \
  -H "Content-Type: application/fhir+json" \
  --data-binary @fhir/container-closure-update.transaction.json
```

## Verification URLs

Open these directly in the browser after loading:

- `http://localhost:8080/fhir/metadata`
- `http://localhost:8080/fhir/MedicinalProductDefinition/mpd-avelor-10mg`
- `http://localhost:8080/fhir/ManufacturedItemDefinition/mid-avelor-10mg-tablet`
- `http://localhost:8080/fhir/PackagedProductDefinition/ppd-avelor-10mg-28ct-us`
- `http://localhost:8080/fhir/PackagedProductDefinition/ppd-avelor-10mg-28ct-us/_history`

What to expect:

- the product anchor stays stable
- the manufactured item stays stable
- the packaged presentation shows the bottle and closure hierarchy
- `_history` on the PPD shows version `1` after the initial load and version `2` after the update load
- `_history` on the MPD and MID show only version `1` — the update transaction PUTs only the PPD, so unchanged resources accumulate no spurious version bumps

## The Controlled Update

The update is deliberately small and semantically credible for the same packaged presentation:

- only the foil seal liner supplier changes
- initial state: `SealTech North America`
- updated state: `BarrierSeal Systems`
- the logical ids stay the same
- the package is not re-modeled as a new presentation
- the update transaction bundle (`container-closure-update.transaction.json`) PUTs **only the PPD** — MPD and MID are unchanged and do not receive a new version

## Demo Talk Track

- “We are not claiming that free text is solved in general. We are showing that a small, patternable portfolio can be normalized safely.”
- “The raw string still matters because it is how the business currently maintains critical package meaning.”
- “The CSV is the deterministic operational extract. The collection bundle is the canonical asset.”
- “The product anchor is reusable. The package state is where most of the operational change happens.”
- “HAPI is the persistence and history surface. Governance comes from the canonical model and controlled updates.”
- “This is the pattern that scales from one demo product to a small number of product anchors and many package variants for downstream RIM delivery.”

## Dev Lead Review Notes

- The canonical bundle and the HAPI ingestion bundle are intentionally separate because the PQI bundle profile patterns `collection`, while HAPI loading is safest with a prebuilt `transaction` bundle.
- The model is intentionally partial and expandable. PQI cardinality flexibility is treated as an advantage, not a gap.
- CI validates the two canonical collection bundles against the vendored IG package. The transaction bundles are deployment artifacts and are not validated against the profile.
- The validator CLI version is pinned to `latest` at download time. For production, pin to a specific release tag.
- The stable ids are the main review point:
  - `mpd-avelor-10mg`
  - `mid-avelor-10mg-tablet`
  - `ppd-avelor-10mg-28ct-us`
- The commercial logic is the real design center:
  - a small number of reusable product anchors
  - many package variants below them
  - clean history for controlled package-state changes
  - downstream canonical reuse in RIM-style processes
