# Canvas vs myLedger 三 BAT 实现差异审计报告

> 审计日期：2026-11-07
> 性质：**只读静态审计**。未修改任何代码、未执行任何 Git 写操作、未启停服务、未触碰数据库
> 审计方法：直接读取两侧源码，逐行比对；不引用此前任何 PASS 报告作为功能正确性证据

---

## 一、审计基线与可追溯性

### 1.1 myLedger（参照实现）

| 项 | 值 |
|---|---|
| 实际项目目录 | `E:\01_Work\01_PersonalProjects\010-my-ledger\myLedger-2026-9-8` |
| Git SHA | `c53f750` |
| 分支 | `fix/affair-v2-delete-guard` |
| 最后提交 | 2026-11-03 11:08:04 `收口已验收的事务修正、近期模块和事务显示色。` |

文件基线（SHA256 前 16 位）：

| 文件 | SHA256-16 | 行数 |
|---|---|---:|
| `01_提交GitHub.bat` | `cc69526ad13d8b0d` | 19 |
| `02_制作Release.bat` | `6864bf6da1237b70` | 19 |
| `scripts/dev/git-publish.ps1` | `58a9052368c36e26` | 715 |
| `scripts/dev/make-release.ps1` | `c8ca35255a54e612` | 186 |
| `scripts/dev/confirm-yn.ps1` | `aa73ae014c9f22fa` | 42 |
| `scripts/release/runtime/03_发布Prod.bat` | `5ec4512eda3fc259` | 19 |
| `scripts/release/runtime/publish-prod.ps1` | — | 582 |

### 1.2 Canvas（本次审计对象）

| 文件 | 行数 |
|---|---:|
| `01_提交GitHub.bat` | 28 |
| `02_制作Release.bat` | 27 |
| `scripts/dev/git-publish.ps1` | 669 |
| `scripts/release/git-release.ps1` | 830 |
| `scripts/release/templates/03_发布Prod.bat` | 26 |
| `scripts/release/templates/publish-prod.ps1` | 825 |

---

## 二、核心问题的直接回答

### Q5：为什么 myLedger 能正常工作，而 Canvas 第一次双击就在 `git fetch origin` 阶段中止？

**先纠正一个预设：myLedger 同样不支持离线提交。**

`scripts/dev/git-publish.ps1` 第 533–544 行：

```powershell
533  $remoteLines = Invoke-GitRaw @('ls-remote', '--heads', 'origin', "refs/heads/$branch")
534  if ($remoteLines.Code -ne 0) { Fail '无法读取 GitHub 远程状态。已停止，没有创建提交。' }
...
543      $fetch = Invoke-GitRaw @('fetch', 'origin', $branch, '--quiet')
544      if ($fetch.Code -ne 0) { Fail '无法获取远程修订。已停止，没有合并，也没有创建提交。' }
```

两者都在 `add`/`commit` 之前联网，失败都硬终止。所以"离线也能提交"这件事，原版也不成立。

**真正的差异有三点：**

| # | 差异 | myLedger | Canvas |
|---|---|---|---|
| 1 | **联网发生的位置** | 第 533 行，在展示仓库/分支/远端/可见性（506–530）**之后** | 第 283 / 326 行，在**分支准备阶段**，即"仓库状态"段落的第一步，用户还没看到任何有用信息 |
| 2 | **联网与什么绑定** | 只用于读取远端修订、判断分叉 | 绑定在"自动建立本地 main"这个**Canvas 新增机制**的前置条件上 |
| 3 | **触发条件** | 每次运行都触发 | 只在"本地无 main / 需切 main"时触发 —— 而 Canvas 仓库**第一次运行必然命中**（本地确实没有 main） |

因此准确的因果是：

> Canvas 把「建立 main」做成了发布流程的强制第一步，又给这一步加了 fetch 门禁。仓库首次运行时本地必然没有 main，于是必然走 fetch；网络不通即中止，且中止发生在任何有价值的信息展示之前。

myLedger 没有"建分支"这一概念，它的联网虽然同样必需，但失败点在信息展示之后，用户至少知道脚本在做什么。

**这不是"Canvas 比 myLedger 多联网"，而是"Canvas 把联网提前并绑定了新增的分支机制"。**

---

