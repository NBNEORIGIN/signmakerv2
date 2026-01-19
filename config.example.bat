@echo off
REM ============================================================
REM   Amazon Publisher - Configuration Template
REM ============================================================
REM Copy this file to config.bat and fill in your actual values
REM DO NOT commit config.bat to version control (it's in .gitignore)

REM ============================================================
REM   Anthropic API Key (for Claude AI content generation)
REM ============================================================
REM Get your API key from: https://console.anthropic.com/
set ANTHROPIC_API_KEY=your_anthropic_api_key_here

REM ============================================================
REM   OpenAI API Key (for lifestyle image generation)
REM ============================================================
REM Get your API key from: https://platform.openai.com/api-keys
set OPENAI_API_KEY=your_openai_api_key_here

REM ============================================================
REM   Cloudflare R2 Settings (for image hosting)
REM ============================================================
REM Get credentials from Cloudflare R2 dashboard
set R2_ACCOUNT_ID=your_r2_account_id
set R2_ACCESS_KEY_ID=your_r2_access_key_id
set R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
set R2_BUCKET_NAME=your_bucket_name
set R2_PUBLIC_URL=https://your-bucket-url.r2.dev

REM ============================================================
REM   Etsy API Settings (optional)
REM ============================================================
REM Get your API key from: https://www.etsy.com/developers/your-apps
set ETSY_API_KEY=your_etsy_api_key

REM ============================================================
REM   eBay API Settings (optional)
REM ============================================================
REM Get credentials from: https://developer.ebay.com/my/keys
set EBAY_CLIENT_ID=your_ebay_client_id
set EBAY_CLIENT_SECRET=your_ebay_client_secret
set EBAY_RU_NAME=your_ebay_ru_name
set EBAY_ENVIRONMENT=production
set EBAY_MERCHANT_LOCATION_KEY=default

REM ============================================================
REM   Async Job System Configuration
REM ============================================================
REM Enable async job processing (true/false)
set ASYNC_JOBS_ENABLED=true

REM Comma-separated list of job types to run async
set ASYNC_JOB_TYPES=generate_amazon_content

REM Worker settings (optional - defaults shown)
REM set WORKER_CONCURRENCY=1
REM set WORKER_POLL_INTERVAL=2
REM set WORKER_STALE_JOB_TIMEOUT=600
