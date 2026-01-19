@echo off
REM ============================================================
REM   Amazon Publisher REV 2.0 - Configuration Template
REM ============================================================
REM 
REM INSTRUCTIONS:
REM   1. Copy this file and rename it to 'config.bat'
REM   2. Replace the placeholder values with your actual API keys
REM   3. DO NOT share config.bat or commit it to version control
REM
REM ============================================================

REM Claude API Key (for content generation)
set ANTHROPIC_API_KEY=sk-ant-your-key-here

REM OpenAI API Key (for lifestyle image generation)
set OPENAI_API_KEY=sk-proj-your-key-here

REM Cloudflare R2 Settings (for image hosting)
set R2_ACCOUNT_ID=your-account-id
set R2_ACCESS_KEY_ID=your-access-key-id
set R2_SECRET_ACCESS_KEY=your-secret-access-key
set R2_BUCKET_NAME=productimages
set R2_PUBLIC_URL=https://pub-xxxxx.r2.dev