## 三、总体差异统计

| 模块 | 审计项数 | A 直接继承 | B 必要适配 | C 非必要偏离 | D 缺失退化 |
|---|---:|---:|---:|---:|---:|
| BAT 01 | 16 | 4 | 1 | 8 | 3 |
| BAT 02 | 14 | 3 | 5 | 6 | 0 |
| BAT 03 | 14 | 1 | 9 | 3 | 1 |
| **合计** | **44** | **8** | **15** | **17** | **4** |

比例：A 18.2% ｜ B 34.1% ｜ **C 38.6%** ｜ D 9.1%

即：**真正照搬的比例不到五分之一；近四成属于非必要偏离。**

---

## 四、BAT 01 专项审计（16 项）

| # | 功能点 | myLedger 实际行为 | Canvas 实际行为 | 分类 | Canvas 源码位置 | 实际影响 |
|---|---|---|---|---|---|---|
| 1 | 双击入口与编码 | 19 行 BAT；不设 `chcp`；全英文输出；`pause >nul` | 28 行 BAT；`chcp 65001`；中文由 PS 输出；`pause` 显式 | **B** | `01_提交GitHub.bat` L20–22 | Canvas 中文输出必须切码页；属需求驱动的呈现适配 |
| 2 | 工作区检查 | `status --porcelain=v1 -z -uall`（L556） | `status --porcelain -uall`（L532 附近） | **A** | `git-publish.ps1` L531 | 一致 |
| 3 | 当前分支处理 | **只用当前分支，从不切换**（L503–507） | **强制 main**，不在 main 则切换（L256–382） | **C** | `git-publish.ps1` L244–382 | 用户被剥夺了"在任意分支提交"的能力；提交来源被强制收窄 |
| 4 | 是否强制 main | 否。任何非游离 HEAD 分支都可用 | 是。`$primary = 'main'`（L248） | **C** | 同上 | myLedger 从未要求 main，此约束为 Canvas 自加 |
| 5 | 自动建 main | **不存在该机制** | `git checkout -b main` + 设上游（L370、L377） | **C** | `git-publish.ps1` L370–379 | 新增的自动分支操作；是首次运行失败的直接触发点 |
| 6 | Fetch 时机 | commit 前，位于信息展示之后（L533、L543） | 位于分支准备阶段（L283、L326），早于任何状态展示 | **C** | `git-publish.ps1` L283、L326 | 网络异常时用户看不到任何仓库信息就被终止 |
| 7 | Commit 是否被联网失败阻断 | **是**（L544 `Fail '…没有创建提交'`） | **是**（L284–288、L327–331） | **A** | `git-publish.ps1` L283–288 | 两者一致；此前"Canvas 新增联网阻断"的说法不成立 |
| 8 | Commit 与 Push 顺序 | `add`(658) → `commit`(673) → 确认(687) → `push`(707) | `add`(538) → `commit`(570) → 确认(620) → `push`(629) | **A** | `git-publish.ps1` L538–631 | 一致 |
| 9 | 远端不可达处理 | `ls-remote` 失败 → `Fail`（exit 1），提示"没有创建提交" | 分支阶段 fetch 失败 → exit 1；**推送阶段** fetch 失败仅警告（L587–590） | **C** | `git-publish.ps1` L283、L587 | Canvas 出现两套不一致的联网失败策略：早期硬停、晚期软警告 |
| 10 | 未提交/已提交未推送/远端领先 | 分叉检测（545–552）：双向 ancestor 判断；远端领先 `Fail '不会自动 pull'` | 落后检测（L587 之后 `rev-list --left-right`），落后即 exit 1 | **A** | `git-publish.ps1` L595–605 | 逻辑等价，Canvas 略简化（未做双向 ancestor） |
| 11 | 敏感文件检查 | 12 类规则：`.env` 系列、私钥、`backups/secrets` 目录、`.dump`、`.sql`（非官方迁移路径即敏感）、**暂存内容字节特征**（pg_dump/COPY/INSERT/postgresql://）、**已忽略文件混入检测**、**单文件 5MB 上限**（L101–121、L662–671） | 13 条路径正则：`.env`、私钥、`.dump`、`node_modules`、`dist/target/build`、`*.log`、`.DS_Store`（L128 `Test-DangerousPath`） | **D** | `git-publish.ps1` L128–150 | Canvas **丢失**了内容级检测、ignored 混入检测、体积上限；纯路径正则无法拦住"改名的 dump"或"塞进 .txt 的密钥" |
| 12 | 大批量删除确认 | **无此机制**（全文仅 L373 提及"已从工作区删除的历史文件"） | 删除 ≥500 阻断、≥50 额外确认（L489–496） | **C** | `git-publish.ps1` L489 | 原版无此门禁。Canvas 首次运行 428 个删除会多一次确认；对本次场景是必要的，但属自加 |
| 13 | Commit Message | **要求用户手输**（L649 `Read-Host '请输入提交说明'`），空则 Fail | 自动生成 `type(scope): add N, update M, remove K`，截断 72 字符 | **C** | `git-publish.ps1` L400 附近 `New-CommitMessage` | 需求驱动（任务书明确要求不手填），但偏离幅度大：质量取决于分类器，不如人工准确 |
| 14 | Y/N 交互 | **混合**：`YES-PUBLIC-PUSH`（L640）、`YES-COMMIT`（L650）字符串确认 + `choice.exe` 的 `YES-PUSH (Y/N)`（L688） | 全部 `Read-Host` + `Y/N`，回车=N，非法重问（L100 `Ask-YesNo`） | **C** | `git-publish.ps1` L100–121 | 需求驱动（任务书明令禁止 YES-COMMIT）。但注意：**myLedger 的 YES-COMMIT 是有意的高摩擦设计**，Canvas 把它降到单键 Y，误触成本随之下降 |
| 15 | 错误退出与失败恢复 | 三态退出码：`0` 成功/取消、`1` Fail、**`2` 已提交未推送**（L691、L700） | 两态：`0` / `1`。已提交未推送用 exit 1 + 文案说明 | **D** | `git-publish.ps1` L620–630 | 丢失 `2` 语义，脚本链或用户无法从退出码区分"完全失败"与"提交成功但推送失败" |
| 16 | 是否自动修改分支/索引/工作区 | 只 `add` + `commit`，**不动分支** | 可能执行 `checkout` / `checkout -b`（L306、L370） | **C** | `git-publish.ps1` L306、L370 | 引入了原版不存在的分支副作用，且发生在用户确认之前 |

