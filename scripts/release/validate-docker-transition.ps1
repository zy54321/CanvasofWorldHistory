#Requires -Version 5.1
<#
One-shot, read-only validation for the Canvas Docker PROD transition.
No image build, container start/stop, migrations or writes to PROD.
#>
[CmdletBinding()]
param(
    [string]$ReleasePackage = 'E:\01_Work\03_Release\01_Personal\CanvasofWorldHistory\1.0.0',
    [string]$ProdRoot = 'E:\01_Work\04_Prod\01_Personal\CanvasofWorldHistory',
    [string]$DevEnvFile = 'E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory\code\.env.dev',
    [switch]$ApplyCanary
)
$ErrorActionPreference = 'Stop'
$templates = Join-Path $PSScriptRoot 'templates'
$toParse = @(
    (Join-Path $templates 'publish-container.ps1'),
    (Join-Path $templates 'publish-prod.ps1'),
    (Join-Path $templates 'prod-status.ps1'),
    (Join-Path $PSScriptRoot 'git-release.ps1')
)
foreach ($file in $toParse) {
    $tok = $null; $err = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile($file,[ref]$tok,[ref]$err)
    if (@($err).Count -gt 0) {
        foreach ($entry in $err) { Write-Host "[PARSE ERROR] $($entry.Message) at $($entry.Extent.StartLineNumber)" -ForegroundColor Red }
        throw "PowerShell syntax invalid: $file"
    }
    Write-Host "[PASS] PowerShell parser: $(Split-Path -Leaf $file)" -ForegroundColor Green
}
$cfg = Join-Path $ProdRoot 'config\.env'
if (-not (Test-Path -LiteralPath $cfg)) { throw "Missing existing production configuration: $cfg" }
$compose = Join-Path $templates 'docker-compose.app.prod.yml'
$env:CANVAS_APP_IMAGE = 'canvas-history-app:config-check'
$env:CANVAS_CONFIG_JS_PATH = Join-Path $ProdRoot 'config\web\config.js'
try {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & docker compose -p canvas-history --env-file $cfg -f $compose config --quiet 2>&1 | ForEach-Object { Write-Host "$_" }; $rc = $LASTEXITCODE }
    finally { $ErrorActionPreference = $prev }
    if ($rc -ne 0) { throw "Docker Compose config failed: $rc" }
    Write-Host '[PASS] Docker app Compose validates (no startup)' -ForegroundColor Green
} finally {
    Remove-Item Env:\CANVAS_APP_IMAGE,Env:\CANVAS_CONFIG_JS_PATH -ErrorAction SilentlyContinue
}
$publisher = Join-Path $templates 'publish-container.ps1'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $publisher -ReleasePackage $ReleasePackage -ProdRoot $ProdRoot -DryRun
if ($LASTEXITCODE -ne 0) { throw "Publisher dry-run failed: $LASTEXITCODE" }
Write-Host '[PASS] Deployment preflight completed. No changes made.' -ForegroundColor Green


if ($ApplyCanary) {
    Write-Host '[CANARY] Starting DEV-only Docker validation (port 5199)' -ForegroundColor Cyan
    if (-not (Test-Path -LiteralPath $DevEnvFile)) { throw "DEV config missing: $DevEnvFile" }
    $devHealth = (& docker inspect '--format={{.State.Health.Status}}' canvas-history-db-dev 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $devHealth -ne 'healthy') { throw 'DEV DB is not healthy' }
    if (@(Get-NetTCPConnection -State Listen -LocalPort 5199 -ErrorAction SilentlyContinue).Count -gt 0) {
        throw 'Port 5199 is already occupied: refuse to replace an existing process'
    }
    $m = Get-Content -LiteralPath (Join-Path $ReleasePackage 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $jar = Join-Path $ReleasePackage 'api\canvas-history-api.jar'
    if (-not (Test-Path -LiteralPath $jar)) { throw 'Release JAR missing for canary' }
    $hash = (Get-FileHash -LiteralPath $jar -Algorithm SHA256).Hash.ToLower()
    if ($hash -ne ([string]$m.artifacts.api.sha256).ToLower()) { throw 'Release JAR hash mismatch' }
    $canaryImage = ('canvas-history-app:{0}-{1}' -f [string]$m.releaseVersion,$hash.Substring(0,12))
    $ctx = Join-Path $env:TEMP ('canvas-canary-build-'+[guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $ctx -Force | Out-Null
    try {
        Copy-Item -LiteralPath $jar -Destination (Join-Path $ctx 'canvas-history-api.jar')
        Copy-Item -LiteralPath (Join-Path $templates 'Dockerfile.app') -Destination (Join-Path $ctx 'Dockerfile.app')
        Write-Host "[BUILD] $canaryImage (minimal JAR-only build context)"
        & docker build -t $canaryImage -f (Join-Path $ctx 'Dockerfile.app') $ctx
        if ($LASTEXITCODE -ne 0) { throw 'Canary Docker build failed' }
    } finally {
        Remove-Item -LiteralPath $ctx -Recurse -Force -ErrorAction SilentlyContinue
    }
    $canaryCompose = Join-Path $templates 'docker-compose.canary.dev.yml'
    $env:CANVAS_APP_IMAGE = $canaryImage
    $baseArgs = @('compose','-p','canvas-history-validation','--env-file',$DevEnvFile,'-f',$canaryCompose)
    try {
        $launchArgs = $baseArgs + @('up','-d','--no-build','canary')
        & docker @launchArgs
        if ($LASTEXITCODE -ne 0) { throw 'DEV canary startup failed' }
        $ok = $false
        for ($i=0; $i -lt 45; $i++) {
            Start-Sleep -Seconds 2
            try {
                $h = Invoke-RestMethod -Uri 'http://127.0.0.1:5199/api/v1/meta/health' -TimeoutSec 3
                if ($h.status -eq 'ok' -and $h.database -eq 'canvas_history_dev') {
                    $page = Invoke-WebRequest -Uri 'http://127.0.0.1:5199/' -UseBasicParsing -TimeoutSec 5
                    if ($page.StatusCode -eq 200) { $ok = $true; break }
                }
            } catch {}
        }
        if (-not $ok) { throw 'DEV canary health/page failed; see docker compose logs (validation project)' }
        Write-Host '[PASS] DEV canary uses canvas_history_dev and serves HTTP 200.' -ForegroundColor Green
    } finally {
        $shutdownArgs = $baseArgs + @('down','--remove-orphans')
        & docker @shutdownArgs
        Remove-Item Env:\CANVAS_APP_IMAGE -ErrorAction SilentlyContinue
        Write-Host '[CLEANUP] Removed DEV canary container. DEV and PROD databases untouched.'
    }
}
