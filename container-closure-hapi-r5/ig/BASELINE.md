# Frozen IG Baseline

This directory contains the vendored FHIR NPM package used as the internal canonical baseline for this service.

## Package

| Field | Value |
|---|---|
| Package ID | `hl7.fhir.uv.pharm-quality` |
| Version | `1.0.0` |
| FHIR | `5.0.0 / R5` |
| File | `hl7.fhir.uv.pharm-quality-1.0.0.tgz` |
| SHA-256 | `d9e856a42c4332f5350597fca060f74d4a31c30a427057642ffb145d13aafc16` |
| Adopted | `2026-03-28` |
| Source | Extracted from the HL7 PQI IG site package at the 1.0.0 continuous build |

## Package authorship note

The vendored `package.json` contains `"notForPublication": true`. This reflects that the upstream HL7 PQI IG is a continuous build and has not completed the HL7 balloting/authorization process. This baseline is used as an internal frozen snapshot, not as evidence of conformance to an HL7 authorized standard.

## Dependency packages (resolved at validation time)

Versions match exactly what the vendored `package.json` declares under `dependencies`:

| Package | Version |
|---|---|
| `hl7.fhir.uv.extensions.r5` | `5.1.0` |
| `hl7.terminology.r5` | `5.0.0` |

## Validator CLI

| Field | Value |
|---|---|
| Tool | `org.hl7.fhir.core` validator CLI |
| Version | **TODO — pin after first green CI run.** Check the "Download FHIR validator CLI" step log for the version string, then replace `latest` in `.github/workflows/ci.yml` with the exact tag and record it here. |
| Pin URL pattern | `https://github.com/hapifhir/org.hl7.fhir.core/releases/download/X.Y.Z/validator_cli.jar` |

## Conformance statement

This service is validated against an internally frozen implementation baseline:
`hl7.fhir.uv.pharm-quality#1.0.0` (FHIR R5), with pinned package versions matching the IG-declared dependencies.
It is used as an internal canonical exchange contract and is not represented as formal conformance to an HL7 authorized publication.

## Upgrade policy

Changes to the upstream PQI IG will be assessed deliberately and adopted as an explicit version bump to this baseline.
Validation is not automatically updated when the upstream CI build changes.