**BAT 01 小计：A 4 ｜ B 1 ｜ C 8 ｜ D 3**

### 4.1 BAT 01 被忽略的原版能力

myLedger 有一项 Canvas **完全没有**的机制：**仓库可见性检查**（L515–523）。

```powershell
$visibility = Get-RemoteVisibility $remoteUrl
if ($visibility -eq 'unknown') { Fail '无法确认远程仓库是否公开。已停止，没有创建提交。' }
...
if ($visibility -eq 'public') { ... $ConfirmPublic = Read-Host '确认公开推送请输入 YES-PUBLIC-PUSH…' }
```

Canvas 侧 `grep -c "public|visibility|可见性"` 结果为 **0**。对一个即将首次推送到 GitHub 的项目，这是能力缺口（计入 BAT 01 的 D 类，与第 11、15 项并列）。

---

## 五、BAT 02 专项审计（14 项）

| # | 功能点 | myLedger 实际行为 | Canvas 实际行为 | 分类 | Canvas 源码位置 | 实际影响 |
|---|---|---|---|---|---|---|
| 1 | 前置条件 | HEAD 存在、`status --porcelain` 干净、origin 存在（L43–56） | 同三项（L205–226） | **A** | `git-release.ps1` L205 | 一致 |
| 2 | 分支与远端同步 | `ls-remote` 比对 `remoteSha -eq head`（L60–71），不等即 Fail | 强制 `branch -eq 'main'` + `origin/main == HEAD`（L260–292） | **C** | `git-release.ps1` L260 | 原版只要"本地=远端"，Canvas 额外锁死分支名 |
| 3 | 版本号识别 | `Resolve-NextReleaseVersion`：读 tag + GitHub Release API | 读远端 tag（`ls-remote --tags`）+ 本地目录 + Prod `current.json`，三源交叉校验 | **B** | `git-release.ps1` L300–360 | 技术栈无关，属实现选择；Canvas 多了本地目录这一源 |
| 4 | 用户 Y/N | **单次** `YES-RELEASE (Y/N)`（L117） | **串行三次**：PATCH→MINOR→MAJOR，全 N 才退出（L380–420） | **C** | `git-release.ps1` L380 | 多 2 轮交互，换来手工选 major/minor 的能力 |
| 5 | 编译测试 | `pnpm typecheck` + `test-release-gates.ps1`（L137–144） | `npm run build`（含 vue-tsc）+ `mvnw -Pwith-web`；无独立门禁测试集 | **B** | `git-release.ps1` L470–520 | 技术栈差异；但 Canvas **没有**等价的"发布门禁测试"脚本 |
| 6 | Release 目录结构 | 版本目录含 `images/ scripts/ docs/` + manifest，自包含 | `api/ db/ deploy/ config/ docs/` + manifest + SHA256SUMS | **B** | `git-release.ps1` L480–500 | 交付形态不同（Docker 镜像 vs 单 Jar） |
| 7 | 构建产物独立性 | 镜像 TAR 离线包 | 单 Jar（前端已内联 static） | **B** | `pom.xml` with-web profile | 技术栈差异 |
| 8 | Manifest/SHA256 | `RELEASE-MANIFEST.json` + `verify-package.ps1` | `manifest.json` + `SHA256SUMS.txt` + 内部复核 | **A** | `git-release.ps1` L600–660 | 等价 |
| 9 | Tag 创建与推送 | **不创建 Git Tag**。版本权威是 Docker 镜像 tag + GitHub Release；脚本仅 `ls-remote --tags` 读取 | `git tag -a` + `git push origin <tag>`（L725、L792） | **C** | `git-release.ps1` L725、L792 | Canvas 引入 Git Tag 作为版本锚点，原版没有这层；属新增体系（虽为任务书 R2 要求） |
| 10 | 归档与 Tag 顺序 | 先打包后校验，无 Tag 概念 | **先 Tag 成功、后归档**；归档失败回退 Tag（L725→L770） | **C** | `git-release.ps1` L698–790 | 逻辑正确，但这是为解决 Canvas 自建 Tag 体系而产生的一致性设计 |
| 11 | 失败残留 | 打包失败时"相同修订的正式镜像会保留" | 失败清理临时目录；Tag 回退 | **B** | `git-release.ps1` L790–830 | 各自适配 |
| 12 | 重复版本 | `Test-ReleaseVersionAvailable` 两次校验（L93、L133） | 目录存在 + tag 存在双重拒绝（L430） | **A** | `git-release.ps1` L430 | 一致 |
| 13 | 耗时与复杂度 | 单次确认 → typecheck → 门禁 → 构建 → 打包 → 校验 | 三级确认 → 版本交叉校验 → 前端构建 → 后端构建 → 单 Jar 校验 → 组装 → 清单 → 复核 → 敏感扫描 → 密钥扫描 → Tag → 归档 → 推送确认 | **C** | 全文 | Canvas 步骤数约为原版 2 倍 |
| 14 | 额外门禁 | 无 `-AllowNonMainBranch` 之类的测试逃生口 | 新增 `-AllowNonMainBranch`、`-SkipTag` 两个参数 | **C** | `git-release.ps1` L42–46 | 为测试便利新增的旁路，正式流程需靠文档约束不用 |

