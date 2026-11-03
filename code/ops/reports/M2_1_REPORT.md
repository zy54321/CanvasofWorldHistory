# M2-1 数据库扩展交付报告

执行时间（UTC）：2026-11-03T11:52Z 起 ｜ 工作目录：`E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory\code` ｜ 正式库：`canvas_history`

---

## 一、结论

| 验收项 | 判定 | 依据 |
|---|---|---|
| 1. 新 Migration 在正式库成功执行 | **PASS** | `V4__person_event_model.sql` → 版本 v4，checksum `1291861836` |
| 2. 六张新表结构与设计一致 | **PASS** | 依据 `03_核心数据模型与时间规范.md` §5；字段核对见 `07_schema_dump.log` |
| 3. 主键/外键/唯一/CHECK 实际生效 | **PASS** | 48 项测试中 A01–A05、D01–D12、E01–E08、F01–F03 逐条触发并断言 |
| 4. 人物/名称/事件/三类关联可写可读 | **PASS** | B01–B07、C01–C03 |
| 5. BCE/CE 换算与区间约束通过 | **PASS** | `time_model_test.sql` 18/18 PASS |
| 6. 删除有关联数据时正确阻止/处理，无孤儿 | **PASS** | F04–F10、`12_delete_semantics.log` 孤儿扫描 = 0 |
| 7. 数据库重启后数据仍在 | **PASS** | 重启容器后 6 表/2 名称/1 事件/3 关联全部可读 |
| 8. 原九表数据量与施工前完全一致 | **PASS** | 29,391 / 19,039 / 47,499 / 18,101 / 53,131 / 12,831 / 7 / 7 / 4 逐表相等 |
| 9. 原 Flyway 记录与校验和不变 | **PASS** | V1 `882334605` / V2 `966227528` / V3 `-2058740630` 全部未变 |
| 10. M0/M1 功能未受影响 | **PASS** | 6 项 API 回归 + 15 项浏览器 E2E 全 PASS（`06`、`shots/e2e_result.json`） |

**总判定：PASS（10/10）。** 有 3 项需 Owner 知晓的偏差，见 §6。

---

## 二、Migration 执行结果

```
Database: jdbc:postgresql:******** (PostgreSQL 17.11)
Successfully validated 4 migrations
Current version of schema "public": 3
Migrating schema "public" to version "4 - person event model"
Successfully applied 1 migration to schema "public", now at version v4
```

- 新增文件：`backend/src/main/resources/db/migration/V4__person_event_model.sql`（约 380 行）
- V1、V2、V3 **未改动一个字节**，校验和与施工前逐位相同
- 空库从零重建同样通过（`10_empty_db_rebuild.log`）：V1→V4 一次跑通，48/48 测试全 PASS

---

## 三、六张新表

| 表 | 行数（列数） | 主键 | 关键约束 |
|---|---:|---|---|
| `person` | 17 | `person_id` identity | 生卒年份与精度成对（`(birth_year_astro IS NULL) = (birth_precision='unknown')`）、生 ≤ 卒、姓名非空 |
| `person_name` | 13 | `person_name_id` | `uq_pn_name(person_id, name_type, name_text, coalesce(name_lang,''))`、8 类 name_type、BCP-47 语言形态 |
| `event` | 17 | `event_id` | precision=unknown ⇒ 起止年皆空；precision≠unknown ⇒ 起年必填；起 ≤ 止 |
| `event_place` | 8 | `event_place_id` | `uq_event_place(event_id, place_id, location_role)`、有效期起 ≤ 止 |
| `event_person` | 8 | `event_person_id` | `uq_event_person(event_id, person_id, role)` |
| `person_place` | 11 | `person_place_id` | `uq_person_place(person_id, place_id, relation_type, coalesce(start,-2147483648))`、时间三元组一致性 |

