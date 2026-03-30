# PQI Container Closure Demo — RINVOQ 45MG BOTTLE CANADA

Minimal honest canonical model. One source string becomes two FHIR R5 resources loaded into HAPI.

**Source string:** `RINVOQ 45MG 28 TABS BOTTLE CANADA`

---

## What this shows

A single product source string parsed into a valid, minimal PQI/FHIR canonical representation — with no invented data.

The model contains only what the source string actually states:

| Source token | Canonical field |
|---|---|
| `RINVOQ` | product name |
| `45MG` | strength |
| `TABS` | dose form → Tablet (EDQM 10219000) |
| `28` | contained item quantity |
| `BOTTLE` | packaging type → Bottle (100000073497) |
| `CANADA` | market → CA (ISO 3166) |

Deliberately excluded because the source string does not support them: route, bottle material, closure type, foil liner, manufacturer names, quality standards, color, marketing status.

---

## Resources

| Resource | ID |
|---|---|
| MedicinalProductDefinition | `mpd-rinvoq-45mg` |
| PackagedProductDefinition | `ppd-rinvoq-45mg-28tabs-bottle-ca` |

---

## How to run

Requires Docker.

```bash
# Start HAPI R5
docker compose up -d

# Wait until HAPI responds
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/fhir/metadata

# Load the bundle
./load_bundle.sh

# Verify
curl http://localhost:8080/fhir/MedicinalProductDefinition/mpd-rinvoq-45mg
curl http://localhost:8080/fhir/PackagedProductDefinition/ppd-rinvoq-45mg-28tabs-bottle-ca
```

---

## Files

```
compose.yaml                                        HAPI R5 service (port 8080)
load_bundle.sh                                      one-command loader
fhir/
  rinvoq-45mg-28tabs-bottle-ca.collection.json      canonical collection bundle
  rinvoq-45mg-28tabs-bottle-ca.transaction.json     HAPI transaction bundle
```

---

## Pinned runtime

- HAPI image: `hapiproject/hapi:v8.6.5-1`
- FHIR version: R5 (5.0.0)
- REST base: `http://localhost:8080/fhir`