**BAT 02 小计：A 3 ｜ B 5 ｜ C 6 ｜ D 0**

---

## 六、BAT 03 专项审计（14 项）

| # | 功能点 | myLedger 实际行为 | Canvas 实际行为 | 分类 | Canvas 源码位置 | 实际影响 |
|---|---|---|---|---|---|---|
| 1 | 包内独立运行 | `runtime/` 目录含 16 个脚本 + 镜像 TAR，完全自包含 | 单 Jar + `deploy/` 5 个脚本 + 迁移 | **B** | 包结构 | 交付形态差异 |
| 2 | PROD 目录结构 | `VERSION` 文件 + `config/` + 版本目录 | `current.json` + `config/` + `backups/` + `logs/` + `legacy-unversioned/` + 版本目录 | **B** | `publish-prod.ps1` L700+ | 结构不同，Canvas 多两类记录目录 |
| 3 | 生产版本识别 | 读 `PROD/VERSION` 纯文本（L322） | 读 `PROD/current.json`（JSON）+ 无记录时 `legacy_unversioned` | **B** | `publish-prod.ps1` L330 | 等价，格式不同 |
| 4 | 正式配置管理 | `render-env.ps1` 渲染 env | `config/.env` + 首次从容器读取凭据生成 | **B** | `publish-prod.ps1` L350–400 | 各自适配 |
| 5 | 数据库身份校验 | 查容器运行状态（L158） | `current_database()` 必须等于目标库名 + 容器 health 精确匹配 | **B** | `publish-prod.ps1` L430 | Canvas 更严，属技术栈适配（PostGIS 单实例多库） |
| 6 | 备份与迁移 | 独立的 `backup.bat`、`restore-validation.bat`、`drizzle-migrations.ps1`；迁移风险评估（L381 阻断删除类迁移） | 迁移前一次性 `pg_dump`；Flyway 正向迁移；**无独立备份/恢复入口** | **B/D** | `publish-prod.ps1` L500–560 | 迁移工具不同（Flyway vs drizzle）属 B；但 **Canvas 缺少独立的备份/恢复脚本**（原版有 backup.bat 与 restore-validation.bat），此项计 D |
| 7 | 进程启动方式 | `docker compose` 起容器 | `Start-Process java -jar` | **B** | `publish-prod.ps1` L600 | 技术栈差异 |
| 8 | 端口切换 | 无此概念（容器内部端口） | **临时端口验证 → 正式端口 → 占用时 Y/N 停旧进程** | **C** | `publish-prod.ps1` L580–680 | 单 Jar 直接占宿主端口，这是 Canvas 特有复杂度的根源 |
| 9 | 健康检查 | compose healthcheck + 就绪轮询 | HTTP `/meta/health` 轮询（校验 database 字段） | **A** | `publish-prod.ps1` L590 | 等价 |
| 10 | 应用回滚 | `stop.bat` / `start.bat` / `status.bat` 独立可调用；版本目录保留可回退 | **无自动回滚**；冒烟失败仅报告并保留进程，靠人工启动旧版本 | **D** | `publish-prod.ps1` L700–730 | 丢失了原版可用的回滚操作路径 |
| 11 | 部署失败状态 | Fail 时明确"没有修改" | 不写 `current.json`，打印进程/PID/日志路径与恢复方式 | **B** | `publish-prod.ps1` L700 | 各自适配，Canvas 更详细 |
| 12 | `current.json` 记录 | `VERSION` + 验收记录（`ACCEPTED <version>`） | `current.json`（版本/路径/时间/Tag/Commit/库/端口/SHA） | **B** | `publish-prod.ps1` L740 | 格式不同；注意 **myLedger 有 Owner 验收门禁（L335–342），Canvas 没有** |
| 13 | 交互次数 | **1 次** `YES-UPGRADE (Y/N)`（L397） | **最多 3 次**：部署确认 → 迁移确认 → 停旧进程确认 | **C** | `publish-prod.ps1` L486、L544、L676 | 交互次数翻倍以上 |
| 14 | 部署复杂度 | 镜像 + compose，无端口协商 | 临时端口 + 正式端口 + 进程接管 + 冒烟 + 原子写 | **C** | 全文 | 825 行 vs 582 行，复杂度提升 42% |

