#!/bin/sh

set -eu

SERVER_BASE="${FHIR_BASE_URL:-http://localhost:8080/fhir}"
MODE="${1:-initial}"

case "$MODE" in
  initial)
    BUNDLE_PATH="fhir/container-closure.transaction.json"
    ;;
  update)
    BUNDLE_PATH="fhir/container-closure-update.transaction.json"
    ;;
  *)
    echo "Usage: ./load_bundle.sh [initial|update]" >&2
    exit 1
    ;;
esac

echo "Posting $BUNDLE_PATH to $SERVER_BASE"
curl --fail --silent --show-error \
  -X POST "$SERVER_BASE" \
  -H "Content-Type: application/fhir+json" \
  --data-binary "@$BUNDLE_PATH"
echo
