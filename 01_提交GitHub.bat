@echo off
rem ==========================================================================
rem  Canvas of World History - GitHub commit tool (entry point)
rem
rem  This file is intentionally ASCII-only and contains no logic.
rem  All Chinese interaction and the actual work live in:
rem      scripts\dev\git-publish.ps1
rem
rem  Usage:
rem      double-click                          normal interactive run
rem      double-click with -DryRun argument    read-only preview (nothing written)
rem
rem  Exit codes: 0 = finished normally (including user cancel)
rem              1 = error (security block, git failure, push rejected)
rem              2 = committed locally, but not pushed (local commit kept)
rem ==========================================================================
setlocal
cd /d "%~dp0"

rem Switch console to UTF-8 so the PowerShell script's Chinese output renders
rem correctly regardless of the system default code page.
chcp 65001 >nul

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev\git-publish.ps1" %*
set "RC=%ERRORLEVEL%"

if "%RC%"=="2" echo [GitHub] local commit kept, remote NOT updated (exit 2)
if "%RC%"=="1" echo [GitHub] stopped with an error (exit 1)

echo.
pause
exit /b %RC%