**BAT 03 小计：A 1 ｜ B 9 ｜ C 3 ｜ D 1**

---

## 七、重点偏离清单（按实际影响排序）

### 第一档：直接导致 BAT 无法按原版体验使用的偏离

| 序号 | 偏离 | 证据 | 影响 |
|---|---|---|---|
| 1 | **分支准备阶段强制 fetch，且绑定"建 main"** | `git-publish.ps1` L283、L326 | 首次运行必触发；网络异常时在任何信息展示前终止 |
| 2 | **自动 checkout / checkout -b** | L306、L370 | 原版从不动分支；现在双击 BAT 可能改变当前分支 |
| 3 | **强制 main 单分支** | L248、L256–382 | 丢弃原版"在任意分支提交"的能力 |

### 第二档：导致用户增加手工操作的偏离

| 序号 | 偏离 | 影响 |
|---|---|---|
| 4 | 提交信息自动生成 | 用户失去对 commit message 的控制，分类器错了只能事后 amend |
| 5 | 三级版本选择（PATCH/MINOR/MAJOR） | 简单发版从 1 次确认变 3 轮 |
| 6 | BAT 03 三处确认 | 部署操作从 1 次确认变 3 次 |
| 7 | `-SkipTag` / `-AllowNonMainBranch` 旁路 | 需要靠文档约束"正式流程不用"，属于为测试妥协的可维护性负债 |

