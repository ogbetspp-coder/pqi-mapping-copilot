# PQI Mapping Copilot Architecture (pqi_copilot)

## ROI Goal
Accelerate consultant mapping workshops for PQI Step I-III exchange by producing explainable, governed mapping proposals for two wedge domains:
- Batch/Lot Information
- Batch Analysis
- Plus explicit `out_of_scope` triage for low-signal administrative tables/columns

## Core Principles
- Semantic contract: HL7 FHIR R5 + PQI (`hl7.fhir.uv.pharm-quality#1.0.0`).
- Local-first execution: no network calls.
- Deterministic artifacts: stable ordering + stable hashes.
- Governance-as-product: immutable approved versions.

## Pipeline
1. Ingest (`pqi_copilot.ingest.normalize`)
- Read CSV/JSON/XML.
- Normalize into row tables with clear unsupported guidance.

2. Profile (`pqi_copilot.profiler.stats`)
- Infer types, null/unique rates, top values, units, regex hits, ID likelihood.

3. Domain classify (`pqi_copilot.classify.domain_classifier`)
- Score each table for wedge domains with explainable rationale.

4. Resource classify (`pqi_copilot.classify.resource_classifier`)
- Assign primary resource model per table (Medication/Observation/DiagnosticReport/Specimen).

5. Propose mappings (`pqi_copilot.propose.mapping`)
- Constrained candidate universe using curated target spaces (`pqi_copilot.propose.target_spaces`).
- Hard anchor rules (`pqi_copilot.propose.hard_rules`) enforce consultant-safe behavior.
- Out-of-scope non-anchor fields are emitted explicitly as out-of-scope (not noisy mappings).
- Confidence calibration labels:
  - `AUTO_APPROVE_CANDIDATE`
  - `GOOD_CANDIDATE`
  - `REQUIRES_SME`

6. Propose relationships (`pqi_copilot.propose.relationships`)
- Key-based join suggestions with match rates.

7. Generate decisions (`pqi_copilot.propose.decisions`)
- Decision objects for SME review with top options + question prompts.

8. Report (`pqi_copilot.report.render`)
- Markdown + HTML stakeholder report with decisions first-class.

9. Govern approvals (`pqi_copilot.governance.store`)
- `PROPOSED -> APPROVED` artifact versions.
- Manual override support for source-level picks.
- Immutable versioned library artifacts.

10. Optional generate (`pqi_copilot.generate.bundle`)
- Minimal wedge bundle from approved mappings + manifest hashes.

## Key Paths
- IG catalog: `artifacts/library/ig_catalog.json`
- Run artifacts: `artifacts/runs/<run_id>/...`
- Library mappings: `artifacts/library/mappings/<mapping_name>/vX.Y.Z/approved.yaml`

All active implementation for this tool is under `pqi_copilot/`.
