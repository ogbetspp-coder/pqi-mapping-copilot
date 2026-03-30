#!/bin/sh
set -eu

SERVER_BASE="${FHIR_BASE_URL:-http://localhost:8080/fhir}"

echo "Loading RINVOQ 45MG 28 TABS BOTTLE CANADA -> $SERVER_BASE"
curl --fail --silent --show-error \
  -X POST "$SERVER_BASE" \
  -H "Content-Type: application/fhir+json" \
  --data-binary "@fhir/rinvoq-45mg-28tabs-bottle-ca.transaction.json"
echo

echo "Verify:"
echo "  $SERVER_BASE/MedicinalProductDefinition/mpd-rinvoq-45mg"
echo "  $SERVER_BASE/PackagedProductDefinition/ppd-rinvoq-45mg-28tabs-bottle-ca"
