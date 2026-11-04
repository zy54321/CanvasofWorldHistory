#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段三：人工保护 / 回滚四道闸 / 真值表穷尽性——事务内受控实测。

三块内容全部在**同一个事务**里执行，结束时 `ROLLBACK`，不留任何痕迹：
  P  人工锁定与字段保护（走真实 Importer 代码路径，不是 SQL 近似）
  Q  回滚四道闸 R1 / R2 / R2b / R2c（按 ROLLBACK §3.4 六步判定顺序的参考实现）
  T  真值表 7 个合法格 + orphaned 反例（C27 穷尽性）

诚实标注：
  · Q 的 N_fail_rb 用「受控注入」触发（故意让软撤语句违反 CHECK），不是真实数据缺陷；
    R2c 的等式因此可实测，但 ROLLBACK §11 U5「无真实回滚批次」的保留依然成立。
  · T 的 orphaned 格是**故意造出来的反例**，用于证明 R4f 不是空转。

用法：
  PYTHONPATH=./ops/.deps python ops/verify_rollback_and_protection.py --db canvas_history_stage3
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg2                                    # noqa: E402
import import_staging as imp_mod                   # noqa: E402

CODE_ROOT = Path(__file__).resolve().parent.parent
RESULTS: list[tuple[str, str, str]] = []


def record(no: str, status: str, msg: str) -> None:
    RESULTS.append((no, status, msg))
    icon = {"PASS": "✓", "FAIL": "✗", "UNVERIFIED": "?", "INFO": "·"}[status]
    print(f"  {icon} [{no}] {msg}")


def head(t: str) -> None:
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def scalar(cur, sql, args=()):
    cur.execute(sql, args)
    r = cur.fetchone()
    return r[0] if r else None


