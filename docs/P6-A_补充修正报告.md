# P6-A 补充：发布脚本最小修正报告

> 日期：2026-11-07
> 范围：仅修正发布脚本与模板，未重设发布体系
> 未执行真实 Commit / Push / Tag / Release 归档 / 生产部署

---

## 一、修改文件

| 文件 | 涉及项 |
|---|---|
| `scripts/release/git-release.ps1` | 修正 1（发布来源检查）、修正 2（完成状态） |
| `scripts/release/templates/publish-prod.ps1` | 修正 3（冒烟）、修正 4（原子写）、修正 5（取消副作用） |
| `scripts/release/templates/docker-compose.prod.yml` | 修正 6（Volume 声明） |

---

## 二、六项修正的具体做法

### 1. BAT 02 发布来源检查

新增正式模式强制检查（在 [1/7] 前置检查中，工作区干净之后）：

```
分支必须是 main
  ↓ 否 → 停止，给出切换建议，不自动切换
fetch 必须成功（否则无法确认远端状态）
  ↓ 否 → 停止
HEAD 必须与 origin/main 完全一致（SHA 相等）
  ↓ 否 → 停止，打印两个 SHA 供核对
```

新增 `-AllowNonMainBranch` 参数，**仅用于临时测试仓库**；使用时会打印醒目警告。正式模式无法通过任何参数绕过。

### 2. BAT 02 完成状态

| 场景 | 修正前 | 修正后 |
|---|---|---|
| `-SkipTag` | 直接把无 Tag 包写进正式归档目录 | 只写到 `%TEMP%\canvas-release-untagged\<版本>`，正式目录零内容，并明确标注"不是正式 Release" |
| 拒绝推送 Tag | exit 0 + 警告 | **exit 1**，标题为"发布未完成"，列出包路径 / 本地 Tag / 远端无 Tag 三项实际状态，给出 `git push origin <tag>` 恢复指引 |
| 推送失败 | exit 1（原本正确） | 保持，文案明确为"未推送状态" |
| 归档失败 | 删目录 + 回退 Tag | **保持**（P6-A 前一阶段已修：父目录创建也纳入 try 范围） |
| 删除远端 Tag | — | 代码中不存在 `push --delete`，已加注释声明从不删除远端 Tag |

### 3. BAT 03 冒烟验证

冒烟失败不再"警告后继续"：

```
关键接口失败
  → 不写 current.json
  → 不停止已启动进程（避免连带关掉可用服务）
  → 不触碰数据库
  → 打印实际状态（新版本已落在哪个目录、进程 PID、数据库仍为 V10、current.json 仍是旧记录）
  → 打印恢复方式（看日志、删目录重发或换版本号、如何先回旧版本）
  → exit 1
```

### 4. current.json 原子写

`Write-JsonNoBom` 改为：

```
写 <path>.tmp（同目录）
  ↓ 成功
Move-Item -Force 覆盖目标（NTFS 同目录 rename，原子）
  ↓ 失败
删除 .tmp 并抛出 —— 目标文件保持旧的完整内容
```

写入中途失败不会产生半截 JSON，旧记录始终可读。

### 5. 取消部署的副作用

生产配置的生成从 [2/6] 推迟到 [4/6] 用户确认之后：

| 阶段 | 修正前 | 修正后 |
|---|---|---|
| [2/6] 识别环境 | 若 `config/.env` 不存在，立即写入生产目录 | 只在内存中解析（从既有文件或容器环境读取），不落盘 |
| [4/6] 取消 | 已留下 `config/.env` | 目录保持原样，明确提示"生产配置未创建" |
| [4/6] 确认后 | — | 此时才创建 `config/.env` |

### 6. Docker Volume 声明

`docker-compose.prod.yml` 的卷改为：

```yaml
volumes:
  pgdata:
    external: true
    name: canvas-history-pgdata
```

`external: true` 要求卷必须已存在，否则 `docker compose up` 直接报错，不会静默创建空卷再初始化空库。网络仍允许自动创建（可再生基础设施）。

---

## 三、测试结果

全部在临时目录 / 临时 Git 仓库 / DEV 库完成，真实 PROD 未参与。

