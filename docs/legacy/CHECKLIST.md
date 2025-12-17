# Pre-Demo Checklist

Complete this checklist before your investor presentation.

## ☁️ GCP Setup

### Prerequisites
- [ ] GCP account created with billing enabled
- [ ] `gcloud` CLI installed on your machine
- [ ] Authenticated: `gcloud auth login`
- [ ] Project created or selected
- [ ] Project ID noted: `___________________________`

### APIs Enabled
- [ ] Document AI API
- [ ] Cloud Run API
- [ ] Cloud Storage API
- [ ] Firestore API
- [ ] Cloud Build API
- [ ] Cloud Tasks API (optional)

### Resources Created
- [ ] Document AI Processor created
  - Type: `[ ] Document OCR` or `[ ] Form Parser` (recommended)
  - Location: `us`
  - Processor ID: `___________________________`
- [ ] Cloud Storage bucket created
  - Bucket name: `___________________________`
  - CORS configured
- [ ] Firestore database initialized
  - Database: `(default)`
  - Location: `us-central`
- [ ] Service account created with IAM roles
  - Service account email: `___________________________`

## 🔧 Backend Setup

### Local Testing
- [ ] Python 3.11+ installed
- [ ] Virtual environment created
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] `.env` file created with correct values
- [ ] Backend runs locally: `uvicorn app.main:app --reload`
- [ ] Health endpoint works: `curl http://localhost:8000/health`
- [ ] API docs accessible: `http://localhost:8000/docs`

### Production Deployment
- [ ] Backend deployed to Cloud Run
- [ ] Service URL noted: `___________________________`
- [ ] Health check passes
- [ ] API docs accessible online
- [ ] CORS configured with frontend domain

## 🎨 Frontend Setup

### Local Testing
- [ ] Node.js 18+ installed
- [ ] Dependencies installed: `npm install`
- [ ] `.env.local` file created
- [ ] API URL configured correctly
- [ ] Frontend runs locally: `npm run dev`
- [ ] Can access at `http://localhost:3000`
- [ ] No console errors

### Production Deployment
- [ ] Frontend deployed (Vercel or Cloud Run)
- [ ] Frontend URL noted: `___________________________`
- [ ] Environment variables set in deployment
- [ ] Backend API URL configured
- [ ] Site loads without errors

## 🧪 End-to-End Testing

### Upload Test
- [ ] Can select PDF file
- [ ] Upload completes successfully
- [ ] No CORS errors
- [ ] PDF ID received

### Extraction Test
- [ ] PDF renders correctly
- [ ] Can draw region on PDF
- [ ] Region appears with blue overlay
- [ ] Can add multiple regions
- [ ] Can remove regions
- [ ] Can add labels to regions

### Processing Test
- [ ] Click "Extract Data" button
- [ ] Job created successfully
- [ ] Job ID displayed
- [ ] Status updates from "queued" to "processing"
- [ ] Status updates to "completed"
- [ ] Download button appears

### Download Test
- [ ] Can click download button
- [ ] File downloads successfully
- [ ] File has correct format (CSV/TSV/JSON)
- [ ] Data is accurate
- [ ] Confidence scores present
- [ ] Structured data (tables) extracted correctly

## 📄 Test Documents

### Prepared PDFs
- [ ] Have 3-4 test PDFs ready
- [ ] PDFs are high quality (300 DPI+)
- [ ] Know what's in each PDF
- [ ] Tested each PDF beforehand
- [ ] Have backup PDFs

### Test Scenarios
- [ ] Invoice: vendor info + line items
- [ ] Form: field extraction
- [ ] Table: financial statement
- [ ] Receipt: itemized list

## 🎤 Demo Preparation

### Presentation
- [ ] Demo script written
- [ ] Key talking points identified
- [ ] ROI calculation prepared
- [ ] Competitive analysis ready
- [ ] Pricing tiers defined

### Technical Setup
- [ ] Internet connection verified
- [ ] Laptop fully charged
- [ ] Backup hotspot available
- [ ] Screen sharing tested
- [ ] Demo account created (not personal)

