@echo off
rem ==========================================================================
rem  Canvas of World History - start the API (single-jar, serves web + api)
rem
rem  Reads config\.env (never committed). Refuses to start if the target
rem  database is not the production one.
rem ==========================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0.."

set "CFG=config\.env"
if not exist "%CFG%" (
  echo [X] config\.env not found. Copy config\.env.example to config\.env first.
  exit /b 2
)
if not exist "api\canvas-history-api.jar" (
  echo [X] api\canvas-history-api.jar not found.
  exit /b 2
)

for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%CFG%") do (
  if not "%%a"=="" set "%%a=%%b"
)

if not "%POSTGRES_DB%"=="canvas_history" (
  echo [X] Refusing to start: POSTGRES_DB=!POSTGRES_DB! , expected canvas_history.
  echo     This package is for the production database only.
  exit /b 2
)

set "DB_URL=jdbc:postgresql://127.0.0.1:!DB_HOST_PORT!/!POSTGRES_DB!"
set "DB_USER=!POSTGRES_USER!"
set "DB_PASSWORD=!POSTGRES_PASSWORD!"
set "DB_WRITE_ALLOWED_DATABASES=!DB_WRITE_ALLOWED_DATABASES!"
set "SERVER__PORT="
set "SERVER_PORT="

echo Starting Canvas of World History
echo   db   = !POSTGRES_DB! @ 127.0.0.1:!DB_HOST_PORT!
echo   port = !API_PORT!
echo   web  = http://127.0.0.1:!API_PORT!/

rem ?????? web\ ??? jar ?????
rem ???? config.js?? MapTiler key??? web\ ????????????
java -jar "api\canvas-history-api.jar" --server.port=!API_PORT! --spring.web.resources.static-locations=file:./web/,classpath:/static/
exit /b %ERRORLEVEL%
