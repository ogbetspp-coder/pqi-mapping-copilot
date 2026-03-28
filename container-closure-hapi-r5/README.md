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
- secondary paperboard package modeled as a `Carton` and marked reference-only

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

## Resource Ownership

- `MedicinalProductDefinition`
  Owns product identity, product code, strength at product naming level, and the product-level dose-form expression.
- `ManufacturedItemDefinition`
  Owns the physical tablet/item view, manufactured dose form, and unit of presentation.
- `PackagedProductDefinition`
  Owns the package presentation, count, market, closure hierarchy, materials, suppliers, and governance markers.

## Packaging Hierarchy

```text
Neutral packaging wrapper
- Bottle
  - Child-resistant closure
    - Pulp liner
    - Induction seal
- Carton (optional sibling, reference-only)
```

Modeling note:

- The source wording is effectively a secondary paperboard package.
- For simple FHIR readability in this MVP, it is modeled as a `Carton` packaging node with `Paperboard` as the material.

## Governance Encoding

Governance is explicit in both the CSV and the FHIR output.

- `regulatory-relevant` + `change-controlled`
  Applied to the bottle and closure-system components.
- `reference-only` + `not-subject-to-change-control`
  Applied to the secondary paperboard carton.

This is stored on packaging nodes as lightweight `property` elements. HAPI persists the governed facts, but HAPI does not create governance automatically.

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
- `_history` shows version `1` after the initial load and version `2` after the update load

## The Controlled Update

The update is deliberately small and semantically credible for the same packaged presentation:

- only the induction seal supplier changes
- initial state: `SealTech North America`
- updated state: `BarrierSeal Systems`
- the logical ids stay the same
- the package is not re-modeled as a new presentation

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
- The stable ids are the main review point:
  - `mpd-avelor-10mg`
  - `mid-avelor-10mg-tablet`
  - `ppd-avelor-10mg-28ct-us`
- The commercial logic is the real design center:
  - a small number of reusable product anchors
  - many package variants below them
  - clean history for controlled package-state changes
  - downstream canonical reuse in RIM-style processes