| # | 场景 | 预期 | 实测 | 结果 |
|---|---|---|---|---|
| T1 | 正式模式、非 main 分支 | 拒绝 | `正式发布必须在 main 分支上进行，当前分支：dev-test`，exit 1，给出切换建议 | **PASS** |
| T2 | 同上 + `-AllowNonMainBranch` | 通过 | 分支检查跳过并告警，DryRun 完成，exit 0，无残留 | **PASS** |
| T3 | `-SkipTag` | 不写正式目录 | 正式 `release/` 目录不存在；候选包落在 `%TEMP%\canvas-release-untagged\1.0.0`；无 Tag；exit 0 | **PASS** |
| T4 | 创建 Tag 后拒绝推送 | 报未完成 | exit **1**，标题"发布未完成"，包与本地 Tag 存在、远端为空，含恢复命令 | **PASS** |
| T5 | 首次部署时取消（N） | 不创建 config | prod 目录为空，`config/.env` 不存在，提示"生产配置未创建" | **PASS** |
| T6 | 正常部署 | current.json 完整 | `status=success`，字段齐全，**无 `.tmp` 残留** | **PASS** |
| T7 | compose 卷不存在 | 拒绝启动 | `external volume "nonexistent-volume-for-test" not found`，exit 1 | **PASS** |
| T8 | compose 解析 | 声明 external | 输出含 `external: true` 与 `name: canvas-history-pgdata` | **PASS** |

### 未端到端验证的两项（以代码路径审查代替）

| 项 | 原因 | 审查结论 |
|---|---|---|
| 冒烟失败 → 不写 current.json | 需要一个「有表结构但零数据」的隔离库；创建临时容器时被安全策略拦截（审批超时），无法构造 | 代码中冒烟判断块内直接 `exit $exitFail`，且位于 `Write-JsonNoBom` 之前，失败不可能写入成功记录 |
| current.json 写入失败 → 保留旧记录 | 难以稳定构造 Move 失败 | `Move-Item -Force` 之前目标文件未被触碰；异常路径删除 `.tmp` 后抛出 |

这两项如需实证，可在下次有 Docker 权限时用独立空库补测。

---

## 四、遗留问题

| # | 项 | 说明 |
|---|---|---|
| 1 | 冒烟失败分支未实证 | 见上，逻辑上已保证不写成功记录 |
| 2 | 应用自动回滚仍未实现 | 冒烟失败时保留进程、保留旧版本目录，由人工决定；数据库不回滚 |
| 3 | `-AllowNonMainBranch` 是逃生口 | 仅应在临时仓库使用；正式发布流程文档需注明不得使用 |
| 4 | resolve 分支策略仍未定 | 本地无 `main`，BAT 02 正式模式现在会强制要求 main，因此首次发布前必须先建立/切到 main |

---

## 五、环境状态

| 项 | 状态 |
|---|---|
| 真实仓库 HEAD | `9efea3a`（未变），0 Tag |
| 生产数据库 | `canvas_history` V10，`historical_place` 57,967（未变） |
| 生产部署目录 | 不存在 |
| 临时测试环境 | 已全部删除，无残留测试库 |

---

## 六、追加修正：BAT 01 改为单 main 分支模式

> 正式确定：本项目采用单 `main` 分支工作模式，不建设多分支开发流程。

### 6.1 修改范围

只改 `scripts/dev/git-publish.ps1` 的分支准备段。`01_提交GitHub.bat` **本身未改动**（仍是纯 ASCII / CRLF / 无 BOM 的入口，只负责转发）。

原有能力全部保留：敏感文件检查、大批量删除警告、Commit 与 Push 两次独立 Y/N。

### 6.2 分支判定逻辑

进入 BAT 01 后先做分支准备，再做后续步骤：

| 当前状态 | 行为 |
|---|---|
| 已在 `main` | 直接继续 |
| 本地有 `main`，当前分支 HEAD 与 `main` **相同** | 提示 Y/N，确认后 `git checkout main`（工作区修改保留） |
| 本地有 `main`，当前分支 HEAD 与 `main` **不同** | **停止**，打印两个 SHA，说明不会合并/重置/覆盖 |
| 本地无 `main`，HEAD 与 `origin/main` **相同** | 提示 Y/N，确认后 `git checkout -b main` + 设置上游为 `origin/main`（工作区修改保留） |
| 本地无 `main`，HEAD 与 `origin/main` **不同** | **停止**，说明建立 main 会让历史与远端错位 |
| 用户选 N（任一处） | 取消，Git 状态完全不变 |

推送统一使用 `main`，不创建其它远端分支。

### 6.3 测试结果（临时仓库，6 项全 PASS）

