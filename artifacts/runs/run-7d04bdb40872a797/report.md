# PQI Mapping Copilot Report - run-7d04bdb40872a797

## Dataset Overview

| Table | Source File | Rows | Columns |
|---|---|---:|---:|
| lims_results | data/examples/lims_results.csv | 3 | 9 |
| mes_steps | data/examples/mes_steps.json | 2 | 4 |
| qms_deviations | data/examples/qms_deviations.xml | 2 | 4 |
| sap_batch | data/examples/sap_batch.csv | 2 | 8 |

## Domain Classification

| Table | Primary Domain | Scores | Rationale (top) |
|---|---|---|---|
| lims_results | batch_analysis | batch_analysis=0.91, batch_lot_information=0.09 | batch_analysis:table-keyword:result(+0.90); batch_lot_information:batch_id:keyword:batch(+1.2) |
| mes_steps | batch_lot_information | batch_analysis=0.33, batch_lot_information=0.67 | batch_analysis:batch_id:value-pattern:test_code_like(+0.3); batch_lot_information:batch_id:keyword:batch(+1.2) |
| qms_deviations | batch_lot_information | batch_analysis=0.33, batch_lot_information=0.67 | batch_analysis:batch_id:value-pattern:test_code_like(+0.3); batch_lot_information:batch_id:keyword:batch(+1.2) |
| sap_batch | batch_lot_information | batch_analysis=0.13, batch_lot_information=0.87 | batch_analysis:batch_id:value-pattern:test_code_like(+0.3); batch_lot_information:table-keyword:batch(+0.90) |

## Top Mapping Candidates

| Source | Domain | Candidate Target | Confidence | Status | Evidence |
|---|---|---|---:|---|---|
| lims_results.analysis_time | batch_analysis | Specimen::Specimen.receivedTime | 0.61 | PROPOSED | token_overlap=['time']; date/datetime compatible |
| lims_results.batch_id | batch_analysis | Observation::Observation.referenceRange.appliesTo | 0.67 | PROPOSED | token_overlap=[]; string compatible |
| lims_results.method | batch_analysis | Observation::Observation.method | 0.77 | PROPOSED | token_overlap=['analysis', 'assay', 'method', 'procedure', 'protocol', 'test']; string compatible |
| lims_results.result_unit | batch_analysis | ObservationDefinition::ObservationDefinition.component.code | 0.53 | REQUIRES_REVIEW | token_overlap=[]; string compatible |
| lims_results.result_value | batch_analysis | Extension::Extension.value[x] | 0.60 | PROPOSED | token_overlap=['outcome', 'result', 'value']; numeric compatible |
| lims_results.spec_limit_high | batch_analysis | ObservationDefinition::ObservationDefinition.qualifiedValue.range.high | 0.55 | REQUIRES_REVIEW | token_overlap=['criteria', 'high', 'limit', 'spec', 'specification']; numeric compatible |
| lims_results.spec_limit_low | batch_analysis | ObservationDefinition::ObservationDefinition.qualifiedValue.range.low | 0.54 | REQUIRES_REVIEW | token_overlap=['criteria', 'limit', 'low', 'spec', 'specification']; numeric compatible |
| lims_results.test_code | batch_analysis | Observation::Observation.method | 0.70 | PROPOSED | token_overlap=['analysis', 'assay', 'method', 'test']; string compatible |
| lims_results.test_name | batch_analysis | DiagnosticReport::DiagnosticReport.conclusionCode | 0.56 | REQUIRES_REVIEW | token_overlap=['analysis', 'assay', 'method', 'test']; string compatible |
| mes_steps.batch_id | batch_lot_information | Observation::Observation.referenceRange.appliesTo | 0.67 | PROPOSED | token_overlap=[]; string compatible |
| mes_steps.duration_hr | batch_lot_information | Observation::Observation.value[x] | 0.47 | REQUIRES_REVIEW | token_overlap=[]; numeric compatible |
| mes_steps.equipment_id | batch_lot_information | Organization::Organization.identifier.type | 0.68 | PROPOSED | token_overlap=[]; string compatible |
| mes_steps.step_name | batch_lot_information | DiagnosticReport::DiagnosticReport.code | 0.51 | REQUIRES_REVIEW | token_overlap=['name']; string compatible |
| qms_deviations.batch_id | batch_lot_information | Observation::Observation.referenceRange.appliesTo | 0.67 | PROPOSED | token_overlap=[]; string compatible |
| qms_deviations.category | batch_lot_information | Observation::Observation.code | 0.49 | REQUIRES_REVIEW | token_overlap=[]; string compatible |
| qms_deviations.deviation_id | batch_lot_information | Organization::Organization.identifier.type | 0.71 | PROPOSED | token_overlap=[]; string compatible |
| qms_deviations.status | batch_lot_information | DiagnosticReport::DiagnosticReport.code | 0.48 | REQUIRES_REVIEW | token_overlap=[]; string compatible |
| sap_batch.batch_id | batch_lot_information | Observation::Observation.referenceRange.appliesTo | 0.67 | PROPOSED | token_overlap=[]; string compatible |
| sap_batch.batch_quantity | batch_lot_information | Medication::Medication.ingredient.strength[x] | 0.50 | REQUIRES_REVIEW | token_overlap=['quantity']; numeric compatible |
| sap_batch.batch_uom | batch_lot_information | PackagedProductDefinition::PackagedProductDefinition.packaging.property.value[x].code | 0.52 | REQUIRES_REVIEW | token_overlap=['unit', 'units', 'uom']; string compatible |
| sap_batch.lot_number | batch_lot_information | Observation::Observation.interpretation | 0.62 | PROPOSED | token_overlap=[]; string compatible |
| sap_batch.manufacturing_date | batch_lot_information | Specimen::Specimen.processing.time[x] | 0.57 | REQUIRES_REVIEW | token_overlap=['date']; date/datetime compatible |
| sap_batch.material_id | batch_lot_information | Observation::Observation.referenceRange.normalValue | 0.66 | PROPOSED | token_overlap=[]; string compatible |
| sap_batch.packaging_date | batch_lot_information | Specimen::Specimen.processing.time[x] | 0.58 | REQUIRES_REVIEW | token_overlap=['date']; date/datetime compatible |
| sap_batch.release_date | batch_lot_information | ObservationDefinition::ObservationDefinition.date | 0.58 | REQUIRES_REVIEW | token_overlap=['date']; date/datetime compatible |

## Relationship Suggestions

| Join | Match Rate | Overlap |
|---|---:|---:|
| lims_results.batch_id -> mes_steps.batch_id | 100.0% | 2 |
| lims_results.batch_id -> qms_deviations.batch_id | 100.0% | 2 |
| lims_results.batch_id -> sap_batch.batch_id | 100.0% | 2 |
| qms_deviations.batch_id -> mes_steps.batch_id | 100.0% | 2 |
| sap_batch.batch_id -> mes_steps.batch_id | 100.0% | 2 |
| sap_batch.batch_id -> qms_deviations.batch_id | 100.0% | 2 |

## Unresolved / Ambiguous Items

- lims_results.result_unit
- lims_results.spec_limit_high
- lims_results.spec_limit_low
- lims_results.test_name
- mes_steps.duration_hr
- mes_steps.step_name
- qms_deviations.category
- qms_deviations.status
- sap_batch.batch_quantity
- sap_batch.batch_uom
- sap_batch.manufacturing_date
- sap_batch.packaging_date
- sap_batch.release_date

## Decisions Required From SMEs

- Confirm target profile/element for unresolved columns listed above.
- Confirm terminology mapping for code-like fields lacking ValueSet bindings.
