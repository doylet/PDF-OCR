#!/bin/bash

# PDF-OCR Frontend Deployment Script for Cloud Run
# Deploys Next.js application to GCP Cloud Run

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== PDF-OCR Frontend Deployment ===${NC}\n"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    exit 1
fi

# Get project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: No GCP project set${NC}"
    echo "Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo -e "${YELLOW}Project ID:${NC} $PROJECT_ID"

# Configuration
SERVICE_NAME="pdf-ocr-frontend"
REGION="us-central1"
MEMORY="512Mi"
MAX_INSTANCES="10"
MIN_INSTANCES="0"

# Ask for backend URL
read -p "Enter Backend API URL (e.g., https://pdf-ocr-api-xxx.run.app): " API_URL
read -p "Enter API Key: " API_KEY

echo -e "\n${YELLOW}Building and deploying to Cloud Run using Cloud Build...${NC}\n"

# Deploy using Cloud Build with substitutions
gcloud builds submit \
    --config cloudbuild.yaml \
    --substitutions _API_URL="$API_URL",_API_KEY="$API_KEY"

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')

echo -e "\n${GREEN}✓ Deployment successful!${NC}"
echo -e "${YELLOW}Frontend URL:${NC} $SERVICE_URL"
echo -e "\n${YELLOW}Next steps:${NC}"
echo "1. Open frontend: $SERVICE_URL"
echo "2. Test PDF upload and extraction"
echo "3. Update backend CORS with frontend URL:"
echo "   gcloud run services update pdf-ocr-api \\"
echo "     --region us-central1 \\"
echo "     --update-env-vars CORS_ORIGINS='[\"http://localhost:3000\",\"$SERVICE_URL\"]'"
