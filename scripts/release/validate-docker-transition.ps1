#Requires -Version 5.1
<#
One-shot, read-only validation for the Canvas Docker PROD transition.
No image build, container start/stop, migrations or writes to PROD.
#>
[CmdletBinding()]
param(
    [string]$ReleasePackage = 'E:\01_Work\03_Release\01_Personal\CanvasofWorldHistory\1.0.0',
    [string]$ProdRoot = 'E:\01_Work\04_Prod\01_Personal\CanvasofWorldHistory'
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
