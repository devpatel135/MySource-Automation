@echo off
cd /d "%~dp0"
python schedule_automation.py
exit /b %ERRORLEVEL%