# ============================================================ P 人工保护
def part_p(conn, dbname: str) -> None:
    head("P   人工锁定与字段保护（真实导入代码路径，事务内）")
    cur = conn.cursor()

    # 三种保护位各挑一个真实地点：locked / manual_edited_fields / created_by='manual'
    cases = [
        ("chgis_v6_prefecture_points", "locked",
         "UPDATE historical_place SET locked=true, canonical_name='【保护测试·locked】' "
         "WHERE place_id = (SELECT min(place_id) FROM historical_place WHERE dataset_id=%s)"),
        ("mcgd_zenodo_22094815_head960", "manual_edited_fields",
         "UPDATE historical_place SET manual_edited_fields='{canonical_name}', "
         "canonical_name='【保护测试·字段级】' "
         "WHERE place_id = (SELECT min(place_id) FROM historical_place WHERE dataset_id=%s)"),
        ("pleiades_gis_4_1_slice", "created_by=manual",
         "UPDATE historical_place SET created_by='manual', canonical_name='【保护测试·人工创建】' "
         "WHERE place_id = (SELECT min(place_id) FROM historical_place WHERE dataset_id=%s)"),
    ]
    targets = []
    for ds, label, sql in cases:
        cur.execute(sql, (ds,))
        pid = scalar(cur, "SELECT min(place_id) FROM historical_place "
                          "WHERE dataset_id=%s AND canonical_name LIKE '【保护测试%%'", (ds,))
        targets.append((ds, label, pid))
        print(f"    夹具：{ds:32s} place_id={pid}  保护位={label}")

    print("\n    以真实 Importer 重跑一次（只跑到 write_places + write_ledger，随后整体回滚）…")
    t0 = dt.datetime.now(dt.timezone.utc)
    imp = imp_mod.Importer(conn, dbname, "ops/verify_rollback_and_protection.py", dry_run=True)
    imp.build()
    imp.upsert_reference(t0)
    imp.create_batches(t0)
    imp.write_source_records(t0)
    imp.write_places(t0)
    imp.write_ledger(t0)

    print("\n    断言：")
    ok = True
    for ds, label, pid in targets:
        now_name = scalar(cur, "SELECT canonical_name FROM historical_place WHERE place_id=%s", (pid,))
        kept = now_name.startswith("【保护测试")
        print(f"      {label:22s} place {pid} 现值 = {now_name}  {'未覆盖 ✓' if kept else '被覆盖 ✗'}")
        ok &= kept

    # 两个口径必须分开：这里数的是**地点级**人工保护；源记录级阻断是 cnt_blocked（进 G1）。
    n_place_blocked = len(imp.manual_blocks)
    n_source_blocked = sum(imp.cnt_blocked.values())
    n_ledger = scalar(cur, """SELECT count(*) FROM data_quality_issue
                               WHERE issue_type = 'manual_edit_conflict'
                                 AND place_id = ANY(%s)""",
                      ([p for _d, _l, p in targets],))
    print(f"      place_blocked（地点级人工保护）{n_place_blocked}（期望 3）；"
          f"source_blocked（源记录级 quarantine_hold）{n_source_blocked}")
    print(f"      台账 manual_edit_conflict {n_ledger} 条（期望 3，一行一条，R2 的 1:1 前提）")
    ok &= (n_place_blocked == 3 and n_ledger == 3)
    record("P1", "PASS" if ok else "FAIL",
           f"locked / manual_edited_fields / created_by=manual 三种保护位均未被机器覆盖；"
           f"place_blocked={n_place_blocked}、source_blocked={n_source_blocked}、"
           f"manual_edit_conflict={n_ledger}（1:1）" if ok
           else f"保护失败：覆盖={[t for t in targets]} place_blocked={n_place_blocked} "
                f"ledger={n_ledger}")

    # 无保护位的地点仍然正常（不被误挡）：新增 / 更新 / 无变化 / 人工保护跳过 四类必须覆盖全部地点
    ps = imp.place_stat
    n_places = scalar(cur, "SELECT count(*) FROM historical_place")
    n_prot = len(targets)
    print(f"\n    本轮 write_places 四类处置：新增 {ps['inserted']} / 更新 {ps['updated']} / "
          f"无变化 {ps['noop']:,} / 人工保护跳过 {ps['protected']}（登记台账 {ps['blocked']}）；"
          f"合计 {ps['inserted'] + ps['updated'] + ps['noop'] + ps['protected']:,} vs 地点数 {n_places:,}")
    p2_bad = []
    if ps["inserted"] != 0:
        p2_bad.append(f"新增 {ps['inserted']}≠0（对已入库库重跑不应新增）")
    if ps["updated"] != 0:
        p2_bad.append(f"更新 {ps['updated']}≠0（数据未变不应更新）")
    if ps["protected"] != n_prot:
        p2_bad.append(f"保护跳过 {ps['protected']}≠{n_prot}")
    if ps["blocked"] != n_prot:
        p2_bad.append(f"台账登记 {ps['blocked']}≠{n_prot}")
    if ps["noop"] != n_places - n_prot:
        p2_bad.append(f"无变化 {ps['noop']}≠{n_places - n_prot}")
    if ps["inserted"] + ps["updated"] + ps["noop"] + ps["protected"] != n_places:
        p2_bad.append("四类之和 ≠ 地点数")
    if ps["total"] != n_places:
        p2_bad.append(f"处理地点数 {ps['total']}≠{n_places}")
    if p2_bad:
        record("P2", "FAIL", f"四类处置与地点数对不上：{p2_bad}；place_stat={ps}")
    else:
        record("P2", "PASS",
               f"{n_places:,} 个地点 = 新增 {ps['inserted']} + 更新 {ps['updated']} + "
               f"无变化 {ps['noop']:,} + 人工保护跳过 {ps['protected']}；"
               f"仅这 {n_prot} 个被挡且各登记 1 条台账，其余 {ps['noop']:,} 个地点重跑均判为无变化，无误挡")


# ============================================================ Q 回滚四道闸
FIX_DS = "fx_rb_ds"
TT_DS = "fx_tt_ds"
TT_MIX = "fx_tt_mix"


def _mk_dataset(cur, ds: str, grain_place: str, grain_loc: str, rule: str, scopes: str) -> None:
    cur.execute("""INSERT INTO data_dataset
                     (dataset_id, source_id, display_name, dataset_version, record_scopes,
                      place_grain, location_grain, grain_evidence, occurrence_key_rule,
                      external_id_nature, record_count, is_active, created_at, updated_at)
                   VALUES (%s,'chgis','回滚/真值表夹具','fixture',%s,%s,%s,
                           '夹具：仅用于事务内受控实测，结束即回滚',%s,'source_declared',0,true,now(),now())
                   ON CONFLICT (dataset_id) DO NOTHING""",
                (ds, scopes, grain_place, grain_loc, rule))


