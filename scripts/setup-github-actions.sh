#!/bin/bash

# GitHub Actions Workload Identity Federation Setup
# This script sets up secure authentication for GitHub Actions to deploy to GCP

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== GitHub Actions WIF Setup ===${NC}\n"

# Get project info
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: No GCP project set${NC}"
    exit 1
fi

PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

echo -e "${YELLOW}Project ID:${NC} $PROJECT_ID"
echo -e "${YELLOW}Project Number:${NC} $PROJECT_NUMBER\n"

# Get GitHub repo
read -p "Enter your GitHub repository (format: username/repo): " REPO

echo -e "\n${YELLOW}Step 1: Creating Workload Identity Pool...${NC}"
gcloud iam workload-identity-pools create "github-pool" \
  --project="$PROJECT_ID" \
  --location="global" \
  --display-name="GitHub Actions Pool" \
  2>/dev/null || echo "Pool already exists"

echo -e "${GREEN}✓ Workload Identity Pool created${NC}\n"

echo -e "${YELLOW}Step 2: Creating Workload Identity Provider...${NC}"
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  2>/dev/null || echo "Provider already exists"

echo -e "${GREEN}✓ Workload Identity Provider created${NC}\n"

echo -e "${YELLOW}Step 3: Creating Service Account...${NC}"
gcloud iam service-accounts create github-actions \
  --project="$PROJECT_ID" \
  --display-name="GitHub Actions" \
  2>/dev/null || echo "Service account already exists"

echo -e "${GREEN}✓ Service Account created${NC}\n"

echo -e "${YELLOW}Step 4: Granting permissions...${NC}"

# Grant required roles
for role in "roles/run.admin" "roles/storage.admin" "roles/cloudbuild.builds.editor" "roles/iam.serviceAccountUser" "roles/artifactregistry.writer"; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="$role" \
    --condition=None \
    > /dev/null 2>&1
  echo "  ✓ Granted $role"
done

echo -e "${GREEN}✓ Permissions granted${NC}\n"

echo -e "${YELLOW}Step 5: Binding Workload Identity...${NC}"
gcloud iam service-accounts add-iam-policy-binding \
  "github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/$REPO" \
  > /dev/null 2>&1

echo -e "${GREEN}✓ Workload Identity bound${NC}\n"

# Output secrets for GitHub
WIF_PROVIDER="projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
WIF_SERVICE_ACCOUNT="github-actions@$PROJECT_ID.iam.gserviceaccount.com"

echo -e "${GREEN}=== Setup Complete! ===${NC}\n"
echo -e "${YELLOW}Add these secrets to your GitHub repository:${NC}"
echo -e "${YELLOW}(Settings → Secrets and variables → Actions → New repository secret)${NC}\n"

echo "WIF_PROVIDER=$WIF_PROVIDER"
echo "WIF_SERVICE_ACCOUNT=$WIF_SERVICE_ACCOUNT"
echo "GCP_PROCESSOR_ID=785c0d6231d28978"
echo "GCS_BUCKET_NAME=pdf-ocr-mvp"
echo "API_KEY=M3CIlxn7kDnBSRy5OeDn1m36EkF1YTD9iaQqZiB02ys="
echo "BACKEND_API_URL=https://pdf-ocr-api-e3b7ctuuxa-uc.a.run.app"
echo "CORS_ORIGINS=http://localhost:3000 https://pdf-ocr-frontend-785693222332.us-central1.run.app"

echo -e "\n${YELLOW}Next steps:${NC}"
echo "1. Add the secrets above to GitHub"
echo "2. Initialize git: git init"
echo "3. Add remote: git remote add origin git@github.com:$REPO.git"
echo "4. Commit and push: git add . && git commit -m 'Initial commit' && git push -u origin main"
