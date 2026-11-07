#Requires -Version 5.1
<#
.SYNOPSIS
    Canvas of World History —— GitHub 提交工具（BAT 01 的实际逻辑）

.DESCRIPTION
    对标 myLedger 的 scripts/dev/git-publish.ps1，按本项目技术栈做必要适配。

    执行顺序（信息优先，联网检查后置）：
      1/5 仓库        分支、HEAD、远端地址
      2/5 变更        新增/修改/删除/重命名 统计与样本、冲突检测
      3/5 安全检查    路径规则 + 暂存内容字节检测 + 忽略文件混入 + 单文件上限 + 大批量删除
      4/5 远端与分支  一次性读取远端（ls-remote），同步判定，单 main 分支准备
      5/5 提交与推送  自动提交信息 → Y/N 提交 → 公开仓库确认 → Y/N 推送

    分支模式：单 main 分支。
      · 已在 main → 直接继续；
      · 本地有 main 且提交一致 → 询问后切换；
      · 本地无 main 且 HEAD 与远端 main 一致 → 询问后建立并切换；
      · 其余情况 → 停止，不合并、不重置、不覆盖。

    硬性禁止：force push、reset、rebase、merge、覆盖远端、创建/推送 Tag、建其它远端分支。

    退出码：0 = 完成或用户取消；1 = 失败；2 = 已提交但未推送（本地保留）。

.PARAMETER RepoRoot
    仓库根目录。缺省时由脚本位置向上两级推断。

.PARAMETER DryRun
    严格只读：不做 checkout / 建分支 / add / commit / push，也不写任何本地引用。
    仅做只读的 ls-remote 与文件读取，用于预览。

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev\git-publish.ps1 -DryRun
#>
[CmdletBinding()]
param(
    [string]$RepoRoot,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
# 控制台与外部程序统一 UTF-8：BAT 入口已执行 chcp 65001。
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch { }
# Invoke-WebRequest 的进度条会把交互输出冲掉
$ProgressPreference = 'SilentlyContinue'

# 单文件上限（与 myLedger 一致）。超过即阻断，避免把二进制/数据文件写进历史。
$SizeLimit = 5MB
# 允许的 Flyway 迁移路径（本项目的“官方 SQL 路径”）
$MigrationPattern = '^code/backend/src/main/resources/db/migration/V[0-9]+__[A-Za-z0-9_]+\.sql$'

# ------------------------------------------------------------------ 输出工具
function Write-Title([string]$Text) {
    Write-Host ''
    Write-Host ('=' * 64) -ForegroundColor DarkCyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ('=' * 64) -ForegroundColor DarkCyan
}
function Write-Section([string]$Text) {
    Write-Host ''
    Write-Host "[$Text]" -ForegroundColor Yellow
}
function Write-Ok([string]$Text)   { Write-Host "  [OK] $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "  [!]  $Text" -ForegroundColor Yellow }
function Write-Bad([string]$Text)  { Write-Host "  [X]  $Text" -ForegroundColor Red }
function Write-Info([string]$Text) { Write-Host "       $Text" -ForegroundColor Gray }

# ------------------------------------------------------------------ 参数拼装
# 带空格或引号的参数需要加引号，否则会被 git 拆成两段。
function ConvertTo-ArgLine {
    param([string[]]$Items)
    return (($Items | ForEach-Object {
                if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ }
            }) -join ' ')
}

# ------------------------------------------------------------------ Git 封装（文本）
# git 的 stderr 被 2>&1 捕获后会变成 ErrorRecord，直接 "$_" 会带出
# "System.Management.Automation.RemoteException" 这类噪音，这里统一取消息文本。
function Format-GitLine {
    param($Item)
    if ($Item -is [System.Management.Automation.ErrorRecord]) {
        return $Item.Exception.Message
    }
    return "$Item"
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [bool]$AllowFail = $false
    )
    # 在 Stop 模式下，外部程序写 stderr 会被 2>&1 转成终止性错误直接抛出，
    # 根本走不到下面的退出码判断。这里临时降为 Continue。
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $raw = & git -c core.quotepath=false @Arguments 2>&1
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $prevEap
    }
    $output = @($raw | ForEach-Object { Format-GitLine $_ })
    if ($code -ne 0 -and -not $AllowFail) {
        throw ("git {0} 失败（退出码 {1}）：`n{2}" -f ($Arguments -join ' '), $code, ($output -join "`n"))
    }
    return [pscustomobject]@{ Output = $output; Code = $code }
}

function Get-GitText {
    param([string[]]$Arguments, [bool]$AllowFail = $false)
    $r = Invoke-Git -Arguments $Arguments -AllowFail $AllowFail
    if ($r.Output.Count -eq 0) { return '' }
    return (($r.Output | ForEach-Object { "$_" }) -join "`n").Trim()
}

# ------------------------------------------------------------------ Git 封装（字节）
# 需要精确拿到 NUL 分隔输出（status -z、diff -z）或文件原始内容（cat-file）时用这个。
# 走 ProcessStartInfo 而非 $() 捕获，避免 PowerShell 按行切分、改写编码。
function Invoke-GitBytes {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [int]$TimeoutMs = 0
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = 'git'
    $psi.Arguments = ConvertTo-ArgLine (@('-c', 'core.quotepath=false') + $Arguments)
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $psi.WorkingDirectory = $script:Root

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    [void]$proc.Start()
    $errTask = $proc.StandardError.ReadToEndAsync()
    $ms = New-Object System.IO.MemoryStream
    $proc.StandardOutput.BaseStream.CopyTo($ms)

    if ($TimeoutMs -gt 0) { [void]$proc.WaitForExit($TimeoutMs) } else { $proc.WaitForExit() }
    if (-not $proc.HasExited) { try { $proc.Kill() } catch { } }
    $code = 1
    try { if ($proc.HasExited) { $code = $proc.ExitCode } } catch { }
    $errText = ''
    try { $errText = $errTask.Result } catch { }
    try { $proc.Dispose() } catch { }

    $bytes = $ms.ToArray()
    return [pscustomobject]@{
        Code  = $code
        Bytes = $bytes
        Text  = [System.Text.Encoding]::UTF8.GetString($bytes)
        Error = $errText
    }
}

