#Requires -Version 5.1
<#
.SYNOPSIS
    Canvas of World History —— 生产环境状态查看（只读）

.DESCRIPTION
    对标 myLedger 的 runtime/status.bat：只报告，不修改。
    不启停服务、不写文件、不对数据库执行任何写操作。

    显示内容：
      · current.json 记录的部署版本
      · 数据库容器健康状态与库内 Flyway 版本
      · 应用端口监听与进程
      · HTTP 健康检查结果
      · 已部署的历史版本目录

.PARAMETER ProdRoot
    生产根目录。

.PARAMETER Port
    应用监听端口。不指定时使用 current.json 记录的实际部署端口（缺省 5180）。

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File deploy\prod-status.ps1
#>
[CmdletBinding()]
param(
    [string]$ProdRoot = 'E:\01_Work\04_Prod\01_Personal\CanvasofWorldHistory',
    [string]$DbContainer = 'canvas-history-db',
    [string]$DbName = 'canvas_history',
    # 0 表示「未指定」：此时优先使用 current.json 记录的实际部署端口
    [int]$Port = 0
)

$ErrorActionPreference = 'Continue'
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch { }
$ProgressPreference = 'SilentlyContinue'

function Say([string]$Text, [string]$Color = 'Gray') { Write-Host "  $Text" -ForegroundColor $Color }
function Head([string]$Text) {
    Write-Host ''
    Write-Host "[$Text]" -ForegroundColor Yellow
}

Write-Host ''
Write-Host ('=' * 64) -ForegroundColor DarkCyan
Write-Host '  生产环境状态（只读）' -ForegroundColor Cyan
Write-Host ('=' * 64) -ForegroundColor DarkCyan

if (-not (Test-Path -LiteralPath $ProdRoot)) {
    Say "生产目录不存在：$ProdRoot" 'Red'
    Say '说明：尚未执行过任何正式部署。' 'Yellow'
    exit 1
}

# ------------------------------------------------------------------ 版本记录
Head '1/5 版本记录'
$recordPath = Join-Path $ProdRoot 'current.json'
# 端口优先级：用户显式指定 > current.json 记录 > 5180
$recordPort = 0
if (Test-Path -LiteralPath $recordPath) {
    try {
        $j = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($j.port -and [int]$j.port -gt 0) { $recordPort = [int]$j.port }
        Say "状态        : $($j.status)"
        Say "部署版本    : $(if ($j.releaseVersion) { $j.releaseVersion } else { '（无）' })"
        Say "上一个版本  : $(if ($j.previousVersion) { $j.previousVersion } else { '（无）' })"
        Say "部署时间    : $($j.deployedAt)"
        Say "Git Tag     : $($j.gitTag)"
        $commit = [string]$j.gitCommit
        if ($commit.Length -gt 7) { $commit = $commit.Substring(0, 7) }
        Say "Git Commit  : $commit"
        Say "安装目录    : $($j.deployPath)"
        Say "数据库      : $($j.database.name) / Flyway V$($j.database.flywayVersion)"
        Say "端口        : $($j.port)"
    }
    catch {
        Say "无法解析 $recordPath" 'Red'
    }
}
else {
    Say '没有 current.json：该生产目录尚未登记正式版本。' 'Yellow'
}