合计 **74 列、6 主键、7 外键、33 条 CHECK、4 个业务唯一索引**（`A01–A05` 实测：6 表 / 6 主键 / 7 外键 / 33 CHECK / 4 唯一索引；`pg_indexes` 共 20 条含 6 个主键索引与 10 个查询索引）。

**时间模型**：全部使用天文学纪年整数（公元前 1 年 = 0）。`person` 用 `birth_year_astro/death_year_astro` + 各自 precision，`event` 用 `start/end_year_astro` + `time_precision`，`person_place` 带关系有效期，`event_place`/`event_person` 可选有效期——与设计文档 §4「时间属性应用位置」逐条对应。

**删除语义**（对应验收第 6 条）：
- `person_name` / `event_place` / `event_person` / `person_place` → 引用 `person` / `event` 时 **ON DELETE CASCADE**（关联行不是独立业务对象，随主体消失）
- 三类关联表 → 引用 `historical_place` 时 **ON DELETE RESTRICT**（地点是独立业务对象，绝不连带删除）

---

## 四、实际测试结果

### 4.1 结构与行为测试：48/48 PASS

在**正式库**执行（事务内，末尾 ROLLBACK），日志 `04_schema_test_formal.log`：

| 组 | 覆盖 | 结果 |
|---|---|---|
| A01–A05 | 六表存在、主键、外键、CHECK、唯一索引 | 5/5 |
| B01–B07 | 写入回读、名称三型、一对多关联、多地点多人物 | 7/7 |
| C01–C03 | 资料残缺可保存、同名人物不合并（李密 2 行并存） | 3/3 |
| D01–D12 | 时间约束：年精度成对、生卒顺序、事件起止、开放区间、公元前倒挂、**跨 0 年** | 12/12 |
| E01–E08 | 唯一约束正反例（同人同名不同类型允许、同事件同地点不同角色允许、多时段到访允许） | 8/8 |
| F01–F10 | 外键拒绝、RESTRICT 拒删地点、CASCADE 清关联、孤儿扫描、拒绝后地点仍在 | 10/10 |
| G01 | `updated_at` 触发器 | 1/1 |
| H01–H02 | 原九表 170 列未变、三个视图仍在 | 2/2 |

### 4.2 时间模型测试：18/18 PASS

`11_time_model_test.log`，逐条核对设计文档 §2 的换算表：

```
T01 BCE 771 → -770    T02 BCE 2 → -1    T03 BCE 1 → 0
T04 CE 1 → 1          T05 CE 2026 → 2026
T06 astro=0 显示「公元前 1 年」而非「公元 0 年」
T10 按「公元前 770 年」检出 1 条（不重不漏）
T11 按「公元前 1 年」(astro=0) 命中该年与覆盖它的事件，且不误命中「公元 1 年」
T12/T13 区间重叠查询：查 CE 50 命中跨前后事件，查 BCE 200 不命中
T14 跨前后 BCE100~CE100：差值 199、含首尾 200 年
T15 生卒 BCE100~CE50：差值 149、含首尾 150 年
T17/T18 单年事件端点包含式：查 -769 命中、查 -768 不命中
```

### 4.3 持久化

重启容器（healthy 5s）后重新查询：`person=1 / person_name=2 / event=1 / event_place=1 / event_person=1 / person_place=1` 全部仍在，Flyway 四条记录完好。验证后已删除样本数据，六表归零，避免把自造内容当真实史料留在正式库（`05_persistence.log`）。

### 4.4 删除语义（真实地点实测）

```
1) DELETE 被引用的地点 → ERROR 23503，被外键拒绝
2) 拒绝后该地点仍在（place_still_exists = 1）
3) 删事件 → event_place 归 0，person_place 仍 1，地点仍 1
4) 删人物 → person_place 归 0，地点仍 1
5) 全库七条外键孤儿扫描 = 0
```

### 4.5 数据保护对照（`09_final_compare.log`）

九表行数、V1–V3 校验和、七张 CSV 指纹全部与施工前一致；`max(place_id)=38084`、`max(name_id)=94998` 未变。

