# Product CMC Digital Twin MVP Architecture (PQI / FHIR R5)

## Defaults Chosen
- Canonical semantic contract: HL7 FHIR R5 + PQI STU1 package `hl7.fhir.uv.pharm-quality#1.0.0`.
- Execution mode: deterministic local batch pipeline.
- Governance mode: Git-friendly JSON artifact store with immutable approved snapshots.
- Validation mode: local structural + terminology + business rules, with external validator hook stub.

## PQI Step I-III Alignment

### Step I: Partner/System Exchange (Ingest)
- Inputs: raw CSV/JSON/XML from SAP, LIMS, MES, QMS, PLM, RIM (synthetic examples included).
- Component: `pqi_twin.profiler`
- Outputs:
  - schema/data-type inference
  - code distributions
  - unit detection
  - candidate keys/joins with overlap evidence

### Step II: Collate into Discrete PQI Resources/Profiles
- Components:
  - `pqi_twin.ig_loader` (PQI IG index: profiles, required elements, bindings, examples)
  - `pqi_twin.domain_classifier` (PQ1..PQ14 confidence + evidence)
  - `pqi_twin.mapping_recommender` (source->target proposals + relationship graph)
  - `pqi_twin.terminology` (CodeSystem/ValueSet/ConceptMap scaffolds + CodeableConcept recommendations)
  - `pqi_twin.governance` (lifecycle + versioned immutable artifacts)
- Outputs:
  - MappingProposalSet JSON
  - Relationship graph
  - terminology scaffolds
  - governed/approved versions for downstream generation

### Step III: Bundle / Submittable Extraction & Transform-Ready Packaging
- Components:
  - `pqi_twin.generator` (approved mappings -> PQI-aligned FHIR Bundles)
  - `pqi_twin.validator` (structural/terminology/business checks)
  - `pqi_twin.evidence` (hash manifest + canonicalization/signing hooks)
- Outputs:
  - PQI-style collection bundles (R5 JSON)
  - validation report
  - evidence manifest (input hashes, mapping/terminology versions, validator version, output hashes)

## Repository Plan
- `src/pqi_twin/ig_loader.py`: parses package.tgz or full-ig.zip, builds IG catalog.
- `src/pqi_twin/profiler.py`: profiles extracts, infers schema + joins.
- `src/pqi_twin/domain_classifier.py`: classifies tables/fields into PQ domains.
- `src/pqi_twin/mapping_recommender.py`: produces MappingProposal artifacts + relationship graph.
- `src/pqi_twin/terminology.py`: builds local terminology scaffolds + coding recommendations.
- `src/pqi_twin/governance.py`: lifecycle state management and versioned immutable store.
- `src/pqi_twin/generator.py`: emits deterministic PQI-aligned bundles (definition + instance resources).
- `src/pqi_twin/validator.py`: local validator + external validator integration stub.
- `src/pqi_twin/evidence.py`: deterministic evidence manifest builder.
- `src/pqi_twin/pipeline.py`: orchestration.
- `src/pqi_twin/cli.py`: CLI (`pqi-twin run-mvp ...`).
- `data/synthetic/`: sample inputs.
- `examples/out/`: generated example artifacts.
- `governance/`: mapping/terminology versions.
- `tests/`: determinism, golden bundle, mapping stability.

## Determinism Controls
- Stable ordering of files/tables/columns/resources.
- Stable JSON serialization (sorted keys).
- Stable IDs from SHA-256 over semantic keys.
- No runtime timestamps in generated content.
- Manifest run ID derived from canonical manifest hash.

## Validation Model
1. Structural validation
   - resource basics (`resourceType`, `id`, bundle shape)
   - profile reference existence in local IG catalog
   - MVP required element checks from profile metadata
2. Terminology validation
   - all codings enforce explicit `system`, `code`, `display`
   - unresolved bindings flagged `REQUIRES_REVIEW`
3. Business-rule validation
   - `Medication.batch.lotNumber` required
   - `Observation.subject` and `Observation.value[x]` required
   - `DiagnosticReport.result` required

## Governance Rules
- Lifecycle: `proposed -> reviewed -> approved -> deprecated`.
- Approved snapshots are immutable.
- Any content change after approval creates a new version.
- Version artifacts are JSON files under `governance/{mappings|terminology}/{artifactId}/vN.json`.
