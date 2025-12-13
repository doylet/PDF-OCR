# GitHub Actions Setup Guide

This project uses GitHub Actions for automated deployment to Google Cloud Run.

## Prerequisites

1. A GitHub repository
2. Google Cloud Project with Cloud Run enabled
3. Workload Identity Federation configured

## Setup Steps

### 1. Set up Workload Identity Federation

This allows GitHub Actions to authenticate to Google Cloud without service account keys.

```bash
# Set variables
export PROJECT_ID="sylvan-replica-478802-p4"
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
export REPO="YOUR_GITHUB_USERNAME/YOUR_REPO_NAME"  # e.g., "octocat/pdf-ocr"

# Create Workload Identity Pool
gcloud iam workload-identity-pools create "github-pool" \
  --project="$PROJECT_ID" \
  --location="global" \
  --display-name="GitHub Actions Pool"

# Create Workload Identity Provider
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# Create Service Account for GitHub Actions
gcloud iam service-accounts create github-actions \
  --project="$PROJECT_ID" \
  --display-name="GitHub Actions"

# Grant permissions to the service account
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.editor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Allow GitHub Actions to impersonate the service account
gcloud iam service-accounts add-iam-policy-binding \
  "github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/$REPO"

# Get the Workload Identity Provider resource name
echo "WIF_PROVIDER=projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
echo "WIF_SERVICE_ACCOUNT=github-actions@$PROJECT_ID.iam.gserviceaccount.com"
```

### 2. Set GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these secrets:

```
WIF_PROVIDER=projects/YOUR_PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider
WIF_SERVICE_ACCOUNT=github-actions@sylvan-replica-478802-p4.iam.gserviceaccount.com
GCP_PROCESSOR_ID=785c0d6231d28978
GCS_BUCKET_NAME=pdf-ocr-mvp
API_KEY=M3CIlxn7kDnBSRy5OeDn1m36EkF1YTD9iaQqZiB02ys=
BACKEND_API_URL=https://pdf-ocr-api-e3b7ctuuxa-uc.a.run.app
CORS_ORIGINS=http://localhost:3000 https://pdf-ocr-frontend-785693222332.us-central1.run.app
```

### 3. Push to GitHub

```bash
git add .
git commit -m "Initial commit with GitHub Actions"
git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 4. Workflows

Two workflows are configured:

- **deploy-backend.yml** - Deploys backend when `backend/` changes
- **deploy-frontend.yml** - Deploys frontend when `frontend/` changes

Both workflows:
- Trigger on push to `main` branch
- Can be manually triggered via workflow_dispatch
- Use Workload Identity Federation for secure authentication

## Manual Deployment

You can also manually trigger deployments:
1. Go to Actions tab in GitHub
2. Select the workflow (Deploy Backend or Deploy Frontend)
3. Click "Run workflow"

## Monitoring

- Check GitHub Actions tab for deployment status
- View Cloud Run logs: `gcloud run services logs read SERVICE_NAME --region us-central1`