| # | 场景 | 结果 |
|---|---|---|
| A | 无本地 main + HEAD==origin/main + 有未提交修改，Y/Y/Y | 建立 main 并切换，`work-in-progress.txt` 保留并成功提交；推送 `5faf891..2681a78 main -> main` |
| B | 已在 main，无变更 | 无分支提示，直接"工作区干净"退出 |
| C | 本地有 main，当前分支 HEAD 不同 | 停止，exit 1，分支未变 |
| D | 本地无 main，HEAD != origin/main | 停止，exit 1，**未误建 main** |
| E | 无 main，提示后选 N | 取消，exit 0，未创建 main，分支未变 |
| F | 本地有 main 且提交一致，选 Y | 切换成功，后续正常 |

远端分支列表验证：全程只有 `main`，没有产生任何多余远端分支。

### 6.4 对既有流程的影响

- **BAT 02** 无需改动：它已强制要求 `main` 且 HEAD 与 `origin/main` 一致，与本修正天然一致。
- 首次真实使用 BAT 01 时，会提示"本地还没有 main / 当前提交与 origin/main 一致（9efea3a）/ 是否建立"，选 Y 即可完成，不需要手工敲任何 Git 命令。

### 6.5 遗留

`dev-work` 之类旧分支不会被删除（测试中保留），真实仓库里 `m4-3-pleiades-gis`、`m3-time-map`、`m4-2-import-rules`、`master` 也都还在。是否清理属于独立决定，本次未动。

---

## 七、再次修正：DryRun 严格只读 + 分支操作前先 Fetch

只改 `scripts/dev/git-publish.ps1` 的分支准备段，`01_提交GitHub.bat` 未动（仍是 1043 字节、修改时间 09:26）。

### 7.1 修正一：`-DryRun` 严格只读

原先 `-DryRun` 的退出点在「确认提交」之后，而分支切换发生在此之前 —— 也就是说 `-DryRun` + 选 Y 仍会真的 `checkout -b`。

现在分支准备段独立判断 `$DryRun`：

| 场景 | 行为 |
|---|---|
| 需要建立 / 切换 main 且 `-DryRun` | **不执行任何 Git 写操作**，只打印「正常运行时此处会执行 `git checkout -b main`，并把上游设为 `origin/main`」，随后按「已在 main」预览 |
| `-DryRun` 下 fetch | **不执行**（fetch 会写 `.git/refs/remotes`），改用本地已有的 `origin/main` 引用，并明确标注「不联网」 |
| `-DryRun` 下 add / commit / push | 仍在确认之后直接 `exit`，不执行 |

### 7.2 修正二：分支操作前先 Fetch 核对

正常模式在两类分支动作前都先 `git fetch origin`：

| 动作 | fetch 失败 | 额外核对 |
|---|---|---|
| 切到已有 main | **停止**，不切换 | 本地 `main` 落后 `origin/main` 时也停止（避免把分叉带到下一步） |
| 新建 main | **停止**，不建分支 | 用 fetch 后的 `origin/main` 与 HEAD 比对，而不是过期缓存 |

fetch 失败时的输出包含 git 原始错误与「请检查网络或凭据后重试」，退出码 1，分支状态完全不变。

### 7.3 定向测试（临时仓库）

| # | 场景 | 验证点 | 结果 |
|---|---|---|---|
| A | 无 main + `-DryRun` + 选 Y | 分支名 `dev-work`、分支数 1、HEAD `e740119`、工作区 `?? pending.txt` —— **前后完全一致**；输出含「只读模式：未执行任何分支操作」 | **PASS** |
| A2 | 同上，检查上游预览 | 显示「上游：origin/main（运行时设置）」，不再误报「将创建远端分支」 | **PASS** |
| B | 正常模式 + 远端不可达 | fetch 失败即停止，exit 1，分支数与 HEAD 未变，输出含 git 原始错误 | **PASS** |
| C | 正常模式 + 远端可用 | 「已获取最新 origin/main」→ 建立 main → 上游 `origin/main` → 提交成功 → 拒绝推送时保留本地提交 | **PASS** |

### 7.4 环境状态

| 项 | 状态 |
|---|---|
| 真实仓库 HEAD | `9efea3a`（未变），0 Tag，分支仍 `m4-3-pleiades-gis` |
| 临时测试仓库 | 已删除 |
| 真实仓库提交 / 推送 | **未执行** |


