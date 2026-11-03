#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段一基础设施自检脚本（宿主机侧，通过 TCP 连接 Docker 中的 PostgreSQL）。

用途：从宿主机真实连接数据库，验证连接、PostGIS 可用性与数据卷持久化。
不是业务代码，不参与后端构建。

用法：
    python ops/verify_db.py check              # 连接 + 版本 + PostGIS 能力
    python ops/verify_db.py write              # 写入持久化标记（重启前）
    python ops/verify_db.py read               # 读取持久化标记（重启后）
    python ops/verify_db.py cleanup            # 删除自检 schema

依赖：psycopg2-binary（仅本机自检用，见 ops/README.md）
凭证来源：与容器同一份 .env，脚本不硬编码任何密码。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2

CODE_ROOT = Path(__file__).resolve().parent.parent


def load_env() -> dict[str, str]:
    """读取 code/.env，解析简单的 KEY=VALUE；只读，不修改环境。"""
    env: dict[str, str] = {}
    env_file = CODE_ROOT / ".env"
    if not env_file.exists():
        sys.exit(f"缺少 {env_file}，请先 cp .env.example .env 并填写密码")
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def connect(env: dict[str, str]):
    return psycopg2.connect(
        host="127.0.0.1",
        port=int(env.get("DB_HOST_PORT", "55432")),
        dbname=env["POSTGRES_DB"],
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
        connect_timeout=10,
        application_name="stage1-verify",
    )


def cmd_check(env: dict[str, str]) -> None:
    with connect(env) as conn, conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_user, inet_server_addr(), inet_server_port()")
        db, user, addr, port = cur.fetchone()
        print(f"[host->db] 已从宿主机连接：db={db} user={user} server={addr}:{port}")

        cur.execute("SHOW server_version")
        print(f"[postgres] {cur.fetchone()[0]}")

        cur.execute("SELECT postgis_version(), postgis_lib_version()")
        gis_ver, lib_ver = cur.fetchone()
        print(f"[postgis]  postgis_version={gis_ver} lib={lib_ver}")

        cur.execute(
            "SELECT extname, extversion FROM pg_extension WHERE extname LIKE 'postgis%' ORDER BY extname"
        )
        for name, ver in cur.fetchall():
            print(f"[extension] {name} {ver}")

        # 空间能力实测：两点距离（EPSG:4326 球面），不依赖任何业务表
        cur.execute(
            "SELECT round(ST_Distance(ST_SetSRID(ST_MakePoint(116.4074, 39.9042), 4326)::geography,"
            " ST_SetSRID(ST_MakePoint(121.4737, 31.2304), 4326)::geography) / 1000.0)::int"
        )
        print(f"[geometry] 北京-上海球面距离 ≈ {cur.fetchone()[0]} km")

        cur.execute("SELECT srid FROM spatial_ref_sys WHERE srid = 4326")
        print(f"[srid]    EPSG:4326 存在={cur.fetchone() is not None}")

        # 只统计业务基本表：排除 PostGIS 自带的 spatial_ref_sys
        cur.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "AND table_name <> 'spatial_ref_sys'"
        )
        print(f"[schema]  public 下业务表数量={cur.fetchone()[0]}（阶段一应为 0）")


def cmd_write(env: dict[str, str]) -> None:
    with connect(env) as conn, conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS infra")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS infra.smoke_check (
                id          bigserial PRIMARY KEY,
                marker      text        NOT NULL,
                note        text,
                created_at  timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        cur.execute(
            "INSERT INTO infra.smoke_check (marker, note) VALUES (%s, %s) RETURNING id, created_at",
            ("stage1-persistence", "容器重启前写入，用于验证 named volume 持久化"),
        )
        row_id, created = cur.fetchone()
    print(f"[write] 已写入 infra.smoke_check id={row_id} at={created.isoformat()}")


def cmd_read(env: dict[str, str]) -> None:
    with connect(env) as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('infra.smoke_check')")
        if cur.fetchone()[0] is None:
            sys.exit("[read] infra.smoke_check 不存在：数据卷未持久化")
        cur.execute("SELECT id, marker, note, created_at FROM infra.smoke_check ORDER BY id")
        rows = cur.fetchall()
    if not rows:
        sys.exit("[read] 表存在但没有数据：持久化验证失败")
    print(f"[read] 重启后读到 {len(rows)} 行：")
    for row_id, marker, note, created in rows:
        print(f"       id={row_id} marker={marker} created_at={created.isoformat()} note={note}")


def cmd_cleanup(env: dict[str, str]) -> None:
    with connect(env) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS infra CASCADE")
    print("[cleanup] 已删除 infra schema")


COMMANDS = {"check": cmd_check, "write": cmd_write, "read": cmd_read, "cleanup": cmd_cleanup}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(f"用法: python {sys.argv[0]} [{'|'.join(COMMANDS)}]")
    if os.name == "nt":
        sys.stdout.reconfigure(encoding="utf-8")
    COMMANDS[sys.argv[1]](load_env())