function Split-GitNul {
    param([string]$Text)
    $list = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrEmpty($Text)) {
        foreach ($part in $Text.Split([char]0)) {
            if ($part -ne '') { [void]$list.Add($part) }
        }
    }
    return , $list.ToArray()
}

# ------------------------------------------------------------------ Y/N 交互
function Ask-YesNo {
    param([string]$Question)
    while ($true) {
        Write-Host ''
        Write-Host "  $Question (Y/N) " -ForegroundColor White -NoNewline
        $answer = Read-Host
        $answer = "$answer".Trim()
        if ($answer -eq '') { return $false }              # 直接回车 = N
        if ($answer -match '^[Yy]$') { return $true }
        if ($answer -match '^[Nn]$') { return $false }
        Write-Host '  输入无效，请重新输入 Y 或 N（直接回车 = N）。' -ForegroundColor Yellow
    }
}

# ------------------------------------------------------------------ 路径规则
# 返回危险原因；安全则返回 $null
function Test-DangerousPath {
    param([string]$Path)
    $p = $Path -replace '\\', '/'

    if ($p -match '(^|/)\.env\.example$') { return $null }   # 模板必须允许

    if ($p -match '(^|/)\.env$')              { return '真实环境配置（.env）' }
    if ($p -match '(^|/)\.env\.(dev|local|prod|test|staging)$') { return '环境配置变体' }
    if ($p -match '\.(pem|key|p12|pfx|jks|keystore)$')   { return '证书/私钥' }
    if ($p -match '(^|/)(id_rsa|id_ed25519)$')            { return 'SSH 私钥' }
    if ($p -match '\.(dump|backup|bak)$')                 { return '数据库备份' }
    if ($p -match '\.sql\.gz$')                           { return '数据库备份' }
    if ($p -match '(^|/)node_modules/')                   { return '依赖目录' }
    if ($p -match '\.(jar|war|exe|dll|so|dylib)$')        { return '二进制产物' }
    if ($p -match '(^|/)(dist|target|build|\.vite)/')     { return '构建产物' }
    if ($p -match '\.log$')                               { return '日志文件' }
    if ($p -match '(^|/)\.DS_Store$')                     { return '系统垃圾文件' }
    return $null
}

function Test-OfficialMigrationPath {
    param([string]$Path)
    $norm = ($Path -replace '\\', '/').TrimStart('./')
    return $norm -match $MigrationPattern
}

# ------------------------------------------------------------------ 内容检测
# 密钥/TLS 私钥特征 + 体积上限
function Test-SensitiveBytes {
    param([byte[]]$Bytes)
    if ($null -eq $Bytes) { return $null }
    if ($Bytes.Length -gt $SizeLimit) { return ("超过 {0} MB 上限（{1:N1} MB）" -f ($SizeLimit / 1MB), ($Bytes.Length / 1MB)) }
    $sample = [System.Text.Encoding]::GetEncoding(28591).GetString($Bytes)
    if ($sample -match 'BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY') { return '包含私钥内容' }
    if ($sample -match 'AKIA[0-9A-Z]{16}') { return '包含 AWS Access Key' }
    return $null
}

# 导出型 SQL / 连接串 / 明文口令特征。
# 注意：不含裸 INSERT INTO —— 本项目 V5 迁移里有 2 处 INSERT（种子数据），
# 把 INSERT 一律判为导出会误伤正常迁移。
function Test-SqlExportBytes {
    param([byte[]]$Bytes)
    if ($null -eq $Bytes -or $Bytes.Length -eq 0) { return $null }
    $sample = [System.Text.Encoding]::GetEncoding(28591).GetString($Bytes)
    if ($sample -match '(?i)pg_dump') { return '包含 pg_dump 导出标记' }
    if ($sample -match '(?i)^[ \t]*COPY[ \t]+[^;]*FROM[ \t]+stdin') { return '包含 COPY ... FROM stdin 导出段' }
    if ($sample -match '(?i)postgresql://[^\s"'']*:[^\s"'']*@') { return '包含带口令的数据库连接串' }
    if ($sample -match '(?i)\b(POSTGRES_PASSWORD|DB_PASSWORD|PGPASSWORD)[ \t]*=') { return '包含数据库口令' }
    return $null
}

function Test-IgnoredPath {
    param(
        [string]$Path,
        # 默认跳过已跟踪文件（git 默认行为）。加此开关连已跟踪的一起判断，
        # 用来发现“被 ignore 却仍被强行加入索引”的文件。
        [switch]$IncludeTracked
    )
    $gitArgs = @('check-ignore', '-q')
    if ($IncludeTracked) { $gitArgs += '--no-index' }
    $gitArgs += @('--', $Path)
    return (Invoke-GitBytes $gitArgs).Code -eq 0
}

function Get-IndexBytes {
    param([string]$Path)
    $r = Invoke-GitBytes @('cat-file', '-p', (':' + $Path))
    if ($r.Code -ne 0) { return $null }
    return $r.Bytes
}

