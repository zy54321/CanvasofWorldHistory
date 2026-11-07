#Requires -Version 5.1
<#
.SYNOPSIS
    Canvas of World History —— 发布到生产（BAT 03 的实际逻辑）

.DESCRIPTION
    在 Release 包内运行。流程：
      识别版本 → 校验包完整性 → 识别生产环境 → Y/N 确认
      → （必要时）Flyway 正向迁移 → 临时端口验证 → 切换正式版本 → 健康与冒烟 → 更新 current.json

    硬性约束：
      - 只连 canvas_history，库名不符立即停止；
      - 只执行 Flyway 正向迁移，不做 clean、不重建数据库、不自动回滚数据库；
      - 历史版本目录不覆盖；
      - 部署失败不写入成功的 current.json；
      - 不修改包内冻结的构建产物。

.PARAMETER ProdRoot
    生产部署根目录。

.PARAMETER Port
    正式运行端口（单 Jar 同时提供页面与 API）。

.PARAMETER DbName
    期望的数据库名。默认 canvas_history，仅测试时可覆盖。

.PARAMETER DbContainer
    数据库容器名。

.PARAMETER VerifyPort
    切换前用于验证新版本的临时端口。

.PARAMETER DryRun
    只做识别与校验，不部署、不迁移、不改 current.json。

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File deploy\publish-prod.ps1
#>
[CmdletBinding()]
param(
    [string]$ProdRoot = 'E:\01_Work\04_Prod\01_Personal\CanvasofWorldHistory',
    [int]$Port = 5180,
    [string]$DbName = 'canvas_history',
    [string]$DbContainer = 'canvas-history-db',
    [int]$VerifyPort = 5199,
    [switch]$DryRun,
    [switch]$SkipBackup
)

$ErrorActionPreference = 'Stop'
# 关掉 Invoke-WebRequest 的进度条：在管道/非交互环境下会产生大量噪音输出
$ProgressPreference = 'SilentlyContinue'
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch { }

# 说明：本机环境里同时存在 HTTPS_PROXY 与 https_proxy 时，PowerShell 5.1 的
# Start-Process 在构造子进程环境块时会抛
#   "Item has already been added. Key in dictionary: 'HTTPS_PROXY'"
# 导致根本无法启动 java。这里在启动任何子进程前，删掉仅大小写不同的重复代理变量。
# 只作用于当前 PowerShell 进程，不影响系统环境，关闭窗口即恢复。
foreach ($proxyVar in @('http_proxy', 'https_proxy', 'no_proxy', 'all_proxy')) {
    if (Test-Path "Env:\$proxyVar") {
        Remove-Item -Path "Env:\$proxyVar" -ErrorAction SilentlyContinue
    }
}

# ------------------------------------------------------------------ 输出
function Write-Title([string]$Text) {
    Write-Host ''
    Write-Host ('=' * 70) -ForegroundColor DarkCyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ('=' * 70) -ForegroundColor DarkCyan
}
function Write-Section([string]$Text) {
    Write-Host ''
    Write-Host "[$Text]" -ForegroundColor Yellow
}
function Write-Ok([string]$Text)   { Write-Host "  [OK] $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "  [!]  $Text" -ForegroundColor Yellow }
function Write-Bad([string]$Text)  { Write-Host "  [X]  $Text" -ForegroundColor Red }
function Write-Info([string]$Text) { Write-Host "       $Text" -ForegroundColor Gray }
function Write-Step([string]$Text) { Write-Host "  -> $Text" -ForegroundColor DarkGray }

function Format-Native {
    param($Item)
    if ($Item -is [System.Management.Automation.ErrorRecord]) { return $Item.Exception.Message }
    return "$Item"
}

function Invoke-NativeText {
    param([string]$Exe, [string[]]$Arguments = @())
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $raw = & $Exe @Arguments 2>&1
        $code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $prev }
    $lines = @($raw | ForEach-Object { Format-Native $_ })
    return [pscustomobject]@{ Output = $lines; Text = (($lines) -join "`n").Trim(); Code = $code }
}

function Ask-YesNo {
    param([string]$Question)
    while ($true) {
        Write-Host ''
        Write-Host "  $Question (Y/N) " -ForegroundColor White -NoNewline
        $answer = ("$(Read-Host)").Trim()
        if ($answer -eq '') { return $false }
        if ($answer -match '^[Yy]$') { return $true }
        if ($answer -match '^[Nn]$') { return $false }
        Write-Host '  输入无效，请重新输入 Y 或 N（直接回车 = N）。' -ForegroundColor Yellow
    }
}