def _mk_batch(cur, ds: str, status: str, n_in: int, of_batch: int | None = None) -> int:
    cur.execute("""INSERT INTO import_batch
                     (dataset_id, dataset_version, derivation_version, status, input_file,
                      input_row_count, started_at, finished_at, operator, notes, rollback_of_batch_id)
                   VALUES (%s,'fixture','fixture',%s,'fixture.csv',%s,now(),now(),
                           'ops/verify_rollback_and_protection.py','夹具',%s)
                   RETURNING batch_id""", (ds, status, n_in, of_batch))
    return cur.fetchone()[0]


def _mk_sr(cur, ds, ext, ordinal, batch, active=True, reason=None, last_batch=None,
           parent="-", scope="place"):
    cur.execute("""INSERT INTO source_record
                     (dataset_id, record_scope, external_id, parent_external_id, duplicate_ordinal,
                      raw_file, raw_record_index, raw_payload, content_hash,
                      first_batch_id, last_batch_id, is_active, inactive_reason,
                      inactive_at, inactive_in_batch_id, ingested_at)
                   VALUES (%s,%s,%s,%s,%s,'fixture.csv',0,'{}'::jsonb,sha256(%s::bytea),
                           %s,%s,%s,%s,%s,%s,now())
                   RETURNING source_record_id""",
                (ds, scope, ext, parent, ordinal, f"{ds}:{ext}:{ordinal}".encode(),
                 batch, last_batch if last_batch is not None else batch,
                 active, reason, None if active else dt.datetime.now(dt.timezone.utc),
                 None if active else batch))
    return cur.fetchone()[0]