# 对一个即将进入提交的文件做完整内容检查，返回问题描述数组
function Test-FileContent {
    param(
        [string]$Path,
        [string]$Stage            # 'worktree' 或 'index'
    )
    $problems = @()

    $bytes = $null
    if ($Stage -eq 'index') {
        $bytes = Get-IndexBytes $Path
    }
    else {
        $full = Join-Path $script:Root ($Path -replace '/', '\')
        if (Test-Path -LiteralPath $full -PathType Leaf) {
            $item = Get-Item -LiteralPath $full
            if ($item.Length -gt $SizeLimit) {
                $problems += ("{0}  超过 {1} MB 上限（{2:N1} MB）" -f $Path, ($SizeLimit / 1MB), ($item.Length / 1MB))
                return $problems
            }
            $bytes = [System.IO.File]::ReadAllBytes($full)
        }
    }
    if ($null -eq $bytes) { return $problems }

    $hit = Test-SensitiveBytes $bytes
    if ($hit) { $problems += ("{0}  {1}" -f $Path, $hit) }

    if ($Path -match '(?i)\.sql$') {
        $sqlHit = Test-SqlExportBytes $bytes
        if ($sqlHit) { $problems += ("{0}  {1}" -f $Path, $sqlHit) }
        elseif (-not (Test-OfficialMigrationPath $Path)) {
            # 非官方迁移路径的 SQL 不阻断，只提示（本项目 ops/ 下有合法测试脚本）
            $script:SqlNotes += ("{0}  非迁移路径的 SQL 脚本" -f $Path)
        }
    }
    return $problems
}

# ------------------------------------------------------------------ 仓库可见性
function Convert-GitHubVisibility {
    param($Payload)
    if ($null -eq $Payload) { return 'unknown' }
    $visibility = ([string]$Payload.visibility).Trim().ToLower()
    if ($Payload.private -eq $true -and $visibility -eq 'private') { return 'private' }
    if ($Payload.private -eq $false -and $visibility -eq 'public') { return 'public' }
    return 'unknown'
}

# 从 Git 凭据管理器取 token（不弹窗、不落盘）
function Get-GitHubToken {
    $prevInput = [Console]::InputEncoding
    $savedPrompt = $env:GIT_TERMINAL_PROMPT
    $savedGcm = $env:GCM_INTERACTIVE
    $token = $null
    try {
        [Console]::InputEncoding = New-Object System.Text.UTF8Encoding $false
        $env:GIT_TERMINAL_PROMPT = '0'
        $env:GCM_INTERACTIVE = 'never'

        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = 'git'
        $psi.Arguments = 'credential fill'
        $psi.UseShellExecute = $false
        $psi.RedirectStandardInput = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true

        $proc = New-Object System.Diagnostics.Process
        $proc.StartInfo = $psi
        [void]$proc.Start()
        $writer = New-Object System.IO.StreamWriter($proc.StandardInput.BaseStream, (New-Object System.Text.UTF8Encoding $false))
        $writer.NewLine = "`n"
        $writer.WriteLine('protocol=https')
        $writer.WriteLine('host=github.com')
        $writer.WriteLine('')
        $writer.Flush()
        $writer.Close()

        $outTask = $proc.StandardOutput.ReadToEndAsync()
        $errTask = $proc.StandardError.ReadToEndAsync()
        if (-not $proc.WaitForExit(20000)) { try { $proc.Kill() } catch { } return $null }
        $text = ''
        try { $text = $outTask.Result } catch { }
        try { [void]$errTask.Result } catch { }
        if ($proc.ExitCode -ne 0) { return $null }
        foreach ($line in ($text -split "`n")) {
            if ($line.StartsWith('password=')) { $token = $line.Substring(9).Trim() }
        }
    }
    catch { return $null }
    finally {
        try { [Console]::InputEncoding = $prevInput } catch { }
        if ($null -eq $savedPrompt) { Remove-Item Env:GIT_TERMINAL_PROMPT -ErrorAction SilentlyContinue } else { $env:GIT_TERMINAL_PROMPT = $savedPrompt }
        if ($null -eq $savedGcm) { Remove-Item Env:GCM_INTERACTIVE -ErrorAction SilentlyContinue } else { $env:GCM_INTERACTIVE = $savedGcm }
    }
    if ([string]::IsNullOrWhiteSpace($token)) { return $null }
    return $token
}

function Get-RemoteVisibility {
    param([string]$Url)
    if ($Url -match '^(https://github\.com/|ssh://git@github\.com/|git@github\.com:)([^/]+)/([^/]+?)(\.git)?$') {
        $owner = $Matches[2]
        $repo = $Matches[3]
        $token = Get-GitHubToken
        if ([string]::IsNullOrWhiteSpace($token)) { return 'unknown' }
        try {
            $resp = Invoke-WebRequest -Uri ('https://api.github.com/repos/{0}/{1}' -f $owner, $repo) `
                -Headers @{
                    Authorization = "Bearer $token"
                    'User-Agent'  = 'canvas-git-publish'
                    Accept        = 'application/vnd.github+json'
                } -UseBasicParsing -TimeoutSec 20
            return Convert-GitHubVisibility ($resp.Content | ConvertFrom-Json)
        }
        catch { return 'unknown' }
        finally { $token = $null }
    }
    if ($Url -match '^[A-Za-z]:\\' -or $Url -match '^\\\\' -or $Url -match '^/' -or $Url -match '^file://') { return 'local' }
    if ($Url -match '^(https?://|ssh://|git@)') { return 'unknown' }
    return 'unknown'
}

# ------------------------------------------------------------------ 提交信息
function New-CommitMessage {
    param(
        [string[]]$Added,
        [string[]]$Modified,
        [string[]]$Deleted
    )
    $all = @($Added) + @($Modified) + @($Deleted)

    $type = 'chore'
    $hasSource = $false
    foreach ($p in $all) {
        if ($p -match '(code/backend/src/.*\.java|code/frontend/src/.*\.(ts|vue)|code/frontend/src/.*\.css)$') { $hasSource = $true; break }
    }
    if ($hasSource) { $type = 'feat' }
    elseif ($all.Count -gt 0 -and -not ($all | Where-Object { $_ -notmatch '\.md$' })) { $type = 'docs' }

    # 影响区域：取变更最多的两个二级目录
    $areas = @()
    foreach ($p in $all) {
        $norm = $p -replace '\\', '/'
        $segs = $norm -split '/'
        if ($segs.Count -ge 2 -and $segs[1] -notmatch '\.') { $areas += ($segs[0] + '/' + $segs[1]) }
    }
    $scope = ''
    if ($areas.Count -gt 0) {
        $scope = (($areas | Group-Object | Sort-Object Count -Descending | Select-Object -First 2 |
            ForEach-Object { $_.Name }) -join ', ')
    }

    $hints = @()
    if ($all -match 'ops/reports/')        { $hints += 'clean up stage reports' }
    if ($all -match 'docker-compose\.dev') { $hints += 'add DEV environment' }
    if ($all -match 'run-dev-api\.sh')     { $hints += 'add DEV launcher' }
    if ($all -match 'scripts/(dev|release)/') { $hints += 'align release tooling' }
    if ($hints.Count -gt 2) { $hints = @($hints[0], $hints[1]) }

    $summaryParts = @()
    if ($Added.Count -gt 0)    { $summaryParts += ("add {0}" -f $Added.Count) }
    if ($Modified.Count -gt 0) { $summaryParts += ("update {0}" -f $Modified.Count) }
    if ($Deleted.Count -gt 0)  { $summaryParts += ("remove {0}" -f $Deleted.Count) }
    $summary = $summaryParts -join ', '

    if ($hints.Count -gt 0) {
        $summary = (($hints -join '; ') + ' (' + $summary + ')')
    }

    $head = $type
    if ($scope -ne '') { $head = "${type}(${scope})" }
    # 注意：变量后紧跟冒号必须写成 ${head}:
    $subject = "${head}: $summary"

    if ($subject.Length -gt 72) {
        $subject = $subject.Substring(0, 69).TrimEnd() + '...'
    }
    return $subject
}

# ================================================================== 主流程
$exitOk = 0
$exitFail = 1
$exitUnpushed = 2
$script:Root = ''
$script:SqlNotes = New-Object System.Collections.Generic.List[string]

try {
    # ---------------------------------------------------------- 0. 定位仓库
    $root = $RepoRoot
    if ([string]::IsNullOrWhiteSpace($root)) {
        $here = $PSScriptRoot
        if ([string]::IsNullOrWhiteSpace($here)) {
            $here = Split-Path -Parent $MyInvocation.MyCommand.Path
        }
        # scripts/dev → scripts → 仓库根
        $root = Split-Path -Parent (Split-Path -Parent $here)
    }
    if (-not (Test-Path (Join-Path $root '.git'))) {
        Write-Title '提交 GitHub'
        Write-Bad "这里不是 Git 仓库根目录：$root"
        exit $exitFail
    }
    $script:Root = $root
    Set-Location -LiteralPath $root

    Write-Title '提交 GitHub'
    if ($DryRun) {
        Write-Warn '只读模式（-DryRun）：不做分支操作，不 add / commit / push'
    }
    Write-Info "仓库：$root"

    $gitVersion = Get-GitText @('--version')
    if (-not $gitVersion) {
        Write-Bad '未找到 git 命令，请确认 Git 已安装并加入 PATH。'
        exit $exitFail
    }
    Write-Info $gitVersion

    # ---------------------------------------------------------- 1/5 仓库状态
    Write-Section '1/5 仓库'

    $branch = Get-GitText @('rev-parse', '--abbrev-ref', 'HEAD')
    if ($branch -eq 'HEAD' -or [string]::IsNullOrWhiteSpace($branch)) {
        Write-Bad '当前处于游离 HEAD 状态，已停止。'
        Write-Host '  请先切回一个正常分支（本项目为 main）后再运行。' -ForegroundColor Yellow
        exit $exitFail
    }
    $headNow = Get-GitText @('rev-parse', 'HEAD')
    $headShort = $headNow.Substring(0, 7)
    $headLine = Get-GitText @('log', '-1', '--format=%s')
    $headDate = Get-GitText @('log', '-1', '--format=%ci')

    $remoteUrl = Get-GitText @('remote', 'get-url', 'origin') -AllowFail $true
    if (-not $remoteUrl) {
        Write-Bad '没有名为 origin 的远端仓库，已停止。'
        Write-Host '  本工具只向 origin 推送，不会自动创建远端。' -ForegroundColor Yellow
        exit $exitFail
    }
    $displayUrl = $remoteUrl -replace '://[^/\s@]+@', '://***@'

    Write-Info "分支：$branch"
    Write-Info "HEAD：$headShort  $headLine"
    Write-Info "提交时间：$headDate"
    Write-Info "远端：origin  $displayUrl"
    if ($branch -ne 'main') {
        Write-Info '正式分支：main（本项目采用单 main 分支模式）'
    }

    # ---------------------------------------------------------- 2/5 变更
    # 先看变更，再做联网检查：网络异常时用户至少已经看到工作区实况。
    Write-Section '2/5 变更文件'

    $statusRes = Invoke-GitBytes @('status', '--porcelain=v1', '-z', '--untracked-files=all')
    if ($statusRes.Code -ne 0) {
        Write-Bad '无法读取工作区状态，已停止。'
        Write-Host ("    " + $statusRes.Error.Trim()) -ForegroundColor Red
        exit $exitFail
    }
    $records = Split-GitNul $statusRes.Text

    $added = New-Object System.Collections.Generic.List[string]
    $modified = New-Object System.Collections.Generic.List[string]
    $deleted = New-Object System.Collections.Generic.List[string]
    $renamed = New-Object System.Collections.Generic.List[string]
    $addPaths = New-Object System.Collections.Generic.List[string]   # 交给 git add 的路径（含重命名旧路径）
    $conflict = $false

    $i = 0
    while ($i -lt $records.Count) {
        $entry = [string]$records[$i]
        $i++
        if ($entry.Length -lt 4) { continue }
        $xy = $entry.Substring(0, 2)
        $path = $entry.Substring(3)

        if ($xy -match 'U' -or $xy -eq 'AA' -or $xy -eq 'DD') { $conflict = $true }

        $isRename = ($xy[0] -eq 'R' -or $xy[0] -eq 'C' -or $xy[1] -eq 'R' -or $xy[1] -eq 'C')
        $oldPath = ''
        if ($isRename -and $i -lt $records.Count) { $oldPath = [string]$records[$i]; $i++ }

        if ($xy -eq '??') {
            [void]$added.Add($path)
            [void]$addPaths.Add($path)
        }
        elseif ($isRename) {
            [void]$renamed.Add("$path  ← $oldPath")
            [void]$addPaths.Add($path)
            if ($oldPath) { [void]$addPaths.Add($oldPath) }
        }
        elseif ($xy -match 'D') {
            [void]$deleted.Add($path)
            [void]$addPaths.Add($path)
        }
        elseif ($xy -match 'A') {
            [void]$added.Add($path)
            [void]$addPaths.Add($path)
        }
        else {
            [void]$modified.Add($path)
            [void]$addPaths.Add($path)
        }
    }

    if ($conflict) {
        Write-Bad '存在未合并的冲突文件，已停止。'
        Write-Host '  本工具不会自动解决冲突，也不会 reset。' -ForegroundColor Yellow
        exit $exitFail
    }

    $changeCount = $added.Count + $modified.Count + $deleted.Count + $renamed.Count

    function Show-Sample([string]$Label, $Items, [string]$Color) {
        if ($Items.Count -eq 0) { return }
        Write-Host ''
        Write-Host ("  $Label（{0}）" -f $Items.Count) -ForegroundColor $Color
        $max = 8
        for ($k = 0; $k -lt [Math]::Min($max, $Items.Count); $k++) {
            Write-Host ("    {0}" -f $Items[$k]) -ForegroundColor Gray
        }
        if ($Items.Count -gt $max) {
            Write-Host ("    ... 另有 {0} 个" -f ($Items.Count - $max)) -ForegroundColor DarkGray
        }
    }

    # 工作区干净不等于没有工作：已提交但尚未推送的提交仍需处理。
    # 这里只做标记，不退出——是否真要推送要先读远端才能判断。
    $noChanges = $false
    if ($changeCount -eq 0) {
        $noChanges = $true
        Write-Ok '工作区干净，没有需要提交的变更。'
        Write-Info '检查是否有已提交但尚未推送的提交…'
    }
    else {
        Write-Info ("新增 {0} 个 / 修改 {1} 个 / 删除 {2} 个 / 重命名 {3} 个" -f `
                $added.Count, $modified.Count, $deleted.Count, $renamed.Count)
        Show-Sample '新增' $added 'Green'
        Show-Sample '修改' $modified 'Yellow'
        Show-Sample '删除' $deleted 'Red'
        Show-Sample '重命名' $renamed 'Cyan'
    }

    # ---------------------------------------------------------- 3/5 安全检查
    Write-Section '3/5 安全检查'

    # 3.1 路径规则（对所有非删除项）
    $dangerous = @()
    $checkPaths = New-Object System.Collections.Generic.List[string]
    foreach ($p in @($added) + @($modified)) { if (-not $checkPaths.Contains($p)) { [void]$checkPaths.Add($p) } }
    foreach ($r in $renamed) { $p = ($r -split '  ← ')[0]; if (-not $checkPaths.Contains($p)) { [void]$checkPaths.Add($p) } }

    foreach ($p in $checkPaths) {
        $reason = Test-DangerousPath $p
        if ($reason) { $dangerous += ("{0}  ← {1}" -f $p, $reason) }
    }

    # 3.2 被忽略文件混入：只针对**新增**项
    # 已跟踪但后来被 ignore 的文件是历史残留（本项目 ops/reports 即如此），
    # 修改它们不会泄漏新内容，不应阻断；真正危险的是把被忽略的文件强行加入索引。
    $ignoredHits = @()
    foreach ($p in $added) {
        if (Test-IgnoredPath $p -IncludeTracked) { $ignoredHits += $p }
    }

    # 3.3 内容检测（工作区）
    $contentHits = @()
    foreach ($p in $checkPaths) {
        foreach ($h in (Test-FileContent -Path $p -Stage 'worktree')) { $contentHits += $h }
    }

    $blocked = $false

    if ($dangerous.Count -gt 0) {
        $blocked = $true
        Write-Bad ("发现 {0} 个敏感文件，已停止提交：" -f $dangerous.Count)
        foreach ($d in $dangerous) { Write-Host ("    {0}" -f $d) -ForegroundColor Red }
        Write-Host ''
        Write-Host '  请把这些文件加入 .gitignore 或移出仓库后重新运行。' -ForegroundColor Yellow
    }

    if ($ignoredHits.Count -gt 0) {
        $blocked = $true
        Write-Bad ("发现 {0} 个被 .gitignore 忽略、却被强制加入索引的文件：" -f $ignoredHits.Count)
        foreach ($d in $ignoredHits) { Write-Host ("    {0}" -f $d) -ForegroundColor Red }
        Write-Host ''
        Write-Host '  这类文件不应进入历史，请先从索引移除并加入 .gitignore。' -ForegroundColor Yellow
    }

    if ($contentHits.Count -gt 0) {
        $blocked = $true
        Write-Bad ("发现 {0} 个文件内容异常，已停止提交：" -f $contentHits.Count)
        foreach ($d in $contentHits) { Write-Host ("    {0}" -f $d) -ForegroundColor Red }
    }

    if ($noChanges) {
        Write-Ok '没有待提交的文件，跳过文件级检查。'
    }
    elseif (-not $blocked) {
        Write-Ok ("已检查 {0} 个文件：路径规则、忽略规则、内容特征、单文件 {1} MB 上限" -f $checkPaths.Count, ($SizeLimit / 1MB))
    }
    if ($script:SqlNotes.Count -gt 0) {
        Write-Warn ("{0} 个非迁移路径的 SQL 脚本（仅提示，不阻断）：" -f $script:SqlNotes.Count)
        foreach ($n in $script:SqlNotes) { Write-Host ("    {0}" -f $n) -ForegroundColor DarkYellow }
    }

    # 3.3 大批量删除
    $deleteConfirmExtra = $false
    if ($deleted.Count -ge 500) {
        $blocked = $true
        Write-Bad ("删除文件数量异常：{0} 个（阈值 500），已停止提交。" -f $deleted.Count)
        Write-Host '  请确认这些删除确属预期操作。' -ForegroundColor Yellow
    }
    elseif ($deleted.Count -ge 50) {
        $deleteConfirmExtra = $true
        Write-Warn ("本次包含 {0} 个删除，数量较大。" -f $deleted.Count)
        Write-Host '  请确认这些文件确实应当被删除。' -ForegroundColor Yellow
    }

    if ($blocked) {
        Write-Host ''
        Write-Bad '安全检查未通过，未做任何改动。'
        exit $exitFail
    }

    # ---------------------------------------------------------- 4/5 远端与分支
    Write-Section '4/5 远端与分支'

    # 一次性读取远端（只读，不写本地引用）。
    # 与 myLedger 一致：提交前必须确认远端状态；失败则明确告知失败发生在哪一步。
    Write-Info '读取 GitHub 远端状态…'
    # credential.interactive=never：凭据缺失时立刻报错，而不是弹窗卡住
    $lsRemote = Invoke-GitBytes @('-c', 'credential.interactive=never', 'ls-remote', '--heads', 'origin', 'refs/heads/main') -TimeoutMs 60000
    if ($lsRemote.Code -ne 0) {
        Write-Bad '读取 GitHub 远端状态失败（第 4/5 步，尚未做任何本地改动）。'
        $detail = "$($lsRemote.Error)".Trim()
        if ($detail) { Write-Host ("    " + ($detail -replace "`n", "`n    ")) -ForegroundColor Red }
        Write-Host '  请确认网络与 GitHub 凭据可用后重新运行。' -ForegroundColor Yellow
        exit $exitFail
    }
    $remoteMainSha = ''
    foreach ($line in ($lsRemote.Text -split "`n")) {
        if ($line -match '^([0-9a-f]{40})\s+') { $remoteMainSha = $Matches[1] }
    }
    if ($remoteMainSha) { Write-Info "远端 main：$($remoteMainSha.Substring(0,7))" }
    else { Write-Warn '远端还没有 main 分支。' }

    # 4.1 单 main 分支准备（只用远端读到的 sha 判断，不做 fetch）
    $primary = 'main'
    $switchNeeded = $false
    $createNeeded = $false

    if ($branch -eq $primary) {
        Write-Ok "已在 $primary 分支"
    }
    else {
        $hasLocalMain = (Invoke-Git -Arguments @('show-ref', '--verify', '--quiet', "refs/heads/$primary") -AllowFail $true).Code -eq 0
        if ($hasLocalMain) {
            $mainSha = Get-GitText @('rev-parse', "refs/heads/$primary")
            if ($mainSha -ne $headNow) {
                Write-Bad "当前分支 $branch 与本地 $primary 指向不同提交，已停止。"
                Write-Info "当前 HEAD : $headNow"
                Write-Info "$primary     : $mainSha"
                Write-Host ''
                Write-Host '  直接切换会混淆提交来源。本工具不会自动合并、重置或覆盖代码。' -ForegroundColor Yellow
                Write-Host "  请先决定 $branch 上的提交如何处理，再重新运行。" -ForegroundColor Yellow
                exit $exitFail
            }
            $switchNeeded = $true
        }
        else {
            if (-not $remoteMainSha) {
                Write-Bad "本地没有 $primary，远端也没有 $primary，已停止。"
                Write-Host '  请先在 GitHub 上确认 main 分支存在，或由人工建立后再运行。' -ForegroundColor Yellow
                exit $exitFail
            }
            if ($remoteMainSha -ne $headNow) {
                Write-Bad "本地没有 $primary，且当前提交与远端 main 不一致，已停止。"
                Write-Info "当前 HEAD   : $headNow"
                Write-Info "远端 main   : $remoteMainSha"
                Write-Host ''
                Write-Host '  此时建立 main 会让本地历史与远端错位。本工具不会自动处理。' -ForegroundColor Yellow
                Write-Host '  请先确认这些提交应如何进入 main，再重新运行。' -ForegroundColor Yellow
                exit $exitFail
            }
            $createNeeded = $true
        }

        if ($DryRun) {
            Write-Host ''
            Write-Warn '只读模式：未执行任何分支操作。'
            if ($createNeeded) {
                Write-Info "正常运行时，此处会执行：git checkout -b $primary，并把上游设为 origin/$primary"
            }
            else {
                Write-Info "正常运行时，此处会执行：git checkout $primary"
            }
            Write-Info "以下内容按「已在 $primary」预览，当前实际仍在 $branch"
        }
        else {
            Write-Host ''
            if ($createNeeded) {
                Write-Warn "本地还没有 $primary 分支。"
                Write-Info "当前提交与远端 main 完全一致（$headShort），可以安全建立。"
                if (-not (Ask-YesNo "建立本地 $primary 并切换过去？（未提交的修改会保留）")) {
                    Write-Host ''
                    Write-Host '  已取消，Git 状态未改变。' -ForegroundColor Gray
                    exit $exitOk
                }
                $sw = Invoke-Git -Arguments @('checkout', '-b', $primary) -AllowFail $true
                if ($sw.Code -ne 0) {
                    Write-Bad "建立 $primary 失败："
                    $sw.Output | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
                    exit $exitFail
                }
                # 关联上游，后续推送直接落到 origin/main
                $up = Invoke-Git -Arguments @('branch', '--set-upstream-to', "origin/$primary", $primary) -AllowFail $true
                if ($up.Code -ne 0) {
                    Invoke-Git -Arguments @('config', "branch.$primary.remote", 'origin') -AllowFail $true | Out-Null
                    Invoke-Git -Arguments @('config', "branch.$primary.merge", "refs/heads/$primary") -AllowFail $true | Out-Null
                }
                $branch = $primary
                Write-Ok "已建立并切换到 $primary（未提交的修改已保留）"
            }
            else {
                Write-Warn "本地已存在 $primary，且与当前提交一致，需要先切换过去。"
                if (-not (Ask-YesNo "切换到 $primary？（未提交的修改会保留）")) {
                    Write-Host ''
                    Write-Host '  已取消，Git 状态未改变。' -ForegroundColor Gray
                    exit $exitOk
                }
                $sw = Invoke-Git -Arguments @('checkout', $primary) -AllowFail $true
                if ($sw.Code -ne 0) {
                    Write-Bad "切换到 $primary 失败："
                    $sw.Output | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
                    Write-Host '  工作区可能与该分支存在冲突，请手动处理。' -ForegroundColor Yellow
                    exit $exitFail
                }
                $branch = $primary
                Write-Ok "已切换到 $primary（未提交的修改已保留）"
            }
        }
    }

    # 4.2 同步状态判定（用 ls-remote 的 sha，不再 fetch）
    $ahead = 0
    if ($remoteMainSha) {
        # 未 fetch 时，远端可能含有本地缺失的提交对象；此时 merge-base 会报错，
        # 无法区分「远端领先」与「已分叉」。两种情况都必须停止，但要说清是哪一种未知。
        $remoteKnown = (Invoke-Git -Arguments @('cat-file', '-e', "$remoteMainSha^{commit}") -AllowFail $true).Code -eq 0
        if (-not $remoteKnown) {
            Write-Bad '远端 main 含有本地没有的提交，已停止。'
            Write-Info "本地 HEAD : $headNow"
            Write-Info "远端 main : $remoteMainSha"
            Write-Host ''
            Write-Host '  无法在未获取远端的情况下判断是「远端领先」还是「已分叉」，' -ForegroundColor Yellow
            Write-Host '  因此不做任何推送。本工具不会 pull、merge、rebase 或 force push。' -ForegroundColor Yellow
            Write-Host '  请先由人工处理远端差异后再运行。' -ForegroundColor Yellow
            exit $exitFail
        }

        $isRemoteAncestor = (Invoke-Git -Arguments @('merge-base', '--is-ancestor', $remoteMainSha, 'HEAD') -AllowFail $true).Code -eq 0
        $isLocalAncestor = (Invoke-Git -Arguments @('merge-base', '--is-ancestor', 'HEAD', $remoteMainSha) -AllowFail $true).Code -eq 0

        if (-not $isRemoteAncestor -and -not $isLocalAncestor) {
            Write-Bad '本地与远端历史已分叉，已停止。'
            Write-Host '  本工具不会 merge、pull、rebase 或 force push。' -ForegroundColor Yellow
            exit $exitFail
        }
        if ($isLocalAncestor -and $remoteMainSha -ne $headNow) {
            Write-Bad '远端 main 比本地更新，已停止。'
            Write-Info "本地 HEAD : $headNow"
            Write-Info "远端 main : $remoteMainSha"
            Write-Host ''
            Write-Host '  本工具不会自动 pull。请先处理远端差异后再运行。' -ForegroundColor Yellow
            exit $exitFail
        }
        $countText = Get-GitText @('rev-list', '--count', "$remoteMainSha..HEAD") -AllowFail $true
        if ($countText -match '^\d+$') { $ahead = [int]$countText }
        Write-Info "相对远端 main：本地领先 $ahead 个提交"
    }
    else {
        $countText = Get-GitText @('rev-list', '--count', 'HEAD') -AllowFail $true
        if ($countText -match '^\d+$') { $ahead = [int]$countText }
        Write-Info "远端尚无 main，本次推送将建立该分支"
    }

    # ---------------------------------------------------------- 5/5 提交
    # $newHead 先按当前 HEAD 兜底：工作区干净时不会产生新提交，后续推送文案仍要有值。
    $newHead = $headNow

    # 工作区干净时整段跳过：绝不创建空提交，直接进入推送。
    if (-not $noChanges) {
    $message = New-CommitMessage -Added $added -Modified $modified -Deleted $deleted

    Write-Section '5/5 提交'
    Write-Host ''
    Write-Host '  拟用提交信息：' -ForegroundColor White
    Write-Host "    $message" -ForegroundColor Cyan
    Write-Host ''
    Write-Host ("  将暂存 {0} 个变更（含删除）。" -f $changeCount) -ForegroundColor White

    if ($deleteConfirmExtra) {
        Write-Host ''
        Write-Host ("  本次将删除 {0} 个文件。" -f $deleted.Count) -ForegroundColor Yellow
        if (-not (Ask-YesNo '确认这些删除是正确的，继续提交？')) {
            Write-Host ''
            Write-Host '  已取消，Git 状态未改变。' -ForegroundColor Gray
            exit $exitOk
        }
    }

    if (-not (Ask-YesNo '是否暂存并提交以上变更？')) {
        Write-Host ''
        Write-Host '  已取消，Git 状态未改变。' -ForegroundColor Gray
        exit $exitOk
    }

    if ($DryRun) {
        Write-Host ''
        Write-Ok '只读模式：跳过 add / commit / push。'
        exit $exitOk
    }

    # 5.1 暂存（分块，避免命令行过长）
    $allAdd = @($addPaths | Select-Object -Unique)
    $chunkSize = 80
    $addErr = $null
    for ($start = 0; $start -lt $allAdd.Count; $start += $chunkSize) {
        $end = [Math]::Min($start + $chunkSize - 1, $allAdd.Count - 1)
        $chunk = @($allAdd[$start..$end])
        $addResult = Invoke-Git -Arguments (@('add', '-A', '--') + $chunk) -AllowFail $true
        if ($addResult.Code -ne 0) { $addErr = $addResult; break }
    }
    if ($addErr) {
        Write-Bad '暂存失败：'
        $addErr.Output | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        exit $exitFail
    }

    # 5.2 暂存后复查：只检查会真正进入提交的条目（新增/修改/重命名）
    $stagedRes = Invoke-GitBytes @('diff', '--cached', '--name-status', '-z')
    if ($stagedRes.Code -ne 0) {
        Write-Bad '无法读取暂存区，已停止（未提交）。'
        exit $exitFail
    }
    $stagedParts = Split-GitNul $stagedRes.Text
    $stagedContent = @()      # 真正会进入提交的条目（新增/修改/重命名）
    $stagedCount = 0
    $j = 0
    while ($j -lt $stagedParts.Count) {
        $st = [string]$stagedParts[$j]
        $j++
        if ($st.Length -lt 2) { continue }
        $stagedCount++
        $code = $st.Substring(0, 1)
        $isR = ($code -eq 'R' -or $code -eq 'C')
        $pathA = ''
        if ($j -lt $stagedParts.Count) { $pathA = [string]$stagedParts[$j]; $j++ }
        if ($isR -and $j -lt $stagedParts.Count) { $pathA = [string]$stagedParts[$j]; $j++ }
        if ($code -eq 'D' -or -not $pathA) { continue }
        $stagedContent += [pscustomobject]@{ Code = $code; Path = $pathA }
    }

    if ($stagedCount -eq 0) {
        Write-Bad '暂存区为空，未执行提交。'
        exit $exitFail
    }
    Write-Info ("已暂存 {0} 个文件" -f $stagedCount)

    $stagedProblems = @()
    foreach ($item in $stagedContent) {
        $p = $item.Path
        $reason = Test-DangerousPath $p
        if ($reason) { $stagedProblems += ("{0}  ← {1}" -f $p, $reason); continue }
        if ($item.Code -eq 'A' -and (Test-IgnoredPath $p -IncludeTracked)) {
            $stagedProblems += ("{0}  ← 被忽略的文件进入了暂存区" -f $p)
            continue
        }
        foreach ($h in (Test-FileContent -Path $p -Stage 'index')) { $stagedProblems += $h }
    }
    if ($stagedProblems.Count -gt 0) {
        Write-Bad '暂存区复查未通过，已撤销暂存：'
        foreach ($d in $stagedProblems) { Write-Host ("    {0}" -f $d) -ForegroundColor Red }
        Invoke-Git -Arguments @('reset') -AllowFail $true | Out-Null
        Write-Host '  已把文件退回未暂存状态，未创建提交。' -ForegroundColor Yellow
        exit $exitFail
    }
    Write-Ok '暂存区复查通过（路径 / 忽略 / 内容 / 体积）'

    # 5.3 提交
    $commitResult = Invoke-Git -Arguments @('commit', '-m', $message) -AllowFail $true
    if ($commitResult.Code -ne 0) {
        Write-Bad '提交失败：'
        $commitResult.Output | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        exit $exitFail
    }
    $newHead = Get-GitText @('rev-parse', 'HEAD')
    Write-Ok "提交成功：$($newHead.Substring(0,7))  $message"
    }

    # ---------------------------------------------------------- 推送
    Write-Section '推送 GitHub'

    if ($noChanges) {
        Write-Info '本次没有新建提交，只处理尚未推送的提交。'
    }

    $countAfter = Get-GitText @('rev-list', '--count', "$remoteMainSha..HEAD") -AllowFail $true
    if ($remoteMainSha -and $countAfter -match '^\d+$') { $ahead = [int]$countAfter }
    elseif (-not $remoteMainSha) {
        $c = Get-GitText @('rev-list', '--count', 'HEAD') -AllowFail $true
        if ($c -match '^\d+$') { $ahead = [int]$c }
    }

    # 工作区干净且本地没有领先提交：确实无事可做
    if ($noChanges -and $ahead -le 0) {
        Write-Host ''
        Write-Ok '本地与远端一致，没有待推送的提交。'
        Write-Host '  无需操作，正常退出。' -ForegroundColor Gray
        exit $exitOk
    }

    Write-Info "分支：$branch"
    Write-Info "远端：origin  $displayUrl"
    Write-Info "尚未推送的提交数：$ahead"
    Write-Host '  最近提交：' -ForegroundColor White
    (Get-GitText @('log', '--oneline', '-3') -split "`n") | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }

    if ($DryRun) {
        Write-Host ''
        Write-Ok '只读模式：跳过推送。'
        exit $exitOk
    }

    # 5.4 公开仓库推送确认（恢复 myLedger 的可见性保护）
    $visibility = Get-RemoteVisibility $remoteUrl
    switch ($visibility) {
        'public'  { Write-Info '仓库可见性：公开' }
        'private' { Write-Info '仓库可见性：私有' }
        'local'   { Write-Info '仓库可见性：本地' }
        default   { Write-Info '仓库可见性：无法确认' }
    }

    if ($visibility -eq 'public') {
        Write-Host ''
        Write-Warn 'origin 是公开的 GitHub 仓库。推送会把本次提交的全部内容发布到互联网。'
        if (-not (Ask-YesNo '确认向公开仓库推送？')) {
            Write-Host ''
            Write-Host '  已取消推送。本地提交保留，远端未更新。' -ForegroundColor Gray
            exit $exitUnpushed
        }
    }
    elseif ($visibility -eq 'unknown') {
        Write-Host ''
        Write-Warn '无法确认 origin 是否为公开仓库（GitHub API 不可用或未取到凭据）。'
        Write-Host '  如果它是公开仓库，推送会把内容发布到互联网。' -ForegroundColor Yellow
        if (-not (Ask-YesNo '仍要推送？')) {
            Write-Host ''
            Write-Host '  已取消推送。本地提交保留，远端未更新。' -ForegroundColor Gray
            exit $exitUnpushed
        }
    }

    if (-not (Ask-YesNo '是否推送到 GitHub？')) {
        Write-Host ''
        Write-Host '  已取消推送。本地提交保留，远端未更新。' -ForegroundColor Gray
        exit $exitUnpushed
    }

    # 5.5 推送（永远不用 --force）
    $pushResult = Invoke-Git -Arguments @('push', 'origin', "HEAD:refs/heads/$branch") -AllowFail $true
    if ($pushResult.Code -ne 0) {
        Write-Bad '推送失败：'
        $pushResult.Output | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        Write-Host ''
        Write-Host "  本地提交仍在（$($newHead.Substring(0,7))），没有被撤销。" -ForegroundColor Yellow
        Write-Host '  常见原因：远端有新提交、凭据失效、网络不通。' -ForegroundColor Yellow
        Write-Host "  处理后可手动重跑本工具，或执行：git push origin $branch" -ForegroundColor DarkGray
        exit $exitFail
    }
    $pushResult.Output | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }

    Write-Host ''
    Write-Host ('=' * 64) -ForegroundColor DarkCyan
    Write-Host '  完成' -ForegroundColor Green
    Write-Host ('=' * 64) -ForegroundColor DarkCyan
    Write-Info "本地修订：$($newHead.Substring(0,7))"
    Write-Info "远端分支：origin/$branch"
    exit $exitOk
}
catch {
    Write-Host ''
    Write-Bad ("执行中断：{0}" -f $_.Exception.Message)
    Write-Host ''
    Write-Host '  未执行强制推送、重置或覆盖远端。请检查上方信息后重试。' -ForegroundColor Yellow
    exit $exitFail
}
