#!/bin/bash

# PDF-OCR Backend Deployment Script for Cloud Run
# This script builds and deploys the FastAPI service to GCP Cloud Run

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== PDF-OCR Backend Deployment ===${NC}\n"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    echo "Install it from: https://cloud.google.com/sdk/docs/install"
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
SERVICE_NAME="pdf-ocr-api"
REGION="us-central1"
MEMORY="2Gi"
TIMEOUT="300"
MAX_INSTANCES="10"
MIN_INSTANCES="0"

# Ask for environment variables if not set
read -p "Enter GCP Processor ID (Document AI): " PROCESSOR_ID
read -p "Enter GCS Bucket Name: " BUCKET_NAME
read -p "Enter API Key (or press Enter for default): " API_KEY
API_KEY=${API_KEY:-"change-this-in-production"}
read -p "Enter Frontend URL (or press Enter for localhost only): " FRONTEND_URL
CORS_VALUE="http://localhost:3000"
if [ -n "$FRONTEND_URL" ]; then
    CORS_VALUE="http://localhost:3000 $FRONTEND_URL"
fi

echo -e "\n${YELLOW}Deploying to Cloud Run...${NC}\n"

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
    --source . \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory $MEMORY \
    --timeout $TIMEOUT \
    --max-instances $MAX_INSTANCES \
    --min-instances $MIN_INSTANCES \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,GCP_PROCESSOR_ID=$PROCESSOR_ID,GCS_BUCKET_NAME=$BUCKET_NAME,API_KEY=$API_KEY,GCP_LOCATION=us,FIRESTORE_COLLECTION=extraction_jobs,CORS_ORIGINS=$CORS_VALUE"

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')

echo -e "\n${GREEN}✓ Deployment successful!${NC}"
echo -e "${YELLOW}Service URL:${NC} $SERVICE_URL"
echo -e "\n${YELLOW}Next steps:${NC}"
echo "1. Test the API: curl $SERVICE_URL/health"
echo "2. View API docs: $SERVICE_URL/docs"
echo "3. Update frontend .env with: NEXT_PUBLIC_API_URL=$SERVICE_URL"
echo "4. Configure CORS in backend with your frontend domain"
