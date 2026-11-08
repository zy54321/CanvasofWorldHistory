#Requires -Version 5.1
<#
.SYNOPSIS
    Canvas of World History —— 制作 Release（BAT 02 的实际逻辑）

.DESCRIPTION
    流程：前置检查 → 版本识别 → Y/N 选版本 → 构建 → 组装 → 清单与校验 → Tag → 归档 → 推送

    硬性约束：
      - 已有版本目录绝不覆盖；
      - **先打 Tag、成功后才归档**：取消 Tag 或 Tag 失败都不会在正式目录留下包，
        避免出现「没有 Tag 却被当作正式 Release」的假成功；
      - 任一构建/校验环节失败都不产出正式 Release，临时目录会被清理；
      - 不切换分支、不 reset、不 rebase、不 force push；
      - 构建产物不含任何真实密钥。

.PARAMETER RepoRoot
    执行 Git 操作的仓库根。缺省为脚本所在项目的根目录。
    测试时可指向临时仓库，以验证 Tag 流程而不影响真实仓库。

.PARAMETER ReleaseRoot
    正式 Release 归档根目录。

.PARAMETER ProdRoot
    生产部署根，用于读取 current.json 判断当前生产版本（可能不存在）。

.PARAMETER DryRun
    只做检查与版本识别，不构建、不打包、不打 Tag。

.PARAMETER SkipTag
    跳过 Git Tag 环节（仍然构建并归档）。

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\release\git-release.ps1
#>
[CmdletBinding()]
param(
    [string]$RepoRoot,
    [string]$ReleaseRoot = 'E:\01_Work\03_Release\01_Personal\CanvasofWorldHistory',
    [string]$ProdRoot = 'E:\01_Work\04_Prod\01_Personal\CanvasofWorldHistory',
    [switch]$DryRun,
    [switch]$SkipTag,

    # 仅供临时测试仓库使用：跳过「分支必须是 main 且 HEAD 已推送到 origin/main」的检查。
    # 正式发布不得加这个参数。
    [switch]$AllowNonMainBranch
)

$ErrorActionPreference = 'Stop'
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch { }

# ------------------------------------------------------------------ 输出
function Write-Title([string]$Text) {
    Write-Host ''
    Write-Host ('=' * 68) -ForegroundColor DarkCyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ('=' * 68) -ForegroundColor DarkCyan
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

# ------------------------------------------------------------------ Git
function Format-GitLine {
    param($Item)
    if ($Item -is [System.Management.Automation.ErrorRecord]) { return $Item.Exception.Message }
    return "$Item"
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [bool]$AllowFail = $false
    )
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

# ------------------------------------------------------------------ 交互
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

# ------------------------------------------------------------------ 版本
function ConvertTo-Version {
    param([string]$Text)
    if ($Text -match '^v?(\d+)\.(\d+)\.(\d+)$') {
        return [pscustomobject]@{
            Major = [int]$Matches[1]; Minor = [int]$Matches[2]; Patch = [int]$Matches[3]
        }
    }
    return $null
}
function Format-Version {
    param($V)
    return ("{0}.{1}.{2}" -f $V.Major, $V.Minor, $V.Patch)
}
function Get-HighestVersion {
    param([string[]]$Texts)
    $parsed = @()
    foreach ($t in $Texts) {
        $v = ConvertTo-Version ([string]$t).Trim()
        if ($v) { $parsed += $v }
    }
    if ($parsed.Count -eq 0) { return $null }
    return ($parsed | Sort-Object Major, Minor, Patch | Select-Object -Last 1)
}

# 校验一个已归档的 Release 目录：SHA256SUMS.txt 里每个文件都必须存在且哈希一致。
# 只读，不修复、不重写任何文件。
function Test-PackageIntegrity {
    param([Parameter(Mandatory = $true)][string]$PackageDir)
    $problems = New-Object System.Collections.Generic.List[string]

    $sumsPath = Join-Path $PackageDir 'SHA256SUMS.txt'
    if (-not (Test-Path -LiteralPath $sumsPath)) {
        return @('缺少 SHA256SUMS.txt')
    }
    $lines = @([System.IO.File]::ReadAllLines($sumsPath) | Where-Object { $_.Trim() -ne '' })
    if ($lines.Count -eq 0) { return @('SHA256SUMS.txt 为空') }

    foreach ($line in $lines) {
        $m = [regex]::Match($line, '^([0-9a-fA-F]{64})\s+\*?(.+)$')
        if (-not $m.Success) {
            [void]$problems.Add("校验和格式异常：$line")
            continue
        }
        $expected = $m.Groups[1].Value.ToLower()
        $rel = $m.Groups[2].Value.Trim()
        $full = Join-Path $PackageDir ($rel -replace '/', '\')
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
            [void]$problems.Add("缺少文件：$rel")
            continue
        }
        $actual = (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLower()
        if ($actual -ne $expected) { [void]$problems.Add("校验和不符：$rel") }
    }
    return @($problems)
}

# ------------------------------------------------------------------ 外部命令
function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [string[]]$Arguments = @(),
        [Parameter(Mandatory = $true)][string]$WorkDir,
        [Parameter(Mandatory = $true)][string]$LogPath
    )
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $prevLoc = (Get-Location).Path
    try {
        Set-Location -LiteralPath $WorkDir
        & $Exe @Arguments *> $LogPath
        $code = $LASTEXITCODE
    }
    finally {
        Set-Location -LiteralPath $prevLoc
        $ErrorActionPreference = $prevEap
    }
    return $code
}

# ================================================================== 主流程
$exitOk = 0
$exitFail = 1
$stageDir = $null

