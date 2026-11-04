#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段二约束行为验证：在真实数据库里逐条触发约束，证明它们不是"写在文件里"而是"真的拦得住"。

做法：整个验证跑在一个事务里，结束时 ROLLBACK —— 数据库不会留下任何业务数据，
      但约束的通过/拒绝行为已被真实执行验证。

覆盖：C01/C03/C04/C05/C06/C07/C08/C09/C10/C11/C12/C13/C14/C15/C16/C17/C19/C20/C21/C22/C23/C24/C25/C26
      以及几何类型门禁、生成列指纹、三个视图的可查询性与派生语义。

用法：PYTHONPATH=./ops/.deps python ops/verify_constraints.py <数据库名>
"""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg2

CODE_ROOT = Path(__file__).resolve().parent.parent

ok_count = 0
bad_count = 0
failures: list[str] = []


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in (CODE_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


class Probe:
    def __init__(self, conn):
        self.conn = conn
        self.cur = conn.cursor()
        self.sp = 0

    def _savepoint(self, name: str) -> None:
        self.sp += 1
        self.cur.execute(f"SAVEPOINT {name}_{self.sp}")

    def _rollback_to(self, name: str) -> None:
        self.cur.execute(f"ROLLBACK TO SAVEPOINT {name}_{self.sp}")

    def accept(self, label: str, sql: str, params=None) -> None:
        """期望成功。"""
        global ok_count, bad_count
        self._savepoint("sp_ok")
        try:
            self.cur.execute(sql, params)
            print(f"  ✓ 通过  {label}")
            ok_count += 1
        except psycopg2.Error as exc:
            self._rollback_to("sp_ok")
            print(f"  ✗ 失败  {label}  ← 应通过却被拒绝：{str(exc).splitlines()[0]}")
            failures.append(f"{label}: {exc}")
            bad_count += 1

    def reject(self, label: str, sql: str, params=None) -> None:
        """期望被约束拒绝。"""
        global ok_count, bad_count
        self._savepoint("sp_bad")
        try:
            self.cur.execute(sql, params)
            self._rollback_to("sp_bad")
            print(f"  ✗ 失败  {label}  ← 应被拒绝却通过了")
            failures.append(f"{label}: 未被拒绝")
            bad_count += 1
        except psycopg2.Error as exc:
            self._rollback_to("sp_bad")
            msg = str(exc).splitlines()[0]
            print(f"  ✓ 拒绝  {label}   [{msg[:90]}]")
            ok_count += 1

    def scalar(self, sql: str, params=None):
        self.cur.execute(sql, params)
        return self.cur.fetchone()[0]


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("用法: python ops/verify_constraints.py <数据库名>")
    dbname = sys.argv[1]
    env = load_env()
    conn = psycopg2.connect(
        host="127.0.0.1", port=int(env.get("DB_HOST_PORT", "55432")),
        dbname=dbname, user=env["POSTGRES_USER"], password=env["POSTGRES_PASSWORD"],
    )
    conn.autocommit = False
    p = Probe(conn)
    cur = p.cur

    print(f"### 约束行为验证（库={dbname}，全程在事务内，结束回滚）\n")

    # ---------------------------------------------------------------- 基础数据
    print("## 0. 建立最小证据链（事务内，结束回滚）")
    p.accept("data_source 插入 chgis",
             "INSERT INTO data_source (source_id, display_name) VALUES ('chgis','China Historical GIS')")

    p.accept("data_dataset 插入 per_record 数据集",
             """INSERT INTO data_dataset
                (dataset_id, source_id, display_name, record_scopes, place_grain, location_grain,
                 grain_evidence, occurrence_key_rule, external_id_nature, created_at, updated_at)
                VALUES ('ds_a','chgis','A',ARRAY['place','name'],'per_record','per_record',
                        'ev','none','source_declared',now(),now())""")
    p.accept("data_dataset 插入 per_parent 数据集",
             """INSERT INTO data_dataset
                (dataset_id, source_id, display_name, record_scopes, place_grain, location_grain,
                 grain_evidence, occurrence_key_rule, external_id_nature, created_at, updated_at)
                VALUES ('ds_b','chgis','B',ARRAY['name'],'per_parent_external_id','per_parent_external_id',
                        'ev','parent_ordinal','source_declared',now(),now())""")

    p.accept("import_batch 插入 succeeded 批次",
             """INSERT INTO import_batch (dataset_id, derivation_version, status, operator)
                VALUES ('ds_a','v2.1.1','succeeded','stage2-verify')""")
    batch_id = p.scalar("SELECT batch_id FROM import_batch ORDER BY batch_id DESC LIMIT 1")

    p.accept("source_record 插入 place 记录（父级哨兵 '-'）",
             """INSERT INTO source_record
                (dataset_id, record_scope, external_id, parent_external_id, duplicate_ordinal,
                 raw_file, raw_record_index, raw_payload, content_hash, first_batch_id, ingested_at)
                VALUES ('ds_a','place','100','-',0,'f.csv',1,'{"k":1}'::jsonb,
                        sha256('a'::bytea),%s,now())""", (batch_id,))
    sr1 = p.scalar("SELECT source_record_id FROM source_record ORDER BY source_record_id DESC LIMIT 1")

    p.accept("source_record 插入 name 记录",
             """INSERT INTO source_record
                (dataset_id, record_scope, external_id, parent_external_id, duplicate_ordinal,
                 raw_file, raw_record_index, raw_payload, content_hash, first_batch_id, ingested_at)
                VALUES ('ds_a','name','100-n1','100',0,'f.csv',2,'{"k":2}'::jsonb,
                        sha256('b'::bytea),%s,now())""", (batch_id,))
    sr2 = p.scalar("SELECT source_record_id FROM source_record ORDER BY source_record_id DESC LIMIT 1")

    p.accept("historical_place 插入导入地点",
             """INSERT INTO historical_place
                (dataset_id, grain_key, canonical_name, place_type, place_type_source,
                 created_from_source_record_id, created_at, updated_at)
                VALUES ('ds_a','100','测试城','unknown','unknown',%s,now(),now())""", (sr1,))
    place1 = p.scalar("SELECT place_id FROM historical_place ORDER BY place_id DESC LIMIT 1")

    p.accept("historical_place 插入人工地点（无源记录）",
             """INSERT INTO historical_place
                (dataset_id, grain_key, canonical_name, place_type, place_type_source,
                 created_by, created_at, updated_at)
                VALUES ('ds_a','manual-1','人工地点','unknown','manual','manual',now(),now())""")
    place2 = p.scalar("SELECT place_id FROM historical_place ORDER BY place_id DESC LIMIT 1")

    p.accept("historical_place_name 插入名称行",
             """INSERT INTO historical_place_name
                (place_id, source_record_id, name_text, name_type, name_lang, created_at, updated_at)
                VALUES (%s,%s,'测试城','primary','zh',now(),now())""", (place1, sr2))

    p.accept("historical_place_location 插入位置行",
             """INSERT INTO historical_place_location
                (place_id, source_record_id, geom, geom_type, crs_confidence,
                 representative_lon, representative_lat, original_x, original_y,
                 valid_from_year_astro, valid_to_year_astro, time_bound_type, created_at, updated_at)
                VALUES (%s,%s,ST_SetSRID(ST_MakePoint(116.4,39.9),4326),'Point','confirmed',
                        116.4,39.9,'116.4','39.9',-214,-207,'exact',now(),now())""", (place1, sr1))
    loc1 = p.scalar("SELECT location_id FROM historical_place_location ORDER BY location_id DESC LIMIT 1")

    # ---------------------------------------------------------------- C01 / 键
    print("\n## 1. C01 五段业务键 / C29 父级必需段")
    p.reject("C01 同五段键重复插入",
             """INSERT INTO source_record
                (dataset_id, record_scope, external_id, parent_external_id, duplicate_ordinal,
                 raw_file, raw_payload, content_hash, first_batch_id, ingested_at)
                VALUES ('ds_a','place','100','-',0,'f.csv','{}'::jsonb,sha256('z'::bytea),%s,now())""", (batch_id,))
    p.accept("C01 同 external_id 不同父级可共存（parent 生效）",
             """INSERT INTO source_record
                (dataset_id, record_scope, external_id, parent_external_id, duplicate_ordinal,
                 raw_file, raw_payload, content_hash, first_batch_id, ingested_at)
                VALUES ('ds_a','name','100','999',0,'f.csv','{}'::jsonb,sha256('y'::bytea),%s,now())""", (batch_id,))
    p.reject("C01 同 external_id 同父级 ordinal=1 可共存 → 但 ordinal=0 重复被拒",
             """INSERT INTO source_record
                (dataset_id, record_scope, external_id, parent_external_id, duplicate_ordinal,
                 raw_file, raw_payload, content_hash, first_batch_id, ingested_at)
                VALUES ('ds_a','name','100-n1','100',0,'f.csv','{}'::jsonb,sha256('w'::bytea),%s,now())""", (batch_id,))
    p.reject("C29 parent_external_id 为 NULL 被拒",
             """INSERT INTO source_record
                (dataset_id, record_scope, external_id, parent_external_id, raw_file,
                 raw_payload, content_hash, first_batch_id, ingested_at)
                VALUES ('ds_a','place','777',NULL,'f.csv','{}'::jsonb,sha256('v'::bytea),%s,now())""", (batch_id,))
    p.reject("C29 parent_external_id 为空串被拒",
             """INSERT INTO source_record
                (dataset_id, record_scope, external_id, parent_external_id, raw_file,
                 raw_payload, content_hash, first_batch_id, ingested_at)
                VALUES ('ds_a','place','778','','f.csv','{}'::jsonb,sha256('u'::bytea),%s,now())""", (batch_id,))

    # ---------------------------------------------------------------- 失效状态机
    print("\n## 2. C03/C19/C20/C21/C22 失效状态机")
    p.reject("C03 is_active=false 但无 inactive_reason",
             "UPDATE source_record SET is_active=false WHERE source_record_id=%s", (sr1,))
    p.reject("C03 is_active=true 但带 inactive_reason",
             "UPDATE source_record SET inactive_reason='source_absent' WHERE source_record_id=%s", (sr1,))
    p.reject("C19 inactive_reason 非法值",
             """UPDATE source_record SET is_active=false, inactive_reason='import_error',
                inactive_at=now(), inactive_in_batch_id=%s WHERE source_record_id=%s""", (batch_id, sr1))
    p.reject("C20 duplicate_quarantine 但 ordinal=0",
             """UPDATE source_record SET is_active=false, inactive_reason='duplicate_quarantine',
                inactive_at=now(), inactive_in_batch_id=%s WHERE source_record_id=%s""", (batch_id, sr1))
    p.reject("C21 有 reason 无 inactive_at",
             """UPDATE source_record SET is_active=false, inactive_reason='source_absent',
                inactive_in_batch_id=%s WHERE source_record_id=%s""", (batch_id, sr1))
    p.reject("C22 有 reason 无 inactive_in_batch_id",
             """UPDATE source_record SET is_active=false, inactive_reason='source_absent',
                inactive_at=now() WHERE source_record_id=%s""", (sr1,))
    p.accept("C03/C19/C21/C22 合法的 source_absent 失效",
             """UPDATE source_record SET is_active=false, inactive_reason='source_absent',
                inactive_at=now(), inactive_in_batch_id=%s WHERE source_record_id=%s""", (batch_id, sr1))
    p.accept("恢复活性（子行/源行回到 staging 语义上由导入器决定）",
             """UPDATE source_record SET is_active=true, inactive_reason=NULL,
                inactive_at=NULL, inactive_in_batch_id=NULL WHERE source_record_id=%s""", (sr1,))

    # ---------------------------------------------------------------- 地点约束
    print("\n## 3. C04/C05/C06 地点约束")
    p.reject("C04 (dataset_id, grain_key) 重复",
             """INSERT INTO historical_place
                (dataset_id, grain_key, canonical_name, place_type, place_type_source,
                 created_from_source_record_id, created_at, updated_at)
                VALUES ('ds_a','100','重复城','unknown','unknown',%s,now(),now())""", (sr1,))
    p.reject("C05 非人工地点缺 created_from_source_record_id",
             """INSERT INTO historical_place
                (dataset_id, grain_key, canonical_name, place_type, place_type_source, created_at, updated_at)
                VALUES ('ds_a','no-anchor','无锚点','unknown','unknown',now(),now())""")
    p.reject("C06 合并无审批（缺 merge_review_ref/merged_at）",
             """UPDATE historical_place SET record_status='merged', merged_into_place_id=%s
                WHERE place_id=%s""", (place2, place1))
    p.reject("合并到自己被拒",
             """UPDATE historical_place SET record_status='merged', merged_into_place_id=place_id,
                merge_review_ref=NULL, merged_at=now() WHERE place_id=%s""", (place1,))
    p.reject("地点 record_status 写入 V2.1 的 published（已作废）",
             "UPDATE historical_place SET record_status='published' WHERE place_id=%s", (place1,))
    p.reject("place_type_source='lev_rank' 但 place_type='unknown'",
             "UPDATE historical_place SET place_type_source='lev_rank' WHERE place_id=%s", (place1,))
    p.reject("非人工地点把 place_type_source 写成 manual",
             "UPDATE historical_place SET place_type_source='manual' WHERE place_id=%s", (place1,))

    # ---------------------------------------------------------------- 子表约束
    print("\n## 4. C07/C08/C13/C14/C15/C16/C25/C26 子表约束")
    p.reject("C07 同一 source_record 再派生一条位置行",
             """INSERT INTO historical_place_location
                (place_id, source_record_id, crs_confidence, created_at, updated_at)
                VALUES (%s,%s,'confirmed',now(),now())""", (place1, sr1))
    p.reject("C08 同 (source_record, name_type, name_text, name_lang) 重复",
             """INSERT INTO historical_place_name
                (place_id, source_record_id, name_text, name_type, name_lang, created_at, updated_at)
                VALUES (%s,%s,'测试城','primary','zh',now(),now())""", (place1, sr2))
    p.reject("C14 CRS 未知却 published（CRS 门禁）",
             "UPDATE historical_place_location SET crs_confidence='unknown', record_status='published' WHERE location_id=%s", (loc1,))
    p.reject("C15 无几何却 published（几何门禁）",
             """INSERT INTO historical_place_location
                (place_id, source_record_id, geom, geom_type, crs_confidence, record_status, created_at, updated_at)
                VALUES (%s,NULL,NULL,NULL,'confirmed','published',now(),now())""", (place1,))
    p.reject("C16 time_bound_type='exact' 但缺端点",
             "UPDATE historical_place_location SET time_bound_type='exact', valid_to_year_astro=NULL WHERE location_id=%s", (loc1,))
    p.reject("C25 record_status='rejected' 但 rejected_by 为空",
             "UPDATE historical_place_location SET record_status='rejected' WHERE location_id=%s", (loc1,))
    p.reject("C25 rejected_by 非空但 record_status 不是 rejected",
             "UPDATE historical_place_location SET rejected_by='auto' WHERE location_id=%s", (loc1,))
    p.reject("C26 rejected_by 非法值",
             "UPDATE historical_place_location SET record_status='rejected', rejected_by='robot' WHERE location_id=%s", (loc1,))
    p.accept("C25/C26 合法的 auto 拒绝",
             "UPDATE historical_place_location SET record_status='rejected', rejected_by='auto' WHERE location_id=%s", (loc1,))
    p.accept("恢复 location 为 staging 并清 rejected_by",
             "UPDATE historical_place_location SET record_status='staging', rejected_by=NULL WHERE location_id=%s", (loc1,))
    p.reject("C13 source_time_columns 非空但同时有数字规则码",
             """UPDATE historical_place_location SET source_time_columns='year_after_which', source_beg_rule=1
                WHERE location_id=%s""", (loc1,))
    p.reject("几何类型与 geom_type 不一致",
             "UPDATE historical_place_location SET geom_type='Polygon' WHERE location_id=%s", (loc1,))
    p.reject("name_lang 非法 BCP-47 被拒",
             """INSERT INTO historical_place_name
                (place_id, source_record_id, name_text, name_type, name_lang, created_at, updated_at)
                VALUES (%s,%s,'x','alternate','中文',now(),now())""", (place1, sr2))
    p.accept("name_lang='und' 与 NULL 均合法",
             """INSERT INTO historical_place_name
                (place_id, source_record_id, name_text, name_type, name_lang, created_at, updated_at)
                VALUES (%s,%s,'x-und','alternate','und',now(),now())""", (place1, sr2))

    # ---------------------------------------------------------------- 候选
    print("\n## 5. C09/C17 候选匹配")
    p.accept("candidate_match 插入合法候选",
             """INSERT INTO candidate_match
                (relation_type, place_id_a, place_id_b, confidence, created_at, updated_at)
                VALUES ('homonym_diff_place',%s,%s,'medium',now(),now())""", (place1, place2))
    p.reject("C09 (relation_type, a, b) 重复",
             """INSERT INTO candidate_match
                (relation_type, place_id_a, place_id_b, confidence, created_at, updated_at)
                VALUES ('homonym_diff_place',%s,%s,'low',now(),now())""", (place1, place2))
    p.reject("C17 direction 只在迁移类可用",
             """INSERT INTO candidate_match
                (relation_type, place_id_a, place_id_b, confidence, direction, created_at, updated_at)
                VALUES ('homonym_diff_place',%s,%s,'low','a_to_b',now(),now())""", (place1, place2))
    p.reject("同一对地点 a=b 被拒",
             """INSERT INTO candidate_match
                (relation_type, place_id_a, place_id_b, confidence, created_at, updated_at)
                VALUES ('same_entity_same_seat',%s,%s,'low',now(),now())""", (place1, place1))
    p.reject("confirmed 缺 reviewer/reviewed_at",
             """INSERT INTO candidate_match
                (relation_type, place_id_a, place_id_b, confidence, status, created_at, updated_at)
                VALUES ('same_entity_same_seat',%s,%s,'high','confirmed',now(),now())""", (place1, place2))

    # ---------------------------------------------------------------- 台账
    print("\n## 6. C10/C11/C12/C23/C24 + 生成列指纹")
    insert_dq = """INSERT INTO data_quality_issue
                     (dataset_id, source_record_id, place_id, issue_type, severity, field_name,
                      observed_value, action_taken, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,now())"""
    p.accept("台账插入（六段齐全）", insert_dq,
             ("ds_a", sr1, place1, "unknown_crs", "warning", "crs", "unknown", "preserved_and_flagged"))
    fp = p.scalar("""SELECT issue_fingerprint FROM data_quality_issue
                     WHERE place_id=%s ORDER BY issue_id DESC LIMIT 1""", (place1,))
    direct = p.scalar("""SELECT md5(jsonb_build_array(%s::bigint,%s::text,%s::bigint,
                                %s::text,%s::text,%s::text)::text)""",
                      (sr1, "ds_a", place1, "unknown_crs", "crs", "unknown"))
    print(f"    生成列指纹 = {fp}")
    print(f"    直算式指纹 = {direct}")
    if fp == direct:
        print("    ✓ 生成列与 §4.5 直算式逐字节相等")
        globals()["ok_count"] += 1
    else:
        print("    ✗ 生成列与直算式不等")
        failures.append("指纹不等")

    p.reject("C10 同六段重复插入（指纹唯一）", insert_dq,
             ("ds_a", sr1, place1, "unknown_crs", "warning", "crs", "unknown", "preserved_and_flagged"))
    p.accept("observed_value 不同 ⇒ 不同指纹，可各占一行", insert_dq,
             ("ds_a", sr1, place1, "unknown_crs", "warning", "crs", "EPSG:9999", "preserved_and_flagged"))
    p.reject("C11 dataset_id 与 place_id 同时为空",
             insert_dq, (None, None, None, "unknown_crs", "warning", "", "x", "preserved_and_flagged"))
    p.reject("C12 dataset_id 为空但带 source_record_id",
             insert_dq, (None, sr1, place1, "unknown_crs", "warning", "", "y", "preserved_and_flagged"))
    # 注意：此处验证的是「枚举值域校验」，与许可无关。issue_type 的设计值域为 19 值（V2.1.1 §5.9），
    #       任何不在值域内的字符串都会被 ck_data_quality_issue_issue_type 拒绝，这是枚举完整性，
    #       不是许可门禁；M4-2 起系统内已不存在任何许可概念（审计脚本随之删除）。
    p.reject("issue_type 写入值域外的任意字符串被枚举拒绝",
             insert_dq, ("ds_a", sr1, place1, "not_a_designed_issue_type", "warning", "", "z", "preserved_and_flagged"))
    p.reject("C23 occurrence_count = 0",
             "UPDATE data_quality_issue SET occurrence_count=0 WHERE place_id=%s", (place1,))
    p.reject("C24 有 first_batch_id 无 last_batch_id",
             "UPDATE data_quality_issue SET first_batch_id=%s, last_batch_id=NULL WHERE place_id=%s",
             (batch_id, place1))

    # ---------------------------------------------------------------- 数据集
    print("\n## 7. data_dataset 约束")
    p.reject("record_scopes 空数组被拒",
             """INSERT INTO data_dataset
                (dataset_id, source_id, display_name, record_scopes, place_grain, location_grain,
                 grain_evidence, occurrence_key_rule, external_id_nature, created_at, updated_at)
                VALUES ('ds_empty','chgis','E',ARRAY[]::text[],'per_record','per_record',
                        'ev','none','source_declared',now(),now())""")
    p.reject("place_grain 写入已作废的 per_external_id",
             "UPDATE data_dataset SET place_grain='per_external_id' WHERE dataset_id='ds_a'")
    p.reject("pipeline_composed 却声明 parent_ordinal",
             "UPDATE data_dataset SET external_id_nature='pipeline_composed' WHERE dataset_id='ds_b'")

    # ---------------------------------------------------------------- 视图
    print("\n## 8. 三个派生视图（真实数据路径）")
    cur.execute("SELECT place_id, evidence_role, is_anchor, is_canonical_row FROM v_place_evidence ORDER BY place_id, evidence_role")
    rows = cur.fetchall()
    print(f"  v_place_evidence 行数={len(rows)}")
    for r in rows:
        print(f"    place={r[0]} role={r[1]} anchor={r[2]} canonical={r[3]}")
    cur.execute("SELECT place_id, liveness, record_status, manual_rejected_rows, distinct_inactive_reasons FROM v_place_liveness ORDER BY place_id")
    for r in cur.fetchall():
        print(f"  v_place_liveness place={r[0]} liveness={r[1]} status={r[2]} manual_rejected={r[3]} reasons={r[4]}")
    cur.execute("""SELECT place_id, span_from_astro, span_to_astro, valid_child_rows, child_rows_total,
                          derivation_kind, all_children_rejected FROM v_place_time_span ORDER BY place_id""")
    for r in cur.fetchall():
        print(f"  v_place_time_span place={r[0]} [{r[1]},{r[2]}] valid={r[3]}/{r[4]} kind={r[5]} all_rejected={r[6]}")

    # 视图派生语义抽查：人工地点 liveness 必为 manual；带年份的有跨度
    cur.execute("SELECT place_id, liveness FROM v_place_liveness")
    live = dict(cur.fetchall())
    checks = [
        ("人工地点 liveness='manual'", live.get(place2) == "manual"),
        ("导入地点 liveness='active'", live.get(place1) == "active"),
    ]
    cur.execute("SELECT span_from_astro, span_to_astro FROM v_place_time_span WHERE place_id=%s", (place1,))
    span = cur.fetchone()
    checks.append(("时间跨度取到 -214/-207", span == (-214, -207)))
    for label, good in checks:
        print(f"  {'✓' if good else '✗'} {label}")
        if good:
            globals()["ok_count"] += 1
        else:
            failures.append(label)

    # ---------------------------------------------------------------- 收尾
    conn.rollback()
    print("\n### 事务已 ROLLBACK，数据库未留下任何验证数据")
    cur.execute("SELECT count(*) FROM historical_place")
    print(f"    historical_place 现有行数={cur.fetchone()[0]}（应为 0）")

    print("\n" + "=" * 60)
    print(f"结果：通过 {ok_count} 项，失败 {bad_count} 项，附加断言失败 {len(failures)} 项")
    return 0 if bad_count == 0 and not failures else 1


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
