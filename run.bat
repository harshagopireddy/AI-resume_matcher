@echo off
title AI Resume Matcher
cd /d "%~dp0"
echo ============================================
echo    AI RESUME MATCHER  -  starting up
echo ============================================

if not exist "data\resume_matcher.db" (
  echo [1/3] Building database with sample data...
  python seed_data.py
) else (
  echo [1/3] Database found, skipping seed.
)

echo [2/3] Starting Flask server...
echo [3/3] Opening browser at http://127.0.0.1:5000
start "" http://127.0.0.1:5000
python app.py
pause