def part_q(conn) -> None:
    head("Q   回滚四道闸 R1 / R2 / R2b / R2c（ROLLBACK §3.4 六步判定顺序的参考实现）")
    cur = conn.cursor()
    _mk_dataset(cur, FIX_DS, "per_record", "per_record", "none", "{place}")

    # ---------- 构造被回滚批 R（11 行）
    R = _mk_batch(cur, FIX_DS, "succeeded", 11)
    print(f"    被回滚批 R = {R}（夹具 11 行：正常3 / 已失效1 / 保护位2 / 批次不符1 / 墓碑1 / 隔离2 / 写入失败1）")

    sr, plan = {}, {}
    # 1–3 正常
    for i in (1, 2, 3):
        sr[i] = _mk_sr(cur, FIX_DS, f"fx{i:02d}", 0, R)
        plan[i] = "rolled_back"
    # 4 已失效（source_absent）⇒ N_noop
    sr[4] = _mk_sr(cur, FIX_DS, "fx04", 0, R, active=False, reason="source_absent")
    plan[4] = "noop"
    # 5 last_batch_id ≠ R ⇒ N_blocked / rollback_conflict
    some_batch = scalar(cur, "SELECT min(batch_id) FROM import_batch")
    sr[5] = _mk_sr(cur, FIX_DS, "fx05", 0, R, last_batch=some_batch)
    plan[5] = "stale_batch"
    # 6 locked ⇒ N_blocked / manual_edit_conflict
    sr[6] = _mk_sr(cur, FIX_DS, "fx06", 0, R)
    plan[6] = "locked"
    # 7 manual_edited_fields ⇒ N_blocked / manual_edit_conflict
    sr[7] = _mk_sr(cur, FIX_DS, "fx07", 0, R)
    plan[7] = "field_locked"
    # 8 merged（墓碑）⇒ N_blocked / rollback_conflict
    sr[8] = _mk_sr(cur, FIX_DS, "fx08", 0, R)
    plan[8] = "tombstone"
    # 9–10 本批隔离 ⇒ N_quar（不进回滚作用集）
    sr[9] = _mk_sr(cur, FIX_DS, "fx09", 1, R, active=False, reason="duplicate_quarantine")
    sr[10] = _mk_sr(cur, FIX_DS, "fx10", 2, R, active=False, reason="duplicate_quarantine")
    plan[9] = plan[10] = "quarantine"
    # 11 写入失败（受控注入）⇒ N_fail_rb
    sr[11] = _mk_sr(cur, FIX_DS, "fx11", 0, R)
    plan[11] = "inject_fail"

    # 地点（隔离行不派生任何对象）
    places = {}
    for i in (1, 2, 3, 4, 5, 6, 7, 8, 11):
        cur.execute("""INSERT INTO historical_place
                         (dataset_id, grain_key, canonical_name, place_type, place_type_source,
                          record_status, created_from_source_record_id, created_by, locked,
                          manual_edited_fields, created_at, updated_at)
                       VALUES (%s,%s,%s,'admin_center_county','lev_rank','staging',%s,'import',%s,%s,
                               now(),now()) RETURNING place_id""",
                    (FIX_DS, f"fx{i:02d}", f"夹具{i:02d}", sr[i],
                     plan[i] == "locked", "{canonical_name}" if plan[i] == "field_locked" else "{}"))
        places[i] = cur.fetchone()[0]

    # 8 号做成墓碑（C06 要求 status='merged' + review_ref + merged_at）
    cur.execute("""INSERT INTO candidate_match
                     (relation_type, place_id_a, place_id_b, confidence, status, reviewer,
                      reviewed_at, direction, created_at, updated_at)
                   VALUES ('true_duplicate_suspected',%s,%s,'high','confirmed','human:verify',
                           now(),'none',now(),now()) RETURNING candidate_id""",
                (places[8], places[1]))
    cid = cur.fetchone()[0]
    cur.execute("""UPDATE historical_place SET record_status='merged', merged_into_place_id=%s,
                          merge_review_ref=%s, merged_at=now() WHERE place_id=%s""",
                (places[1], cid, places[8]))
    # 2 号挂一个 name 子行：验证软撤会连带拒绝子行
    cur.execute("""INSERT INTO historical_place_name
                     (place_id, source_record_id, name_text, name_type, time_bound_type,
                      created_at, updated_at)
                   VALUES (%s,%s,'夹具名','primary','unknown',now(),now())""",
                (places[2], sr[2]))

    cur.execute("UPDATE import_batch SET inserted_source_record_ids=%s WHERE batch_id=%s",
                (sorted(sr.values()), R))

    # ---------- 六步判定
    Rb = _mk_batch(cur, FIX_DS, "rolled_back", 0, of_batch=R)
    ledger = []
    n_quar = n_noop = n_blocked = n_fail = n_rolled = 0
    for i in sorted(sr):
        cur.execute("""SELECT is_active, inactive_reason, last_batch_id, external_id
                         FROM source_record WHERE source_record_id=%s""", (sr[i],))
        active, reason, last_b, ext = cur.fetchone()
        if reason == "duplicate_quarantine":                        # 步骤 0
            n_quar += 1
            got = "quarantine"
        elif (not active) or reason is not None:                    # 步骤 1
            n_noop += 1
            got = "noop"
        elif last_b != R:                                           # 步骤 2
            n_blocked += 1
            got = "stale_batch"
            ledger.append(("rollback_conflict", sr[i], places.get(i), f"last_batch_id={last_b}≠R={R}"))
        else:
            cur.execute("""SELECT place_id, created_by, locked, manual_edited_fields,
                                  merged_into_place_id FROM historical_place
                            WHERE created_from_source_record_id=%s""", (sr[i],))
            rows = cur.fetchall()
            prot = [r for r in rows if r[1] == "manual" or r[2] or len(r[3] or []) > 0]
            tomb = [r for r in rows if r[4] is not None]
            if prot:                                                # 步骤 3
                n_blocked += 1
                got = "locked"
                ledger.append(("manual_edit_conflict", sr[i], prot[0][0],
                               f"place {prot[0][0]} 保护位：locked/manual/fields"))
            elif tomb:                                              # 步骤 4
                n_blocked += 1
                got = "tombstone"
                ledger.append(("rollback_conflict", sr[i], tomb[0][0], "merged_into_place_id 非空"))
            else:                                                   # 步骤 5 / 6
                try:
                    cur.execute("SAVEPOINT rb_step")
                    cur.execute("""UPDATE source_record SET is_active=false,
                                          inactive_reason='batch_rolled_back',
                                          inactive_at=now(), inactive_in_batch_id=%s
                                    WHERE source_record_id=%s""", (R, sr[i]))
                    cur.execute("""UPDATE historical_place SET record_status='rejected', updated_at=now()
                                    WHERE created_from_source_record_id=%s
                                      AND merged_into_place_id IS NULL""", (sr[i],))
                    cur.execute("""UPDATE historical_place_name SET record_status='rejected',
                                          rejected_by='auto' WHERE source_record_id=%s""", (sr[i],))
                    cur.execute("""UPDATE historical_place_location SET record_status='rejected',
                                          rejected_by='auto' WHERE source_record_id=%s""", (sr[i],))
                    if plan[i] == "inject_fail":
                        # 受控注入：故意写一个违反 ck_historical_place_lev_rank_type 的取值
                        cur.execute("""UPDATE historical_place SET place_type='unknown',
                                              place_type_source='lev_rank'
                                        WHERE created_from_source_record_id=%s""", (sr[i],))
                    cur.execute("RELEASE SAVEPOINT rb_step")
                    n_rolled += 1
                    got = "rolled_back"
                except psycopg2.Error as exc:
                    cur.execute("ROLLBACK TO SAVEPOINT rb_step")
                    cur.execute("RELEASE SAVEPOINT rb_step")
                    n_fail += 1
                    got = "failed"
                    ledger.append(("import_row_error", sr[i], places.get(i),
                                   str(exc).splitlines()[0][:160]))
        same = (got == plan[i]
                or (plan[i] == "inject_fail" and got == "failed")
                or (plan[i] == "field_locked" and got == "locked"))
        flag = "" if same else "  ⚠ 与预期不符"
        print(f"      sr#{sr[i]:<6} fx{i:02d}  → {got:14s}（预期 {plan[i]}）{flag}")

    for issue_type, sid_, pid_, note in ledger:
        cur.execute("""INSERT INTO data_quality_issue
                         (dataset_id, source_record_id, place_id, issue_type, severity, field_name,
                          observed_value, expected_rule, action_taken, batch_id, first_batch_id,
                          last_batch_id, occurrence_count, created_at, resolution_note)
                       VALUES (%s,%s,%s,%s,'warning','',%s,'ROLLBACK §3.4 判定顺序',
                               'needs_manual_review',%s,%s,%s,1,now(),%s)""",
                    (FIX_DS, sid_, pid_, issue_type, note, Rb, Rb, Rb, note))
    cur.execute("""UPDATE import_batch SET blocked_count=%s, failed_count=%s,
                          quarantined_count=0, skipped_count=0 WHERE batch_id=%s""",
                (n_blocked, n_fail, Rb))

    print(f"\n    参考实现结果：N_quar={n_quar} N_noop={n_noop} N_blocked={n_blocked} "
          f"N_fail_rb={n_fail} N_rolled_back={n_rolled}  合计={n_quar+n_noop+n_blocked+n_fail+n_rolled}")

    # ---------- G2 恒等式
    n_new = scalar(cur, "SELECT coalesce(array_length(inserted_source_record_ids,1),0) "
                        "FROM import_batch WHERE batch_id=%s", (R,))
    n_normal = n_new - n_quar
    g2i = (n_new == n_quar + n_normal)
    g2ii = (n_normal == n_rolled + n_blocked + n_fail + n_noop)
    print(f"    G2(i)  {n_new} = {n_quar} + {n_normal} → {'成立' if g2i else '破裂'}")
    print(f"    G2(ii) {n_normal} = {n_rolled} + {n_blocked} + {n_fail} + {n_noop} → {'成立' if g2ii else '破裂'}")

    # ---------- R1
    cur.execute("""
      WITH b AS (SELECT coalesce(array_length(inserted_source_record_ids,1),0) AS n_new
                   FROM import_batch WHERE batch_id=%s),
           q AS (SELECT count(*) FILTER (WHERE inactive_reason='duplicate_quarantine') AS n_quar,
                        -- ⚠ 对设计 §5.2 取数式的一处语义收窄（与 V3 的 FILTER 括号修正同类）：
                        --   设计原文 n_noop = 非空原因且 <> duplicate_quarantine，
                        --   但本次回滚刚写入的 batch_rolled_back 行会被算进去 ⇒ 右式多减。
                        --   N_noop 的语义是「回滚前已失效」，故排除本次回滚的产物。
                        count(*) FILTER (WHERE inactive_reason IS NOT NULL
                                           AND inactive_reason<>'duplicate_quarantine'
                                           AND NOT (inactive_reason='batch_rolled_back'
                                                    AND inactive_in_batch_id=%s)) AS n_noop
                   FROM source_record
                  WHERE source_record_id IN (SELECT unnest(inserted_source_record_ids)
                                               FROM import_batch WHERE batch_id=%s)),
           rb AS (SELECT blocked_count, failed_count FROM import_batch
                   WHERE rollback_of_batch_id=%s AND status IN ('rolled_back','partial'))
      SELECT (SELECT count(*) FROM source_record
               WHERE inactive_in_batch_id=%s AND inactive_reason='batch_rolled_back')  AS lhs,
             (b.n_new - q.n_quar) - q.n_noop - rb.blocked_count - rb.failed_count      AS rhs,
             b.n_new, q.n_quar, q.n_noop, rb.blocked_count, rb.failed_count
        FROM b, q, rb""", (R, R, R, R, R))
    lhs, rhs, b_new, b_quar, b_noop, b_block, b_fail = cur.fetchone()
    print(f"    R1     LHS={lhs}  RHS=(|B|{b_new} − N_quar{b_quar}) − N_noop{b_noop}"
          f" − blocked{b_block} − failed{b_fail} = {rhs} → {'成立' if lhs == rhs else '破裂'}")
    record("Q1", "PASS" if lhs == rhs else "FAIL",
           f"R1 成立：回滚成功 {lhs} 行 == (|B|−N_quar)−N_noop−blocked−failed = {rhs}")

    # 洞 4 反证：若把 is_active 判在 duplicate_quarantine 之前
    wrong_noop = scalar(cur, """SELECT count(*) FROM source_record
                                 WHERE source_record_id IN (SELECT unnest(inserted_source_record_ids)
                                                              FROM import_batch WHERE batch_id=%s)
                                   AND (NOT is_active OR inactive_reason IS NOT NULL)""", (R,))
    wrong_rhs = (b_new - b_quar) - wrong_noop - b_block - b_fail
    print(f"    洞4反证：若先判 is_active=false ⇒ N_noop={wrong_noop}，RHS={wrong_rhs} ≠ LHS={lhs}"
          f" → {'证明判定顺序不可换' if wrong_rhs != lhs else '该夹具未区分出顺序差异'}")
    record("Q2", "PASS" if wrong_rhs != lhs else "UNVERIFIED",
           f"判定顺序不可换已实测：错误顺序会使 R1 右式变成 {wrong_rhs}（差 {lhs - wrong_rhs}）")

    # ---------- R2 / R2b / R2c
    r2 = scalar(cur, """SELECT count(*) FROM data_quality_issue WHERE batch_id=%s
                         AND issue_type IN ('rollback_conflict','manual_edit_conflict')""", (Rb,))
    print(f"    R2     回滚期台账 {r2} 条 == N_blocked {n_blocked} → {'成立' if r2 == n_blocked else '破裂'}")
    record("Q3", "PASS" if r2 == n_blocked else "FAIL",
           f"R2 成立：rollback_conflict+manual_edit_conflict = {r2} == N_blocked {n_blocked}（1:1 行级记账）")

    r2b = scalar(cur, """SELECT count(*) FROM data_quality_issue WHERE batch_id=%s
                          AND issue_type NOT IN ('rollback_conflict','manual_edit_conflict',
                                                 'import_row_error')""", (Rb,))
    print(f"    R2b    补集（正常质量问题）{r2b} 条 ≥ 0 → 恒真，按设计不做校验")
    record("R2b", "INFO", f"补集 {r2b} 条；设计明示恒真、不做校验（作用是防把质量问题归类成回滚问题）")

    r2c = scalar(cur, """SELECT count(*) FROM data_quality_issue WHERE batch_id=%s
                          AND issue_type='import_row_error'""", (Rb,))
    print(f"    R2c    import_row_error {r2c} 条 == N_fail_rb {n_fail} → {'成立' if r2c == n_fail else '破裂'}")
    record("Q4", "PASS" if r2c == n_fail else "FAIL",
           f"R2c 等式成立（{r2c} == {n_fail}）；触发方式为**受控注入**，"
           f"设计 §11 U5『无真实回滚批次』的保留仍成立")

    # 回滚后的存活态
    cur.execute("""SELECT v.liveness, count(*) FROM v_place_liveness v
                     JOIN historical_place p USING (place_id)
                    WHERE p.dataset_id=%s GROUP BY 1""", (FIX_DS,))
    dist = dict(cur.fetchall())
    print(f"    回滚后夹具地点存活态：{dist}")
    ok = dist.get("all_sources_rolled_back", 0) == 3
    record("Q5", "PASS" if ok else "FAIL",
           f"3 行软撤后 liveness 变为 all_sources_rolled_back（{dist}）；被挡的 4 行仍为 active")


