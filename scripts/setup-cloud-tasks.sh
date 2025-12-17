#!/bin/bash
set -e

PROJECT_ID="${GCP_PROJECT_ID:-pdf-ocr-mvp-446420}"
REGION="${GCP_REGION:-us-central1}"
QUEUE_NAME="${QUEUE_NAME:-extraction-queue}"

echo "Creating Cloud Tasks queue: $QUEUE_NAME"

gcloud tasks queues describe "$QUEUE_NAME" --location="$REGION" --project="$PROJECT_ID" 2>/dev/null || \
gcloud tasks queues create "$QUEUE_NAME" \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --max-dispatches-per-second=10 \
  --max-concurrent-dispatches=100 \
  --max-attempts=3 \
  --min-backoff=60s \
  --max-backoff=3600s

echo "✓ Queue created/verified: $QUEUE_NAME"

gcloud tasks queues describe "$QUEUE_NAME" --location="$REGION" --project="$PROJECT_ID"
