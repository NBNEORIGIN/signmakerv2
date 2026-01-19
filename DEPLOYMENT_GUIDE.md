# Deployment Guide - GitHub & Render

This guide covers deploying the Amazon Publisher app to GitHub and Render as a separate project.

## Prerequisites

- GitHub account
- Render account (free tier works)
- Git installed locally
- All API keys ready (Anthropic, OpenAI, R2, etc.)

---

## Part 1: Push to GitHub

### Step 1: Initialize Git Repository

Open PowerShell in the project directory:

```powershell
cd "G:\My Drive\003 APPS\AMAZON PUBLISHER - Gabby"
git init
```

### Step 2: Create GitHub Repository

1. Go to [github.com/new](https://github.com/new)
2. Repository name: `amazon-publisher-async` (or your choice)
3. Description: "Amazon product publisher with async job queue"
4. **Private** repository (recommended - contains business logic)
5. **Do NOT** initialize with README (we already have one)
6. Click "Create repository"

### Step 3: Add Files to Git

```powershell
# Add all files (respects .gitignore)
git add .

# Commit
git commit -m "Initial commit - Amazon Publisher with async job queue"
```

### Step 4: Push to GitHub

Replace `YOUR_USERNAME` with your GitHub username:

```powershell
# Add remote
git remote add origin https://github.com/YOUR_USERNAME/amazon-publisher-async.git

# Push
git branch -M main
git push -u origin main
```

**Important:** You'll be prompted for GitHub credentials. Use a Personal Access Token (not password):
- Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
- Generate new token with `repo` scope
- Use token as password when prompted

---

## Part 2: Deploy to Render

### Step 1: Connect GitHub to Render

1. Go to [render.com](https://render.com)
2. Click "New +" → "Blueprint"
3. Connect your GitHub account if not already connected
4. Select the `amazon-publisher-async` repository

### Step 2: Configure Blueprint

Render will automatically detect `render.yaml` and show:
- **Web Service:** `amazon-publisher-web`
- **Worker Service:** `amazon-publisher-worker`

Click "Apply" to create both services.

### Step 3: Set Environment Variables

For **both services** (web and worker), add these environment variables in Render dashboard:

**Required:**
```
ANTHROPIC_API_KEY=your_key_here
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=your_bucket_name
R2_PUBLIC_URL=https://your-bucket.r2.dev
```

**Optional (if using):**
```
OPENAI_API_KEY=your_key_here
ETSY_API_KEY=your_key_here
EBAY_CLIENT_ID=your_client_id
EBAY_CLIENT_SECRET=your_secret
EBAY_RU_NAME=your_ru_name
```

**Already set in render.yaml:**
```
ASYNC_JOBS_ENABLED=true
ASYNC_JOB_TYPES=generate_amazon_content
WORKER_CONCURRENCY=1
```

### Step 4: Deploy

1. Render will automatically build and deploy both services
2. Wait for builds to complete (5-10 minutes first time)
3. Web service will be available at: `https://amazon-publisher-web-XXXX.onrender.com`

### Step 5: Verify Deployment

**Check Web Service:**
- Visit your Render URL
- Should see the publisher web interface

**Check Worker:**
- Go to Render dashboard → Worker service → Logs
- Should see: "Worker worker-XXXX starting"

**Test Async Jobs:**
1. Use the web interface to trigger a job
2. Check worker logs - should see job processing
3. Check web service logs - should see job enqueued

---

## Part 3: Important Notes

### Database Persistence

Both services share a persistent disk (`publisher-data`) for `jobs.db`. This ensures:
- Jobs persist across deployments
- Web and worker see the same queue

### Free Tier Limitations

Render free tier:
- Services sleep after 15 minutes of inactivity
- First request after sleep takes ~30 seconds to wake up
- 750 hours/month total across all services

**Workaround:** Use a service like [UptimeRobot](https://uptimerobot.com/) to ping your app every 14 minutes.

### Scaling

To upgrade from free tier:
1. Go to service settings in Render
2. Change plan to Starter ($7/month per service)
3. Services won't sleep
4. Better performance

### Monitoring

**View Logs:**
- Render Dashboard → Service → Logs tab
- Real-time streaming logs
- Search and filter available

**Job Queue Stats:**
- Visit: `https://your-app.onrender.com/api/jobs/stats`
- Shows queued, running, succeeded, failed counts

---

## Part 4: Updating the Deployment

### Push Updates to GitHub

```powershell
cd "G:\My Drive\003 APPS\AMAZON PUBLISHER - Gabby"

# Make your changes, then:
git add .
git commit -m "Description of changes"
git push
```

Render will automatically:
1. Detect the push
2. Rebuild both services
3. Deploy new version
4. Zero-downtime deployment

### Manual Deploy

In Render dashboard:
1. Go to service
2. Click "Manual Deploy" → "Deploy latest commit"

---

## Part 5: Troubleshooting

### Services Won't Start

**Check logs for:**
- Missing environment variables
- Python package installation errors
- Port binding issues

**Common fixes:**
- Verify all required env vars are set
- Check `requirements.txt` is complete
- Ensure `render.yaml` syntax is correct

### Worker Not Processing Jobs

**Check:**
1. Worker service is running (not crashed)
2. Worker logs show "Worker starting"
3. Environment variables are set on worker
4. Shared disk is mounted correctly

**Debug:**
- Check `/api/jobs/stats` - are jobs queued?
- Check worker logs for errors
- Restart worker service

### Jobs Failing

**Check worker logs for:**
- API key errors (Anthropic, R2)
- Network timeouts
- Missing files/directories

**Common issues:**
- R2 credentials incorrect
- API rate limits hit
- Insufficient memory (upgrade plan)

### Database Locked Errors

**Cause:** Multiple workers or high contention

**Fix:**
- Ensure only one worker instance
- Check for zombie processes
- Restart both services

---

## Part 6: Rollback Plan

If deployment has issues:

### Option 1: Rollback in Render
1. Go to service → Deploys tab
2. Find previous working deploy
3. Click "Rollback to this version"

### Option 2: Revert Git Commit
```powershell
git revert HEAD
git push
```
Render will auto-deploy the revert.

### Option 3: Disable Async Mode
In Render dashboard, change env var:
```
ASYNC_JOBS_ENABLED=false
```
This reverts to synchronous mode without code changes.

---

## Part 7: Security Best Practices

### API Keys
- ✅ Never commit `config.bat` to Git (it's in `.gitignore`)
- ✅ Use Render's environment variables (encrypted at rest)
- ✅ Rotate keys periodically
- ✅ Use separate keys for dev/prod

### Repository
- ✅ Keep repository private
- ✅ Review `.gitignore` before first commit
- ✅ Don't commit `jobs.db` or exports
- ✅ Don't commit customer data

### Access Control
- ✅ Limit GitHub collaborators
- ✅ Use Render teams for access control
- ✅ Enable 2FA on GitHub and Render

---

## Part 8: Cost Estimates

### Free Tier (Current Setup)
- Web service: Free (sleeps after 15 min)
- Worker service: Free (sleeps after 15 min)
- Disk: 1GB free
- **Total: $0/month**

### Paid Tier (Recommended for Production)
- Web service: $7/month (Starter)
- Worker service: $7/month (Starter)
- Disk: 1GB included
- **Total: $14/month**

### Additional Costs
- Cloudflare R2: ~$0.015/GB storage + $0.36/million requests
- Anthropic API: Pay per token
- OpenAI API: Pay per image
- **Estimate: $5-20/month depending on usage**

---

## Support Resources

- **Render Docs:** https://render.com/docs
- **GitHub Docs:** https://docs.github.com
- **Project Issues:** Create issue on GitHub repo
- **Render Support:** support@render.com (paid plans)

---

## Quick Reference Commands

```powershell
# Git commands
git status                    # Check what's changed
git add .                     # Stage all changes
git commit -m "message"       # Commit changes
git push                      # Push to GitHub

# View remote URL
git remote -v

# View commit history
git log --oneline

# Create new branch
git checkout -b feature-name

# Switch branches
git checkout main
```

---

**Deployment complete!** Your app is now running on Render with async job processing. 🚀
