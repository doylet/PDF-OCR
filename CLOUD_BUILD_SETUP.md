# Cloud Build Triggers Setup

Since the gcloud CLI has issues with the new GitHub connection format, please set up the triggers manually in the console:

## Backend Trigger

1. Go to: https://console.cloud.google.com/cloud-build/triggers?project=sylvan-replica-478802-p4
2. Click "CREATE TRIGGER"
3. Configuration:
   - Name: `deploy-backend`
   - Region: `us-central1`
   - Description: `Deploy backend API on push to main`
   - Event: Push to a branch
   - Source:
     - Repository: `doylet/PDF-OCR` (2nd gen)
     - Branch: `^main$`
   - Configuration:
     - Type: Cloud Build configuration file (yaml or json)
     - Location: `backend/cloudbuild.yaml`
   - Filters (Advanced):
     - Included files filter (glob): `backend/**`
4. Click "CREATE"

## Frontend Trigger

1. Click "CREATE TRIGGER" again
2. Configuration:
   - Name: `deploy-frontend`
   - Region: `us-central1`
   - Description: `Deploy frontend on push to main`
   - Event: Push to a branch
   - Source:
     - Repository: `doylet/PDF-OCR` (2nd gen)
     - Branch: `^main$`
   - Configuration:
     - Type: Cloud Build configuration file (yaml or json)
     - Location: `frontend/cloudbuild.yaml`
   - Filters (Advanced):
     - Included files filter (glob): `frontend/**`
3. Click "CREATE"

## Test the Triggers

After creating both triggers, test them:

```bash
# Make a small change to backend
echo "# Test" >> backend/README.md
git add backend/README.md
git commit -m "Test backend trigger"
git push

# Check the build
gcloud builds list --region=us-central1 --limit=5
```

The triggers are now set up and will automatically deploy when you push changes to the respective directories!