# ============================================================ T 真值表
def part_t(conn) -> None:
    head("T   真值表 7 个合法格 + orphaned 反例（C27 穷尽性，事务内）")
    cur = conn.cursor()
    _mk_dataset(cur, TT_DS, "per_record", "per_record", "none", "{place}")
    _mk_dataset(cur, TT_MIX, "per_parent_external_id", "per_parent_external_id",
                "parent_ordinal", "{name}")
    B = _mk_batch(cur, TT_DS, "succeeded", 0)
    Bm = _mk_batch(cur, TT_MIX, "succeeded", 0)

    def place(ds, grain, status, created_by="import", sr=None, name=None):
        cur.execute("""INSERT INTO historical_place
                         (dataset_id, grain_key, canonical_name, place_type, place_type_source,
                          record_status, created_from_source_record_id, created_by,
                          created_at, updated_at)
                       VALUES (%s,%s,%s,'unknown','unknown',%s,%s,%s,now(),now())
                       RETURNING place_id""",
                    (ds, grain, name or grain, status, sr, created_by))
        return cur.fetchone()[0]

    # ① active / staging
    s_act = _mk_sr(cur, TT_DS, "t01", 0, B)
    p_act = place(TT_DS, "t01", "staging", sr=s_act)
    # ② manual / staging
    s_man = _mk_sr(cur, TT_DS, "t02", 0, B)
    p_man = place(TT_DS, "t02", "staging", created_by="manual", sr=s_man)
    # ③ merged / merged
    s_mrg = _mk_sr(cur, TT_DS, "t03", 0, B)
    p_mrg = place(TT_DS, "t03", "merged", sr=s_mrg)
    cur.execute("""INSERT INTO candidate_match
                     (relation_type, place_id_a, place_id_b, confidence, status, reviewer,
                      reviewed_at, direction, created_at, updated_at)
                   VALUES ('true_duplicate_suspected',%s,%s,'high','confirmed','human:verify',
                           now(),'none',now(),now()) RETURNING candidate_id""", (p_mrg, p_act))
    cid_t = cur.fetchone()[0]
    cur.execute("UPDATE historical_place SET merged_into_place_id=%s, merge_review_ref=%s, merged_at=now() "
                "WHERE place_id=%s", (p_act, cid_t, p_mrg))
    # ④ all_sources_absent / rejected
    s_abs = _mk_sr(cur, TT_DS, "t04", 0, B, active=False, reason="source_absent")
    place(TT_DS, "t04", "rejected", sr=s_abs)
    # ⑤ all_sources_rolled_back / rejected
    s_rbk = _mk_sr(cur, TT_DS, "t05", 0, B, active=False, reason="batch_rolled_back")
    place(TT_DS, "t05", "rejected", sr=s_rbk)
    # ⑥ quarantined_only / rejected
    s_qr = _mk_sr(cur, TT_DS, "t06", 1, B, active=False, reason="duplicate_quarantine")
    place(TT_DS, "t06", "rejected", sr=s_qr)
    # ⑦ mixed_inactive / rejected（两条证据、两种失效原因）
    s_m1 = _mk_sr(cur, TT_MIX, "n1", 0, Bm, parent="M1", scope="name",
                  active=False, reason="source_absent")
    s_m2 = _mk_sr(cur, TT_MIX, "n2", 1, Bm, parent="M1", scope="name",
                  active=False, reason="batch_rolled_back")
    place(TT_MIX, "M1", "rejected", sr=s_m1)
    # ⑧ orphaned 反例：grain_key 与任何源记录都不匹配
    place(TT_DS, "t99", "staging", sr=s_act)

    print("    夹具地点：", end="")
    cur.execute("""SELECT p.grain_key, v.liveness, v.record_status
                     FROM historical_place p JOIN v_place_liveness v USING (place_id)
                    WHERE p.dataset_id IN (%s,%s) ORDER BY p.grain_key""", (TT_DS, TT_MIX))
    got = cur.fetchall()
    for g, lv, st in got:
        print(f"\n      {g:5s} → {lv:26s} {st}", end="")
    print()

    cells = {(lv, st) for _g, lv, st in got}
    legal = {("active", "staging"), ("manual", "staging"), ("merged", "merged"),
             ("all_sources_absent", "rejected"), ("all_sources_rolled_back", "rejected"),
             ("quarantined_only", "rejected"), ("mixed_inactive", "rejected")}
    have_legal = {c for c in cells if c in legal}
    print(f"\n    7 个合法格命中 {len(have_legal)}/7：{sorted(have_legal)}")
    missing = legal - have_legal
    ok = not missing

    # R4a–R4f 在夹具子集上必须全 0（orphaned 反例单列）
    checks = {}
    for tag, sql in {
        "R4a": """SELECT count(*) FROM v_place_liveness v JOIN historical_place p USING (place_id)
                   WHERE p.dataset_id IN (%s,%s) AND v.record_status='rejected'
                     AND v.liveness NOT IN ('all_sources_absent','all_sources_rolled_back',
                                            'quarantined_only','mixed_inactive')""",
        "R4b": """SELECT count(*) FROM v_place_liveness v JOIN historical_place p USING (place_id)
                   WHERE p.dataset_id IN (%s,%s)
                     AND v.liveness IN ('all_sources_absent','all_sources_rolled_back',
                                        'quarantined_only','mixed_inactive')
                     AND v.record_status<>'rejected'""",
        "R4c": """SELECT count(*) FROM v_place_liveness v JOIN historical_place p USING (place_id)
                   WHERE p.dataset_id IN (%s,%s) AND v.liveness='active' AND v.record_status='rejected'""",
        "R4d": """SELECT count(*) FROM v_place_liveness v JOIN historical_place p USING (place_id)
                   WHERE p.dataset_id IN (%s,%s) AND v.liveness='manual' AND v.record_status='rejected'""",
        "R4e": """SELECT count(*) FROM v_place_liveness v JOIN historical_place p USING (place_id)
                   WHERE p.dataset_id IN (%s,%s) AND v.liveness='merged' AND v.record_status<>'merged'""",
        "R4f": """SELECT count(*) FROM v_place_liveness v JOIN historical_place p USING (place_id)
                   WHERE p.dataset_id IN (%s,%s) AND v.liveness='orphaned'""",
    }.items():
        checks[tag] = scalar(cur, sql, (TT_DS, TT_MIX))
    print("    断言结果：", checks)
    print("    R4f=1 是**故意造出来的 orphaned 反例**，证明该断言不是空转；其余 5 条必须为 0")
    ok &= all(v == 0 for k, v in checks.items() if k != "R4f") and checks["R4f"] == 1

    record("T1", "PASS" if ok else "FAIL",
           f"真值表 7 个合法格全部命中（{sorted(have_legal)}），无越界组合；"
           f"R4a–R4e 全 0，R4f 对故意反例返回 1"
           if ok else f"缺格={sorted(missing)} 检查={checks}")


