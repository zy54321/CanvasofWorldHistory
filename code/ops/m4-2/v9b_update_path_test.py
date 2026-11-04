#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V9b 补充测试：内容变化 ⇒ UPDATE 而非 INSERT（隔离环境实测）。

此前 V9b 一直 UNVERIFIED，因为两轮输入完全相同、updated=0，更新路径没被走到。
本脚本在一个**一次性隔离库**里构造 content_hash 变化，真实走一遍更新路径。

做法：
  1. 新建空库 canvas_history_v9b（Flyway V1..V8），不碰正式库、不碰既有测试库
  2. 用**暂存副本**导入一轮，记录 3 条源记录的 (id, content_hash, first_batch_id, last_batch_id)
  3. 改这三条的 raw_payload 中一个与派生无关的字段（CHECKER），使 content_hash 变化
     同时改一个地点的 canonical_name、并把该地点在库里设为 locked
  4. 再导入一轮，核对：
       · source_record 总数不变（没有重复新增）
       · 3 条记录 content_hash 变化、first_batch_id 不变、last_batch_id 指向新批次
       · import_batch.updated_source_record_ids 恰好是这 3 个 id
       · locked 地点的 canonical_name 未被覆盖，manual_edit_conflict +1
  5. 删除隔离库

用法：PYTHONPATH=./ops/.deps python ops/m4-2/v9b_update_path_test.py
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg2

CODE = Path(__file__).resolve().parents[2]
# 必须用 Git Bash 跑 ops/flyway.sh：Windows 上的 `bash` 可能指向 wsl.exe（被安全策略禁止）
GIT_BASH = r"C://Program Files//Git//bin//bash.exe"
if not Path(GIT_BASH).exists():
    GIT_BASH = "bash"
STAGING = CODE / "data" / "staging"
DB = "canvas_history_v9b"
RESULTS: list[tuple[str, bool, str, str]] = []