### Rehearsal
- [ ] Practiced demo 2-3 times
- [ ] Timed demo (< 10 minutes ideal)
- [ ] Prepared for questions
- [ ] Tested on demo computer
- [ ] Backup demo video recorded (just in case)

## 💼 Investor Deck

### Slides Prepared
- [ ] Problem statement
- [ ] Solution overview
- [ ] Live demo slide (placeholder)
- [ ] Market opportunity
- [ ] Business model
- [ ] Team introduction
- [ ] Ask and use of funds

### Supporting Materials
- [ ] One-pager printed
- [ ] Technical architecture diagram
- [ ] Cost analysis spreadsheet
- [ ] Roadmap (3-6 months)

## 🔒 Security & Privacy

### For Demo
- [ ] Using non-sensitive test documents
- [ ] No real customer data
- [ ] API keys secure (not in git)
- [ ] Demo account credentials separate
- [ ] Test data can be shown publicly

### For Production
- [ ] Changed default API key
- [ ] Set up authentication plan
- [ ] Data retention policy defined
- [ ] Privacy policy drafted
- [ ] Terms of service drafted

## 📊 Metrics to Track

### During Demo Period
- [ ] Number of extractions
- [ ] Average processing time
- [ ] Accuracy rate
- [ ] Error rate
- [ ] GCP costs

### To Present
- [ ] Cost per extraction: `$_______`
- [ ] Processing speed: `_______ seconds`
- [ ] Accuracy: `_______%`
- [ ] Scalability: `_______ concurrent users`

## 🚨 Contingency Plans

### If Live Demo Fails
- [ ] Recorded demo video ready
- [ ] Screenshots prepared
- [ ] Sample outputs ready to show
- [ ] Can explain architecture verbally

### If Questions Can't Be Answered
- [ ] "Great question, let me follow up"
- [ ] Technical advisor contact ready
- [ ] Documentation URLs bookmarked

## 📝 Post-Demo Follow-Up

### Immediate (Same Day)
- [ ] Thank you email template ready
- [ ] Demo recording (if recorded)
- [ ] Additional info packets
- [ ] Calendly link for next meeting

### Short Term (1 Week)
- [ ] Investor feedback survey
- [ ] Detailed technical docs
- [ ] Financial projections
- [ ] Partnership opportunities

## ✅ Final Pre-Demo Check (Day Before)

**24 Hours Before Demo:**
- [ ] Backend health check: `curl https://your-backend.run.app/health`
- [ ] Frontend loads: Open in browser
- [ ] Test extraction works end-to-end
- [ ] All test PDFs downloaded locally
- [ ] Laptop fully updated and restarted
- [ ] Backup PDFs on USB drive
- [ ] Phone hotspot tested
- [ ] Investors confirmed attendance
- [ ] Demo script reviewed one last time

**1 Hour Before Demo:**
- [ ] Backend still healthy
- [ ] Frontend still working
- [ ] Test extraction performed
- [ ] Browser cache cleared
- [ ] Demo user logged in
- [ ] Screen mirroring tested
- [ ] Phone on silent
- [ ] Water/coffee ready

## 🎉 You're Ready!

When all items are checked, you're fully prepared for your investor demo.

**Pro Tips:**
1. Arrive 15 minutes early
2. Have your demo open and ready before investors arrive
3. Disable notifications during demo
4. Speak slowly and clearly
5. Make eye contact, not just screen
6. Show enthusiasm for your product
7. Listen to feedback

**Good luck!** 🚀

---

## Quick Recovery Commands

If something breaks during demo:

```bash
# Backend health check
curl https://your-backend.run.app/health

# Restart local backend
cd backend && uvicorn app.main:app --reload

# Restart local frontend
cd frontend && npm run dev

# View backend logs
gcloud run services logs read pdf-ocr-api --region us-central1 --limit 50

# Redeploy backend
cd backend && ./deploy.sh

# Clear browser cache
Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
```