# ------------------------------------------------------------------ 历史版本
Head '2/5 已部署版本'
$versions = @(Get-ChildItem -LiteralPath $ProdRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^\d+\.\d+\.\d+$' } | ForEach-Object { $_.Name } | Sort-Object)
if ($versions.Count -eq 0) { Say '（无）' }
else { Say (($versions -join ', ')) }

# ------------------------------------------------------------------ 数据库
Head '3/5 数据库'
$inspect = & docker inspect $DbContainer --format '{{.State.Health.Status}}' 2>&1
if ($LASTEXITCODE -ne 0) {
    Say "容器 $DbContainer 不存在或不可查询" 'Red'
}
else {
    $health = ("$inspect").Trim()
    Say "容器 $DbContainer : $health" $(if ($health -eq 'healthy') { 'Green' } else { 'Red' })
    $q = "SELECT current_database()||'|'||(SELECT max(version::int) FROM flyway_schema_history)||'|'||(SELECT count(*) FROM historical_place);"
    $row = & docker exec $DbContainer psql -U canvas_app -d $DbName -t -A -c $q 2>&1
    if ($LASTEXITCODE -eq 0) {
        $parts = ("$row").Trim() -split '\|'
        Say "数据库      : $($parts[0])"
        Say "Flyway      : V$($parts[1])"
        Say "地点记录    : $($parts[2])"
    }
    else {
        Say '无法查询数据库版本' 'Yellow'
    }
}

# ------------------------------------------------------------------ 编排
Head '4/5 PROD 编排（唯一 Compose 入口）'
$composeFile = Join-Path (Split-Path -Parent $ProdRoot) 'canvas-history\compose.yaml'
$prodCfgPath = Join-Path $ProdRoot 'config\.env'
if (Test-Path -LiteralPath $composeFile) {
    $composeSha = (Get-FileHash -LiteralPath $composeFile -Algorithm SHA256).Hash.Substring(0, 16)
    Say "Compose 文件: $composeFile" 'Green'
    Say "SHA256(16)  : $composeSha"
    if (Test-Path -LiteralPath $prodCfgPath) {
        $svc = & docker compose -p canvas-history --env-file $prodCfgPath -f $composeFile config --services 2>&1
        if ($LASTEXITCODE -eq 0) {
            Say "服务        : $((@($svc) -join ', '))" 'Green'
        }
        else {
            Say '服务        : 无法解析（环境文件或 CANVAS_APP_IMAGE 缺失）' 'Red'
        }
    }
    else {
        Say "缺少环境文件: $prodCfgPath" 'Red'
    }
}
else {
    Say "未安装统一 Compose: $composeFile" 'Yellow'
}
foreach ($c in @($DbContainer, 'canvas-history-prod-app')) {
    $applied = $false
    $proj = ''
    $cf = ''
    $rawLabels = (& docker inspect '--format={{json .Config.Labels}}' $c 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $rawLabels) {
        try {
            $labels = $rawLabels | ConvertFrom-Json
            $proj = [string]$labels.'com.docker.compose.project'
            $cf = [string]$labels.'com.docker.compose.project.config_files'
            $applied = $true
        }
        catch { $applied = $false }
    }
    if ($applied -and $proj) {
        $aligned = ($cf -eq $composeFile)
        Say ("{0,-22}: project={1} config={2}" -f $c, $proj, $(if ($cf) { $cf } else { '(none)' })) $(if ($aligned) { 'Green' } else { 'Yellow' })
        if (-not $aligned) {
            Say ("{0,-22}  未与本文件对齐（容器仍由旧定义创建，重建后才会对齐）" -f '') 'Yellow'
        }
    }
    else {
        Say ("{0,-22}: 容器不存在或无法查询" -f $c) 'Yellow'
    }
}

# ------------------------------------------------------------------ 应用
Head 'Docker PROD app container'
$app = & docker inspect canvas-history-prod-app --format '{{.State.Status}}|{{.State.Health.Status}}|{{.Config.Image}}' 2>$null
if ($LASTEXITCODE -eq 0 -and $app) {
    Say "Docker APP   : $app" 'Green'
} else {
    Say 'Docker APP   : not installed (legacy Windows JAR may be running)' 'Yellow'
}

Head '5/5 应用进程'
$userSpecified = $PSBoundParameters.ContainsKey('Port') -and $Port -gt 0
$effectivePort = if ($userSpecified) { $Port } elseif ($recordPort -gt 0) { $recordPort } else { 5180 }
if ($userSpecified) {
    Say "检查端口    : $effectivePort（命令行指定）"
}
elseif ($recordPort -gt 0) {
    Say "检查端口    : $effectivePort（取自 current.json）"
}
else {
    Say "检查端口    : $effectivePort（无版本记录，使用默认值）"
}

$conn = Get-NetTCPConnection -LocalPort $effectivePort -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    $procId = $conn.OwningProcess
    $procName = ''
    try { $procName = (Get-Process -Id $procId -ErrorAction SilentlyContinue).ProcessName } catch { }
    Say "端口 $effectivePort : 监听中 PID=$procId ($procName)" 'Green'
}
else {
    Say "端口 $effectivePort : 未监听" 'Red'
}

try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$effectivePort/api/v1/meta/health" -UseBasicParsing -TimeoutSec 5
    $body = $resp.Content | ConvertFrom-Json
    Say "健康检查    : HTTP $($resp.StatusCode) status=$($body.status) db=$($body.database)" 'Green'
}
catch {
    Say '健康检查    : 无响应' 'Red'
}

Write-Host ''
Say '以上均为只读检查，未修改任何文件或服务。' 'DarkGray'
exit 0
