#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V9b 内容变化 UPDATE 路径 + 第三轮相同内容幂等路径（隔离库实测）。

覆盖两条**不同**的路径，结论分别记录，不混为一谈：

  A. 内容变化路径（V9–V17）：payload 改了 ⇒ content_hash 变化 ⇒ 必须 UPDATE 而非 INSERT；
     first_batch_id 不变、last_batch_id 推进、人工保护位仍然挡住覆盖。
  B. 相同内容重导路径（V18–V24）：再把同一份变更导一次 ⇒ 应「零新增、零更新」，
     但按设计 last_batch_id 会推进、台账 occurrence_count 会 +1。

数据库生命周期交给 ephemeral_db.EphemeralDatabase：库名带 pid+uuid、存在即拒绝、
异常也清理、只删自己建的库。

用法：
  PYTHONPATH=./ops/.deps python ops/m4-2/v9b_update_path_test.py
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ephemeral_db import EphemeralDatabase, connect          # noqa: E402

STAGING = CODE / "data" / "staging"
WORK = CODE / "ops" / "m4-2" / "v9b-work"
RESULTS: list[tuple[str, bool]] = []


def rec(cid: str, desc: str, ok: bool, expect, actual) -> None:
    RESULTS.append((cid, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {cid:<5} {desc:<46} | 期望 {expect} | 实际 {str(actual)[:100]}")


def run_import(db: str, staging: Path, summary_path: Path) -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(CODE / "ops" / ".deps")
    cmd = [sys.executable, str(CODE / "ops" / "import_staging.py"), "--db", db,
           "--staging-dir", str(staging), "--summary-json", str(summary_path),
           "--excluded-csv", str(summary_path.with_suffix(".excluded.csv"))]
    p = subprocess.run(cmd, cwd=str(CODE), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    summary_path.with_suffix(".log").write_text(p.stdout + "\n" + p.stderr, encoding="utf-8")
    return p.returncode


def copy_staging(dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for f in STAGING.glob("*.csv"):
        shutil.copy2(f, dst / f.name)


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh)
        return list(rd.fieldnames or []), list(rd)


def write_csv(path: Path, fields, rows) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    print("== V9b：内容变化 UPDATE 路径 + 第三轮相同内容幂等 ==")
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    base_dir, mut_dir = WORK / "base", WORK / "mut"

    with EphemeralDatabase("canvas_history_v9b") as db:
        print(f"隔离库：{db.name}（本次创建，退出时自动删除）")
        db.migrate()

        # ================================================================ 首轮
        copy_staging(base_dir)
        rc1 = run_import(db.name, base_dir, WORK / "run1.json")
        rec("V1", "首轮导入成功（空库）", rc1 == 0, 0, rc1)
        if rc1 != 0:
            print((WORK / "run1.log").read_text(encoding="utf-8", errors="replace")[-1200:])
            return summary()

        conn = connect(db.name)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM source_record")
        src_total_1 = cur.fetchone()[0]

        cur.execute("""SELECT source_record_id, external_id, content_hash, first_batch_id, last_batch_id
                         FROM source_record WHERE dataset_id='chgis_v6_county_points'
                        ORDER BY source_record_id LIMIT 3""")
        targets = cur.fetchall()
        rec("V2", "取到 3 条待变更源记录", len(targets) == 3, 3, len(targets))
        if len(targets) != 3:
            cur.close(); conn.close(); return summary()
        ext_ids = {t[1] for t in targets}
        before = {t[0]: dict(hash=t[2], first=t[3], last=t[4]) for t in targets}

        # ---- P3：用「源记录外部 ID」把 DB 地点与暂存 CSV 行稳定对应起来
        cur.execute("""SELECT p.place_id, p.canonical_name, sr.external_id
                         FROM historical_place p
                         JOIN source_record sr ON sr.source_record_id = p.created_from_source_record_id
                        WHERE p.dataset_id = 'chgis_v6_county_points'
                        ORDER BY p.place_id LIMIT 1""")
        row = cur.fetchone()
        rec("V3", "县级数据集里取到带源记录锚点的地点", row is not None, "1 行", row)
        if row is None:
            cur.close(); conn.close(); return summary()
        locked_pid, locked_name, locked_ext = row

        copy_staging(mut_dir)
        hp_fields, hp_rows = read_csv(mut_dir / "historical_places.csv")
        hit_idx = [i for i, r in enumerate(hp_rows)
                   if r["source_id"] == "chgis"
                   and r["source_dataset"] == "chgis_cnty"
                   and r["primary_external_id"] == locked_ext]
        rec("V4", "CSV 侧按 (县级图层, external_id) 唯一命中", len(hit_idx) == 1,
            "恰好 1 行", f"{len(hit_idx)} 行 · ext={locked_ext}")
        if len(hit_idx) != 1:
            cur.close(); conn.close(); return summary()
        csv_row = hp_rows[hit_idx[0]]
        rec("V5", "CSV 行与 DB 地点同名（确认同一对象）",
            csv_row["canonical_name"] == locked_name, locked_name, csv_row["canonical_name"])

        cur.execute("""SELECT count(*) FROM historical_place p
                         JOIN source_record sr ON sr.source_record_id = p.created_from_source_record_id
                        WHERE p.dataset_id='chgis_v6_county_points' AND sr.external_id = %s""",
                    (locked_ext,))
        n_db = cur.fetchone()[0]
        rec("V6", "DB 侧同一 external_id 的县级地点唯一", n_db == 1, 1, n_db)

        cur.execute("UPDATE historical_place SET locked=true WHERE place_id=%s", (locked_pid,))
        print(f"      已锁定地点 {locked_pid}「{locked_name}」用于人工保护验证")

        # ================================================================ 构造变更
        src_fields, src_rows = read_csv(mut_dir / "source_records.csv")
        changed = 0
        for r in src_rows:
            if r["dataset_id"] == "chgis_v6_county_points" and r["external_id"] in ext_ids:
                payload = json.loads(r["raw_payload_json"])
                payload["CHECKER"] = str(payload.get("CHECKER") or "") + "-v9b"
                r["raw_payload_json"] = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                                   separators=(",", ":"))
                changed += 1
        write_csv(mut_dir / "source_records.csv", src_fields, src_rows)
        rec("V7", "已构造 3 条 content_hash 变化", changed == 3, 3, changed)

        csv_row["canonical_name"] = locked_name + "-V9B"
        write_csv(mut_dir / "historical_places.csv", hp_fields, hp_rows)
        rec("V8", "已构造被锁定地点的正名变更", True, "已写入", csv_row["place_id"])

        cur.execute("SELECT count(*) FROM data_quality_issue WHERE issue_type='manual_edit_conflict'")
        conflict_before = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM historical_place")
        place_total_1 = cur.fetchone()[0]

        # ================================================================ 第二轮：内容变化
        rc2 = run_import(db.name, mut_dir, WORK / "run2.json")
        rec("V9", "第二轮导入成功（内容变化场景）", rc2 == 0, 0, rc2)
        if rc2 != 0:
            print((WORK / "run2.log").read_text(encoding="utf-8", errors="replace")[-1500:])
            cur.close(); conn.close(); return summary()

        cur.execute("SELECT count(*) FROM source_record")
        src_total_2 = cur.fetchone()[0]
        rec("V10", "源记录总数不变（没有重复新增）", src_total_2 == src_total_1, src_total_1, src_total_2)

        cur.execute("""SELECT source_record_id, content_hash, first_batch_id, last_batch_id
                         FROM source_record WHERE source_record_id = ANY(%s)""", (list(before),))
        after2 = {r[0]: dict(hash=r[1], first=r[2], last=r[3]) for r in cur.fetchall()}
        n_hash = sum(1 for k, v in before.items() if after2[k]["hash"] != v["hash"])
        n_first = sum(1 for k, v in before.items() if after2[k]["first"] == v["first"])
        n_last = sum(1 for k, v in before.items() if after2[k]["last"] != v["last"])
        rec("V11", "3 条 content_hash 均已变化", n_hash == 3, 3, n_hash)
        rec("V12", "first_batch_id 未被改写", n_first == 3, 3, n_first)
        rec("V13", "last_batch_id 已推进到新批次", n_last == 3, 3, n_last)

        new_batch = max(v["last"] for v in after2.values())
        cur.execute("SELECT dataset_id, updated_source_record_ids FROM import_batch WHERE batch_id=%s",
                    (new_batch,))
        ds, upd_ids = cur.fetchone()
        rec("V14", "updated_source_record_ids 恰好是这 3 条",
            set(upd_ids or []) == set(before) and ds == "chgis_v6_county_points",
            "3 个 id · chgis_v6_county_points", f"{len(upd_ids or [])} 个 · {ds}")

        cur.execute("SELECT canonical_name, locked FROM historical_place WHERE place_id=%s", (locked_pid,))
        now_name, now_locked = cur.fetchone()
        rec("V15", "被锁定地点的正名未被导入覆盖", now_name == locked_name and now_locked is True,
            f"{locked_name} / locked", f"{now_name} / {now_locked}")

        cur.execute("SELECT count(*) FROM data_quality_issue WHERE issue_type='manual_edit_conflict'")
        conflict_after = cur.fetchone()[0]
        rec("V16", "人工保护登记 1 条 manual_edit_conflict",
            conflict_after == conflict_before + 1, conflict_before + 1, conflict_after)

        cur.execute("SELECT count(*) FROM historical_place")
        place_total_2 = cur.fetchone()[0]
        rec("V17", "地点总数不变（无重复新增）", place_total_2 == place_total_1, place_total_1, place_total_2)

        # ================================================================ 第三轮：相同内容重导（P2）
        cur.execute("SELECT count(*) FROM source_record")
        snap_src = cur.fetchone()[0]
        cur.execute("""SELECT source_record_id, content_hash, first_batch_id, last_batch_id
                         FROM source_record WHERE source_record_id = ANY(%s)""", (list(before),))
        snap3 = {r[0]: dict(hash=r[1], first=r[2], last=r[3]) for r in cur.fetchall()}
        cur.execute("SELECT count(*), count(DISTINCT issue_fingerprint), coalesce(sum(occurrence_count),0) "
                    "FROM data_quality_issue")
        snap_led = cur.fetchone()
        cur.execute("SELECT coalesce(max(batch_id),0) FROM import_batch")
        snap_batch = cur.fetchone()[0]

        rc3 = run_import(db.name, mut_dir, WORK / "run3.json")
        rec("V18", "第三轮导入退出码 0", rc3 == 0, 0, rc3)

        s3 = json.loads((WORK / "run3.json").read_text(encoding="utf-8"))
        st3 = s3.get("source_stat") or {}
        rec("V19", "第三轮 source_stat：新增 0 / 内容更新 0",
            st3.get("inserted") == 0 and st3.get("updated") == 0, "inserted=0 updated=0",
            f"inserted={st3.get('inserted')} updated={st3.get('updated')} "
            f"touched={st3.get('touched')} held={st3.get('held')}")

        cur.execute("SELECT count(*) FROM source_record")
        src_after3 = cur.fetchone()[0]
        rec("V20", "第三轮后 source_record 总数不变", src_after3 == snap_src, snap_src, src_after3)

        cur.execute("""SELECT source_record_id, content_hash, first_batch_id, last_batch_id
                         FROM source_record WHERE source_record_id = ANY(%s)""", (list(before),))
        snap4 = {r[0]: dict(hash=r[1], first=r[2], last=r[3]) for r in cur.fetchall()}
        same = sum(1 for k in snap3
                   if snap4[k]["hash"] == snap3[k]["hash"] and snap4[k]["first"] == snap3[k]["first"])
        rec("V21", "第三轮后 3 条 content_hash 与 first_batch_id 均不变", same == 3, 3, same)

        # 设计：每轮都会把命中的源记录 last_batch_id 推进到本轮的批次（含 quarantine_hold）。
        # 因此判据是「全部源记录的 last_batch_id 都 > 第三轮前的最大批次」，而不是某个固定行数。
        cur.execute("SELECT count(*), count(*) FILTER (WHERE last_batch_id > %s) FROM source_record",
                    (snap_batch,))
        src_all, moved = cur.fetchone()
        rec("V22", "第三轮 last_batch_id 全部推进到本轮批次", moved == src_all, src_all, moved)

        cur.execute("""SELECT count(*) FROM import_batch
                        WHERE batch_id > %s
                          AND coalesce(array_length(inserted_source_record_ids,1),0) > 0""",
                    (snap_batch,))
        n_new = cur.fetchone()[0]
        rec("V23", "第三轮没有新增源记录 ID", n_new == 0, 0, n_new)

        cur.execute("SELECT count(*), count(DISTINCT issue_fingerprint), coalesce(sum(occurrence_count),0) "
                    "FROM data_quality_issue")
        led3 = cur.fetchone()
        rec("V24", "第三轮台账：行数/指纹不变，occurrence_count 每行恰好 +1",
            led3[0] == snap_led[0] and led3[1] == snap_led[1]
            and led3[2] == snap_led[2] + snap_led[0],
            f"行 {snap_led[0]} / 指纹 {snap_led[1]} / Σocc {snap_led[2] + snap_led[0]}",
            f"行 {led3[0]} / 指纹 {led3[1]} / Σocc {led3[2]}")

        cur.close()
        conn.close()

    return summary()


def summary() -> int:
    n = len(RESULTS)
    p = sum(1 for r in RESULTS if r[1])
    print(f"\n=== V9b：PASS {p} / {n} ===")
    return 0 if p == n else 1


if __name__ == "__main__":
    sys.exit(main())