try {
    # ---------------------------------------------------------- 0. 定位
    $scriptDir = $PSScriptRoot
    if ([string]::IsNullOrWhiteSpace($scriptDir)) {
        $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    $projectRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)   # scripts/release → 项目根

    $repo = $RepoRoot
    if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $projectRoot }
    $repo = (Resolve-Path -LiteralPath $repo).Path

    if (-not (Test-Path (Join-Path $repo '.git'))) {
        Write-Title '制作 Release'
        Write-Bad "不是 Git 仓库根目录：$repo"
        exit $exitFail
    }

    $frontendDir = Join-Path $projectRoot 'code\frontend'
    $backendDir = Join-Path $projectRoot 'code\backend'

    Set-Location -LiteralPath $repo

    Write-Title '制作 Release'
    if ($DryRun) { Write-Warn '只读模式（-DryRun）：不构建、不打包、不打 Tag' }
    if ($SkipTag) { Write-Warn '已指定 -SkipTag：本次不会创建 Git Tag' }
    Write-Info "仓库：$repo"
    Write-Info "构建源：$projectRoot"
    Write-Info "Release 归档：$ReleaseRoot"

    # ---------------------------------------------------------- 1. 前置检查
    Write-Section '1/7 前置检查'

    $branch = Get-GitText @('rev-parse', '--abbrev-ref', 'HEAD')
    $headSha = Get-GitText @('rev-parse', 'HEAD')
    $headShort = Get-GitText @('rev-parse', '--short', 'HEAD')
    $headSubject = Get-GitText @('log', '-1', '--format=%s')

    Write-Info "分支：$branch"
    Write-Info "HEAD：$headShort  $headSubject"

    $statusLines = @((Invoke-Git -Arguments @('status', '--porcelain', '-uall')).Output |
        Where-Object { -not [string]::IsNullOrWhiteSpace("$_") })
    if ($statusLines.Count -gt 0) {
        Write-Bad ("工作区不干净：{0} 项未提交变更。" -f $statusLines.Count)
        Write-Host '  正式 Release 必须来自已提交的状态。请先运行 01_提交GitHub.bat。' -ForegroundColor Yellow
        Write-Host '  脚本不会自动提交或清理工作区。' -ForegroundColor Yellow
        exit $exitFail
    }
    Write-Ok '工作区干净'

    # 与远端同步 + 读取远端 Tag：只联网一次（只读，不写本地引用）
    $remoteUrl = Get-GitText @('remote', 'get-url', 'origin') -AllowFail $true
    $remoteMainSha = ''
    $remoteTags = @()
    $remoteOk = $false
    if ([string]::IsNullOrWhiteSpace($remoteUrl)) {
        Write-Warn '未配置 origin 远端，后续无法推送 Tag'
    } else {
        Write-Info "远端：$remoteUrl"
        $lsRemote = Invoke-Git -Arguments @('ls-remote', '--heads', '--tags', 'origin') -AllowFail $true
        if ($lsRemote.Code -ne 0) {
            Write-Warn '读取远端状态失败（网络或凭据不可用）'
        } else {
            $remoteOk = $true
            foreach ($line in $lsRemote.Output) {
                $ln = "$line"
                if ($ln -match 'refs/heads/main$') {
                    if ($ln -match '^([0-9a-f]{40})') { $remoteMainSha = $Matches[1] }
                }
                elseif ($ln -match 'refs/tags/(.+?)(\^\{\})?$') {
                    $remoteTags += $Matches[1]
                }
            }
            $remoteTags = @($remoteTags | Sort-Object -Unique)

            if ($remoteMainSha) {
                if ($remoteMainSha -eq $headSha) {
                    Write-Info '远端 main：与本地 HEAD 一致'
                }
                else {
                    $remoteIsAncestor = (Invoke-Git -Arguments @('merge-base', '--is-ancestor', $remoteMainSha, 'HEAD') -AllowFail $true).Code -eq 0
                    $localIsAncestor = (Invoke-Git -Arguments @('merge-base', '--is-ancestor', 'HEAD', $remoteMainSha) -AllowFail $true).Code -eq 0
                    if (-not $remoteIsAncestor -and -not $localIsAncestor) {
                        Write-Bad '本地与远端 main 已分叉，已停止。'
                        Write-Host '  脚本不会合并、rebase 或强推。' -ForegroundColor Yellow
                        exit $exitFail
                    }
                    if ($localIsAncestor) {
                        Write-Bad '远端 main 比本地更新，请先同步再制作 Release。'
                        Write-Info "本地 HEAD : $headSha"
                        Write-Info "远端 main : $remoteMainSha"
                        exit $exitFail
                    }
                    $aheadCount = Get-GitText @('rev-list', '--count', "$remoteMainSha..HEAD") -AllowFail $true
                    Write-Warn "有 $aheadCount 个本地提交尚未推送"
                }
            }
            else {
                Write-Warn '远端还没有 main 分支'
            }
        }
    }

    # 发布来源检查（正式模式强制）
    if ($AllowNonMainBranch) {
        Write-Warn '已指定 -AllowNonMainBranch：跳过发布分支检查（仅限测试仓库）'
    } else {
        if ($branch -ne 'main') {
            Write-Bad "正式发布必须在 main 分支上进行，当前分支：$branch"
            Write-Host ''
            Write-Host '  本脚本不会自动切换、合并或推送分支。请自行决定并手动处理，例如：' -ForegroundColor Yellow
            Write-Host '    git checkout -b main origin/main    # 若本地还没有 main' -ForegroundColor DarkGray
            Write-Host '    git checkout main                   # 若已有 main 且与 origin/main 一致' -ForegroundColor DarkGray
            exit $exitFail
        }
        if (-not $remoteOk) {
            Write-Bad '无法读取远端状态，正式发布要求 HEAD 已推送到 origin/main。'
            Write-Host '  请先确认网络与凭据，再重新运行。' -ForegroundColor Yellow
            exit $exitFail
        }
        if ([string]::IsNullOrWhiteSpace($remoteMainSha)) {
            Write-Bad '远端没有 main 分支，无法确认发布来源。'
            exit $exitFail
        }
        if ($remoteMainSha -ne $headSha) {
            Write-Bad 'HEAD 与 origin/main 不一致，正式发布必须基于已推送的提交。'
            Write-Info "HEAD        : $headSha"
            Write-Info "origin/main : $remoteMainSha"
            Write-Host ''
            Write-Host '  可能是本地提交尚未推送，或远端领先。请先处理同步，再重新运行。' -ForegroundColor Yellow
            exit $exitFail
        }
        Write-Ok '发布来源确认：分支 main，HEAD 与 origin/main 一致'
    }

    # 工具链
    # 注意：java -version 的输出走 stderr，在 Stop 模式下会被转成终止性错误，
    # 必须先降为 Continue 并做字符串化，否则这里永远拿到空值。
    $jdkVer = ''
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $jdkRaw = & java -version 2>&1 | Select-Object -First 1
        $jdkVer = (Format-GitLine $jdkRaw) -replace '"', ''
    }
    catch { }
    finally { $ErrorActionPreference = $prevEap }
    if ([string]::IsNullOrWhiteSpace($jdkVer)) { Write-Bad '未找到 java（或无法执行）'; exit $exitFail }
    Write-Info "JDK：$jdkVer"

    $mvnwCmd = Join-Path $backendDir 'mvnw.cmd'
    if (-not (Test-Path $mvnwCmd)) {
        Write-Bad "未找到 Maven Wrapper：$mvnwCmd"
        exit $exitFail
    }
    Write-Ok 'Maven Wrapper 存在（不依赖系统 PATH）'

    $nodeVer = ''
    $npmVer = ''
    $ErrorActionPreference = 'Continue'
    try {
        $nodeVer = (Format-GitLine (& node -v 2>&1 | Select-Object -First 1)).Trim()
        $npmVer = (Format-GitLine (& npm -v 2>&1 | Select-Object -First 1)).Trim()
    }
    catch { }
    finally { $ErrorActionPreference = $prevEap }
    if ([string]::IsNullOrWhiteSpace($nodeVer)) { Write-Bad '未找到 node'; exit $exitFail }
    Write-Info "Node：$nodeVer   npm：$npmVer"

    # ---------------------------------------------------------- 2. 版本识别
    Write-Section '2/7 版本识别'

    # 远端 Tag（已在 1/7 的 ls-remote 中一并取回，不重复联网）
    if (-not $remoteOk) {
        Write-Warn '读取远端 Tag 失败（网络或远端不可用）'
    }

    # 本地 Tag
    $localTags = @((Invoke-Git -Arguments @('tag', '-l')).Output | Where-Object { "$_".Trim() -ne '' } | ForEach-Object { "$_".Trim() })

    # 本地 Release 目录
    $localReleases = @()
    if (Test-Path -LiteralPath $ReleaseRoot) {
        $localReleases = @(Get-ChildItem -LiteralPath $ReleaseRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^\d+\.\d+\.\d+$' } | ForEach-Object { $_.Name })
    }

    # 生产版本记录
    $prodVersion = $null
    $prodRecord = Join-Path $ProdRoot 'current.json'
    if (Test-Path -LiteralPath $prodRecord) {
        try {
            $j = Get-Content -LiteralPath $prodRecord -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($j.releaseVersion) { $prodVersion = [string]$j.releaseVersion }
        } catch {
            Write-Warn "无法解析生产版本记录：$prodRecord"
        }
    }

    $highestRemote = Get-HighestVersion $remoteTags
    $highestLocal = Get-HighestVersion $localReleases

    $remoteText = if ($highestRemote) { 'v' + (Format-Version $highestRemote) } else { '（无）' }
    $localText = if ($highestLocal) { Format-Version $highestLocal } else { '（无）' }
    $prodText = if ($prodVersion) { $prodVersion } else { '（无记录）' }

    Write-Info "最近一次正式 Release（远端 Tag）：$remoteText"
    Write-Info "本地 Release 目录最高版本：$localText"
    Write-Info "当前 Prod 版本：$prodText"
    Write-Info "本地 Tag 数量：$($localTags.Count)"

    # ---------------------------------------------------------- 续传未完成的 Release
    # 场景：上次制作时 Tag 已创建、包已归档，但 Tag 推送失败或被取消（远端没有该 Tag）。
    # 这种状态会被下面的版本一致性检查误判为「来源不一致」而永久阻断。
    # 这里先单独识别：只补推 Tag，不重建、不重新打包、不重复打 Tag、不覆盖已有归档。
    $pendingVersions = @()
    foreach ($v in $localReleases) {
        $t = "v$v"
        if (($localTags -contains $t) -and ($remoteTags -notcontains $t)) { $pendingVersions += [string]$v }
    }

    if ($pendingVersions.Count -gt 0) {
        Write-Section '续传未完成的 Release'

        if ($pendingVersions.Count -gt 1) {
            Write-Bad ('发现 {0} 个「本地有 Tag、远端无 Tag」的版本：{1}' -f $pendingVersions.Count, ($pendingVersions -join ', '))
            Write-Host '  状态不唯一，脚本不猜测、不自动处理，请人工核对后再运行。' -ForegroundColor Yellow
            exit $exitFail
        }

        $pendingVersion = [string]$pendingVersions[0]
        $pendingTag = "v$pendingVersion"
        $pendingDir = Join-Path $ReleaseRoot $pendingVersion

        $problems = New-Object System.Collections.Generic.List[string]
        $manifest = $null

        if (-not (Test-Path -LiteralPath $pendingDir)) {
            [void]$problems.Add("归档目录不存在：$pendingDir")
        }
        else {
            $manifestPath = Join-Path $pendingDir 'manifest.json'
            if (-not (Test-Path -LiteralPath $manifestPath)) {
                [void]$problems.Add('归档目录缺少 manifest.json')
            }
            else {
                try { $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json }
                catch { [void]$problems.Add('manifest.json 无法解析') }
            }
            foreach ($item in (Test-PackageIntegrity -PackageDir $pendingDir)) { [void]$problems.Add([string]$item) }
        }

        if ($manifest) {
            if ([string]$manifest.releaseVersion -ne $pendingVersion) {
                [void]$problems.Add("manifest 版本 $($manifest.releaseVersion) 与目录 $pendingVersion 不一致")
            }
            if ([string]$manifest.gitTag -ne $pendingTag) {
                [void]$problems.Add("manifest Tag $($manifest.gitTag) 与 $pendingTag 不一致")
            }
        }

        $tagCommit = Get-GitText @('rev-list', '-n', '1', $pendingTag) -AllowFail $true
        if ([string]::IsNullOrWhiteSpace($tagCommit)) {
            [void]$problems.Add("无法读取本地 Tag $pendingTag")
        }
        elseif ($manifest -and ([string]$manifest.gitCommit -ne $tagCommit)) {
            [void]$problems.Add("Tag 指向 $tagCommit，manifest 记录 $($manifest.gitCommit)")
        }

        # Tag 指向的提交必须在远端 main 上，否则补推会留下一个远端无法追溯的版本
        if (-not [string]::IsNullOrWhiteSpace($tagCommit) -and -not [string]::IsNullOrWhiteSpace($remoteMainSha)) {
            $onRemote = (Invoke-Git -Arguments @('merge-base', '--is-ancestor', $tagCommit, $remoteMainSha) -AllowFail $true).Code -eq 0
            if (-not $onRemote) {
                [void]$problems.Add("Tag 指向的提交不在远端 main 上（$($tagCommit.Substring(0, 7))）")
            }
        }

        if ($problems.Count -gt 0) {
            Write-Bad '续传校验未通过，已停止（不自动修复、不删除任何东西）：'
            foreach ($item in $problems) { Write-Host ("    {0}" -f $item) -ForegroundColor Red }
            Write-Host ''
            Write-Host '  请人工核对上述项目后再运行本工具。' -ForegroundColor Yellow
            exit $exitFail
        }

        Write-Ok '校验通过：包完整性、Manifest、Tag 与提交对应关系'
        Write-Info "版本：$pendingVersion"
        Write-Info "归档目录：$pendingDir"
        Write-Info "本地 Tag：$pendingTag → $($tagCommit.Substring(0, 7))"
        Write-Info '远端 Tag：无'
        Write-Host ''
        Write-Host '  此步骤只补推 Tag：不重新构建、不重新打包、不重复创建 Tag。' -ForegroundColor Gray

        if (-not (Ask-YesNo "是否补推 Tag $pendingTag 到 origin？")) {
            Write-Host ''
            Write-Warn '已取消。该 Release 仍处于「未推送」状态：包与本地 Tag 都在，远端没有记录。'
            Write-Host "  之后重新运行本工具即可继续，或手动执行：git push origin $pendingTag" -ForegroundColor DarkGray
            exit $exitOk
        }

        $resumePush = Invoke-Git -Arguments @('push', 'origin', $pendingTag) -AllowFail $true
        if ($resumePush.Code -ne 0) {
            Write-Bad '补推 Tag 失败：'
            $resumePush.Output | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
            Write-Host ''
            Write-Warn '远端仍没有该 Tag，Release 未完成。包与本地 Tag 保持原样，可再次运行本工具重试。' -ForegroundColor Yellow
            exit $exitFail
        }
        $resumePush.Output | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
        Write-Host ''
        Write-Ok "补推完成：$pendingTag 已存在于 origin"
        Write-Info "包：$pendingDir"
        Write-Info ('文件 {0} 个' -f (Get-ChildItem -LiteralPath $pendingDir -Recurse -File).Count)
        exit $exitOk
    }

    # 一致性：远端 Tag 与本地目录不一致时停止（首次两者都为空才允许继续）
    $rText = if ($highestRemote) { Format-Version $highestRemote } else { '' }
    $lText = if ($highestLocal) { Format-Version $highestLocal } else { '' }
    if ($rText -ne $lText) {
        Write-Bad '版本来源不一致，已停止：'
        Write-Info "远端最高 Tag：$(if($rText){$rText}else{'无'})"
        Write-Info "本地最高目录：$(if($lText){$lText}else{'无'})"
        Write-Host '  请先人工核对（例如补齐归档目录或确认 Tag 是否应存在），脚本不猜测、不自动修复。' -ForegroundColor Yellow
        exit $exitFail
    }

    # ---------------------------------------------------------- 3. 选择版本
    Write-Section '3/7 选择版本'

    $base = if ($highestRemote) { $highestRemote } elseif ($highestLocal) { $highestLocal } else { $null }

    if (-not $base) {
        Write-Info '这是首次制作 Release（远端与本机都没有任何版本）。'
        Write-Info '按 V1.0 交付状态，建议首次版本为 1.0.0。'
        $candidate = [pscustomobject]@{ Major = 1; Minor = 0; Patch = 0 }
        $label = '首次版本 1.0.0'
        if (-not (Ask-YesNo "使用首次版本 v1.0.0？")) {
            Write-Host ''
            Write-Host '  已取消，未做任何构建或改动。' -ForegroundColor Gray
            exit $exitOk
        }
        $finalVersion = $candidate
    } else {
        $patchV = [pscustomobject]@{ Major = $base.Major; Minor = $base.Minor; Patch = $base.Patch + 1 }
        $minorV = [pscustomobject]@{ Major = $base.Major; Minor = $base.Minor + 1; Patch = 0 }
        $majorV = [pscustomobject]@{ Major = $base.Major + 1; Minor = 0; Patch = 0 }

        Write-Host ''
        Write-Host "  当前基线：v$(Format-Version $base)" -ForegroundColor White
        if (-not (Ask-YesNo "使用建议版本 v$(Format-Version $patchV)（PATCH+1）？")) {
            if (-not (Ask-YesNo "改用 MINOR 版本 v$(Format-Version $minorV)？")) {
                if (-not (Ask-YesNo "改用 MAJOR 版本 v$(Format-Version $majorV)？")) {
                    Write-Host ''
                    Write-Host '  已取消，未做任何构建或改动。' -ForegroundColor Gray
                    exit $exitOk
                }
                $finalVersion = $majorV
            } else {
                $finalVersion = $minorV
            }
        } else {
            $finalVersion = $patchV
        }
    }

    $versionText = Format-Version $finalVersion
    $tagName = "v$versionText"
    $targetDir = Join-Path $ReleaseRoot $versionText

    Write-Ok "选定版本：v$versionText"
    Write-Info "Tag：$tagName"
    Write-Info "目标目录：$targetDir"

    # 不覆盖已存在版本
    if (Test-Path -LiteralPath $targetDir) {
        Write-Bad "目标目录已存在，拒绝覆盖：$targetDir"
        exit $exitFail
    }
    if ($localTags -contains $tagName) {
        Write-Bad "本地已存在 Tag $tagName，拒绝重复制作。"
        exit $exitFail
    }
    if ($remoteTags -contains $tagName) {
        Write-Bad "远端已存在 Tag $tagName，拒绝重复制作。"
        exit $exitFail
    }

    if ($DryRun) {
        Write-Host ''
        Write-Ok '只读模式：检查与版本识别均通过，未执行构建。'
        exit $exitOk
    }

    # ---------------------------------------------------------- 4. 构建
    Write-Section '4/7 构建'

    $tmpRoot = Join-Path $env:TEMP ("canvas-release-" + $versionText + "-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
    New-Item -ItemType Directory -Path $tmpRoot -Force | Out-Null
    $stageDir = $tmpRoot

    # 4a 前端：剥离密钥
    Write-Step '前端构建（npm run build，构建期剥离 MapTiler key）'
    $webLog = Join-Path $tmpRoot 'web-build.log'
    $prevStrip = $env:CANVAS_STRIP_MAPTILER_KEY
    $env:CANVAS_STRIP_MAPTILER_KEY = '1'
    try {
        $webCode = Invoke-Native -Exe 'npm.cmd' -Arguments @('run', 'build') -WorkDir $frontendDir -LogPath $webLog
    }
    finally {
        if ($null -eq $prevStrip) { Remove-Item Env:\CANVAS_STRIP_MAPTILER_KEY -ErrorAction SilentlyContinue }
        else { $env:CANVAS_STRIP_MAPTILER_KEY = $prevStrip }
    }
    if ($webCode -ne 0) {
        Write-Bad "前端构建失败（退出码 $webCode），日志末尾："
        Get-Content -LiteralPath $webLog -Tail 20 | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        throw '前端构建失败'
    }
    $distDir = Join-Path $frontendDir 'dist'
    if (-not (Test-Path (Join-Path $distDir 'index.html'))) {
        throw "前端构建未产出 dist/index.html"
    }
    $distFiles = @(Get-ChildItem -LiteralPath $distDir -Recurse -File)
    Write-Ok ("前端构建成功：{0} 个文件，{1:N1} MB" -f $distFiles.Count, (($distFiles | Measure-Object Length -Sum).Sum / 1MB))

    # 4b 后端：单 Jar（含前端）
    Write-Step '后端构建（mvnw -Pwith-web clean package）'
    $apiLog = Join-Path $tmpRoot 'api-build.log'
    $apiCode = Invoke-Native -Exe $mvnwCmd -Arguments @('-B', '-DskipTests', '-Pwith-web', 'clean', 'package') -WorkDir $backendDir -LogPath $apiLog
    if ($apiCode -ne 0) {
        Write-Bad "后端构建失败（退出码 $apiCode），日志末尾："
        Get-Content -LiteralPath $apiLog -Tail 25 | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        throw '后端构建失败'
    }
    $jarPath = Join-Path $backendDir 'target\canvas-history-api.jar'
    if (-not (Test-Path -LiteralPath $jarPath)) { throw '未找到构建产物 canvas-history-api.jar' }
    $jarInfo = Get-Item -LiteralPath $jarPath
    Write-Ok ("后端构建成功：{0:N1} MB" -f ($jarInfo.Length / 1MB))

    # 4c 校验单 Jar 内确实带前端
    $jarStatic = & jar tf $jarPath 2>&1 | Select-String -Pattern 'BOOT-INF/classes/static/index.html'
    if (-not $jarStatic) {
        throw '构建出的 jar 不含前端资源（static/index.html 缺失），单 Jar 打包未生效'
    }
    Write-Ok '单 Jar 校验通过：jar 内含 static/index.html'

    # ---------------------------------------------------------- 5. 组装
    Write-Section '5/7 组装 Release'

    $pkg = Join-Path $tmpRoot 'pkg'
    $dirs = @(
        (Join-Path $pkg 'api'),
        (Join-Path $pkg 'db\migration'),
        (Join-Path $pkg 'deploy'),
        (Join-Path $pkg 'config'),
        (Join-Path $pkg 'docs')
    )
    foreach ($d in $dirs) { New-Item -ItemType Directory -Path $d -Force | Out-Null }

    Copy-Item -LiteralPath $jarPath -Destination (Join-Path $pkg 'api\canvas-history-api.jar')
    Write-Step '已放入 api/canvas-history-api.jar'

    $migrationDir = Join-Path $backendDir 'src\main\resources\db\migration'
    # 按迁移编号的数字大小排序，避免 V10 排在 V2 前面
    $migrations = @(Get-ChildItem -LiteralPath $migrationDir -Filter 'V*.sql' -File |
        Sort-Object { if ($_.Name -match '^V(\d+)__') { [int]$Matches[1] } else { [int]::MaxValue } })
    foreach ($m in $migrations) { Copy-Item -LiteralPath $m.FullName -Destination (Join-Path $pkg 'db\migration') }
    Write-Step ("已放入 db/migration：{0} 个迁移" -f $migrations.Count)

    $tplDir = Join-Path $scriptDir 'templates'
    foreach ($t in @('docker-compose.prod.yml', 'start-api.bat', 'start-api.sh', 'flyway.sh', 'publish-prod.ps1', 'prod-status.ps1', 'Dockerfile.app', 'docker-compose.app.prod.yml', 'publish-container.ps1', 'README-Docker-PROD.md')) {
        $src = Join-Path $tplDir $t
        if (-not (Test-Path -LiteralPath $src)) { throw "缺少模板：$src" }
        Copy-Item -LiteralPath $src -Destination (Join-Path $pkg 'deploy')
    }
    Write-Step '已放入 deploy/（compose、启动脚本、flyway、发布脚本、状态脚本）'

    # 包根的只读状态入口（对标 myLedger 的 runtime/status.bat）
    $statusBat = Join-Path $tplDir '04_查看Prod状态.bat'
    if (-not (Test-Path -LiteralPath $statusBat)) { throw "缺少模板：$statusBat" }
    Copy-Item -LiteralPath $statusBat -Destination $pkg
    Write-Step '已放入 04_查看Prod状态.bat（只读）'

    # 发布入口放在包根：用户双击即可，不依赖 DEV 目录
    Copy-Item -LiteralPath (Join-Path $tplDir '03_发布Prod.bat') -Destination $pkg
    Write-Step '已放入包根 03_发布Prod.bat'

    Copy-Item -LiteralPath (Join-Path $tplDir 'env.example') -Destination (Join-Path $pkg 'config\.env.example')
    Copy-Item -LiteralPath (Join-Path $tplDir 'DEPLOY.md') -Destination (Join-Path $pkg 'docs\DEPLOY.md')
    Write-Step '已放入 config/.env.example 与 docs/DEPLOY.md'

    # ---------------------------------------------------------- 6. 清单与校验
    Write-Section '6/7 清单与校验'

    $flywayVersion = 0
    if ($migrations.Count -gt 0) {
        foreach ($m in $migrations) {
            if ($m.Name -match '^V(\d+)__') {
                $n = [int]$Matches[1]
                if ($n -gt $flywayVersion) { $flywayVersion = $n }
            }
        }
    }

    $pomText = Get-Content -LiteralPath (Join-Path $backendDir 'pom.xml') -Raw
    # 先剔除 <parent> 段，否则取到的是 spring-boot-starter-parent 的版本号
    $pomOwn = $pomText -replace '(?s)<parent>.*?</parent>', ''
    $pomVersion = ''
    if ($pomOwn -match '<version>([^<]+)</version>') { $pomVersion = $Matches[1].Trim() }
    $pkgJson = Get-Content -LiteralPath (Join-Path $frontendDir 'package.json') -Raw | ConvertFrom-Json

    $jarHash = (Get-FileHash -LiteralPath (Join-Path $pkg 'api\canvas-history-api.jar') -Algorithm SHA256).Hash.ToLower()
    $jarSize = (Get-Item -LiteralPath (Join-Path $pkg 'api\canvas-history-api.jar')).Length

    $manifest = [ordered]@{
        schemaVersion      = 1
        releaseVersion     = $versionText
        gitTag             = $tagName
        gitCommit          = $headSha
        gitCommitShort     = $headShort
        gitBranch          = $branch
        buildTime          = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
        deployMode         = 'single-jar-docker'
        build              = [ordered]@{
            jdk   = $jdkVer
            maven = 'wrapper 3.9.9'
            node  = "$nodeVer".Trim()
            npm   = "$npmVer".Trim()
        }
        sourceVersion      = [ordered]@{
            pom         = $pomVersion
            packageJson = $pkgJson.version
        }
        database           = [ordered]@{
            targetFlywayVersion = $flywayVersion
            migrations          = @($migrations | ForEach-Object { $_.BaseName })
        }
        artifacts          = [ordered]@{
            api = [ordered]@{ path = 'api/canvas-history-api.jar'; size = $jarSize; sha256 = $jarHash }
            web = [ordered]@{ embedded = $true; fileCount = $distFiles.Count; note = '已打入 jar 的 static/' }
        }
        security           = [ordered]@{
            containsSecrets      = $false
            maptilerKeyEmbedded  = $false
            note                 = '构建期剥离 MapTiler key，运行时由 web/config.js 注入'
        }
    }

    $manifestPath = Join-Path $pkg 'manifest.json'
    # 无 BOM 的 UTF-8：带 BOM 会让部分 JSON 解析器（含 Node 的 require、jq 旧版）报错
    $manifestJson = $manifest | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($manifestPath, $manifestJson, (New-Object System.Text.UTF8Encoding($false)))
    Write-Step '已生成 manifest.json'

    # SHA256SUMS（不含自身）
    $allFiles = @(Get-ChildItem -LiteralPath $pkg -Recurse -File | Where-Object { $_.Name -ne 'SHA256SUMS.txt' } | Sort-Object FullName)
    $lines = foreach ($f in $allFiles) {
        $rel = $f.FullName.Substring($pkg.Length + 1).Replace('\', '/')
        $h = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLower()
        "$h  $rel"
    }
    $sumsPath = Join-Path $pkg 'SHA256SUMS.txt'
    # 必须用 LF 而不是 CRLF：sha256sum -c 会把行尾的 \r 当成文件名的一部分而全部失败。
    $sumsText = (($lines -join "`n") + "`n")
    [System.IO.File]::WriteAllText($sumsPath, $sumsText, (New-Object System.Text.UTF8Encoding($false)))
    Write-Step ("已生成 SHA256SUMS.txt：{0} 个文件（LF 换行）" -f $allFiles.Count)

    # 复核
    Write-Step '复核校验和…'
    $mismatch = @()
    foreach ($f in $allFiles) {
        $rel = $f.FullName.Substring($pkg.Length + 1).Replace('\', '/')
        $expected = ($lines | Where-Object { $_ -like "*  $rel" } | Select-Object -First 1) -split '  ' | Select-Object -First 1
        $actual = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLower()
        if ($expected -ne $actual) { $mismatch += $rel }
    }
    if ($mismatch.Count -gt 0) {
        Write-Bad '校验和不一致：'
        $mismatch | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        throw '校验失败'
    }
    Write-Ok ("校验一致：{0} 个文件全部匹配" -f $allFiles.Count)

    # 必需文件
    $required = @(
        '03_发布Prod.bat',
        '04_查看Prod状态.bat',
        'manifest.json', 'SHA256SUMS.txt',
        'api/canvas-history-api.jar',
        'db/migration/V1__enable_extensions.sql',
        'deploy/docker-compose.prod.yml', 'deploy/start-api.bat', 'deploy/start-api.sh',
        'deploy/flyway.sh', 'deploy/publish-prod.ps1', 'deploy/prod-status.ps1',
        'deploy/Dockerfile.app', 'deploy/docker-compose.app.prod.yml', 'deploy/publish-container.ps1',
        'config/.env.example', 'docs/DEPLOY.md'
    )
    $missing = @()
    foreach ($r in $required) {
        if (-not (Test-Path -LiteralPath (Join-Path $pkg ($r -replace '/', '\')))) { $missing += $r }
    }
    if ($missing.Count -gt 0) {
        Write-Bad '缺少必需文件：'
        $missing | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        throw '缺少必需文件'
    }
    Write-Ok '必需文件齐全'

    # 敏感文件扫描
    $dangerPattern = '\.env$|\.env\.(dev|local|prod|test)$|\.(pem|key|p12|pfx|jks)$|\.(dump|backup|bak)$|\.sql\.gz$|\.log$|(^|/)node_modules/'
    $suspicious = @()
    foreach ($f in (Get-ChildItem -LiteralPath $pkg -Recurse -File)) {
        $rel = $f.FullName.Substring($pkg.Length + 1).Replace('\', '/')
        if ($rel -eq 'config/.env.example') { continue }
        if ($rel -match $dangerPattern) { $suspicious += $rel }
    }
    if ($suspicious.Count -gt 0) {
        Write-Bad '发布包中出现疑似敏感/临时文件：'
        $suspicious | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        throw '敏感文件检查未通过'
    }
    Write-Ok '敏感文件检查通过（无 .env / 私钥 / 备份 / 日志）'

    # 密钥扫描：确认 jar 内不含真实 MapTiler key
    $envFile = Join-Path $projectRoot 'code\.env'
    if (Test-Path -LiteralPath $envFile) {
        $realKey = ''
        foreach ($lineText in (Get-Content -LiteralPath $envFile -Encoding UTF8)) {
            if ($lineText -match '^VITE_MAPTILER_API_KEY=(.+)$') { $realKey = $Matches[1].Trim() }
        }
        if ($realKey.Length -ge 8) {
            $hits = & jar tf (Join-Path $pkg 'api\canvas-history-api.jar') 2>&1 | Select-String -Pattern 'static/assets'
            # 直接扫描 dist 目录更可靠：它就是打进 jar 的内容
            $distHit = Select-String -Path (Join-Path $distDir 'assets\*.js') -Pattern ([regex]::Escape($realKey)) -SimpleMatch -ErrorAction SilentlyContinue
            if ($distHit) {
                Write-Bad '构建产物中仍包含真实 MapTiler key！'
                throw '密钥未剥离'
            }
            Write-Ok '密钥扫描通过：构建产物不含真实 MapTiler key'
        }
    }

    $pkgSize = (Get-ChildItem -LiteralPath $pkg -Recurse -File | Measure-Object Length -Sum).Sum

    # ---------------------------------------------------------- 7. Tag 与归档
    # 顺序很关键：先打 Tag，成功后才把包放进正式目录。
    # 这样「没有 Tag 的包」不会出现在正式目录里，取消或失败都不会伪装成成功。
    Write-Section '7/7 Tag 与归档'

    if ($SkipTag) {
        # 没有 Tag 的包不是正式 Release，必须落在临时目录，绝不进入正式归档目录。
        $untaggedRoot = Join-Path $env:TEMP 'canvas-release-untagged'
        $untaggedTarget = Join-Path $untaggedRoot $versionText
        if (Test-Path -LiteralPath $untaggedTarget) { Remove-Item -LiteralPath $untaggedTarget -Recurse -Force }
        New-Item -ItemType Directory -Path $untaggedRoot -Force | Out-Null

        Copy-Item -LiteralPath $pkg -Destination $untaggedTarget -Recurse
        Write-Host ''
        Write-Warn '已指定 -SkipTag：这是一个**未打 Tag 的候选包**，不是正式 Release。'
        Write-Warn '按规则它不会写入正式归档目录，只放在临时目录。'
        Write-Info "候选包路径：$untaggedTarget"
        Write-Info "正式归档目录未产生任何内容：$ReleaseRoot"
        exit $exitOk
    }

    Write-Info "将创建 annotated tag：$tagName"
    Write-Info "指向：$headShort  $headSubject"

    if (-not (Ask-YesNo "是否创建 Git Tag $tagName？")) {
        Write-Host ''
        Write-Warn '未创建 Tag，因此不会生成正式 Release。'
        Write-Host '  临时构建目录会被清理，正式归档目录中不会留下任何东西。' -ForegroundColor Gray
        exit $exitOk
    }

    $tagMsg = "release: v$versionText`n`ncommit $headShort`nflyway V$flywayVersion`nsingle-jar"
    $tagResult = Invoke-Git -Arguments @('tag', '-a', $tagName, '-m', $tagMsg) -AllowFail $true
    if ($tagResult.Code -ne 0) {
        Write-Bad '创建 Tag 失败：'
        $tagResult.Output | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        Write-Host ''
        Write-Warn '未归档，未留下任何正式 Release。' -ForegroundColor Yellow
        exit $exitFail
    }
    Write-Ok "Tag 已创建：$tagName"

    # Tag 成功后归档
    if (Test-Path -LiteralPath $targetDir) {
        Write-Bad "目标目录在构建期间已存在，拒绝覆盖：$targetDir"
        Write-Warn '回退刚创建的 Tag，避免出现「有 Tag 无包」的不一致状态。'
        Invoke-Git -Arguments @('tag', '-d', $tagName) -AllowFail $true | Out-Null
        exit $exitFail
    }
    $parent = Split-Path -Parent $targetDir

    $archiveOk = $false
    try {
        # 父目录创建也放在 try 内：若它抛异常（路径非法、无权限），
        # finally 里的回退逻辑仍会删掉刚创建的 Tag，不留下「有 Tag 无包」。
        if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        Copy-Item -LiteralPath $pkg -Destination $targetDir -Recurse
        $archivedCount = (Get-ChildItem -LiteralPath $targetDir -Recurse -File).Count
        $archiveOk = $true
        Write-Ok "已归档：$targetDir"
        Write-Info ("文件 {0} 个，{1:N1} MB" -f $archivedCount, ($pkgSize / 1MB))
    }
    finally {
        if (-not $archiveOk) {
            Write-Bad '归档失败。'
            if (Test-Path -LiteralPath $targetDir) {
                Remove-Item -LiteralPath $targetDir -Recurse -Force -ErrorAction SilentlyContinue
            }
            Write-Warn '回退刚创建的 Tag，避免出现「有 Tag 无包」的不一致状态。'
            Invoke-Git -Arguments @('tag', '-d', $tagName) -AllowFail $true | Out-Null
        }
    }
    if (-not $archiveOk) { exit $exitFail }

    # ---------------------------------------------------------- 8. 推送 Tag
    Write-Section '推送 Tag'

    if ([string]::IsNullOrWhiteSpace($remoteUrl)) {
        Write-Warn '未配置远端，跳过推送。本地包与 Tag 均已就绪，但远端无法追溯。'
        exit $exitOk
    }

    if (-not (Ask-YesNo "是否推送 Tag $tagName 到 origin？")) {
        Write-Host ''
        Write-Bad '发布未完成：Tag 只存在于本地，远端没有任何记录。'
        Write-Host ''
        Write-Host '  当前状态：' -ForegroundColor Yellow
        Write-Host "    · 包已归档：$targetDir" -ForegroundColor Yellow
        Write-Host "    · 本地 Tag：$tagName" -ForegroundColor Yellow
        Write-Host "    · 远端 Tag：无" -ForegroundColor Yellow
        Write-Host ''
        Write-Host '  本次不计为正式发布成功。补齐远端后可继续：' -ForegroundColor Yellow
        Write-Host "    git push origin $tagName" -ForegroundColor DarkGray
        Write-Host '  不要删除归档目录，也不要重复制作同一版本。' -ForegroundColor DarkGray
        exit $exitFail
    }

    # 说明：本脚本从不删除远端 Tag（不使用 git push --delete）。
    # 本地 Tag 的删除仅发生在「归档失败」的回退路径（此时远端尚无该 Tag）。
    $pushResult = Invoke-Git -Arguments @('push', 'origin', $tagName) -AllowFail $true
    if ($pushResult.Code -ne 0) {
        Write-Bad '推送 Tag 失败：'
        $pushResult.Output | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        Write-Host ''
        Write-Warn '包已归档、本地 Tag 存在，但远端缺失 —— 该 Release 处于「未推送」状态。' -ForegroundColor Yellow
        Write-Host '  请解决网络或权限问题后重试：git push origin ' -NoNewline -ForegroundColor Yellow
        Write-Host $tagName -ForegroundColor Yellow
        Write-Host '  不要删除归档目录，也不要重复制作同一版本。' -ForegroundColor Yellow
        exit $exitFail
    }
    $pushResult.Output | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    Write-Ok "Tag 已推送：$tagName"

    Write-Host ''
    Write-Host ('=' * 68) -ForegroundColor DarkCyan
    Write-Host ("  完成：v{0}" -f $versionText) -ForegroundColor Green
    Write-Host ('=' * 68) -ForegroundColor DarkCyan
    Write-Host "  包路径：$targetDir" -ForegroundColor White
    Write-Host "  Git Tag：$tagName" -ForegroundColor White
    Write-Host "  数据库：Flyway V$flywayVersion" -ForegroundColor White
    exit $exitOk
}
catch {
    Write-Host ''
    Write-Bad ("制作中止：{0}" -f $_.Exception.Message)
    if ($stageDir -and (Test-Path -LiteralPath $stageDir)) {
        Remove-Item -LiteralPath $stageDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host '  临时构建目录已清理。' -ForegroundColor Gray
    }
    Write-Host ''
    Write-Host '  未生成正式 Release：没有归档、也没有打 Tag。' -ForegroundColor Yellow
    exit $exitFail
}
finally {
    if ($stageDir -and (Test-Path -LiteralPath $stageDir)) {
        Remove-Item -LiteralPath $stageDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
