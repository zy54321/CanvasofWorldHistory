# 06 · 正式库全量备份与独立恢复演练

> 目标库：`canvas_history`（**全程只读**，备份用 `pg_dump` 的读事务，不写任何数据）
> 备份目录：`汇报/2026-11-04/210101_P0备份/`
> 恢复库：`canvas_history_p0_backup_restore`（**保留**，未删除）

---

## 一、备份前检查

| 项 | 实测值 |
|---|---|
| 实例地址 / 端口 | `127.0.0.1:15432`（容器 `canvas-history-db`，映射 `127.0.0.1:15432->5432`） |
| 数据库 | `canvas_history` —— 由 `SELECT current_database()` 确认，**不依赖 `.env`** |
| PostgreSQL | 17.11 (Debian 17.11-1.pgdg13+2) |
| PostGIS | 3.6 `USE_GEOS=1 USE_PROJ=1 USE_STATS=1` |
| 备份前 Flyway | **V5**（5 条迁移，全部 success） |
| 备份前各表行数 | 见 §二 |
| 输出目录 | 宿主 `E:` 剩余 775 GB；容器 `/tmp` 可写 |
| 备份前状态 | 无其他进程写入；应用实例连的是 `m4_5_verify`，**不连正式库** |

---

## 二、备份前基线（备份时点）

| 表 | 行数 |
|---|---:|
| `historical_place` | 19,039 |
| `historical_place_name` | 47,499 |
| `historical_place_location` | 18,101 |
| `source_record` | 29,391 |
| `candidate_match` | 53,131 |
| `data_quality_issue` | 12,831 |
| `data_dataset` | 8 |
| `data_source` | 5 |
| `import_batch` | 7 |
| 物理体积 | 167 MB |

---

## 三、备份执行

| 项 | 值 |
|---|---|
| 工具 | `pg_dump`（PostgreSQL 原生） |
| 格式 | **Custom（`-Fc`）**，`-Z6` 压缩 —— 含 schema + data + 大对象 + 序列当前值 |
| 命令 | `pg_dump -U canvas_app -Fc -Z6 -f /tmp/canvas_history_p0.dump canvas_history` |
| 开始（UTC） | 2026-11-04T13:01:04Z |
| 结束（UTC） | 2026-11-04T13:01:05Z |
| 耗时 | 约 1 秒 |
| 退出码 | 0 |
| 文件大小 | **7,338,764 字节**（约 7.0 MB） |
| SHA256 | `30326041c42aaf26f1aa4a98f76c8ab3cd70c9e955327a4006fae7452fe96ee1` |
| MD5 | `db5e142c0747356575bf72ea13e9d1df` |
| 归档条目 | 227 个 TOC，其中 **18 个 TABLE DATA**（public 17 张 + `infra.smoke_check` 1 张） |
| 全局对象 | `pg_dumpall --globals-only` → `globals.sql`（675 B，含角色） |

文件落在容器 `/tmp` 后 `docker cp` 到宿主备份目录，两个位置的字节一致（宿主侧 SHA256 如上）。

> **为什么 167 MB 的库只压出 7.3 MB**：主体是 `raw_payload jsonb` 与 CSV 派生的文本，gzip 压缩率高
> （约 23:1）。这不是"备份不完整"——18 个 TABLE DATA 段与恢复后的逐表指纹已证明内容齐全（见 §五）。

---

## 四、恢复执行

| 项 | 值 |
|---|---|
| 目标库 | `canvas_history_p0_backup_restore`（新建，未覆盖任何已有库） |
| 命令 | `pg_restore -U canvas_app -d canvas_history_p0_backup_restore --exit-on-error --verbose /tmp/canvas_history_p0.dump` |
| 开始（UTC） | 2026-11-04T13:01:15Z |
| 结束（UTC） | 2026-11-04T13:01:17Z |
| 退出码 | **0**（`--exit-on-error` 下任何一条失败都会中止） |
| 日志中 error 次数 | **0** |
| 恢复后体积 | 121 MB（源 167 MB） |

> 体积差 46 MB 属正常：`pg_dump/restore` 不复制死元组与膨胀空间，恢复后的库是"紧凑重建"。
> **逻辑内容必须逐行相等**，这一点由 §五 的整行指纹证明，而不是靠体积。

---

## 五、恢复后核验（36 条判据，全部通过）

工具：`ops/p0/supplemental/verify_backup_restore.py`　结果：`06_backup_restore_verify.json`

### 5.1 对象集合

