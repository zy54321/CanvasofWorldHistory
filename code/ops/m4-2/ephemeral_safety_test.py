#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一次性数据库生命周期安全测试（M4-2 收尾，P4 的安全验证）。

四项：
  S1 正常运行结束后，临时库被删除
  S2 主体抛异常后，临时库仍被删除（异常照常向上抛）
  S3 目标库名已存在时**拒绝执行**，且原有数据库不被删除
  S4 冲突库里的既有数据在拒绝之后保持原样
  S5 非本实例创建的库，`drop()` 不会删除（created=False 时直接跳过）

用法：PYTHONPATH=./ops/.deps python ops/m4-2/ephemeral_safety_test.py
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ephemeral_db import ENV, EphemeralDatabase, connect      # noqa: E402

RESULTS: list[tuple[str, bool]] = []


def rec(cid: str, desc: str, ok: bool, expect, actual) -> None:
    RESULTS.append((cid, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {cid:<4} {desc:<44} | 期望 {expect} | 实际 {str(actual)[:90]}")


def exists(name: str) -> bool:
    admin = connect("postgres")
    try:
        cur = admin.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
        hit = cur.fetchone() is not None
        cur.close()
        return hit
    finally:
        admin.close()


def drop_quiet(name: str) -> None:
    admin = connect("postgres")
    try:
        cur = admin.cursor()
        cur.execute(f'DROP DATABASE IF EXISTS "{name}"')
        cur.close()
    finally:
        admin.close()


def main() -> int:
    print("== 一次性数据库生命周期安全测试 ==")

    # ---------------- S1 正常路径
    name1 = ""
    with EphemeralDatabase("canvas_history_safety") as db:
        name1 = db.name
        db.migrate()
    rec("S1", "正常运行后临时库已删除", not exists(name1) and name1 != "", "不存在", name1)
    rec("S1b", "库名带 pid + uuid（非固定名）", "_" in name1 and name1.startswith("canvas_history_safety_"),
        "canvas_history_safety_<pid>_<uuid8>", name1)

    # ---------------- S2 异常路径
    name2 = ""
    raised = False
    try:
        with EphemeralDatabase("canvas_history_safety") as db:
            name2 = db.name
            db.migrate()
            raise RuntimeError("deliberate failure in body")
    except RuntimeError:
        raised = True
    rec("S2", "主体抛异常后临时库仍被删除", raised and not exists(name2), "已删除且异常上抛",
        f"raised={raised} exists={exists(name2)}")

    # ---------------- S3/S4 名称冲突：拒绝执行，且原库不动
    conflict = f"canvas_history_safety_conflict_{uuid.uuid4().hex[:8]}"
    admin = connect("postgres")
    try:
        cur = admin.cursor()
        cur.execute(f'CREATE DATABASE "{conflict}" OWNER "{ENV["POSTGRES_USER"]}"')
        cur.close()
    finally:
        admin.close()
    c = connect(conflict)
    try:
        cc = c.cursor()
        cc.execute("CREATE TABLE marker(id int primary key, note text)")
        cc.execute("INSERT INTO marker VALUES (1, 'keep me')")
        cc.close()
    finally:
        c.close()

    refused, msg = False, ""
    try:
        EphemeralDatabase("canvas_history_safety", name=conflict).create()
    except RuntimeError as exc:
        refused = True
        msg = str(exc)
    rec("S3", "目标库已存在时拒绝创建", refused, "抛错终止", msg[:60])
    rec("S4", "冲突库仍然存在（未被删除）", exists(conflict), True, exists(conflict))

    c = connect(conflict)
    try:
        cc = c.cursor()
        cc.execute("SELECT note FROM marker WHERE id = 1")
        kept = cc.fetchone()
        cc.close()
    finally:
        c.close()
    rec("S4b", "冲突库里的原有数据完好", kept == ("keep me",), "keep me", kept)

    # ---------------- S5 非本实例创建的库不许删
    ghost = EphemeralDatabase("canvas_history_safety", name=conflict)   # 未调用 create()
    ghost.drop()
    rec("S5", "未由本实例创建的库不会被 drop 删除", exists(conflict), "仍存在", exists(conflict))

    drop_quiet(conflict)
    rec("S6", "测试自建的冲突库已由测试自己清理", not exists(conflict), "已删除", conflict)

    n = len(RESULTS)
    p = sum(1 for r in RESULTS if r[1])
    print(f"\n=== 数据库安全：PASS {p} / {n} ===")
    return 0 if p == n else 1


if __name__ == "__main__":
    sys.exit(main())