# 启动一个后台 java 实例。日志由 Spring 自己写文件（--logging.file.name），
# 同时把控制台输出重定向到文件，便于启动失败时排查。
function Start-AppProcess {
    param(
        [Parameter(Mandatory = $true)][string]$JarPath,
        [Parameter(Mandatory = $true)][int]$AppPort,
        [Parameter(Mandatory = $true)][string]$WorkDir,
        [hashtable]$EnvVars = @{},
        [Parameter(Mandatory = $true)][string]$LogFileName
    )
    # 环境变量通过当前进程传递：Start-Process 会继承 $env: 里的内容
    foreach ($k in @($EnvVars.Keys)) {
        $raw = $EnvVars[$k]
        $val = ''
        if ($null -ne $raw) { $val = [string]$raw }
        Set-Item -Path "Env:\$k" -Value $val
    }
    Remove-Item Env:\SERVER__PORT -ErrorAction SilentlyContinue
    Remove-Item Env:\SERVER_PORT -ErrorAction SilentlyContinue

    $argLine = ('-jar "{0}" --server.port={1} --spring.web.resources.static-locations=file:./web/,classpath:/static/ --logging.file.name="{2}"' -f $JarPath, $AppPort, $LogFileName)
    $outFile = Join-Path $WorkDir ("console-{0}.log" -f $AppPort)

    return Start-Process -FilePath 'java' -ArgumentList $argLine -WorkingDirectory $WorkDir `
        -RedirectStandardOutput $outFile -RedirectStandardError "$outFile.err" `
        -PassThru -WindowStyle Hidden
}

