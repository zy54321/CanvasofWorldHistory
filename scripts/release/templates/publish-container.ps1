#Requires -Version 5.1
<#
Canvas Docker PROD publisher (BAT03).
Initial transition: keeps the existing canvas-history DB container/network/volume.
Only manages the new application container; NEVER runs compose down/up on the DB.
Use -ReleasePackage for an existing immutable Release archive (e.g. 1.0.0).
Default mode is read-only; -Apply requires an additional interactive confirmation.
#>
[CmdletBinding()]
param(
    [string]$ReleasePackage = '',
    [string]$ProdRoot = 'E:\01_Work\04_Prod\01_Personal\CanvasofWorldHistory',
    [switch]$Apply,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$port = 5180
$dbContainer = 'canvas-history-db'
$dbVolume = 'canvas-history-pgdata'
$dbNetwork = 'canvas-history-net'
$appContainer = 'canvas-history-prod-app'
$composeProject = 'canvas-history'
$cutoverAttempted = $false
$oldJavaStopped = $false
$priorImage = ''
$oldWorkingDir = ''
$cfg = @{}
$env:CANVAS_APP_IMAGE = ''
$env:CANVAS_CONFIG_JS_PATH = ''

function Require([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}
function Read-Env([string]$Path) {
    $result = @{}
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $s = $line.Trim()
        if (-not $s -or $s.StartsWith('#')) { continue }
        $i = $s.IndexOf('=')
        if ($i -gt 0) { $result[$s.Substring(0,$i).Trim()] = $s.Substring($i+1).Trim() }
    }
    return $result
}
function Run-Docker([string[]]$Arguments) {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & docker @Arguments 2>&1 | ForEach-Object { Write-Host "$_" }
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    if ($code -ne 0) {
        $shortCommand = (($Arguments | Select-Object -First 4) -join ' ')
        throw "Docker command failed (exit $code): $shortCommand"
    }
}
function Check-Health {
    param([int]$Retries=40)
    for ($i=0; $i -lt $Retries; $i++) {
        Start-Sleep -Seconds 2
        try {
            $h = Invoke-RestMethod -Uri 'http://127.0.0.1:5180/api/v1/meta/health' -TimeoutSec 3
            if ($h.status -eq 'ok' -and $h.database -eq 'canvas_history') {
                $web = Invoke-WebRequest -Uri 'http://127.0.0.1:5180/' -UseBasicParsing -TimeoutSec 6
                if ($web.StatusCode -eq 200) { return $true }
            }
        } catch {}
    }
    return $false
}
function Compose-App([string[]]$Tail) {
    $composeArguments = @('compose', '-p', $composeProject, '--env-file', $cfgPath, '-f', $composeFile) + $Tail
    Run-Docker -Arguments $composeArguments
}
function Restore-Legacy {
    if (-not $oldWorkingDir -or -not (Test-Path -LiteralPath (Join-Path $oldWorkingDir 'api\canvas-history-api.jar'))) {
        Write-Warning 'No verified old JAR found. Restore the previous service manually.'
        return
    }
    $oldJar = Join-Path $oldWorkingDir 'api\canvas-history-api.jar'
    $env:DB_URL = "jdbc:postgresql://127.0.0.1:$($cfg['DB_HOST_PORT'])/canvas_history"
    $env:DB_USER = $cfg['POSTGRES_USER']
    $env:DB_PASSWORD = $cfg['POSTGRES_PASSWORD']
    $env:DB_WRITE_ALLOWED_DATABASES = 'canvas_history'
    Remove-Item Env:\SERVER_PORT, Env:\SERVER__PORT -ErrorAction SilentlyContinue
    foreach ($s in @('http_proxy','https_proxy','no_proxy','all_proxy')) {
        Remove-Item ("Env:\"+$s) -ErrorAction SilentlyContinue
    }
    $arguments = '-jar "{0}" --server.port=5180 --spring.web.resources.static-locations=file:./web/,classpath:/static/ --logging.file.name=rollback-runtime.log' -f $oldJar
    Start-Process -FilePath 'java' -ArgumentList $arguments -WorkingDirectory $oldWorkingDir -WindowStyle Hidden | Out-Null
    Write-Warning 'Attempted to restart the previous Windows JAR. Verify port 5180 and its health endpoint.'
}
try {
    Write-Host '[Canvas] Docker PROD publisher — preflight' -ForegroundColor Cyan
    if (-not $ReleasePackage) { $ReleasePackage = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
    $pkg = (Resolve-Path -LiteralPath $ReleasePackage).Path
    $manifestPath = Join-Path $pkg 'manifest.json'
    $jarPath = Join-Path $pkg 'api\canvas-history-api.jar'
    $cfgPath = Join-Path $ProdRoot 'config\.env'
    $composeFile = Join-Path $PSScriptRoot 'docker-compose.app.prod.yml'
    $dockerfile = Join-Path $PSScriptRoot 'Dockerfile.app'
    foreach ($p in @($manifestPath,$jarPath,$cfgPath,$composeFile,$dockerfile,(Join-Path $pkg 'SHA256SUMS.txt'))) {
        Require (Test-Path -LiteralPath $p) "Required file missing: $p"
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $version = [string]$manifest.releaseVersion
    Require ($version -match '^\d+\.\d+\.\d+$') 'Release version is invalid'
    $jarHash = (Get-FileHash -LiteralPath $jarPath -Algorithm SHA256).Hash.ToLower()
    Require ($jarHash -eq ([string]$manifest.artifacts.api.sha256).ToLower()) 'Release JAR hash mismatch'
    foreach ($line in (Get-Content -LiteralPath (Join-Path $pkg 'SHA256SUMS.txt') -Encoding UTF8)) {
        if (-not $line.Trim()) { continue }
        Require ($line -match '^([a-fA-F0-9]{64})  (.+)$') 'Malformed SHA256SUMS entry'
        $expected = $Matches[1].ToLower()
        $rel = $Matches[2].Replace('/', '\')
        $f = Join-Path $pkg $rel
        Require (Test-Path -LiteralPath $f) "Missing Release file: $rel"
        Require (((Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLower()) -eq $expected) "Release file hash mismatch: $rel"
    }
    $cfg = Read-Env $cfgPath
    Require ($cfg['POSTGRES_DB'] -eq 'canvas_history') 'PROD DB_NAME must be canvas_history'
    Require (-not [string]::IsNullOrWhiteSpace($cfg['POSTGRES_USER'])) 'Missing PROD DB user'
    Require (-not [string]::IsNullOrWhiteSpace($cfg['POSTGRES_PASSWORD'])) 'Missing PROD DB password'
    Require ($cfg['DB_HOST_PORT'] -eq '15432') 'Unexpected PROD DB host port (must be 15432 for this migration)'
    Require (([int]$manifest.database.targetFlywayVersion) -ge 1) 'Invalid target Flyway version'
    $dbHealth = (& docker inspect '--format={{.State.Health.Status}}' $dbContainer 2>$null | Out-String).Trim()
    Require ($LASTEXITCODE -eq 0 -and $dbHealth -eq 'healthy') 'PROD DB container not healthy'
    $mounts = (& docker inspect '--format={{range .Mounts}}{{println .Name}}{{end}}' $dbContainer | Out-String)
    Require ($mounts -match [regex]::Escape($dbVolume)) 'PROD DB volume differs from protected volume'
    $networkInfo = (& docker inspect '--format={{json .NetworkSettings.Networks}}' $dbContainer | Out-String)
    Require ($networkInfo.Contains($dbNetwork)) 'Expected PROD Docker network missing'
    $inspectEnv = & docker inspect '--format={{range .Config.Env}}{{println .}}{{end}}' $dbContainer
    $dbSeen = @($inspectEnv | Where-Object { $_ -like 'POSTGRES_DB=*' } | Select-Object -First 1)
    Require ($dbSeen.Count -eq 1 -and $dbSeen[0] -eq 'POSTGRES_DB=canvas_history') 'Docker database identity mismatch'
    $q = "SELECT current_database()||'|'||COALESCE((SELECT MAX(version::int) FROM flyway_schema_history),0);"
    $raw = (& docker exec $dbContainer psql -U $cfg['POSTGRES_USER'] -d 'canvas_history' -t -A -c $q 2>&1 | Out-String).Trim()
    Require ($LASTEXITCODE -eq 0 -and $raw -match '^canvas_history\|(\d+)$') 'Could not verify database Flyway version'
    $dbFlyway = [int]$Matches[1]
    $targetFlyway = [int]$manifest.database.targetFlywayVersion
    Require ($dbFlyway -eq $targetFlyway) "Flyway mismatch DB=V$dbFlyway Release=V$targetFlyway. Use the approved forward-migration/backup process first. No implicit migration."
    $imageTag = ('canvas-history-app:{0}-{1}' -f $version,$jarHash.Substring(0,12))
    $currentPath = Join-Path $ProdRoot 'current.json'
    $current = $null
    if (Test-Path -LiteralPath $currentPath) { $current = Get-Content -LiteralPath $currentPath -Raw -Encoding UTF8 | ConvertFrom-Json }
    $priorVersion = if ($current) { [string]$current.releaseVersion } else { '' }
    if ($current -and $current.deployPath -and (Test-Path -LiteralPath $current.deployPath)) {
        $oldWorkingDir = [string]$current.deployPath
    } elseif (Test-Path -LiteralPath (Join-Path $ProdRoot '1.0.0\api\canvas-history-api.jar')) {
        $oldWorkingDir = Join-Path $ProdRoot '1.0.0'
    }
    # The new Docker app does NOT exist on a first migration. Probe existence
    # with a successful, empty docker ps response instead of docker inspect stderr,
    # which is a terminating NativeCommandError in Windows PowerShell 5.1.
    $existingAppIds = @( & docker ps -a -q --filter "name=^/$appContainer$" )
    Require ($LASTEXITCODE -eq 0) 'Failed to inspect existing Docker apps'
    if ($existingAppIds.Count -gt 0) {
        $oldDocker = (& docker inspect '--format={{.State.Running}}|{{.Config.Image}}' $appContainer | Out-String).Trim()
        Require ($LASTEXITCODE -eq 0) 'Existing application container could not be inspected'
        if ($oldDocker -match '^true\|(.+)
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
    $legacyPid = 0
    if ($listeners.Count -gt 0) {
        foreach ($listener in $listeners) {
            $pidValue = [int]$listener.OwningProcess
            $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$pidValue"
            if ($proc -and $proc.Name -eq 'java.exe' -and
                $proc.CommandLine -like '*canvas-history-api.jar*' -and
                $proc.CommandLine -like '*CanvasofWorldHistory*') {
                $legacyPid = $pidValue
            } elseif (-not $priorImage -or -not $proc -or
                     $proc.Name -notin @('com.docker.backend.exe','wslrelay.exe','docker-proxy.exe')) {
                throw "Port $port is occupied by an unidentified process (PID $pidValue). Refuse to stop it."
            }
        }
    }
    Write-Host ("[PASS] Release {0}, Jar SHA {1}, DB canvas_history Flyway V{2}" -f $version,$jarHash.Substring(0,12),$dbFlyway)
    Write-Host ("[PASS] Existing PROD DB volume {0}, network {1}; they will NOT be recreated" -f $dbVolume,$dbNetwork)
    Write-Host ("[INFO] Previous runtime: {0}" -f $(if($priorImage){"Docker $priorImage"}elseif($legacyPid){"Windows Java PID $legacyPid"}else{'not running'}))
    if ($DryRun) { $Apply = $false }
    if (-not $Apply) {
        Write-Host '[DRY RUN] No Docker build, application cutover, or file changes. Pass -Apply to deploy.'
        exit 0
    }
    $answer = Read-Host "Build and switch PROD $version to Docker at 127.0.0.1:$port? Type Y to proceed"
    if ($answer -cne 'Y') { Write-Host '[CANCEL] No changes'; exit 0 }
    $targetDir = Join-Path $ProdRoot $version
    if (Test-Path -LiteralPath $targetDir) {
        $existingJar = Join-Path $targetDir 'api\canvas-history-api.jar'
        Require (Test-Path -LiteralPath $existingJar) 'Existing PROD version directory is incomplete'
        Require (((Get-FileHash -LiteralPath $existingJar -Algorithm SHA256).Hash.ToLower()) -eq $jarHash) 'Existing PROD version has a different JAR hash'
    } else {
        Copy-Item -LiteralPath $pkg -Destination $targetDir -Recurse
    }
    $configJsDir = Join-Path $ProdRoot 'config\web'
    New-Item -ItemType Directory -Path $configJsDir -Force | Out-Null
    $configJs = Join-Path $configJsDir 'config.js'
    $keyJson = ConvertTo-Json -InputObject ([string]$cfg['MAPTILER_API_KEY']) -Compress
    [System.IO.File]::WriteAllText($configJs, "window.__ENV__ = { MAPTILER_KEY: $keyJson };", (New-Object System.Text.UTF8Encoding($false)))
    $env:CANVAS_APP_IMAGE = $imageTag
    $env:CANVAS_CONFIG_JS_PATH = $configJs
    $buildDir = Join-Path $env:TEMP ('canvas-docker-build-'+[guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
    try {
        Copy-Item -LiteralPath $jarPath -Destination (Join-Path $buildDir 'canvas-history-api.jar')
        Copy-Item -LiteralPath $dockerfile -Destination (Join-Path $buildDir 'Dockerfile.app')
        Write-Host "[BUILD] $imageTag"
        Run-Docker -Arguments @('build','-f',(Join-Path $buildDir 'Dockerfile.app'),'-t',$imageTag,$buildDir)
    } finally {
        Remove-Item -LiteralPath $buildDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    # Recheck DB identity after the potentially long image build.
    $postBuildHealth = (& docker inspect '--format={{.State.Health.Status}}' $dbContainer | Out-String).Trim()
    Require ($postBuildHealth -eq 'healthy') 'DB became unhealthy before cutover'
    if ($legacyPid) {
        $answer2 = Read-Host "Stop ONLY verified Windows Java PID $legacyPid and hand over port $port to Docker? Type Y"
        if ($answer2 -cne 'Y') { Write-Host '[CANCEL] Docker image built; Windows PROD unchanged'; exit 0 }
        Stop-Process -Id $legacyPid -Force -ErrorAction Stop
        $oldJavaStopped = $true
        Start-Sleep -Seconds 3
    }
    $cutoverAttempted = $true
    Write-Host '[CUTOVER] Starting Docker app service only; DB container untouched.'
    Compose-App -Tail @('up','-d','--no-deps','--force-recreate','app')
    if (-not (Check-Health -Retries 45)) { throw 'Docker app failed health/stats/page smoke check' }
    $dbAfter = (& docker inspect '--format={{.State.Health.Status}}' $dbContainer | Out-String).Trim()
    Require ($dbAfter -eq 'healthy') 'DB unhealthy after cutover'
    $record = [ordered]@{
        releaseVersion = $version
        previousVersion = $priorVersion
        deployPath = $targetDir
        deployedAt = (Get-Date).ToString('o')
        gitTag = [string]$manifest.gitTag
        gitCommit = [string]$manifest.gitCommit
        database = @{ name='canvas_history'; flywayVersion=$dbFlyway }
        jarSha256 = $jarHash
        port = $port
        deployMode = 'docker-app-existing-prod-db'
        dockerImage = $imageTag
        dockerContainer = $appContainer
        status = 'success'
    }
    if (Test-Path -LiteralPath $currentPath) {
        Copy-Item -LiteralPath $currentPath -Destination ($currentPath+'.bak-'+(Get-Date -Format 'yyyyMMddHHmmss')) -ErrorAction Stop
    }
    $tmp = $currentPath+'.tmp'
    [System.IO.File]::WriteAllText($tmp,($record | ConvertTo-Json -Depth 8),(New-Object System.Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $tmp -Destination $currentPath -Force
    Write-Host "[PASS] Dockerized PROD is healthy: http://127.0.0.1:$port/" -ForegroundColor Green
    Write-Host "[PASS] Database container and data volume were not recreated." -ForegroundColor Green
    exit 0
} catch {
    Write-Host ("[FAIL] {0}" -f $_.Exception.Message) -ForegroundColor Red
    if ($cutoverAttempted) {
        Write-Warning 'Cutover failed. Attempting application-only rollback, never touching DB.'
        try {
            if ($priorImage) {
                $env:CANVAS_APP_IMAGE = $priorImage
                Compose-App -Tail @('up','-d','--no-deps','--force-recreate','app')
                if (-not (Check-Health -Retries 20)) { Write-Warning 'Previous Docker image did not pass health check' }
            } else {
                Compose-App -Tail @('stop','app')
                if ($oldJavaStopped) { Restore-Legacy }
            }
        } catch {
            Write-Warning ("Automatic rollback failed: {0}" -f $_.Exception.Message)
            if ($oldJavaStopped) { try { Restore-Legacy } catch {} }
        }
    }
    Write-Warning 'current.json has NOT been updated to successful Docker deployment.'
    exit 1
} finally {
    Remove-Item Env:\CANVAS_APP_IMAGE,Env:\CANVAS_CONFIG_JS_PATH -ErrorAction SilentlyContinue
}
) { $priorImage = $Matches[1] }
    }
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
    $legacyPid = 0
    if ($listeners.Count -gt 0) {
        foreach ($listener in $listeners) {
            $pidValue = [int]$listener.OwningProcess
            $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$pidValue"
            if ($proc -and $proc.Name -eq 'java.exe' -and
                $proc.CommandLine -like '*canvas-history-api.jar*' -and
                $proc.CommandLine -like '*CanvasofWorldHistory*') {
                $legacyPid = $pidValue
            } elseif (-not $priorImage -or -not $proc -or
                     $proc.Name -notin @('com.docker.backend.exe','wslrelay.exe','docker-proxy.exe')) {
                throw "Port $port is occupied by an unidentified process (PID $pidValue). Refuse to stop it."
            }
        }
    }
    Write-Host ("[PASS] Release {0}, Jar SHA {1}, DB canvas_history Flyway V{2}" -f $version,$jarHash.Substring(0,12),$dbFlyway)
    Write-Host ("[PASS] Existing PROD DB volume {0}, network {1}; they will NOT be recreated" -f $dbVolume,$dbNetwork)
    Write-Host ("[INFO] Previous runtime: {0}" -f $(if($priorImage){"Docker $priorImage"}elseif($legacyPid){"Windows Java PID $legacyPid"}else{'not running'}))
    if ($DryRun) { $Apply = $false }
    if (-not $Apply) {
        Write-Host '[DRY RUN] No Docker build, application cutover, or file changes. Pass -Apply to deploy.'
        exit 0
    }
    $answer = Read-Host "Build and switch PROD $version to Docker at 127.0.0.1:$port? Type Y to proceed"
    if ($answer -cne 'Y') { Write-Host '[CANCEL] No changes'; exit 0 }
    $targetDir = Join-Path $ProdRoot $version
    if (Test-Path -LiteralPath $targetDir) {
        $existingJar = Join-Path $targetDir 'api\canvas-history-api.jar'
        Require (Test-Path -LiteralPath $existingJar) 'Existing PROD version directory is incomplete'
        Require (((Get-FileHash -LiteralPath $existingJar -Algorithm SHA256).Hash.ToLower()) -eq $jarHash) 'Existing PROD version has a different JAR hash'
    } else {
        Copy-Item -LiteralPath $pkg -Destination $targetDir -Recurse
    }
    $configJsDir = Join-Path $ProdRoot 'config\web'
    New-Item -ItemType Directory -Path $configJsDir -Force | Out-Null
    $configJs = Join-Path $configJsDir 'config.js'
    $keyJson = ConvertTo-Json -InputObject ([string]$cfg['MAPTILER_API_KEY']) -Compress
    [System.IO.File]::WriteAllText($configJs, "window.__ENV__ = { MAPTILER_KEY: $keyJson };", (New-Object System.Text.UTF8Encoding($false)))
    $env:CANVAS_APP_IMAGE = $imageTag
    $env:CANVAS_CONFIG_JS_PATH = $configJs
    $buildDir = Join-Path $env:TEMP ('canvas-docker-build-'+[guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
    try {
        Copy-Item -LiteralPath $jarPath -Destination (Join-Path $buildDir 'canvas-history-api.jar')
        Copy-Item -LiteralPath $dockerfile -Destination (Join-Path $buildDir 'Dockerfile.app')
        Write-Host "[BUILD] $imageTag"
        Run-Docker -Arguments @('build','-f',(Join-Path $buildDir 'Dockerfile.app'),'-t',$imageTag,$buildDir)
    } finally {
        Remove-Item -LiteralPath $buildDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    # Recheck DB identity after the potentially long image build.
    $postBuildHealth = (& docker inspect '--format={{.State.Health.Status}}' $dbContainer | Out-String).Trim()
    Require ($postBuildHealth -eq 'healthy') 'DB became unhealthy before cutover'
    if ($legacyPid) {
        $answer2 = Read-Host "Stop ONLY verified Windows Java PID $legacyPid and hand over port $port to Docker? Type Y"
        if ($answer2 -cne 'Y') { Write-Host '[CANCEL] Docker image built; Windows PROD unchanged'; exit 0 }
        Stop-Process -Id $legacyPid -Force -ErrorAction Stop
        $oldJavaStopped = $true
        Start-Sleep -Seconds 3
    }
    $cutoverAttempted = $true
    Write-Host '[CUTOVER] Starting Docker app service only; DB container untouched.'
    Compose-App -Tail @('up','-d','--no-deps','--force-recreate','app')
    if (-not (Check-Health -Retries 45)) { throw 'Docker app failed health/stats/page smoke check' }
    $dbAfter = (& docker inspect '--format={{.State.Health.Status}}' $dbContainer | Out-String).Trim()
    Require ($dbAfter -eq 'healthy') 'DB unhealthy after cutover'
    $record = [ordered]@{
        releaseVersion = $version
        previousVersion = $priorVersion
        deployPath = $targetDir
        deployedAt = (Get-Date).ToString('o')
        gitTag = [string]$manifest.gitTag
        gitCommit = [string]$manifest.gitCommit
        database = @{ name='canvas_history'; flywayVersion=$dbFlyway }
        jarSha256 = $jarHash
        port = $port
        deployMode = 'docker-app-existing-prod-db'
        dockerImage = $imageTag
        dockerContainer = $appContainer
        status = 'success'
    }
    if (Test-Path -LiteralPath $currentPath) {
        Copy-Item -LiteralPath $currentPath -Destination ($currentPath+'.bak-'+(Get-Date -Format 'yyyyMMddHHmmss')) -ErrorAction Stop
    }
    $tmp = $currentPath+'.tmp'
    [System.IO.File]::WriteAllText($tmp,($record | ConvertTo-Json -Depth 8),(New-Object System.Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $tmp -Destination $currentPath -Force
    Write-Host "[PASS] Dockerized PROD is healthy: http://127.0.0.1:$port/" -ForegroundColor Green
    Write-Host "[PASS] Database container and data volume were not recreated." -ForegroundColor Green
    exit 0
} catch {
    Write-Host ("[FAIL] {0}" -f $_.Exception.Message) -ForegroundColor Red
    if ($cutoverAttempted) {
        Write-Warning 'Cutover failed. Attempting application-only rollback, never touching DB.'
        try {
            if ($priorImage) {
                $env:CANVAS_APP_IMAGE = $priorImage
                Compose-App -Tail @('up','-d','--no-deps','--force-recreate','app')
                if (-not (Check-Health -Retries 20)) { Write-Warning 'Previous Docker image did not pass health check' }
            } else {
                Compose-App -Tail @('stop','app')
                if ($oldJavaStopped) { Restore-Legacy }
            }
        } catch {
            Write-Warning ("Automatic rollback failed: {0}" -f $_.Exception.Message)
            if ($oldJavaStopped) { try { Restore-Legacy } catch {} }
        }
    }
    Write-Warning 'current.json has NOT been updated to successful Docker deployment.'
    exit 1
} finally {
    Remove-Item Env:\CANVAS_APP_IMAGE,Env:\CANVAS_CONFIG_JS_PATH -ErrorAction SilentlyContinue
}
