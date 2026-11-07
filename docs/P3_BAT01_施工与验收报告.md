# P3 施工与验收报告 — BAT 01 GitHub 提交工具

> 项目：World History Spacetime Canvas
> 日期：2026-11-07
> 范围：仅建设并测试 BAT 01，未做 BAT 02 / BAT 03 / Release / 部署

---

## 一、结论

| 项 | 结果 |
|---|---|
| 工具建设（BAT + PowerShell） | **PASS** |
| 基础功能（状态读取、分类、无变更退出、取消不改状态） | **PASS** |
| 安全行为（敏感文件、大批量删除、远端领先、远端不可用） | **PASS** |
| 提交与推送成功路径（临时仓库 + 本地 Bare Remote） | **PASS** |
| BAT 双击入口（中文显示、pause、退出码） | **PASS** |
| 真实仓库未被 Commit / Push | **PASS**（HEAD 仍为 `9efea3a`） |
| `run-dev.sh` 遗留风险修复 | **PASS**（已修复且未改变 PROD 启动行为） |
| DEV / PROD 运行态复验 | **BLOCKED**（系统于 09:13 重启，Docker 未运行，见 §8） |

**总体：PASS WITH ONE BLOCKED ITEM。** 工具本身全部验收通过；唯一阻塞项是环境层面的运行态复验，与本次代码改动无关。

---

## 二、新增与修改文件清单

### 新增

| 文件 | 行数 / 大小 | 说明 |
|---|---|---|
| `01_提交GitHub.bat` | 28 行，约 1.0 KB | 双击入口。**纯 ASCII、CRLF、无 BOM**，`chcp 65001`，只负责定位目录 + 调用 PowerShell + 透传退出码 + pause |
| `scripts/dev/git-publish.ps1` | 约 500 行，UTF-8 BOM + CRLF | 全部实际逻辑与中文交互 |

### 修改

| 文件 | 改动 | 是否影响 PROD |
|---|---|---|
| `code/backend/run-dev.sh` | 取消「默认连 canvas_history」的三级回退，改为**必须显式提供 DB_NAME**，否则 exit 2 | 不影响（见 §7） |
| `code/README.md` | 同步更新启动方式说明与权限表 | 否 |

### 未改动

`.gitignore`、`docker-compose.yml`、`docker-compose.dev.yml`、`application.yml`、任何 Flyway Migration、生产数据库、生产容器、`.env`、`.env.dev`。

---

## 三、BAT 实际执行流程

```
双击 01_提交GitHub.bat
  → cd /d "%~dp0"            （不依赖当前工作目录）
  → chcp 65001               （中文输出正确）
  → powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev\git-publish.ps1
      → [1/4] 仓库状态：分支 / HEAD / 提交时间 / 远端 / 上游
      → [2/4] 变更文件：新增 / 修改 / 删除 / 重命名 计数 + 各列前 8 条
      → [3/4] 安全检查：敏感文件、大文件、大批量删除
             ├─ 命中 → 停止，exit 1，不做任何改动
             └─ 通过 → [4/4] 提交
                    → 展示自动生成的 Commit Message
                    → 「是否暂存并提交以上变更？(Y/N)」  N → 退出，状态不变
                    → git add -A → 复查暂存区 → git commit
                    → 推送阶段：fetch → 计算 ahead/behind
                           ├─ 落后 > 0 → 停止（不 merge / 不 rebase / 不 force）
                           └─ 「是否推送到 GitHub？(Y/N)」 N → 保留本地提交退出
                                  → git push（无 upstream 时自动 -u）
                                  → 校验本地 HEAD 与远端 ref 一致
  → pause（窗口不立即关闭）
  → exit /b %RC%（透传 0 / 1）
```

**脚本内不存在的动作**：`--force`、`reset`、`rebase`、`checkout`、切分支、建 Tag、覆盖远端。

---

## 四、Git 状态检查结果（真实仓库）

| 项 | 值 |
|---|---|
| 仓库根 | `E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory` |
| 当前分支 | `m4-3-pleiades-gis` |
| HEAD | `9efea3a` — `fix(v1.0): keep the name-first sort in the outer query, add a writable launcher` |
| 提交数 | 40 |
| Git Tag | 0 |
| 远端 | `origin` → `https://github.com/zy54321/CanvasofWorldHistory.git` |
| 上游 | 未设置（推送时会新建远端分支，工具会明确提示） |
| 工作区变更 | 441 项（含本次新增的 BAT 与 scripts） |

### 变更分类（工具实际识别）

| 类别 | 数量 |
|---|---|
| 新增 | 8（含 `01_提交GitHub.bat`、`scripts/dev/git-publish.ps1`、`code/docker-compose.dev.yml`、`code/backend/run-dev-api.sh`、`docs/*`、`DEV环境…报告.md`、`code/ops/reports/v1b/.gitkeep`） |
| 修改 | 3（`code/.gitignore`、`code/frontend/vite.config.ts`、`code/start-dev.sh`） |
| 删除 | 428（上一轮仓库清理产物） |
| 重命名 | 0 |