### 第三档：原版能力丢失

| 序号 | 丢失能力 | 原版位置 | Canvas 现状 |
|---|---|---|---|
| 8 | **仓库公开/私有可见性检查 + 公开推送二次确认** | `git-publish.ps1` L515–523、L638–645 | 完全缺失 |
| 9 | **暂存内容字节级敏感检测**（pg_dump/COPY/INSERT/连接串） | L662–671 | 仅路径正则 |
| 10 | **已忽略文件混入检测** | L664 | 缺失 |
| 11 | **单文件 5MB 上限** | L667 | 缺失 |
| 12 | **退出码 `2`（已提交未推送）** | L691、L700 | 退化为 1 |
| 13 | **独立备份 / 恢复验证脚本** | `runtime/backup.bat`、`restore-validation.bat` | 无 |
| 14 | **应用回滚操作入口** | `runtime/stop.bat`、`start.bat`、`status.bat` | 无自动回滚，仅保留目录 |

### 第四档：无充分必要性的新增设计

| 序号 | 新增 | 是否有证据支持必要 |
|---|---|---|
| 15 | 大批量删除阈值（50/500） | 弱。原版无此门禁仍正常运行；但对本次 428 删除场景有实际价值 |
| 16 | Git Tag 作为版本锚点 | 任务书 R2 要求，非自行发明；但原版用镜像 tag + GitHub Release 已达同等可追溯性 |
| 17 | 三源版本交叉校验（tag/目录/prod） | 弱。原版单源（tag）即可；三源一致性检查增加了停止概率 |
| 18 | 临时端口验证 | 中。单 Jar 直接占宿主端口确实有风险，但代价是端口协商复杂度 |
| 19 | 冒烟测试（stats + 检索） | 中。原版靠 compose healthcheck，无业务冒烟 |

### 第五档：纯技术栈差异（应保留）

| 项 | 原因 |
|---|---|
| Maven Wrapper / `-Pwith-web` 单 Jar | Java + Vue 构建链 |
| Flyway 迁移入口 | 与 drizzle 不同的迁移工具 |
| `docker-compose.prod.yml` external volume | PostGIS 独立数据卷模型 |
| `chcp 65001` + PowerShell 中文 | 任务书要求中文交互 |
| `web/config.js` 运行时注入 key | Vite 构建期内联 vs 前端密钥隔离 |

---

## 八、最小回归原版方案建议

> 仅建议，不执行修改。

### 8.1 建议恢复 myLedger 原有行为（收益最高）

| # | 建议 | 依据 | 风险 |
|---|---|---|---|
| R1 | **把 fetch 从分支准备阶段移出**，恢复到"展示仓库信息之后、确认提交之前"，且失败文案与定位对齐原版 | 原版 L533/543 的位置 | 低。fetch 仍存在，只是不挡在流程最前面 |
| R2 | **删除自动建/切 main**，改为"检测到不在 main 时提示并退出，由用户自行处理" | 原版从不动分支 | 低。可保留提示，去掉副作用 |
| R3 | 补回**仓库可见性检查**与公开推送二次确认 | 原版 L515–523、L638–645 | 低 |
| R4 | 补回**暂存内容字节检测**与 **5MB 上限** | 原版 L662–671 | 低 |
| R5 | 恢复**退出码 2** 语义 | 原版 L691、L700 | 低，需同步文档 |
| R6 | 补回**独立 backup / restore 脚本** | 原版 `runtime/backup.bat` | 中，涉及 BAT 03 范围 |

### 8.2 必须保留的 Canvas 特有适配

