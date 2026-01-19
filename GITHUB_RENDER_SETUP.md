# Quick Setup: GitHub + Render Deployment

## TL;DR - Fast Track

```powershell
# 1. Initialize Git
cd "G:\My Drive\003 APPS\AMAZON PUBLISHER - Gabby"
git init
git add .
git commit -m "Initial commit"

# 2. Create GitHub repo at github.com/new (private)

# 3. Push to GitHub (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/amazon-publisher-async.git
git branch -M main
git push -u origin main

# 4. Deploy to Render
# - Go to render.com → New → Blueprint
# - Connect GitHub repo
# - Add environment variables (see below)
# - Click "Apply"
```

---

## Files Created for Deployment

✅ **`.gitignore`** - Already exists, protects secrets  
✅ **`requirements.txt`** - Already exists, lists dependencies  
✅ **`render.yaml`** - Created, defines web + worker services  
✅ **`config.example.bat`** - Created, template for local config  
✅ **`DEPLOYMENT_GUIDE.md`** - Created, full deployment docs  

---

## Required Environment Variables for Render

Add these in Render dashboard for **both** web and worker services:

### Critical (Must Have)
```
ANTHROPIC_API_KEY=sk-ant-...
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=productimages
R2_PUBLIC_URL=https://pub-....r2.dev
```

### Optional (If Using)
```
OPENAI_API_KEY=sk-proj-...
ETSY_API_KEY=...
EBAY_CLIENT_ID=...
EBAY_CLIENT_SECRET=...
EBAY_RU_NAME=...
```

---

## What Gets Deployed

**Two Services:**

1. **Web Service** (`amazon-publisher-web`)
   - Runs `publisher_web.py`
   - Serves web interface
   - Enqueues jobs
   - Public URL: `https://amazon-publisher-web-XXXX.onrender.com`

2. **Worker Service** (`amazon-publisher-worker`)
   - Runs `worker.py`
   - Processes jobs in background
   - No public URL (internal only)

**Shared Disk:**
- Both services share `jobs.db` via persistent disk
- 1GB storage included

---

## Verification Checklist

After deployment:

- [ ] Web service shows "Live" status in Render
- [ ] Worker service shows "Live" status in Render
- [ ] Can access web URL and see interface
- [ ] Worker logs show "Worker starting"
- [ ] Test job via web UI - should enqueue and process
- [ ] Check `/api/jobs/stats` endpoint works

---

## Cost

**Free Tier:**
- $0/month
- Services sleep after 15 min inactivity
- 750 hours/month total

**Paid Tier (Recommended):**
- $14/month ($7 per service)
- No sleeping
- Better performance

---

## Important Notes

### What's NOT Committed to Git

These files are in `.gitignore` and won't be pushed:
- `config.bat` (contains secrets)
- `jobs.db` (database)
- `exports/` (generated files)
- `*.xlsx` (flatfiles)
- `products.csv` (data files)

### What IS Committed

- All Python code
- Batch scripts
- Documentation
- Templates
- `render.yaml`
- `requirements.txt`
- `.gitignore`

### Secrets Management

- **Local:** Use `config.bat` (not committed)
- **Render:** Use environment variables in dashboard
- **Never** commit API keys to Git

---

## Common Issues & Fixes

### "Permission denied" when pushing to GitHub
**Fix:** Use Personal Access Token instead of password
- GitHub Settings → Developer settings → Personal access tokens
- Generate token with `repo` scope
- Use token as password

### Services fail to start on Render
**Fix:** Check logs for missing environment variables
- Render Dashboard → Service → Logs
- Add missing vars in Environment tab

### Worker not processing jobs
**Fix:** Verify worker is running and has same env vars as web
- Check worker logs
- Ensure `ASYNC_JOBS_ENABLED=true` on web service
- Restart worker if needed

### Database locked errors
**Fix:** Ensure only one worker instance
- Check Render dashboard - should be 1 instance
- Restart both services if needed

---

## Next Steps After Deployment

1. **Test the system:**
   - Visit your Render URL
   - Trigger a job
   - Monitor worker logs
   - Verify flatfile is generated

2. **Set up monitoring:**
   - Use UptimeRobot to prevent sleeping (free tier)
   - Monitor `/api/jobs/stats` endpoint
   - Set up Render email alerts

3. **Consider upgrades:**
   - Upgrade to paid tier for production
   - Add custom domain
   - Enable auto-scaling if needed

---

## Support

- **Full Guide:** See `DEPLOYMENT_GUIDE.md`
- **Async Jobs:** See `ASYNC_JOBS_GUIDE.md`
- **Implementation:** See `ASYNC_IMPLEMENTATION_SUMMARY.md`
- **Render Docs:** https://render.com/docs
- **GitHub Docs:** https://docs.github.com

---

**Ready to deploy!** Follow the TL;DR steps above to get started. 🚀