### `.gitignore` 覆盖验证

| 路径 | 结果 |
|---|---|
| `code/.env` | 已忽略 |
| `code/.env.dev` | 已忽略 |
| `code/backend/target/canvas-history-api.jar` | 已忽略 |
| `code/data/backup/*.dump` | 已忽略 |
| `code/ops/reports/*.log` | 已忽略 |
| `code/frontend/dist/` | 已忽略（`git check-ignore` 对不存在的目录会返回非零，属正常；对其中文件与带尾斜杠的目录均可正确匹配） |

---

## 五、测试结果

所有涉及写操作的测试均在**临时仓库**（`%TEMP%\canvas-bat01-test`，含本地 Bare Remote）中完成，测试后已删除。

| # | 场景 | 预期 | 实测 | 结果 |
|---|---|---|---|---|
| 1 | 干净仓库（无变更） | 明确提示并正常退出 | 提示「工作区干净」，exit 0，HEAD 不变 | **PASS** |
| 2 | 正常提交 + 推送 | Commit 成功、Push 成功、远端一致 | 本地/远端均为 `13b4cfe`，中文含空格文件名 `说明 文档.md` 正确入库 | **PASS** |
| 3 | 含 `.env` / `.pem` / `.dump` | 阻断，不提交 | 3 个全部识别并阻断，exit 1，暂存区为空，HEAD 不变 | **PASS** |
| 4 | 远端领先 1 个提交 | 停止推送，不自动合并 | 提示「落后 1 个」，exit 1，本地提交保留，远端未变 | **PASS** |
| 5 | 60 个删除 | 额外确认，N 后不提交 | 触发额外确认，N 后 exit 0，HEAD 不变 | **PASS** |
| 6 | 501 个删除 | 纯阻断 | 提示「超过阈值 500」，exit 1，HEAD 不变 | **PASS** |
| 7 | 远端不可用 | 明确报错、本地提交保留 | fetch 警告 + push 失败，exit 1，本地提交保留 | **PASS** |
| 8 | 真实仓库 DryRun + 输入 N | 只读、不改状态 | 状态与分类正确，exit 0，HEAD 不变 | **PASS** |
| 9 | 经 BAT 入口调用（`-DryRun`） | 中文正常、pause、退出码正确 | 中文无乱码，显示 pause，exit 0，HEAD 不变 | **PASS** |

### 交互细节验证

- 直接回车 = N（已实现并在代码中显式判断空字符串）
- 非法输入重新提示（非 Y/N 的任意输入都会循环）
- Commit 与 Push **两次独立确认**，不合并
- 取消 Commit 后，`git status` 与 `git diff` 均无变化

### 施工中发现并修复的 5 个缺陷

| # | 缺陷 | 后果 | 修复 |
|---|---|---|---|
| 1 | `$ErrorActionPreference='Stop'` + `2>&1` | git 写 stderr（如「无上游」）会被转成终止性错误直接抛出，根本走不到退出码判断 | `Invoke-Git` 内临时降为 `Continue`，恢复后再判断 |
| 2 | `"$head: $summary"` | PowerShell 把 `$head:` 当驱动器限定符，语法报错 | 改为 `"${head}: ..."` |
| 3 | `-AllowFail` 用 `[switch]` 传参 | 开关未被识别，`AllowFail` 始终为 false | 改为 `[bool]$AllowFail`，调用处写 `-AllowFail $true` |
| 4 | git stderr 的 `ErrorRecord` 直接 `"$_"` | 输出里混入 `System.Management.Automation.RemoteException` 噪音 | 新增 `Format-GitLine` 统一取 `Exception.Message` |
| 5 | Commit Message 无长度限制 | 真实仓库场景达 130 字符，折行难看 | 截断到 72 字符；scope 过滤掉根目录散文件；hint 最多取 2 条 |

---

## 六、是否执行过真实 Commit / Push

**否。**

| 操作 | 真实仓库 | 临时测试仓库 |
|---|---|---|
| `git add` | 未执行 | 已执行（测试用） |
| `git commit` | **未执行** | 已执行（测试用） |
| `git push` | **未执行** | 已推送到本地 Bare Remote（测试用） |
| `git tag` | **未执行** | 未执行 |
| `git reset --hard` | 未执行 | 已执行（重置测试环境） |

真实仓库验证前后对比：

```
HEAD  before: 9efea3ac52b6bb5ad96d5055bfe3cdeb160f0ba0
HEAD  after : 9efea3ac52b6bb5ad96d5055bfe3cdeb160f0ba0
提交数      : 40 -> 40
Tag         : 0 -> 0
暂存区      : 空
远端        : origin 未变
```

测试临时目录 `%TEMP%\canvas-bat01-test` 已删除。

---

## 七、`run-dev.sh` 遗留风险处理

### 7.1 修复前的调用关系

