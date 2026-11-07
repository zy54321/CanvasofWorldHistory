@echo off
rem ==========================================================================
rem  Canvas of World History - build a release package (entry point)
rem
rem  This file is intentionally ASCII-only and contains no logic.
rem  All Chinese interaction and the actual work live in:
rem      scripts\release\git-release.ps1
rem
rem  Usage:
rem      double-click                          normal interactive run
rem      with -DryRun                          check only, no build
rem      with -SkipTag                         build and archive, no git tag
rem
rem  Exit codes: 0 = finished normally (including user cancel),
rem              1 = error (dirty workspace, build failure, checksum, tag)
rem ==========================================================================
setlocal
cd /d "%~dp0"

chcp 65001 >nul

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\release\git-release.ps1" %*
set "RC=%ERRORLEVEL%"

echo.
pause
exit /b %RC%