| 项 | 理由 |
|---|---|
| Maven Wrapper + `-Pwith-web` | Java/Vue 构建链，无法照搬 pnpm |
| Flyway 迁移入口（`deploy/flyway.sh`） | 数据库迁移工具不同 |
| `external: true` 卷声明 | 防静默建空库，PostGIS 单实例模型必需 |
| `current.json` | 等价于原版 `VERSION`，格式差异无害 |
| 数据库身份断言（`current_database()`） | 单实例多库环境下必需 |
| `chcp 65001` + 中文交互 | 任务书明确要求 |

### 8.3 可直接删除的新增功能

| 项 | 理由 |
|---|---|
| 三级版本选择（PATCH/MINOR/MAJOR 串行询问） | 原版单次确认足够；major 变更频率极低，可用参数实现 |
| `-AllowNonMainBranch` | 若移除强制 main，此参数自动失去意义 |
| 大批量删除阈值 | 弱必要性；可降级为"提示"而非"阻断" |
| 临时端口验证 | 若接受"启动失败即回滚"的简单策略，可省去 |

### 8.4 应由 Owner 决定

| 项 | 需要权衡 |
|---|---|
| Git Tag 体系是否保留 | 任务书 R2 要求，但与 myLedger 的镜像 tag 方案不一致 |
| BAT 03 的确认次数（1 次 vs 3 次） | 安全 vs 流畅 |
| Commit message 自动生成 vs 手输 | 效率 vs 准确性 |
| 是否恢复"任意分支可提交" | 单 main 模式是 Owner 刚确定的决策，与 myLedger 相反 |

---

## 九、六个问题的结论

**1. Canvas 三 BAT 有多少直接继承 myLedger？**
44 项中 8 项（18.2%）。核心骨架（工作区检查、分叉检测、add→commit→push 顺序、manifest/SHA256、重复版本拒绝）确实继承，但交互层与门禁层几乎全部重写。

**2. 哪些差异来自技术栈，确实不可避免？**
15 项（34.1%）。集中在 BAT 02/03：Maven/Vite 构建链、单 Jar vs Docker 镜像、Flyway vs drizzle、PostGIS 卷模型、中文编码。

**3. 哪些属于擅自重新设计？**
17 项（38.6%）。最突出的是 BAT 01：**单 main 强制、自动建/切分支、分支阶段 fetch、删除阈值、commit message 自动生成、全 Y/N 交互**。其中"全 Y/N"与"自动 message"虽由任务书要求，但改变了原版的高摩擦确认设计，仍应计入偏离而非继承。

**4. 哪些成熟能力被削弱或丢失？**
4 项（9.1%）+ 上文第三档列出的 7 项具体能力：仓库可见性检查、字节级敏感检测、ignored 混入检测、5MB 上限、退出码 2、独立备份/恢复脚本、应用回滚入口。

**5. 当前 BAT 01 为什么第一次运行就失败？**
因为它把「建立本地 main」做成了强制第一步，并给这一步加了 fetch 门禁（L283/L326）。仓库首次运行必然没有 main，于是必然 fetch；网络异常即在任何信息展示前终止。**注意：myLedger 同样不支持离线提交（L533/L543 也会 Fail），差异在于失败点位置与是否绑定分支操作，而非"Canvas 多联网"。**

**6. 要恢复 myLedger 原有操作体验，最少需要改变什么？**
按收益排序，最小三件事：
- **R2：删掉自动建/切 main**（去掉分支副作用，首次运行不再必然联网）
- **R1：把 fetch 移回信息展示之后**（网络异常时用户仍能看到状态摘要）
- **R3 + R5：补回可见性检查与退出码 2**（恢复原版的安全提示与状态可区分性）

完成这三项，BAT 01 的操作体验即可回到接近原版的水平；其余（Tag 体系、三级版本、三处确认）属可选优化。

---

## 十、审计边界声明

- 本次为静态代码审计，未运行任何脚本（除仅读的 `grep`/`wc`/`sha256sum`/`git rev-parse`）。
- 未修改两侧任何文件。
- 未执行 `git checkout` / `add` / `commit` / `push` / `tag` / `fetch`。
- 未启停服务、未触碰数据库、未更改 Docker。
- 未对网络、代理、VPN、DNS 做任何排查（按任务要求）。
- 文中所有行号均取自审计当时的实际文件，myLedger 基线为 `c53f750`。