```
run-prod.sh  ──(export DB_NAME=canvas_history)──▶  run-dev.sh  ──▶  java -jar
start-dev.sh ──(已在 DEV 阶段改为调用 run-dev-api.sh)
用户手动     ──▶  run-dev.sh（裸跑，无 DB_NAME）
                   └─ DB_NAME="${DB_NAME:-${POSTGRES_DB:-canvas_history}}" → 连生产库（只读）
```

### 7.2 实施的最小修复

把三级回退改为**强制断言**：

```bash
if [ -z "${DB_NAME-}" ]; then
  echo "拒绝启动：未指定 DB_NAME。" >&2
  echo "        DEV  开发环境：  bash run-dev-api.sh" >&2
  echo "        PROD 正式环境：  bash run-prod.sh" >&2
  echo "        其它临时库：    DB_NAME=<库名> bash run-dev.sh" >&2
  exit 2
fi
```

同时更新脚本头部注释与 `code/README.md`。

### 7.3 为什么这不会影响生产

`run-prod.sh` 在调用前已 `export DB_NAME="$TARGET_DB"`，断言必然通过。已验证：

| 测试 | 结果 |
|---|---|
| 三个启动器 `bash -n` 语法 | 全部通过 |
| 裸跑 `run-dev.sh`（无 DB_NAME） | 拒绝，**exit 2** |
| `DB_NAME=canvas_history bash run-dev.sh`（模拟 run-prod.sh 的调用方式） | 通过断言，正常进入启动流程（打印 `API 启动：... db=canvas_history`，随后因 8088 端口被占用而退出） |

**未修改 `run-prod.sh`**，未改变其任何行为。

### 7.4 未做的事

没有重命名 `run-dev.sh`（会连带改动 `run-prod.sh` 与多处文档，超出「局部修复」边界）。名称仍略显含糊，但「默认连生产」这个真实危险已经消除。

---

## 八、BLOCKED 项：DEV / PROD 运行态复验

### 现象

```
curl 127.0.0.1:8088  → 连接被拒绝
curl 127.0.0.1:8089  → 连接被拒绝
curl 127.0.0.1:5180  → 502
docker ps            → 无法连接 Docker 守护进程
```

### 原因

系统于 **2026-11-07 09:13:49 重启**（今日 09:30 检查时距重启 16 分钟）。重启后：

- Docker Desktop 未自动启动；
- 之前的 java（8088 / 8089）与 vite（5180 / 5181）进程全部退出。

这是**环境重启**导致的，与本轮改动无关：本轮未停止任何容器、未修改数据库、未改动 compose。

### 尝试与限制

已尝试由脚本启动 Docker Desktop，被安全策略拦截（无法在沙箱内发起审批），与既往记录一致。因此无法在本轮内恢复运行态。

### 恢复方式（需你手动执行）

1. 启动 Docker Desktop，等待鲸鱼图标变绿；
2. 启动 DEV：
   ```bash
   cd E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory\code
   docker compose -f docker-compose.dev.yml --env-file .env.dev up -d
   bash start-dev.sh
   ```
   → DEV 前端 http://127.0.0.1:5181/ ，API 8089
3. 如需 PROD：
   ```bash
   cd code\backend && bash run-prod.sh
   ```
   → API 8088

数据本身不受影响：DEV 数据在独立卷 `canvas-history-dev-pgdata`，PROD 数据在 `canvas-history-pgdata`，两者都不随容器重启丢失。

---

## 九、遗留问题

| # | 问题 | 级别 | 说明 |
|---|---|---|---|
| 1 | DEV / PROD 运行态未复验 | 中 | 见 §8，需手动启动 Docker 后确认 |
| 2 | 当前分支 `m4-3-pleiades-gis` 未设置上游 | 低 | 工具会提示「推送时将新建远端分支」，不会自动改写。是否切到 `main` 属发布策略，本轮未动 |
| 3 | 工作区 441 项变更 | 低 | 含 428 个清理删除。首次真实运行时，工具会触发「大批量删除」额外确认，需人工判断一次 |
| 4 | `mvn` 不在 PATH | 中 | 影响 BAT 02 构建，不影响 BAT 01。仍待 P2 补 Maven Wrapper |
| 5 | 工具依赖 PowerShell 5.1 + Git 2.55 | 低 | 已实际验证；未测试 PowerShell 7（`-NoProfile` 调用 Windows PowerShell，行为一致） |
| 6 | 未测试真实 GitHub 凭据下的推送 | 低 | 本轮按边界禁止真实推送。临时测试用的是本地 Bare Remote，凭据链路未验证 |
| 7 | `run-dev.sh` 名称仍有歧义 | 低 | 危险已消除，改名留待后续 |

---

## 十、下一步（等你确认，不自动开始）

- 启动 Docker 后复验 DEV / PROD，补充 §8；
- 首次真实运行 BAT 01（会面对 441 项变更，建议先看分类摘要再决定）；
- 之后再考虑 BAT 02（需要先解决 `mvn` 路径问题）。