| 判据 | 结果 |
|---|---|
| 表集合一致 | ✓ 17 张，缺 0 多 0 |
| V5 应有的 17 张表齐全 | ✓ |
| 视图集合一致 | ✓ 5 个（`geography_columns`、`geometry_columns`、`v_place_evidence`、`v_place_liveness`、`v_place_time_span`） |
| 索引数量一致 | ✓ 46 / 46 |

### 5.1b 全部 schema（不只 public）

正式库里除 `public` 外还有 `infra`（一张 `smoke_check` 探针表）、以及 PostGIS 自带的 `tiger` / `topology`。
只核 public 会漏掉 `infra`，所以这里按 `pg_class` 枚举**所有**非系统 schema：

| 判据 | 结果 |
|---|---|
| 所有 schema 的表集合一致 | ✓ 18 张，缺 0 多 0 |
| 所有 schema 的表行数一致 | ✓ 18 张表，0 张不一致（含 `infra.smoke_check` = 1 行） |

### 5.2 行数与**整行指纹**（不剔除任何列）

| 判据 | 结果 |
|---|---|
| 17 张表行数一致 | ✓ 0 张不一致 |
| 17 张表整行指纹一致 | ✓ 0 张不一致（`infra.smoke_check` 由 §5.1b 的行数比对覆盖） |

> 这里的指纹口径与 §04 的"业务内容指纹"不同：**这次连 `updated_at`、`last_batch_id` 也一起算**，
> 因为备份恢复必须连这些列都一模一样。34 条判据里没有一条被放宽。

### 5.3 约束与索引

| 约束类型 | 源 / 恢复 |
|---|---|
| primary key | 17 / 17 |
| unique | 5 / 5 |
| foreign key | 32 / 32 |
| check | 100 / 100 |
| exclusion | 0 / 0 |

### 5.4 外键孤儿（12 项）

名称→地点、位置→地点、地点→源记录、名称→源记录、位置→源记录、候选 A→地点、候选 B→地点、
事件-地点→地点、事件-地点→事件、事件-人物→人物、人物-地点→人物、台账→地点：
**源库 0，恢复库 0**。

### 5.5 PostGIS

| 判据 | 结果 |
|---|---|
| `postgis_version()` 一致 | ✓ 3.6 |
| `spatial_ref_sys` 行数一致 | ✓ 8,500 / 8,500 |
| `ST_Transform` 可执行 | ✓ `POINT(12957588.73 4851421.18)` |

### 5.6 Flyway

| 判据 | 结果 |
|---|---|
| 迁移条数与 checksum 一致 | ✓ 5 条，最高 V5 |
| 全部 success | ✓ 5/5 |

### 5.7 关键查询

地点+首选位置、名称 ILIKE 搜索、时间窗过滤、候选关系、台账分类、按数据集统计——**6/6 可执行**。

---

## 六、这次备份能不能用来回滚？——能，且已证明

要证明"备份可靠"，光有文件不够，必须证明三件事，本轮三件都做了：

1. **文件是完整的**：Custom 格式 + 227 个 TOC + 18 个 TABLE DATA 段；
2. **能恢复进一个干净的库**：`--exit-on-error` 下退出码 0、日志 0 error；
3. **恢复出来的东西和原库一样**：17 张表整行指纹逐一相同、约束/索引/视图数量相同、孤儿 0、PostGIS 可用、Flyway 完整。

因此，如果第三阶段升级 `canvas_history` 失败，标准回滚动作是：

```
# 1. 停应用
# 2. 删库重建（或在别的实例上恢复后改名）
DROP DATABASE canvas_history;
CREATE DATABASE canvas_history OWNER canvas_app;
pg_restore -U canvas_app -d canvas_history --exit-on-error canvas_history_p0.dump
# 3. 起应用，跑 ops/p0/unification_check.sql 复核
```

该路径已在恢复演练中验证过（除"删原库"这一步——那属于正式操作，本轮不做）。

---

## 七、结论

**通过。** 备份文件为 PostgreSQL 原生 Custom 格式全量备份，SHA256 已记录；
在独立库上完整恢复并逐表核验（34/34），恢复库保留备查。

备份目录 `汇报/2026-11-04/210101_P0备份/`：

| 文件 | 大小 | 说明 |
|---|---:|---|
| `canvas_history_p0.dump` | 7,338,764 B | 全量备份（Custom） |
| `globals.sql` | 675 B | 角色/全局对象 |
| `archive_list.txt` | — | `pg_restore -l` 清单 |
| `backup_sha256.txt` | — | SHA256 + MD5 |
| `backup_timing.txt` / `restore_timing.txt` | — | 起止时间（UTC） |
| `restore_verbose.log` | — | 恢复逐条日志 |