### 4.6 M0/M1 回归

- API：搜索「桂林」10 条、洛阳 year=1200→1 条 / -500→0 条、详情 27421、bbox 返回 FeatureCollection、limit=99999 钳制为 2000、三视图 84,958 / 19,039 / 19,039
- 浏览器 E2E：**15/15 PASS**（`shots/e2e_result.json`），含四样式切换零漂移、四区域、搜索/别名/年代/分页、GeoJSON、互相定位、控制台无真实错误

---

## 五、新增与修改文件清单

**新增**
```
backend/src/main/resources/db/migration/V4__person_event_model.sql   六表 + 约束 + 索引 + updated_at 触发器
ops/m2/schema_behavior_test.sql                                      48 项结构与行为测试（事务内自清理）
ops/m2/time_model_test.sql                                           18 项 BCE/CE 与时区区间测试
ops/m2/final_compare.py                                              数据完整性对比（只读）
ops/reports/m2_1/01_before.log … 12_delete_semantics.log             全部执行日志
ops/reports/m2_1/07_schema_dump.log                                  六表 \d 实测结构
ops/reports/m2_1/08_constraints_dump.log                             33 CHECK / 7 FK / 索引的可核对面
ops/reports/m2_1/shots/                                              M0/M1 回归截图 19 张 + e2e_result.json
```

**修改**：无。V1–V3、九张业务表、七张 CSV、前后端代码全部未动。

---

## 六、需要 Owner 知晓的三处偏差

1. **`historical_place_place_id_seq` 从 38,084 前进到 38,086（+2）**
   测试脚本最初用自增 id 造测试地点，`nextval` 不随事务回滚，导致序列前进 2。已改为显式负 id（`-1/-2`）不再消耗，并把这条约束写进脚本注释。
   **未做 `ALTER SEQUENCE RESTART`**（纪律禁止重置序列），因此**下一次人物/事件以外的新地点将拿到 38,087**。真实数据主键区间未受影响（`max(place_id)=38084`）。

2. **六张新表的 identity 序列已被测试消耗**
   `person=37 / person_name=26 / event=39 / event_place=17 / event_person=16 / person_place=23`。表内 0 行，但**首个真实人物将拿到 `person_id=38`**，不是 1。同理未重置。如果期望从 1 开始，需 Owner 明确授权后再处理。

3. **`event_type` / `location_role` / `role` / `relation_type` 未做枚举**
   设计文档只给了字段名、未给值域（`03_核心数据模型与时间规范.md` §5 仅列 `event_type`）。本版只约束「非空」，不臆造分类。这四处取值规范应在 M2-2 与产品确认后，用新 Migration 追加 CHECK 或字典表，**不回改 V4**。
   同样，`person_name.name_type` 我给了 8 个值（primary/alternate/transliteration/historical/courtesy/art/posthumous/pseudonym），依据是 §7「一个地点可以有多个历史名称」与中文史料里「字/号/谥号」的常态，属于**我做的合理取值**，请确认是否接受。

---

## 七、未做（按指令不属于 M2-1）

- 未写任何 M2 后端 API、未改前端的搜索/详情（M2-2 范畴）
- 未建国家/政权疆域、AI、权限中心、消息队列
- 未给 `person`/`event` 建全文检索（`pg_trgm` 可用但未启用；待 M2-2 确定搜索方案再加）
- 未合并人物/事件提供 merge 通道（`merged_into` 未加列；设计文档也未要求，同名并存已满足）

## 八、未解决问题

1. `event_type` 等四个自由字段的取值规范（阻断 M2-2 的接口设计，需产品确认）
2. 上表第 1、2 条的序列起点是否需要归零（需 Owner 授权）
3. `canvas_history_m2check` 测试库仍保留（含 V1–V4 与 0 行数据），是否删除待定

已停在此处，未进入 M2-2。
