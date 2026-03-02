# PQI Mapping Copilot Report - run-7d04bdb40872a797

## Workshop Summary

- Auto-approve candidates: 4
- Good candidates: 5
- SME decisions required: 10
- Out-of-scope fields: 6
- Out-of-scope labels: 6

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
| lims_results | batch_analysis | batch_analysis=0.91, batch_lot_information=0.09, out_of_scope=0.09 | batch_analysis:table-keyword:result(+0.90); batch_lot_information:batch_id:keyword:batch(+1.2) |
| mes_steps | out_of_scope | batch_analysis=0.33, batch_lot_information=0.67, out_of_scope=0.65 | batch_analysis:batch_id:value-pattern:test_code_like(+0.3); batch_lot_information:batch_id:keyword:batch(+1.2) |
| qms_deviations | out_of_scope | batch_analysis=0.33, batch_lot_information=0.67, out_of_scope=0.65 | batch_analysis:batch_id:value-pattern:test_code_like(+0.3); batch_lot_information:batch_id:keyword:batch(+1.2) |
| sap_batch | batch_lot_information | batch_analysis=0.13, batch_lot_information=0.87, out_of_scope=0.13 | batch_analysis:batch_id:value-pattern:test_code_like(+0.3); batch_lot_information:table-keyword:batch(+0.90) |

## Table-to-Resource Model

| Table | Primary Resource | Resource Scores | Rationale (top) |
|---|---|---|---|
| lims_results | Observation | DiagnosticReport=0.06, Medication=0.08, Observation=0.85, Specimen=0.02 | DiagnosticReport:domain-boost:batch_analysis(+0.40); Medication:column:batch_id:keyword:batch(+1.30) |
| mes_steps | Medication | DiagnosticReport=0.00, Medication=1.00, Observation=0.00, Specimen=0.00 | Medication:column:batch_id:keyword:batch(+1.30) |
| qms_deviations | Medication | DiagnosticReport=0.00, Medication=1.00, Observation=0.00, Specimen=0.00 | Medication:column:batch_id:keyword:batch(+1.30) |
| sap_batch | Medication | DiagnosticReport=0.00, Medication=1.00, Observation=0.00, Specimen=0.00 | Medication:table-keyword:batch(+0.98) |

## Out-of-Scope Tables

| Table | Reason (top) |
|---|---|
| mes_steps | admin_signal_ratio=0.60 and no analysis keywords |
| qms_deviations | admin_signal_ratio=0.80 and no analysis keywords |

## Decisions Required From SMEs

| Decision | Source | Why | Top Option | Question |
|---|---|---|---|---|
| D-001 | lims_results.batch_id | Field is a likely batch/lot join key; appears in 3 cross-table join proposals. | Observation.subject.reference (0.49) | Is this the regulatory lot number or an internal batch surrogate? |
| D-002 | lims_results.method | Field has multiple plausible targets requiring SME choice for regulatory intent. | Observation.method.text (0.65) | Which target path best matches regulatory intent for this field? |
| D-003 | lims_results.spec_limit_high | Field has multiple plausible targets requiring SME choice for regulatory intent. | Observation.referenceRange.high.value (0.55) | Which target path best matches regulatory intent for this field? |
| D-004 | lims_results.spec_limit_low | Field has multiple plausible targets requiring SME choice for regulatory intent. | Observation.referenceRange.low.value (0.55) | Which target path best matches regulatory intent for this field? |
| D-005 | sap_batch.batch_quantity | Field appears to represent quantitative batch context that should be bound to explicit units. | Medication.batch.extension (0.51) | Should this quantity be represented in a PQI batch extension with explicit UOM linkage? |
| D-006 | sap_batch.batch_uom | Field appears to represent unit-of-measure semantics that need controlled coding/UOM treatment. | UNKNOWN (0.30) | Should this be represented as UCUM-compatible Observation.valueQuantity.unit? |
| D-007 | sap_batch.manufacturing_date | Field appears to represent batch lifecycle timing (manufacturing/packaging/release) requiring extension semantics. | Medication.batch.extension (0.53) | Is this manufacturing, packaging, or release timing and which PQI batch extension should capture it? |
| D-008 | sap_batch.material_id | Field appears to be a material/product identifier requiring business meaning confirmation. | Medication.code.coding.code (0.63) | Is this a product code, material master code, or an internal identifier? |
| D-009 | sap_batch.packaging_date | Field appears to represent batch lifecycle timing (manufacturing/packaging/release) requiring extension semantics. | Medication.batch.extension (0.51) | Is this manufacturing, packaging, or release timing and which PQI batch extension should capture it? |
| D-010 | sap_batch.release_date | Field appears to represent batch lifecycle timing (manufacturing/packaging/release) requiring extension semantics. | Medication.batch.extension (0.50) | Is this manufacturing, packaging, or release timing and which PQI batch extension should capture it? |

