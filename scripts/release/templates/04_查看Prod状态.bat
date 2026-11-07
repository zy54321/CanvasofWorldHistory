@echo off
rem ==========================================================================
rem  Canvas of World History - show PROD status (read only, entry point)
rem
rem  This file is intentionally ASCII-only and contains no logic.
rem  All output lives in: deploy\prod-status.ps1
rem
rem  It only reads. It never starts, stops or modifies anything.
rem ==========================================================================
setlocal
cd /d "%~dp0"
chcp 65001 >nul

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy\prod-status.ps1" %*
set "RC=%ERRORLEVEL%"

echo.
pause
exit /b %RC%
