@echo off
echo Starting QA Review Server v2...
echo.
echo Features:
echo   - Real-time icon/text scale adjustment
echo   - Regenerate single product or all pending
echo   - Continue Pipeline button (lifestyle + upload + flatfile)
echo.
call config.bat
python qa_server_v2.py
pause