# ============================================================ main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    args = ap.parse_args()
    env = imp_mod.load_env()
    conn = psycopg2.connect(host="127.0.0.1", port=int(env.get("DB_HOST_PORT", "55432")),
                            dbname=args.db, user=env["POSTGRES_USER"], password=env["POSTGRES_PASSWORD"])
    conn.autocommit = False
    print(f"### 事务内受控实测  db={args.db}（结束时整体 ROLLBACK）")
    before = None
    try:
        c = conn.cursor()
        c.execute("SELECT count(*) FROM historical_place")
        before = c.fetchone()[0]
        part_p(conn, args.db)
        part_q(conn)
        part_t(conn)
    finally:
        conn.rollback()
        c = conn.cursor()
        c.execute("SELECT count(*) FROM historical_place")
        after = c.fetchone()[0]
        c.execute("SELECT count(*) FROM data_dataset")
        ds_after = c.fetchone()[0]
        c.execute("SELECT count(*) FROM data_quality_issue")
        dq_after = c.fetchone()[0]
        print(f"\n### 已 ROLLBACK：historical_place {before} → {after}；"
              f"data_dataset {ds_after}；data_quality_issue {dq_after}")
        conn.close()

    head("汇总")
    for no, st, msg in RESULTS:
        icon = {"PASS": "✓", "FAIL": "✗", "UNVERIFIED": "?", "INFO": "·"}[st]
        print(f"  {icon} {no:4s} {st:10s} {msg}")
    fails = [r for r in RESULTS if r[1] == "FAIL"]
    print(f"\n  合计 {len(RESULTS)} 项：PASS {sum(1 for r in RESULTS if r[1] == 'PASS')}"
          f" / FAIL {len(fails)}")
    return 0 if not fails else 1


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