## Top Mapping Candidates

| Source | Domain | Table Resource | Candidate Target | Confidence | Label | Status | Evidence |
|---|---|---|---|---:|---|---|---|
| lims_results.analysis_time | batch_analysis | Observation | Observation::Observation.effectiveDateTime | 0.80 | GOOD_CANDIDATE | PROPOSED | token_overlap=['time']; date/datetime compatible; boost:Observation.effectiveDateTime(+0.24) |
| lims_results.batch_id | batch_analysis | Observation | Observation::Observation.subject.reference | 0.49 | REQUIRES_SME | REQUIRES_REVIEW | token_overlap=['batch', 'batchid', 'lot']; weak type fit; boost:Observation.subject.reference(+0.14) |
| lims_results.method | batch_analysis | Observation | Observation::Observation.method.text | 0.65 | REQUIRES_SME | PROPOSED | token_overlap=['analysis', 'assay', 'method', 'procedure', 'protocol', 'test']; string compatible |
| lims_results.result_unit | batch_analysis | Observation | Observation::Observation.valueQuantity.unit | 0.91 | AUTO_APPROVE_CANDIDATE | PROPOSED | token_overlap=['outcome', 'result', 'unit', 'units', 'uom', 'value']; string compatible; boost:Observation.valueQuantity.unit(+0.24) |
| lims_results.result_value | batch_analysis | Observation | Observation::Observation.valueQuantity.value | 0.85 | AUTO_APPROVE_CANDIDATE | PROPOSED | token_overlap=['outcome', 'result', 'value']; numeric compatible; boost:Observation.valueQuantity.value(+0.3) |
| lims_results.spec_limit_high | batch_analysis | Observation | Observation::Observation.referenceRange.high.value | 0.55 | REQUIRES_SME | REQUIRES_REVIEW | token_overlap=['criteria', 'high', 'limit', 'spec', 'specification']; numeric compatible |
| lims_results.spec_limit_low | batch_analysis | Observation | Observation::Observation.referenceRange.low.value | 0.55 | REQUIRES_SME | REQUIRES_REVIEW | token_overlap=['criteria', 'limit', 'low', 'spec', 'specification']; numeric compatible |
| lims_results.test_code | batch_analysis | Observation | Observation::Observation.code.coding.code | 0.87 | AUTO_APPROVE_CANDIDATE | PROPOSED | token_overlap=['analysis', 'assay', 'code', 'method', 'test']; string compatible; boost:Observation.code.coding.code(+0.25) |
| lims_results.test_name | batch_analysis | Observation | Observation::Observation.code.coding.code | 0.76 | GOOD_CANDIDATE | PROPOSED | token_overlap=['analysis', 'assay', 'method', 'test']; string compatible; boost:Observation.code.coding.code(+0.25) |
| mes_steps.batch_id | batch_lot_information | Medication | Medication::Medication.batch.lotNumber | 0.73 | GOOD_CANDIDATE | PROPOSED | token_overlap=['batch', 'batchid', 'lot']; string compatible; boost:Medication.batch.lotNumber(+0.28) |
| mes_steps.duration_hr | out_of_scope | Medication | OUT_OF_SCOPE | 0.00 | OUT_OF_SCOPE | REQUIRES_REVIEW | out_of_scope_non_anchor |
| mes_steps.equipment_id | out_of_scope | Medication | OUT_OF_SCOPE | 0.00 | OUT_OF_SCOPE | REQUIRES_REVIEW | out_of_scope_non_anchor |
| mes_steps.step_name | out_of_scope | Medication | OUT_OF_SCOPE | 0.00 | OUT_OF_SCOPE | REQUIRES_REVIEW | out_of_scope_non_anchor |
| qms_deviations.batch_id | batch_lot_information | Medication | Medication::Medication.batch.lotNumber | 0.73 | GOOD_CANDIDATE | PROPOSED | token_overlap=['batch', 'batchid', 'lot']; string compatible; boost:Medication.batch.lotNumber(+0.28) |
| qms_deviations.category | out_of_scope | Medication | OUT_OF_SCOPE | 0.00 | OUT_OF_SCOPE | REQUIRES_REVIEW | out_of_scope_non_anchor |
| qms_deviations.deviation_id | out_of_scope | Medication | OUT_OF_SCOPE | 0.00 | OUT_OF_SCOPE | REQUIRES_REVIEW | out_of_scope_non_anchor |
| qms_deviations.status | out_of_scope | Medication | OUT_OF_SCOPE | 0.00 | OUT_OF_SCOPE | REQUIRES_REVIEW | out_of_scope_non_anchor |
| sap_batch.batch_id | batch_lot_information | Medication | Medication::Medication.batch.lotNumber | 0.73 | GOOD_CANDIDATE | PROPOSED | token_overlap=['batch', 'batchid', 'lot']; string compatible; boost:Medication.batch.lotNumber(+0.28) |
| sap_batch.batch_quantity | batch_lot_information | Medication | Medication::Medication.batch.extension | 0.51 | REQUIRES_SME | REQUIRES_REVIEW | token_overlap=['batch', 'batchid', 'lot']; weak type fit; boost:Medication.batch.extension(+0.24) |
| sap_batch.batch_uom | batch_lot_information | Medication | UNKNOWN::UNKNOWN | 0.30 | REQUIRES_SME | REQUIRES_REVIEW |  |
| sap_batch.lot_number | batch_lot_information | Medication | Medication::Medication.batch.lotNumber | 0.89 | AUTO_APPROVE_CANDIDATE | PROPOSED | token_overlap=['batch', 'batchid', 'lot', 'number']; string compatible; boost:Medication.batch.lotNumber(+0.28) |
| sap_batch.manufacturing_date | batch_lot_information | Medication | Medication::Medication.batch.extension | 0.53 | REQUIRES_SME | REQUIRES_REVIEW | token_overlap=['manufacturing']; weak type fit; boost:Medication.batch.extension(+0.28) |
| sap_batch.material_id | batch_lot_information | Medication | Medication::Medication.code.coding.code | 0.63 | REQUIRES_SME | PROPOSED | token_overlap=[]; string compatible; boost:Medication.code.coding.code(+0.18) |
| sap_batch.packaging_date | batch_lot_information | Medication | Medication::Medication.batch.extension | 0.51 | REQUIRES_SME | REQUIRES_REVIEW | token_overlap=['packaging']; weak type fit; boost:Medication.batch.extension(+0.28) |
| sap_batch.release_date | batch_lot_information | Medication | Medication::Medication.batch.extension | 0.50 | REQUIRES_SME | REQUIRES_REVIEW | token_overlap=['release']; weak type fit; boost:Medication.batch.extension(+0.28) |

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

- lims_results.batch_id
- lims_results.method
- lims_results.spec_limit_high
- lims_results.spec_limit_low
- sap_batch.batch_quantity
- sap_batch.batch_uom
- sap_batch.manufacturing_date
- sap_batch.material_id
- sap_batch.packaging_date
- sap_batch.release_date