# ------------------------------------------------------------------ 配置读写
function Read-DotEnv {
    param([string]$Path)
    $map = @{}
    if (-not (Test-Path -LiteralPath $Path)) { return $map }
    foreach ($line in (Get-Content -LiteralPath $Path -Encoding UTF8)) {
        $t = "$line".Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        $i = $t.IndexOf('=')
        if ($i -gt 0) {
            $map[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim()
        }
    }
    return $map
}

function Write-JsonNoBom {
    param([string]$Path, $Object)
    $json = $Object | ConvertTo-Json -Depth 8
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    # 原子写：先写同目录临时文件，再用 rename 覆盖。
    # 写入中途失败时，目标文件仍是完整的旧内容，不会出现半截 JSON。
    $tmp = "$Path.tmp"
    [System.IO.File]::WriteAllText($tmp, $json, (New-Object System.Text.UTF8Encoding($false)))
    try {
        Move-Item -LiteralPath $tmp -Destination $Path -Force
    }
    catch {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        throw
    }
}

# ================================================================== 主流程
$exitOk = 0
$exitFail = 1

try {
    # ---------------------------------------------------------- 0. 定位
    $scriptDir = $PSScriptRoot
    if ([string]::IsNullOrWhiteSpace($scriptDir)) {
        $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    $pkgRoot = Split-Path -Parent $scriptDir        # <包>/deploy → <包>
    $manifestPath = Join-Path $pkgRoot 'manifest.json'

    Write-Title '发布到生产'

    if (-not (Test-Path -LiteralPath $manifestPath)) {
        Write-Bad "这不是一个 Release 包：缺少 manifest.json（$pkgRoot）"
        exit $exitFail
    }
    if ($DryRun) { Write-Warn '只读模式（-DryRun）：不部署、不迁移、不写 current.json' }
    if ($DbName -ne 'canvas_history') {
        Write-Warn "注意：目标库被覆盖为 '$DbName'（非默认生产库），仅应出现在测试场景。"
    }

    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $targetVersion = [string]$manifest.releaseVersion
    $targetFlyway = [int]$manifest.database.targetFlywayVersion
    $jarExpectedSha = [string]$manifest.artifacts.api.sha256

    Write-Info "包路径：$pkgRoot"
    Write-Info "包内版本：$targetVersion（Flyway V$targetFlyway）"
    Write-Info "生产根：$ProdRoot"
    Write-Info "目标库：$DbName @ 容器 $DbContainer"

    # ---------------------------------------------------------- 1. 校验包
    Write-Section '1/6 校验 Release 包'

    # 1a 版本目录名与 manifest 一致
    $pkgDirName = Split-Path -Leaf $pkgRoot
    if ($pkgDirName -match '^\d+\.\d+\.\d+$' -and $pkgDirName -ne $targetVersion) {
        Write-Bad "目录名（$pkgDirName）与 manifest 版本（$targetVersion）不一致"
        exit $exitFail
    }
    Write-Ok "版本一致：$targetVersion"

    # 1b 必需文件
    $required = @(
        'manifest.json', 'SHA256SUMS.txt',
        'api/canvas-history-api.jar',
        'deploy/publish-prod.ps1', 'deploy/start-api.bat', 'deploy/flyway.sh',
        'db/migration', 'config/.env.example'
    )
    $missing = @()
    foreach ($r in $required) {
        $p = Join-Path $pkgRoot ($r -replace '/', '\')
        if (-not (Test-Path -LiteralPath $p)) { $missing += $r }
    }
    if ($missing.Count -gt 0) {
        Write-Bad '包内缺少必需文件：'
        $missing | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        exit $exitFail
    }
    Write-Ok '必需文件齐全'

    # 1c SHA256SUMS 全量校验
    $sumsPath = Join-Path $pkgRoot 'SHA256SUMS.txt'
    $sumLines = @(Get-Content -LiteralPath $sumsPath -Encoding UTF8 | Where-Object { "$_".Trim() -ne '' })
    if ($sumLines.Count -eq 0) { Write-Bad 'SHA256SUMS.txt 为空'; exit $exitFail }

    $bad = @()
    foreach ($line in $sumLines) {
        $t = "$line".TrimEnd()
        $i = $t.IndexOf('  ')
        if ($i -lt 1) { continue }
        $expect = $t.Substring(0, $i).Trim().ToLower()
        $rel = $t.Substring($i + 2).Trim().Replace('/', '\')
        $full = Join-Path $pkgRoot $rel
        if (-not (Test-Path -LiteralPath $full)) { $bad += "$rel（缺失）"; continue }
        $actual = (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLower()
        if ($actual -ne $expect) { $bad += "$rel（校验和不符）" }
    }
    if ($bad.Count -gt 0) {
        Write-Bad '包完整性校验失败：'
        $bad | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        Write-Host '  包可能被修改或复制损坏，拒绝部署。' -ForegroundColor Yellow
        exit $exitFail
    }
    Write-Ok ("SHA256SUMS 校验通过：{0} 个文件" -f $sumLines.Count)

    # 1d jar 与 manifest 记录一致
    $jarPath = Join-Path $pkgRoot 'api\canvas-history-api.jar'
    $jarActual = (Get-FileHash -LiteralPath $jarPath -Algorithm SHA256).Hash.ToLower()
    if ($jarActual -ne $jarExpectedSha.ToLower()) {
        Write-Bad 'jar 与 manifest 记录的 SHA256 不一致'
        Write-Info "manifest: $jarExpectedSha"
        Write-Info "实际    : $jarActual"
        exit $exitFail
    }
    Write-Ok 'jar 与 manifest 一致'

    # 1e 迁移文件与 manifest 一致
    $migDir = Join-Path $pkgRoot 'db\migration'
    $migFiles = @(Get-ChildItem -LiteralPath $migDir -Filter 'V*.sql' -File)
    $migMax = 0
    foreach ($m in $migFiles) {
        if ($m.Name -match '^V(\d+)__') {
            $n = [int]$Matches[1]
            if ($n -gt $migMax) { $migMax = $n }
        }
    }
    if ($migMax -ne $targetFlyway) {
        Write-Bad "迁移文件最高版本 V$migMax 与 manifest 记录的 V$targetFlyway 不一致"
        exit $exitFail
    }
    Write-Ok ("迁移文件完整：{0} 个，最高 V{1}" -f $migFiles.Count, $migMax)

    # 1f 包内不含敏感文件
    $leak = @()
    foreach ($f in (Get-ChildItem -LiteralPath $pkgRoot -Recurse -File)) {
        $rel = $f.FullName.Substring($pkgRoot.Length + 1).Replace('\', '/')
        if ($rel -eq 'config/.env.example') { continue }
        if ($rel -match '(^|/)\.env$|\.(pem|key|p12|pfx|jks)$|\.(dump|backup)$') { $leak += $rel }
    }
    if ($leak.Count -gt 0) {
        Write-Bad '包内出现敏感文件：'
        $leak | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        exit $exitFail
    }
    Write-Ok '包内无敏感文件'

    # 1g 目标版本目录冲突：尽早失败，不必等到连数据库之后
    $earlyTarget = Join-Path $ProdRoot $targetVersion
    if (Test-Path -LiteralPath $earlyTarget) {
        Write-Bad "目标版本目录已存在，拒绝覆盖：$earlyTarget"
        Write-Host '  历史版本不可覆盖。若确需重发，请使用更高版本号。' -ForegroundColor Yellow
        exit $exitFail
    }
    Write-Ok "目标目录可用：$earlyTarget"

    # ---------------------------------------------------------- 2. 当前生产状态
    Write-Section '2/6 识别当前生产环境'

    $currentPath = Join-Path $ProdRoot 'current.json'
    $current = $null
    $currentVersion = $null
    $prodState = 'legacy_unversioned'

    if (Test-Path -LiteralPath $currentPath) {
        try {
            $current = Get-Content -LiteralPath $currentPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($current.releaseVersion) {
                $currentVersion = [string]$current.releaseVersion
                $prodState = 'versioned'
            }
        } catch {
            Write-Bad "current.json 无法解析：$currentPath"
            exit $exitFail
        }
    }

    if ($prodState -eq 'versioned') {
        Write-Info "当前 Prod 版本：$currentVersion"
        Write-Info "上次部署时间：$($current.deployedAt)"
        Write-Info "上次部署路径：$($current.deployPath)"
    } else {
        Write-Warn '生产环境尚无版本登记（legacy-unversioned）'
        Write-Info '本工具不会伪造历史版本号，只在部署成功后登记本次版本。'
    }

    # 容器与数据库
    $dockerCheck = Invoke-NativeText -Exe 'docker' -Arguments @('inspect', $DbContainer, '--format', '{{.State.Health.Status}}')
    if ($dockerCheck.Code -ne 0) {
        Write-Bad "数据库容器不存在或不可访问：$DbContainer"
        exit $exitFail
    }
    $health = $dockerCheck.Text.Trim()
    if ($health -ne 'healthy') {
        Write-Bad "数据库容器状态为 '$health'，未就绪"
        exit $exitFail
    }
    Write-Ok "数据库容器健康：$DbContainer"

    # 生产配置
    # 关键：在用户确认部署之前，绝不往生产目录写任何东西。
    # 这里只把配置解析到内存（来自既有文件，或从容器环境读取），确认后才落盘。
    $configDir = Join-Path $ProdRoot 'config'
    $configPath = Join-Path $configDir '.env'
    $configExists = Test-Path -LiteralPath $configPath
    $cfgNeedsCreate = $false
    $cfg = @{}

    if ($configExists) {
        $cfg = Read-DotEnv -Path $configPath
        Write-Ok "生产配置存在：$configPath"
    } else {
        Write-Warn '生产配置尚不存在：将在确认部署后才创建（取消不会留下任何文件）'
        $insp = Invoke-NativeText -Exe 'docker' -Arguments @('inspect', $DbContainer, '--format', '{{range .Config.Env}}{{println .}}{{end}}')
        $dbNameSeen = ''
        $dbUserSeen = ''
        $dbPassSeen = ''
        $portSeen = '15432'
        foreach ($ln in $insp.Output) {
            if ("$ln" -match '^POSTGRES_DB=(.*)$') { $dbNameSeen = $Matches[1] }
            elseif ("$ln" -match '^POSTGRES_USER=(.*)$') { $dbUserSeen = $Matches[1] }
            elseif ("$ln" -match '^POSTGRES_PASSWORD=(.*)$') { $dbPassSeen = $Matches[1] }
        }
        if ($dbNameSeen -ne $DbName) {
            Write-Bad "容器内 POSTGRES_DB='$dbNameSeen' 与预期 '$DbName' 不符，拒绝继续"
            exit $exitFail
        }
        $ports = Invoke-NativeText -Exe 'docker' -Arguments @('port', $DbContainer, '5432/tcp')
        if ($ports.Code -eq 0 -and $ports.Text -match '127\.0\.0\.1:(\d+)') { $portSeen = $Matches[1] }

        $cfg['POSTGRES_DB'] = $dbNameSeen
        $cfg['POSTGRES_USER'] = $dbUserSeen
        $cfg['POSTGRES_PASSWORD'] = $dbPassSeen
        $cfg['DB_HOST_PORT'] = $portSeen
        $cfg['TZ'] = 'Asia/Shanghai'
        $cfg['API_PORT'] = "$Port"
        $cfg['DB_WRITE_ALLOWED_DATABASES'] = $dbNameSeen
        $cfg['MAPTILER_API_KEY'] = ''
        $cfgNeedsCreate = $true
        Write-Info '（数据库身份已从容器读取，尚未写入任何文件）'
    }

    $cfgDb = if ($cfg.ContainsKey('POSTGRES_DB')) { $cfg['POSTGRES_DB'] } else { '' }
    $cfgUser = if ($cfg.ContainsKey('POSTGRES_USER')) { $cfg['POSTGRES_USER'] } else { '' }

    if ($cfgDb -ne $DbName) {
        Write-Bad "配置文件中的 POSTGRES_DB='$cfgDb' 与目标 '$DbName' 不一致，拒绝继续"
        exit $exitFail
    }

    # 数据库身份与版本
    $dbVer = Invoke-NativeText -Exe 'docker' -Arguments @(
        'exec', $DbContainer, 'psql', '-U', $cfgUser, '-d', $DbName, '-t', '-A', '-c',
        "SELECT current_database()||'|'||(SELECT COALESCE(max(version::int),0) FROM flyway_schema_history);"
    )
    if ($dbVer.Code -ne 0) {
        Write-Bad '无法连接生产数据库：'
        $dbVer.Output | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        exit $exitFail
    }
    $parts = $dbVer.Text.Trim() -split '\|'
    if ($parts.Count -ne 2) {
        Write-Bad "数据库查询返回异常：$($dbVer.Text)"
        exit $exitFail
    }
    $seenDb = $parts[0].Trim()
    $dbFlyway = [int]$parts[1].Trim()

    if ($seenDb -ne $DbName) {
        Write-Bad "实际连接的数据库是 '$seenDb'，与目标 '$DbName' 不符，立即停止"
        exit $exitFail
    }
    Write-Ok "数据库身份确认：$seenDb，Flyway V$dbFlyway"

    # 目标端口占用
    $portOwner = $null
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        $portOwner = [pscustomobject]@{ Pid = $conn.OwningProcess; Name = if ($proc) { $proc.ProcessName } else { '?' } }
        Write-Warn "目标端口 $Port 已被占用：PID=$($portOwner.Pid) $($portOwner.Name)"
    } else {
        Write-Info "目标端口 $Port 空闲"
    }

    # ---------------------------------------------------------- 3. 变更摘要
    Write-Section '3/6 变更摘要'

    $needMigrate = $dbFlyway -lt $targetFlyway
    $dbAhead = $dbFlyway -gt $targetFlyway

    Write-Info "当前 Prod 版本：$(if($currentVersion){$currentVersion}else{'未登记（legacy）'})"
    Write-Info "目标版本：$targetVersion"
    Write-Info "数据库：V$dbFlyway → V$targetFlyway"

    if ($dbAhead) {
        Write-Bad "数据库版本（V$dbFlyway）高于本包要求（V$targetFlyway），拒绝部署。"
        Write-Host '  降级数据库不在本工具的能力范围内。' -ForegroundColor Yellow
        exit $exitFail
    }
    if ($needMigrate) {
        Write-Warn "需要执行 Flyway 迁移：V$dbFlyway → V$targetFlyway"
    } else {
        Write-Ok '数据库版本一致，无需迁移'
    }

    $existingTarget = Join-Path $ProdRoot $targetVersion
    if (Test-Path -LiteralPath $existingTarget) {
        Write-Bad "目标版本目录已存在，拒绝覆盖：$existingTarget"
        exit $exitFail
    }

    if ($DryRun) {
        Write-Host ''
        Write-Ok '只读模式：识别与校验全部通过，未做任何部署动作。'
        exit $exitOk
    }

    # ---------------------------------------------------------- 4. 确认
    Write-Section '4/6 确认'

    if (-not (Ask-YesNo "是否部署 $targetVersion 到生产（端口 $Port）？")) {
        Write-Host ''
        Write-Host '  已取消，生产环境未做任何改动。' -ForegroundColor Gray
        if ($cfgNeedsCreate) {
            Write-Host '  （生产配置未创建，取消后目录保持原样）' -ForegroundColor DarkGray
        }
        exit $exitOk
    }

    # 用户已确认，此时才把首次生成的生产配置落盘
    if ($cfgNeedsCreate) {
        New-Item -ItemType Directory -Path $configDir -Force | Out-Null
        $cfgLines = @(
            '# 生产运行配置（由 03_发布Prod.bat 首次生成，凭据来自既有容器）',
            '# 本文件不可提交到 Git，也不可回传到开发仓库。',
            "POSTGRES_DB=$($cfg['POSTGRES_DB'])",
            "POSTGRES_USER=$($cfg['POSTGRES_USER'])",
            "POSTGRES_PASSWORD=$($cfg['POSTGRES_PASSWORD'])",
            "DB_HOST_PORT=$($cfg['DB_HOST_PORT'])",
            "TZ=$($cfg['TZ'])",
            "API_PORT=$($cfg['API_PORT'])",
            "DB_WRITE_ALLOWED_DATABASES=$($cfg['DB_WRITE_ALLOWED_DATABASES'])",
            "MAPTILER_API_KEY=$($cfg['MAPTILER_API_KEY'])"
        )
        [System.IO.File]::WriteAllText($configPath, (($cfgLines -join "`n") + "`n"), (New-Object System.Text.UTF8Encoding($false)))
        Write-Ok "已创建生产配置：$configPath"
    }

    # ---------------------------------------------------------- 5. 数据库迁移
    if ($needMigrate) {
        Write-Section '5/6 数据库迁移'

        if (-not $SkipBackup) {
            Write-Step '迁移前一次性数据保护（pg_dump，非正式备份体系）'
            $backupDir = Join-Path $ProdRoot 'backups'
            New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
            $stamp = (Get-Date).ToString('yyyyMMddTHHmmss')
            $dumpPath = Join-Path $backupDir ("pre-$targetVersion-$stamp.dump")
            $dump = Invoke-NativeText -Exe 'docker' -Arguments @(
                'exec', $DbContainer, 'sh', '-c',
                "PGPASSWORD='$($cfg['POSTGRES_PASSWORD'])' pg_dump -U $cfgUser -Fc -d $DbName -f /tmp/pre.dump"
            )
            if ($dump.Code -ne 0) {
                Write-Bad 'pg_dump 失败，已停止：'
                $dump.Output | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
                exit $exitFail
            }
            $copy = Invoke-NativeText -Exe 'docker' -Arguments @('cp', "$($DbContainer):/tmp/pre.dump", $dumpPath)
            Invoke-NativeText -Exe 'docker' -Arguments @('exec', $DbContainer, 'rm', '-f', '/tmp/pre.dump') | Out-Null
            if ($copy.Code -ne 0 -or -not (Test-Path -LiteralPath $dumpPath)) {
                Write-Bad '导出文件复制失败，已停止'
                exit $exitFail
            }
            $sizeMB = [math]::Round((Get-Item -LiteralPath $dumpPath).Length / 1MB, 1)
            Write-Ok "已生成保护性备份：$dumpPath（$sizeMB MB）"
            Write-Info '这不是正式备份体系，仅用于本次迁移的即时保护。'
        }

        if (-not (Ask-YesNo "确认执行 Flyway 迁移 V$dbFlyway → V$targetFlyway？")) {
            Write-Host ''
            Write-Host '  已取消。数据库未改动，未部署新版本。' -ForegroundColor Gray
            exit $exitOk
        }

        Write-Step '执行 flyway migrate'
        $flywayScript = Join-Path $pkgRoot 'deploy\flyway.sh'
        # flyway.sh 读取 config/.env（相对包根），这里把生产配置临时链接进去
        $pkgConfig = Join-Path $pkgRoot 'config\.env'
        $createdLink = $false
        if (-not (Test-Path -LiteralPath $pkgConfig)) {
            Copy-Item -LiteralPath $configPath -Destination $pkgConfig
            $createdLink = $true
        }
        try {
            $fly = Invoke-NativeText -Exe 'bash' -Arguments @($flywayScript, $DbName, 'migrate')
            if ($fly.Code -ne 0) {
                Write-Bad 'Flyway 迁移失败，已停止（不会启动新版本）：'
                $fly.Output | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
                Write-Host ''
                Write-Host '  数据库可能处于部分迁移状态，请人工核对 flyway_schema_history。' -ForegroundColor Yellow
                Write-Host '  本工具不会自动回滚数据库。' -ForegroundColor Yellow
                exit $exitFail
            }
            $fly.Output | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
        }
        finally {
            if ($createdLink -and (Test-Path -LiteralPath $pkgConfig)) {
                Remove-Item -LiteralPath $pkgConfig -Force -ErrorAction SilentlyContinue
            }
        }

        $after = Invoke-NativeText -Exe 'docker' -Arguments @(
            'exec', $DbContainer, 'psql', '-U', $cfgUser, '-d', $DbName, '-t', '-A', '-c',
            "SELECT COALESCE(max(version::int),0) FROM flyway_schema_history;"
        )
        $newVer = [int]$after.Text.Trim()
        if ($newVer -ne $targetFlyway) {
            Write-Bad "迁移后数据库版本为 V$newVer，期望 V$targetFlyway，已停止"
            exit $exitFail
        }
        Write-Ok "迁移完成：V$newVer"
    } else {
        Write-Section '5/6 数据库迁移'
        Write-Ok '版本一致，跳过迁移'
    }

    # ---------------------------------------------------------- 6. 部署
    Write-Section '6/6 部署与切换'

    $targetDir = Join-Path $ProdRoot $targetVersion
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

    Write-Step '复制包内容到版本目录'
    Copy-Item -Path (Join-Path $pkgRoot 'api') -Destination $targetDir -Recurse
    Copy-Item -Path (Join-Path $pkgRoot 'deploy') -Destination $targetDir -Recurse
    Copy-Item -Path (Join-Path $pkgRoot 'docs') -Destination $targetDir -Recurse -ErrorAction SilentlyContinue
    Copy-Item -LiteralPath (Join-Path $pkgRoot 'manifest.json') -Destination $targetDir
    Copy-Item -LiteralPath (Join-Path $pkgRoot 'SHA256SUMS.txt') -Destination $targetDir
    New-Item -ItemType Directory -Path (Join-Path $targetDir 'web') -Force | Out-Null

    # 运行时配置：MapTiler key 从生产配置注入，jar 不重新构建
    $mapKey = if ($cfg.ContainsKey('MAPTILER_API_KEY')) { $cfg['MAPTILER_API_KEY'] } else { '' }
    $cfgJs = "window.__ENV__ = { MAPTILER_KEY: `"$mapKey`" };`n"
    [System.IO.File]::WriteAllText((Join-Path $targetDir 'web\config.js'), $cfgJs, (New-Object System.Text.UTF8Encoding($false)))
    if ([string]::IsNullOrWhiteSpace($mapKey)) {
        Write-Warn '生产配置未设置 MAPTILER_API_KEY，地图将降级为无底图模式'
    } else {
        Write-Ok '已生成 web/config.js（MapTiler key 运行时注入）'
    }

    $targetJar = Join-Path $targetDir 'api\canvas-history-api.jar'
    if ((Get-FileHash -LiteralPath $targetJar -Algorithm SHA256).Hash.ToLower() -ne $jarExpectedSha.ToLower()) {
        Write-Bad '复制后的 jar 校验和不符，已停止'
        exit $exitFail
    }
    Write-Ok '版本目录内容校验通过'

    # 6a 临时端口验证
    Write-Step "临时端口 $VerifyPort 验证新版本"
    $envMap = @{
        DB_URL                    = "jdbc:postgresql://127.0.0.1:$($cfg['DB_HOST_PORT'])/$DbName"
        DB_USER                   = $cfgUser
        DB_PASSWORD               = $cfg['POSTGRES_PASSWORD']
        DB_WRITE_ALLOWED_DATABASES = $(if ($cfg.ContainsKey('DB_WRITE_ALLOWED_DATABASES')) { $cfg['DB_WRITE_ALLOWED_DATABASES'] } else { $DbName })
    }
    # 环境变量通过 Start-AppProcess 直接注入子进程，不污染当前 PowerShell 会话

    $verifyLog = Join-Path $targetDir 'verify.log'
    $verifyProc = Start-AppProcess -JarPath $targetJar -AppPort $VerifyPort -WorkDir $targetDir -EnvVars $envMap -LogFileName 'verify.log'
    $verifyConsole = Join-Path $targetDir ("console-{0}.log" -f $VerifyPort)

    $verifyOk = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 800
        if ($verifyProc.HasExited) { break }
        try {
            $r = Invoke-RestMethod -Uri "http://127.0.0.1:$VerifyPort/api/v1/meta/health" -TimeoutSec 2 -ErrorAction Stop
            if ($r.status -eq 'ok' -and $r.database -eq $DbName) { $verifyOk = $true; break }
        } catch { }
    }

    if (-not $verifyOk) {
        if (-not $verifyProc.HasExited) { Stop-Process -Id $verifyProc.Id -Force -ErrorAction SilentlyContinue }
        Write-Bad '新版本在临时端口验证失败，未切换生产'
        if (Test-Path $verifyLog) { Get-Content -LiteralPath $verifyLog -Tail 15 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" -ForegroundColor Red } }
        if (Test-Path $verifyConsole) { Get-Content -LiteralPath $verifyConsole -Tail 15 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray } }
        Write-Host ''
        Write-Host "  生产环境未改动。新版本目录保留在：$targetDir（可人工排查后删除）" -ForegroundColor Yellow
        exit $exitFail
    }
    Write-Ok "临时端口验证通过：database=$DbName"

    # 验证页面
    $pageOk = $false
    try {
        $page = Invoke-WebRequest -Uri "http://127.0.0.1:$VerifyPort/" -TimeoutSec 5 -UseBasicParsing
        if ($page.StatusCode -eq 200) { $pageOk = $true }
    } catch { }
    if ($pageOk) { Write-Ok '前端页面可访问' } else { Write-Warn '前端页面未返回 200（继续，可能为降级模式）' }

    Stop-Process -Id $verifyProc.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2

    # 6b 切换正式端口
    Write-Step "切换到正式端口 $Port"

    if ($portOwner) {
        Write-Host ''
        Write-Host "  端口 $Port 当前被 PID=$($portOwner.Pid) $($portOwner.Name) 占用。" -ForegroundColor Yellow
        Write-Host '  这是旧运行方式（Vite 或旧 API）。继续将停止该进程。' -ForegroundColor Yellow
        if (-not (Ask-YesNo "停止该进程并让新版本接管端口 $Port？")) {
            Write-Host ''
            Write-Host '  已取消切换。新版本目录已就绪但未启用，生产仍由旧进程提供服务。' -ForegroundColor Gray
            Write-Host "  目录：$targetDir" -ForegroundColor DarkGray
            exit $exitOk
        }
        Stop-Process -Id $portOwner.Pid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }

    $runLog = Join-Path $targetDir 'runtime.log'
    $runProc = Start-AppProcess -JarPath $targetJar -AppPort $Port -WorkDir $targetDir -EnvVars $envMap -LogFileName 'runtime.log'
    $runConsole = Join-Path $targetDir ("console-{0}.log" -f $Port)

    $runOk = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 800
        if ($runProc.HasExited) { break }
        try {
            $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/meta/health" -TimeoutSec 2 -ErrorAction Stop
            if ($r.status -eq 'ok' -and $r.database -eq $DbName) { $runOk = $true; break }
        } catch { }
    }

    if (-not $runOk) {
        if (-not $runProc.HasExited) { Stop-Process -Id $runProc.Id -Force -ErrorAction SilentlyContinue }
        Write-Bad '新版本在正式端口启动失败'
        if (Test-Path $runLog) { Get-Content -LiteralPath $runLog -Tail 15 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" -ForegroundColor Red } }
        if (Test-Path $runConsole) { Get-Content -LiteralPath $runConsole -Tail 15 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray } }
        Write-Host ''
        Write-Host '  未更新 current.json。生产当前处于无服务状态，请人工处理。' -ForegroundColor Yellow
        exit $exitFail
    }
    Write-Ok "正式实例已启动：http://127.0.0.1:$Port/"

    # 6c 冒烟
    Write-Step '基础功能检查'
    $smokeOk = $true
    try {
        $stats = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/meta/stats" -TimeoutSec 10 -ErrorAction Stop
        Write-Info "stats: places=$($stats.places) names=$($stats.names) locations=$($stats.locations)"
        if ([int]$stats.places -le 0) { $smokeOk = $false }
    } catch {
        $smokeOk = $false
        Write-Bad "stats 接口失败：$($_.Exception.Message)"
    }
    try {
        $one = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/places?keyword=Roma&page=1&size=1" -TimeoutSec 10 -ErrorAction Stop
        if ($one.total -le 0) { Write-Warn 'Roma 检索结果为空（可能是数据差异）' } else { Write-Info "检索正常：Roma 命中 $($one.total)" }
    } catch {
        $smokeOk = $false
        Write-Bad "检索接口失败：$($_.Exception.Message)"
    }
    if (-not $smokeOk) {
        # 关键：冒烟失败不得标记为成功。
        # 不回滚数据库、不停止已启动的进程（避免把可用服务一起关掉），
        # 但绝不写 status=success 的 current.json。
        Write-Host ''
        Write-Bad '关键接口冒烟失败，本次部署不标记为成功，current.json 未更新。'
        Write-Host ''
        Write-Host '  当前实际状态：' -ForegroundColor Yellow
        Write-Host "    · 新版本 $targetVersion 已部署到 $targetDir" -ForegroundColor Yellow
        Write-Host "    · 进程可能仍在端口 $Port 运行（PID $($runProc.Id)），页面可能可访问" -ForegroundColor Yellow
        Write-Host "    · 数据库仍为 V$targetFlyway，未做任何回滚" -ForegroundColor Yellow
        Write-Host "    · current.json 保留部署前的记录（未写入本次版本）" -ForegroundColor Yellow
        Write-Host ''
        Write-Host '  恢复方式：' -ForegroundColor Yellow
        Write-Host "    1) 查看日志：$runLog" -ForegroundColor DarkGray
        Write-Host "    2) 修复后重新运行本脚本（版本目录已存在会被拒绝，需先删除 $targetDir 或改用更高版本号）" -ForegroundColor DarkGray
        Write-Host "    3) 如需先恢复旧版本：停止 PID $($runProc.Id)，启动 $ProdRoot\<上一版本>\api\canvas-history-api.jar" -ForegroundColor DarkGray
        exit $exitFail
    }
    Write-Ok '冒烟检查通过'

    # ---------------------------------------------------------- 7. current.json
    Write-Section '更新版本记录'

    $record = [ordered]@{
        releaseVersion = $targetVersion
        previousVersion = $currentVersion
        deployPath     = $targetDir
        deployedAt     = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
        gitTag         = [string]$manifest.gitTag
        gitCommit      = [string]$manifest.gitCommit
        database       = [ordered]@{ name = $DbName; flywayVersion = $targetFlyway }
        jarSha256      = $jarExpectedSha
        port           = $Port
        verifiedViaTemporaryPort = $VerifyPort
        status         = 'success'
    }
    Write-JsonNoBom -Path $currentPath -Object $record
    Write-Ok "已更新 $currentPath"

    # 首次部署：把旧的未版本化运行方式记入 legacy-unversioned
    if ($prodState -eq 'legacy_unversioned') {
        $legacyDir = Join-Path $ProdRoot 'legacy-unversioned'
        New-Item -ItemType Directory -Path $legacyDir -Force | Out-Null
        $legacy = [ordered]@{
            recordedAt      = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
            note            = '首次正式部署前识别的未版本化运行环境'
            oldApiPort      = 8088
            oldWebPort      = 5180
            database        = [ordered]@{ name = $DbName; container = $DbContainer; flywayVersion = $dbFlyway }
            replacedBy      = $targetVersion
            oldProcessOwner = if ($portOwner) { "$($portOwner.Name) (PID $($portOwner.Pid))" } else { 'none' }
        }
        Write-JsonNoBom -Path (Join-Path $legacyDir 'legacy-record.json') -Object $legacy
        Write-Ok '已记录 legacy-unversioned 现场'
    }

    # 部署日志
    $logsDir = Join-Path $ProdRoot 'logs'
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    $logPath = Join-Path $logsDir ("deploy-" + (Get-Date).ToString('yyyyMMddTHHmmss') + ".log")
    $logLines = @(
        "time          = $(Get-Date -Format o)",
        "version       = $targetVersion",
        "previous      = $(if($currentVersion){$currentVersion}else{'legacy'})",
        "gitTag        = $($manifest.gitTag)",
        "gitCommit     = $($manifest.gitCommit)",
        "database      = $DbName",
        "flyway        = V$dbFlyway -> V$targetFlyway",
        "migrated      = $needMigrate",
        "port          = $Port",
        "deployPath    = $targetDir",
        "result        = success"
    )
    [System.IO.File]::WriteAllText($logPath, (($logLines -join "`n") + "`n"), (New-Object System.Text.UTF8Encoding($false)))
    Write-Info "部署日志：$logPath"

    Write-Host ''
    Write-Host ('=' * 70) -ForegroundColor DarkCyan
    Write-Host ("  部署完成：$targetVersion") -ForegroundColor Green
    Write-Host ('=' * 70) -ForegroundColor DarkCyan
    Write-Host "  访问地址：http://127.0.0.1:$Port/" -ForegroundColor White
    Write-Host "  部署目录：$targetDir" -ForegroundColor White
    Write-Host "  数据库：$DbName（V$targetFlyway）" -ForegroundColor White
    exit $exitOk
}
catch {
    Write-Host ''
    Write-Bad ("部署中断：{0}" -f $_.Exception.Message)
    if ($_.ScriptStackTrace) {
        Write-Host '  位置：' -NoNewline -ForegroundColor DarkGray
        Write-Host ($_.ScriptStackTrace -split "`n" | Select-Object -First 1) -ForegroundColor DarkGray
    }
    Write-Host ''
    Write-Host '  未写入成功的 current.json。请核对上方信息与生产现状。' -ForegroundColor Yellow
    exit $exitFail
}
