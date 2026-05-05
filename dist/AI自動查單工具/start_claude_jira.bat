@echo off
chcp 65001 >nul
title Claude Jira Assistant

echo [INFO] start_claude_jira.bat started.
echo [INFO] Running PowerShell script...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_claude_jira_gui.ps1"

echo.
echo [INFO] Finished.
pause
