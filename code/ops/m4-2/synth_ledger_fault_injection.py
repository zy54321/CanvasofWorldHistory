#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""合成台账独立验证的故障注入测试（M4-2 收尾，P1 的验收环节）。

目的：证明验证器对「漏生成」和「多生成」**都会 FAIL**，而不是自我引用式地恒过。

四步（全部在一次性隔离库执行，跑完即删库）：
  A 正常完整导入 → 验证器 PASS
  B 删掉 1 条 derived_value_mismatch → 验证器必须 FAIL
  C 恢复 B，再塞 1 条不存在的 duplicate_external_id → 验证器必须 FAIL
  D 撤掉 C 的多余行 → 验证器重新 PASS

用法：PYTHONPATH=./ops/.deps python ops/m4-2/synth_ledger_fault_injection.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ephemeral_db import EphemeralDatabase, connect        # noqa: E402

STAGING = CODE / "data" / "staging"
WORK = CODE / "ops" / "m4-2" / "fault-work"
RESULTS: list[tuple[str, bool]] = []

LEDGER_COLS = ("issue_id", "dataset_id", "source_record_id", "place_id", "batch_id",
               "issue_type", "severity", "field_name", "observed_value", "expected_rule",
               "action_taken", "first_batch_id", "last_batch_id", "occurrence_count",
               "created_at", "resolution_note", "resolved")


def rec(cid: str, desc: str, ok: bool, expect, actual) -> None:
    RESULTS.append((cid, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {cid:<4} {desc:<46} | 期望 {expect} | 实际 {str(actual)[:90]}")


def run_import(db: str, summary: Path) -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(CODE / "ops" / ".deps")
    cmd = [sys.executable, str(CODE / "ops" / "import_staging.py"), "--db", db,
           "--staging-dir", str(STAGING), "--summary-json", str(summary),
           "--excluded-csv", str(WORK / "stage3_excluded_rows.csv")]
    p = subprocess.run(cmd, cwd=str(CODE), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    summary.with_suffix(".log").write_text(p.stdout + "\n" + p.stderr, encoding="utf-8")
    return p.returncode


def run_verify(db: str, only: str = "") -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(CODE / "ops" / ".deps")
    cmd = [sys.executable, str(CODE / "ops" / "verify_import.py"), "--db", db,
           "--run-dir", str(WORK)]
    if only:
        cmd += ["--only", only]
    p = subprocess.run(cmd, cwd=str(CODE), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def v_status(out: str, key: str) -> str:
    for line in out.splitlines():
        s = line.strip()
        if s.startswith(("✓", "✗", "?", "·")) and f" {key} " in s:
            return {"✓": "PASS", "✗": "FAIL", "?": "UNVERIFIED", "·": "INFO"}[s[0]]
    return "MISSING"


def main() -> int:
    print("== 合成台账独立验证 · 故障注入 ==")
    if WORK.exists():
        for f in WORK.iterdir():
            f.unlink()
    WORK.mkdir(parents=True, exist_ok=True)

    with EphemeralDatabase("canvas_history_synth_fault") as db:
        print(f"隔离库：{db.name}")
        db.migrate()

        rc1 = run_import(db.name, WORK / "run1_summary.json")
        rc2 = run_import(db.name, WORK / "run2_summary.json")
        rec("S0", "两轮导入成功（构造可靠基线）", rc1 == 0 and rc2 == 0, "0/0", f"{rc1}/{rc2}")
        if rc1 or rc2:
            print((WORK / "run2.log").read_text(encoding="utf-8", errors="replace")[-1200:])
            return summary()

        # ---------------- A 正常
        rc, out = run_verify(db.name)
        rec("A1", "正常数据：验证器整体 PASS（exit 0）", rc == 0, "exit 0", f"exit {rc}")
        rec("A2", "正常数据：V2 与 V7 均 PASS",
            v_status(out, "V2") == "PASS" and v_status(out, "V7") == "PASS",
            "PASS/PASS", f"{v_status(out, 'V2')}/{v_status(out, 'V7')}")

        conn = connect(db.name)
        cur = conn.cursor()

        # ---------------- B 删掉 1 条 derived_value_mismatch
        cur.execute("""SELECT %s FROM data_quality_issue
                        WHERE issue_type='derived_value_mismatch'
                        ORDER BY issue_id LIMIT 1""" % ",".join(LEDGER_COLS))
        saved = cur.fetchone()
        cur.execute("DELETE FROM data_quality_issue WHERE issue_id=%s", (saved[0],))
        rc, out = run_verify(db.name, "V2,V7")
        rec("B1", "删除 1 条 derived_value_mismatch 后验证器 FAIL", rc != 0, "exit≠0", f"exit {rc}")
        rec("B2", "V2 判定为 FAIL", v_status(out, "V2") == "FAIL", "FAIL", v_status(out, "V2"))
        rec("B3", "V7 判定为 FAIL", v_status(out, "V7") == "FAIL", "FAIL", v_status(out, "V7"))

        # ---------------- C 恢复 B，再塞一条多余的 duplicate_external_id
        cur.execute(f"""INSERT INTO data_quality_issue ({",".join(LEDGER_COLS)})
                        VALUES ({",".join(["%s"] * len(LEDGER_COLS))})""", saved)
        cur.execute("""INSERT INTO data_quality_issue
                         (dataset_id, issue_type, severity, field_name, observed_value,
                          expected_rule, action_taken, created_at)
                       VALUES ('chgis_v6_county_points','duplicate_external_id','warning',
                               'external_id','INJECTED-EXTRA','fault injection',
                               'preserved_and_flagged', now())""")
        rc, out = run_verify(db.name, "V2,V7")
        rec("C1", "多 1 条 duplicate_external_id 后验证器 FAIL", rc != 0, "exit≠0", f"exit {rc}")
        rec("C2", "V2 判定为 FAIL", v_status(out, "V2") == "FAIL", "FAIL", v_status(out, "V2"))

        # ---------------- D 撤掉多余行，恢复原状
        cur.execute("DELETE FROM data_quality_issue WHERE observed_value='INJECTED-EXTRA'")
        rc, out = run_verify(db.name, "V2,V7")
        rec("D1", "恢复后验证器重新 PASS", rc == 0, "exit 0", f"exit {rc}")
        rec("D2", "V2 与 V7 均恢复 PASS",
            v_status(out, "V2") == "PASS" and v_status(out, "V7") == "PASS",
            "PASS/PASS", f"{v_status(out, 'V2')}/{v_status(out, 'V7')}")

        cur.execute("SELECT count(*) FROM data_quality_issue")
        tot = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM data_quality_issue WHERE issue_type='derived_value_mismatch'")
        mis = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM data_quality_issue WHERE issue_type='duplicate_external_id'")
        dup = cur.fetchone()[0]
        rec("D3", "恢复后台账回到原状（12,833 / 197 / 5）",
            tot == 12833 and mis == 197 and dup == 5, "12833/197/5", f"{tot}/{mis}/{dup}")

        cur.close()
        conn.close()

    return summary()


def summary() -> int:
    n = len(RESULTS)
    p = sum(1 for r in RESULTS if r[1])
    print(f"\n=== 故障注入：PASS {p} / {n} ===")
    return 0 if p == n else 1


if __name__ == "__main__":
    sys.exit(main())