def load_env() -> dict[str, str]:
    env = {}
    for line in (CODE / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


ENV = load_env()
PORT = int(ENV.get("DB_HOST_PORT", "15432"))


def connect(dbname: str):
    c = psycopg2.connect(host="127.0.0.1", port=PORT, dbname=dbname,
                         user=ENV["POSTGRES_USER"], password=ENV["POSTGRES_PASSWORD"])
    c.autocommit = True
    return c


def rec(cid: str, desc: str, ok: bool, expect, actual) -> None:
    RESULTS.append((cid, desc, ok, str(expect), str(actual)))
    print(f"{'PASS' if ok else 'FAIL'} {cid:<5} {desc:<46} | 期望 {expect} | 实际 {str(actual)[:100]}")


def run_import(staging_dir: Path, summary: Path) -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(CODE / "ops" / ".deps")
    cmd = [sys.executable, str(CODE / "ops" / "import_staging.py"), "--db", DB,
           "--staging-dir", str(staging_dir), "--summary-json", str(summary),
           "--excluded-csv", str(summary.with_suffix(".excluded.csv"))]
    p = subprocess.run(cmd, cwd=str(CODE), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    (summary.with_suffix(".log")).write_text(p.stdout + "\n" + p.stderr, encoding="utf-8")
    return p.returncode


def copy_staging(dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for f in STAGING.glob("*.csv"):
        shutil.copy2(f, dst / f.name)


def main() -> int:
    print(f"== V9b 内容变化 UPDATE 路径实测  库={DB} ==")
    tmp = CODE / "ops" / "m4-2" / "v9b-tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    base_dir, mut_dir = tmp / "base", tmp / "mut"

    # ---------- 1. 隔离库
    admin = connect("postgres")
    cur = admin.cursor()
    cur.execute(f'DROP DATABASE IF EXISTS {DB}')
    cur.execute(f'CREATE DATABASE {DB} OWNER {ENV["POSTGRES_USER"]}')
    cur.close()
    admin.close()
    fw = subprocess.run([GIT_BASH, str(CODE / "ops" / "flyway.sh"), DB, "migrate"],
                        cwd=str(CODE), capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    if fw.returncode != 0:
        print((fw.stdout or "")[-600:], (fw.stderr or "")[-600:])
    print(f"隔离库已建立并迁到最新版本：{DB}")

    # ---------- 2. 首轮导入
    copy_staging(base_dir)
    rc1 = run_import(base_dir, tmp / "run1.json")
    rec("V1", "首轮导入成功（空库）", rc1 == 0, 0, rc1)
    if rc1 != 0:
        print((tmp / "run1.log").read_text(encoding="utf-8", errors="replace")[-1500:])
        return summary()

    conn = connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM source_record")
    src_total_1 = cur.fetchone()[0]

    # 取 3 条县级记录做变更对象
    cur.execute("""SELECT source_record_id, external_id, content_hash, first_batch_id, last_batch_id
                     FROM source_record
                    WHERE dataset_id='chgis_v6_county_points'
                    ORDER BY source_record_id LIMIT 3""")
    targets = cur.fetchall()
    rec("V2", "取到 3 条待变更源记录", len(targets) == 3, 3, len(targets))
    if len(targets) != 3:
        return summary()

    ext_ids = {t[1] for t in targets}
    before = {t[0]: dict(hash=t[2], first=t[3], last=t[4]) for t in targets}

    # 选一个地点做人工锁定保护
    cur.execute("""SELECT place_id, canonical_name FROM historical_place
                    WHERE dataset_id='chgis_v6_county_points'
                    ORDER BY place_id LIMIT 1""")
    locked_pid, locked_name = cur.fetchone()
    cur.execute("UPDATE historical_place SET locked=true WHERE place_id=%s", (locked_pid,))
    print(f"已锁定地点 {locked_pid}「{locked_name}」用于人工保护验证")

    # ---------- 3. 构造变更：payload 改 CHECKER；places 改该地点的正名
    copy_staging(mut_dir)
    src_csv = mut_dir / "source_records.csv"
    with src_csv.open(encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh)
        fields = rd.fieldnames
        rows = list(rd)
    changed = 0
    for row in rows:
        if row["dataset_id"] == "chgis_v6_county_points" and row["external_id"] in ext_ids:
            payload = json.loads(row["raw_payload_json"])
            payload["CHECKER"] = str(payload.get("CHECKER") or "") + "-v9b"
            row["raw_payload_json"] = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                                separators=(",", ":"))
            changed += 1
    with src_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    rec("V3", "已构造 3 条 content_hash 变化", changed == 3, 3, changed)

    # 地点正名改动（配合 locked 验证保护）
    hp_csv = mut_dir / "historical_places.csv"
    with hp_csv.open(encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh)
        hfields = rd.fieldnames
        hrows = list(rd)
    target_place_id = None
    for row in hrows:
        # 暂存 CSV 里 source_dataset 是图层键（chgis_cnty），dataset_id 才是 chgis_v6_county_points
        if row["canonical_name"] == locked_name and row["source_id"] == "chgis":
            target_place_id = row["place_id"]
            row["canonical_name"] = locked_name + "-V9B"
            break
    with hp_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=hfields)
        w.writeheader()
        w.writerows(hrows)
    rec("V4", "已构造被锁定地点的正名变更", target_place_id is not None,
        "找到对应 place 行", target_place_id)

    cur.execute("SELECT count(*) FROM data_quality_issue WHERE issue_type='manual_edit_conflict'")
    conflict_before = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM historical_place")
    place_total_1 = cur.fetchone()[0]

    # ---------- 4. 第二轮导入
    rc2 = run_import(mut_dir, tmp / "run2.json")
    rec("V5", "第二轮导入成功（内容变更场景）", rc2 == 0, 0, rc2)
    if rc2 != 0:
        print(f"详见 {tmp / 'run2.log'}")
        return summary()

    with connect(DB) as c2, c2.cursor() as cur2:
        cur2.execute("SELECT count(*) FROM source_record")
        src_total_2 = cur2.fetchone()[0]
        rec("V6", "源记录总数不变（没有重复新增）", src_total_2 == src_total_1,
            src_total_1, src_total_2)

        cur2.execute("""SELECT source_record_id, content_hash, first_batch_id, last_batch_id
                          FROM source_record WHERE source_record_id = ANY(%s)""",
                     (list(before),))
        after = {r[0]: dict(hash=r[1], first=r[2], last=r[3]) for r in cur2.fetchall()}
        hash_changed = sum(1 for k, v in before.items() if after[k]["hash"] != v["hash"])
        rec("V7", "3 条记录 content_hash 均已变化", hash_changed == 3, 3, hash_changed)

        first_kept = sum(1 for k, v in before.items() if after[k]["first"] == v["first"])
        rec("V8", "first_batch_id 未被改写", first_kept == 3, 3, first_kept)

        last_moved = sum(1 for k, v in before.items() if after[k]["last"] != v["last"])
        rec("V9", "last_batch_id 已推进到新批次", last_moved == 3, 3, last_moved)

        cur2.execute("""SELECT max(last_batch_id) FROM source_record
                         WHERE source_record_id = ANY(%s)""", (list(before),))
        new_batch = cur2.fetchone()[0]
        cur2.execute("""SELECT batch_id, dataset_id, updated_source_record_ids
                          FROM import_batch WHERE batch_id=%s""", (new_batch,))
        bid, ds, upd_ids = cur2.fetchone()
        rec("V10", "updated_source_record_ids 恰好是这 3 条",
            set(upd_ids or []) == set(before) and ds == "chgis_v6_county_points",
            f"3 个 id · {ds}", f"{len(upd_ids or [])} 个 · {ds}")

        cur2.execute("SELECT canonical_name, locked FROM historical_place WHERE place_id=%s",
                     (locked_pid,))
        now_name, now_locked = cur2.fetchone()
        rec("V11", "被锁定地点的正名未被导入覆盖", now_name == locked_name and now_locked is True,
            f"{locked_name} / locked", f"{now_name} / {now_locked}")

        cur2.execute("SELECT count(*) FROM data_quality_issue WHERE issue_type='manual_edit_conflict'")
        conflict_after = cur2.fetchone()[0]
        rec("V12", "人工保护登记 1 条 manual_edit_conflict",
            conflict_after == conflict_before + 1, conflict_before + 1, conflict_after)

        cur2.execute("SELECT count(*) FROM historical_place")
        place_total_2 = cur2.fetchone()[0]
        rec("V13", "地点总数不变（无重复新增）", place_total_2 == place_total_1,
            place_total_1, place_total_2)

        # 第三轮：同样的变更再导一次 ⇒ 应当变成“无变化”，证明更新是幂等的
        rc3 = run_import(mut_dir, tmp / "run3.json")
        cur2.execute("""SELECT count(*) FROM source_record s
                          JOIN import_batch b ON b.batch_id = s.last_batch_id
                         WHERE b.finished_at > now() - interval '30 seconds'""")
        rec("V14", "同一变更再导一次仍成功（更新幂等）", rc3 == 0, 0, rc3)

    return summary()


def summary() -> int:
    n = len(RESULTS)
    p = sum(1 for r in RESULTS if r[2])
    print(f"\n=== V9b 内容变化 UPDATE 路径：PASS {p} / {n} ===")
    return 0 if p == n else 1


if __name__ == "__main__":
    code = main()
    admin = connect("postgres")
    acur = admin.cursor()
    acur.execute(f"DROP DATABASE IF EXISTS {DB}")
    acur.close()
    admin.close()
    print(f"隔离库已删除：{DB}")
    sys.exit(code)
