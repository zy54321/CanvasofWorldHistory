@echo off
rem ==========================================================================
rem  Canvas of World History - deploy this release to production (entry point)
rem
rem  This file lives in the ROOT of a release package, next to manifest.json.
rem  It is ASCII-only and contains no logic; everything else is in
rem      deploy\publish-container.ps1
rem
rem  Usage:
rem      double-click                          normal interactive deploy
rem      default                              interactive apply deployment
rem      with -DryRun                        inspect only, no changes
rem
rem  Exit codes: 0 = finished normally (including user cancel),
rem              1 = error (package check, db identity, migration, startup)
rem ==========================================================================
setlocal
cd /d "%~dp0"

chcp 65001 >nul

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy\publish-prod.ps1" %*
set "RC=%ERRORLEVEL%"

echo.
pause
exit /b %RC%
