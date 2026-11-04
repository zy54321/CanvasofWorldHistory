#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一次性隔离数据库的生命周期管理（M4-2 收尾，P4）。

设计目标：**只删自己刚建的库，且一定删得掉**。

  · 库名 = <prefix>_<pid>_<uuid8>，每次运行都不同，不会撞上别人或历史残留；
  · CREATE 之前先查 pg_database：同名已存在 ⇒ 直接抛错终止，**绝不删除已有库**；
  · 只在本实例确实创建成功（self.created=True）时才允许清理；
  · 主体逻辑用上下文管理器（try/finally 语义），异常也会走清理；
  · 清理前显式关闭业务连接，删除失败**抛出并打印**，不静默忽略；
  · 不使用 `DROP DATABASE IF EXISTS` 作为创建前的清理手段。

用法：
    from ephemeral_db import EphemeralDatabase
    with EphemeralDatabase("canvas_history_v9b") as db:
        db.name        # 本次运行的库名
        ...
    # 退出 with 时自动清理，并在 drop 失败时抛异常
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg2

CODE = Path(__file__).resolve().parents[2]


def load_env() -> dict[str, str]:
    env = {}
    for raw in (CODE / ".env").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


ENV = load_env()
PORT = int(ENV.get("DB_HOST_PORT", "15432"))


def connect(dbname: str):
    """连到指定库；autocommit 打开，避免 DDL 卡在事务里。"""
    conn = psycopg2.connect(host="127.0.0.1", port=PORT, dbname=dbname,
                            user=ENV["POSTGRES_USER"], password=ENV["POSTGRES_PASSWORD"])
    conn.autocommit = True
    return conn


def _bash() -> str:
    """Git Bash 的解析：优先 PATH，再回退到常见安装位置。"""
    found = shutil.which("bash")
    if found and "system32" not in found.lower():
        return found
    for cand in (r"C:\Program Files\Git\bin\bash.exe",
                 r"C:\Program Files (x86)\Git\bin\bash.exe"):
        if Path(cand).is_file():
            return cand
    return found or "bash"


class EphemeralDatabase:
    """一次性数据库：建、迁移、用完删。"""

    def __init__(self, prefix: str, *, name: str | None = None, keep_on_failure: bool = False):
        self.prefix = prefix
        self._explicit_name = name
        self.keep_on_failure = keep_on_failure
        self.name = ""
        self.created = False
        self._failed = False

    # ---------------------------------------------------------------- 创建
    def create(self) -> str:
        admin = connect("postgres")
        try:
            cur = admin.cursor()
            if self._explicit_name:
                self.name = self._explicit_name
            else:
                self.name = f"{self.prefix}_{os.getpid()}_{uuid.uuid4().hex[:8]}"
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (self.name,))
            if cur.fetchone():
                raise RuntimeError(
                    f"目标数据库已存在：{self.name}。为避免误删已有数据，本次运行终止（未做任何删除）。")
            cur.execute(f'CREATE DATABASE "{self.name}" OWNER "{ENV["POSTGRES_USER"]}"')
            self.created = True
            cur.close()
        finally:
            admin.close()
        return self.name

    def migrate(self) -> None:
        p = subprocess.run([_bash(), str(CODE / "ops" / "flyway.sh"), self.name, "migrate"],
                           cwd=str(CODE), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if p.returncode != 0:
            raise RuntimeError(f"Flyway 迁移失败（{self.name}）：\n{(p.stdout or '')[-800:]}\n"
                               f"{(p.stderr or '')[-800:]}")

    # ---------------------------------------------------------------- 清理
    def drop(self) -> None:
        """只删自己建的库；失败必须报出来。"""
        if not self.created:
            print(f"[ephemeral] {self.name or '(未创建)'} 不是本次运行创建的，跳过删除")
            return
        admin = connect("postgres")
        try:
            cur = admin.cursor()
            try:
                cur.execute(f'DROP DATABASE "{self.name}"')
            except Exception as exc:                       # noqa: BLE001
                raise RuntimeError(
                    f"清理失败：无法删除 {self.name}（{exc}）。"
                    f"请人工检查是否有残留连接；本次运行不会尝试删除任何其他数据库。") from exc
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (self.name,))
            if cur.fetchone():
                raise RuntimeError(f"清理失败：{self.name} 仍然存在")
            print(f"[ephemeral] 已删除本次运行的隔离库 {self.name}")
            cur.close()
        finally:
            admin.close()

    # ---------------------------------------------------------- 上下文管理
    def __enter__(self) -> "EphemeralDatabase":
        self.create()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self._failed = exc_type is not None
        if self._failed and self.keep_on_failure:
            print(f"[ephemeral] 保留失败现场供排查：{self.name}")
            return False
        self.drop()
        return False


if __name__ == "__main__":
    # 自检：建 → 迁移 → 删除，并打印库名
    with EphemeralDatabase("canvas_history_ephemeral_selftest") as db:
        print("created:", db.name, "migrated:", end=" ")
        db.migrate()
        print("ok")
    sys.exit(0)
