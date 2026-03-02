# PQI Mapping Copilot (Local-First MVP)

A consultant-facing mapping workbench that ingests raw pharma extracts (CSV/JSON/XML) and produces evidence-driven mapping proposals to HL7 FHIR R5 PQI (`hl7.fhir.uv.pharm-quality#1.0.0`).

Scope of this MVP wedge:
- Domain A: Batch/Lot Information
- Domain B: Batch Analysis
- Output focus: profiling, explainable mapping candidates, governance approval, and deterministic artifacts
- Out of scope: regulator submission formatting

## Key Guarantees
- Local-first: no external calls
- Constrained target model: PQI catalog + base FHIR fallback only
- No hallucinated semantics: every candidate has evidence + confidence
- Uncertain mappings are marked `REQUIRES_REVIEW` with confidence `< 0.6`
- Governance lifecycle: `PROPOSED -> REVIEWED -> APPROVED -> DEPRECATED`
- Approved mapping versions are immutable
- Deterministic runs: same inputs + same approved mapping version + same terminology version => same outputs

## Repository Layout
- `pqi_copilot/`
  - `ig/` PQI IG loader + catalog index
  - `ingest/` extract ingestion + normalization
  - `profiler/` profiling/stats
  - `classify/` domain classifier
  - `propose/` mapping + relationship proposer
  - `governance/` artifact/version store
  - `terminology/` optional scaffolds (CodeSystem/ValueSet/ConceptMap)
  - `generate/` optional minimal bundle generator
  - `validate/` structural validation stubs
  - `report/` markdown/html report generation
  - `cli.py` CLI entrypoint
- `data/examples/` synthetic example extracts
- `artifacts/` run outputs + library versions
- `ig/` fallback package location (`ig/pqi-package.tgz`)
- `tests/` pytest tests

## Installation
Python 3.11+

Recommended dependencies (declared in `pyproject.toml`):
- `typer`, `pydantic`, `pandas`, `python-dateutil`, `rapidfuzz`, `jinja2`, `pytest`

## IG Loading Priority
`pqi-copilot` follows this order:
1. `/mnt/data/full-ig.zip` (if present)
   - searches for `package/` JSON, nested `package.tgz`, and loose FHIR artifacts
2. `./ig/pqi-package.tgz`

If neither is available, place the package manually:
- `ig/pqi-package.tgz` containing `hl7.fhir.uv.pharm-quality#1.0.0`

Manual fallback from IG downloads page:
- PQI IG page: <https://build.fhir.org/ig/HL7/uv-dx-pq/>
- Download package and place at `./ig/pqi-package.tgz`
- Or download JSON definitions bundle from the IG downloads section and provide locally

## CLI Usage
### 1) Build IG catalog
```bash
python3 -m pqi_copilot ig index
```

### 2) List profiles
```bash
python3 -m pqi_copilot ig list-profiles --contains Batch
```

### 3) Show profile details
```bash
python3 -m pqi_copilot ig show-profile "http://hl7.org/fhir/uv/pharm-quality/StructureDefinition/Medication-batch-information-drug-pq"
```

### 4) Run propose pipeline
```bash
python3 -m pqi_copilot propose data/examples
```

### 5) Generate stakeholder report
```bash
python3 -m pqi_copilot report <run_id>
```

### 6) Approve mappings using rules
```bash
python3 -m pqi_copilot approve <run_id> --rules data/examples/approval_config.yaml --mapping-name batch-lot-analysis
```

### 7) List mapping library
```bash
python3 -m pqi_copilot library list
```

### 8) Optional minimal bundle generation
```bash
python3 -m pqi_copilot generate <run_id> --mapping-name batch-lot-analysis
```

## Approval Rules File (`.yaml`)
Example:
```yaml
confidence_threshold: 0.72
require_status_proposed: true
```

Approval behavior:
- Chooses exactly one candidate per source column if threshold criteria met
- Otherwise marks source column as `UNMAPPED`
- Writes immutable approved mapping artifact to:
  - `artifacts/library/mappings/<mapping_name>/vX.Y.Z/approved.yaml`
  - plus `approved.json`

## Output Artifacts (per run)
`artifacts/runs/<run_id>/`
- `ingest.json`
- `profile.json`, `profile.md`
- `domain_classification.json`
- `mapping_proposals.json`
- `mapping_proposals/*.yaml` (one per source column)
- `relationship_proposals.json`
- `terminology_scaffold.json`
- `report.md`, `report.html`
- `manifest.json`
- optional: `outputs/bundle.json`, `outputs/generation_manifest.json`, `outputs/bundle_validation.json`

## Extending Heuristics
- Synonyms and scoring keywords:
  - `pqi_copilot/propose/mapping.py` (`SYNONYMS`, scoring logic)
  - `pqi_copilot/classify/domain_classifier.py` (`DOMAIN_SIGNALS`)

## Artifact Versioning
- Library path: `artifacts/library/`
- Mappings are versioned semver-style (`v1.0.0`, `v1.0.1`, ...)
- Approved artifacts are immutable
- Re-approving identical content reuses existing version
- Changes append to `artifacts/library/CHANGELOG.md`

## Tests
Pytest tests include:
- determinism test
- golden hash test for example dataset
- mapping proposal schema validation

Run (once pytest is available):
```bash
pytest -q tests/test_copilot_*.py
```
