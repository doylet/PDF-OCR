#!/bin/bash

# GCP Setup Script for PDF-OCR MVP
# This script enables required APIs and sets up GCP resources

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== GCP PDF-OCR Setup ===${NC}\n"

# Check gcloud
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI not installed${NC}"
    exit 1
fi

# Get project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: No GCP project set${NC}"
    echo "Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo -e "${YELLOW}Project ID:${NC} $PROJECT_ID\n"

# Enable APIs
echo -e "${YELLOW}Enabling required APIs...${NC}"
gcloud services enable documentai.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable cloudtasks.googleapis.com
gcloud services enable cloudbuild.googleapis.com

echo -e "${GREEN}✓ APIs enabled${NC}\n"

# Create service account
SERVICE_ACCOUNT_NAME="pdf-ocr-service"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo -e "${YELLOW}Creating service account...${NC}"
if gcloud iam service-accounts describe $SERVICE_ACCOUNT_EMAIL &>/dev/null; then
    echo "Service account already exists"
else
    gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
        --display-name="PDF OCR Service Account"
    echo -e "${GREEN}✓ Service account created${NC}"
fi

# Grant IAM roles
echo -e "\n${YELLOW}Granting IAM roles...${NC}"
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/documentai.apiUser" \
    --condition=None

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/storage.admin" \
    --condition=None

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/datastore.user" \
    --condition=None

echo -e "${GREEN}✓ IAM roles granted${NC}\n"

# Create Firestore database
echo -e "${YELLOW}Setting up Firestore...${NC}"
if gcloud firestore databases describe --database='(default)' &>/dev/null; then
    echo "Firestore database already exists"
else
    gcloud firestore databases create --location=us-central1
    echo -e "${GREEN}✓ Firestore database created${NC}"
fi

# Create GCS bucket
read -p "Enter bucket name for PDF storage (e.g., ${PROJECT_ID}-pdf-ocr): " BUCKET_NAME
BUCKET_NAME=${BUCKET_NAME:-"${PROJECT_ID}-pdf-ocr"}

echo -e "\n${YELLOW}Creating Cloud Storage bucket...${NC}"
if gsutil ls -b gs://$BUCKET_NAME &>/dev/null; then
    echo "Bucket already exists"
else
    gsutil mb -p $PROJECT_ID -c STANDARD -l US gs://$BUCKET_NAME
    echo -e "${GREEN}✓ Bucket created${NC}"
fi

# Set CORS for bucket
echo -e "\n${YELLOW}Setting CORS for bucket...${NC}"
cat > /tmp/cors.json <<EOF
[
  {
    "origin": ["http://localhost:3000", "https://your-frontend-domain.com"],
    "method": ["GET", "PUT", "POST"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
EOF
gsutil cors set /tmp/cors.json gs://$BUCKET_NAME
rm /tmp/cors.json
echo -e "${GREEN}✓ CORS configured${NC}\n"

# Create Document AI processor
echo -e "${YELLOW}Document AI Processor Setup${NC}"
echo "Please create a Document AI processor manually:"
echo "1. Go to: https://console.cloud.google.com/ai/document-ai/processors"
echo "2. Click 'Create Processor'"
echo "3. Choose 'Document OCR' or 'Form Parser'"
echo "4. Select location: 'us' (United States)"
echo "5. Copy the Processor ID\n"

read -p "Enter Document AI Processor ID: " PROCESSOR_ID

# Create .env file
echo -e "\n${YELLOW}Creating .env file...${NC}"
cat > ../backend/.env <<EOF
# GCP Configuration
GCP_PROJECT_ID=$PROJECT_ID
GCP_LOCATION=us
GCP_PROCESSOR_ID=$PROCESSOR_ID

# Cloud Storage
GCS_BUCKET_NAME=$BUCKET_NAME
GCS_PDF_FOLDER=pdfs
GCS_RESULTS_FOLDER=results

# Firestore
FIRESTORE_COLLECTION=extraction_jobs

# Cloud Tasks (placeholder - update after deploying worker)
CLOUD_TASKS_QUEUE=extraction-queue
CLOUD_TASKS_LOCATION=us-central1
WORKER_SERVICE_URL=https://your-worker-service.run.app

# CORS (update with your frontend domain)
CORS_ORIGINS=["http://localhost:3000","https://your-frontend-domain.com"]

# API Security
API_KEY=change-this-in-production

# Application
DEBUG=false
EOF

echo -e "${GREEN}✓ .env file created at backend/.env${NC}\n"

echo -e "${GREEN}=== Setup Complete! ===${NC}\n"
echo -e "${YELLOW}Summary:${NC}"
echo "- Project ID: $PROJECT_ID"
echo "- Service Account: $SERVICE_ACCOUNT_EMAIL"
echo "- GCS Bucket: $BUCKET_NAME"
echo "- Processor ID: $PROCESSOR_ID"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Review backend/.env file"
echo "2. Run: cd backend && ./deploy.sh"
echo "3. Update frontend .env with backend URL"
echo "4. Deploy frontend to Vercel or Cloud Run"
