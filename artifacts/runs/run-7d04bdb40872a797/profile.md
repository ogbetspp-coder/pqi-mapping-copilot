# Data Profile

Tables: 4
Rows: 9

## Table: lims_results
- Source: data/examples/lims_results.csv
- Rows: 3

| Column | Type | Null% | Unique% | ID Score | Units |
|---|---:|---:|---:|---:|---|
| analysis_time | datetime | 0.00 | 100.00 | 0.20 |  |
| batch_id | string | 0.00 | 66.67 | 0.60 |  |
| method | string | 0.00 | 66.67 | 0.10 |  |
| result_unit | string | 0.00 | 33.33 | 0.10 | % |
| result_value | number | 0.00 | 100.00 | 0.20 |  |
| spec_limit_high | number | 0.00 | 66.67 | 0.00 |  |
| spec_limit_low | number | 0.00 | 66.67 | 0.00 |  |
| test_code | string | 0.00 | 66.67 | 0.10 |  |
| test_name | string | 0.00 | 66.67 | 0.10 |  |

## Table: mes_steps
- Source: data/examples/mes_steps.json
- Rows: 2

| Column | Type | Null% | Unique% | ID Score | Units |
|---|---:|---:|---:|---:|---|
| batch_id | string | 0.00 | 100.00 | 0.90 |  |
| duration_hr | number | 0.00 | 100.00 | 0.20 |  |
| equipment_id | string | 0.00 | 50.00 | 0.60 |  |
| step_name | string | 0.00 | 50.00 | 0.10 |  |

## Table: qms_deviations
- Source: data/examples/qms_deviations.xml
- Rows: 2

| Column | Type | Null% | Unique% | ID Score | Units |
|---|---:|---:|---:|---:|---|
| batch_id | string | 0.00 | 100.00 | 0.90 |  |
| category | string | 0.00 | 100.00 | 0.40 |  |
| deviation_id | string | 0.00 | 100.00 | 0.90 |  |
| status | string | 0.00 | 100.00 | 0.40 |  |

## Table: sap_batch
- Source: data/examples/sap_batch.csv
- Rows: 2

| Column | Type | Null% | Unique% | ID Score | Units |
|---|---:|---:|---:|---:|---|
| batch_id | string | 0.00 | 100.00 | 0.90 |  |
| batch_quantity | number | 0.00 | 100.00 | 0.20 |  |
| batch_uom | string | 0.00 | 50.00 | 0.10 | tablet |
| lot_number | string | 0.00 | 100.00 | 0.90 |  |
| manufacturing_date | date | 0.00 | 100.00 | 0.20 |  |
| material_id | string | 0.00 | 50.00 | 0.60 |  |
| packaging_date | date | 0.00 | 100.00 | 0.20 |  |
| release_date | date | 0.00 | 100.00 | 0.20 |  |

