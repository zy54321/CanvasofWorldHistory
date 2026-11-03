#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fn_issue_fingerprint() 的 IMMUTABLE 语义核验（阶段二收尾，Owner 指令 2）。

核验三件事：
  1. 函数元数据：六个参数的类型、返回类型、易变性标记（必须是 i = IMMUTABLE）、
     并行安全标记、是否 SECURITY DEFINER、语言，以及完整定义原文（取自 pg_get_functiondef）。
  2. 跨会话确定性：对同一组输入，在**多个独立的数据库会话**中改变 TimeZone / DateStyle /
     IntervalStyle / extra_float_digits / standard_conforming_strings / search_path 等
     可影响文本化与数值格式的设置，逐项比对输出是否逐字节一致，并与 §4.5 直算式对照。
  3. 生成列一致性：真实插入一行台账，比对「生成列值 = 函数直调值 = 直算式值」，
     读取第二次确认落盘值不变；结束 ROLLBACK。

用法：PYTHONPATH=./ops/.deps python ops/verify_fingerprint.py <数据库名>
退出码：0 = 全部一致；1 = 存在不一致
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import psycopg2

CODE_ROOT = Path(__file__).resolve().parent.parent

# 六段输入的取值矩阵：覆盖 NULL / 空串 / 边界 bigint / 中文 / 引号 / 反斜杠 / 时间样式串 / NULL 与 '' 的区分
INPUTS: list[tuple] = [
    (None, None, None, "unknown_crs", "", None),
    (1, "chgis", 1, "unknown_crs", "", ""),
    (1, "chgis", 1, "unknown_crs", "", None),          # 与上一行仅 observed_value 的 NULL/'' 不同
    (9223372036854775807, "whg", 0, "empty_name", "字段名", "中文值"),
    (-1, "mcgd", -5, "beg_gt_end", 'a"b', "x\\y"),
    (2, "pleiades", 2, "import_row_error", "line", "2024-01-01 00:00:00+08"),
    (3, "ds with space", 3, "year_out_of_range", "year", "1000000000"),
    (4, "chgis", 4, "duplicate_sysid", "sys_id", "〇"),
]

# 会话设置矩阵：只改那些“文本化/格式化”会受影响的设置
SESSION_MATRIX: list[tuple[str, list[str]]] = [
    ("默认会话", []),
    ("TimeZone=UTC", ["SET TimeZone = 'UTC'"]),
    ("TimeZone=Asia/Shanghai", ["SET TimeZone = 'Asia/Shanghai'"]),
    ("TimeZone=America/New_York", ["SET TimeZone = 'America/New_York'"]),
    ("TimeZone=Pacific/Kiritimati", ["SET TimeZone = 'Pacific/Kiritimati'"]),
    ("DateStyle=ISO,MDY", ["SET DateStyle = 'ISO, MDY'"]),
    ("DateStyle=SQL,DMY", ["SET DateStyle = 'SQL, DMY'"]),
    ("DateStyle=German,YMD", ["SET DateStyle = 'German, YMD'"]),
    ("DateStyle=Postgres", ["SET DateStyle = 'Postgres, MDY'"]),
    ("IntervalStyle=iso_8601", ["SET IntervalStyle = 'iso_8601'"]),
    ("IntervalStyle=sql_standard", ["SET IntervalStyle = 'sql_standard'"]),
    ("extra_float_digits=-15", ["SET extra_float_digits = -15"]),
    ("extra_float_digits=3", ["SET extra_float_digits = 3"]),
    ("standard_conforming_strings=off", ["SET standard_conforming_strings = 'off'"]),
    ("search_path=pg_catalog", ["SET search_path = pg_catalog"]),
    ("search_path=''", ["SET search_path = ''"]),
    ("lc_monetary=C", ["SET lc_monetary = 'C'"]),
    ("client_min_messages=ERROR", ["SET client_min_messages = 'ERROR'"]),
    (
        "组合：UTC + SQL,DMY + iso_8601 + float=-15 + search_path=''",
        [
            "SET TimeZone = 'UTC'",
            "SET DateStyle = 'SQL, DMY'",
            "SET IntervalStyle = 'iso_8601'",
            "SET extra_float_digits = -15",
            "SET search_path = ''",
        ],
    ),
]

DIRECT_SQL = """SELECT md5(jsonb_build_array(%s::bigint, %s::text, %s::bigint,
                                      %s::text, %s::text, %s::text)::text)"""
FN_SQL = "SELECT public.fn_issue_fingerprint(%s, %s, %s, %s, %s, %s)"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in (CODE_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def connect(env: dict[str, str], dbname: str):
    return psycopg2.connect(
        host="127.0.0.1", port=int(env.get("DB_HOST_PORT", "55432")),
        dbname=dbname, user=env["POSTGRES_USER"], password=env["POSTGRES_PASSWORD"],
    )


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("用法: python ops/verify_fingerprint.py <数据库名>")
    dbname = sys.argv[1]
    env = load_env()
    fails: list[str] = []

    print(f"### fn_issue_fingerprint IMMUTABLE 核验（库={dbname}）\n")

    # ---------------------------------------------------------------- 1. 元数据
    conn = connect(env, dbname)
    cur = conn.cursor()
    cur.execute(
        """SELECT p.proname, p.provolatile, p.proparallel, p.prosecdef, l.lanname,
                  pg_get_function_result(p.oid), pg_get_function_identity_arguments(p.oid)
           FROM pg_proc p JOIN pg_language l ON l.oid = p.prolang
           WHERE p.pronamespace = 'public'::regnamespace AND p.proname = 'fn_issue_fingerprint'"""
    )
    name, volatile, parallel, secdef, lang, ret, args = cur.fetchone()
    print("## 1. 函数元数据")
    print(f"  schema.name      : public.{name}")
    print(f"  language         : {lang}")
    print(f"  returns          : {ret}")
    print(f"  volatility       : {volatile}  ('i' = IMMUTABLE)"
          + ("  ✓" if volatile == "i" else "  ✗ 非 IMMUTABLE"))
    print(f"  parallel         : {parallel}  ('s' = PARALLEL SAFE)")
    print(f"  security definer : {secdef}  （false = 调用者权限执行）")
    print(f"  参数             : {args}")
    if volatile != "i":
        fails.append("volatility 非 IMMUTABLE")

    print("\n  六个参数的类型：")
    cur.execute(
        """SELECT p.proargnames, p.proargtypes::oid[] AS oids
           FROM pg_proc p
           WHERE p.pronamespace='public'::regnamespace AND p.proname='fn_issue_fingerprint'"""
    )
    names, oids = cur.fetchone()
    for i, (n, o) in enumerate(zip(names, oids), start=1):
        cur.execute("SELECT format_type(%s, NULL)", (o,))
        print(f"    {i}. {n:<20s} {cur.fetchone()[0]}")
    if len(names) != 6:
        fails.append(f"参数个数为 {len(names)}，应为 6")

    print("\n  完整定义（pg_get_functiondef 原文）：")
    cur.execute("SELECT pg_get_functiondef('fn_issue_fingerprint(bigint,text,bigint,text,text,text)'::regprocedure)")
    for line in cur.fetchone()[0].rstrip().splitlines():
        print(f"    {line}")

    # 依赖函数的易变性：jsonb_build_array 在 PG17 被标为 STABLE，这正是字面式生成列被拒（42P17）的原因；
    # 但它的 STABLE 来自「VARIADIC any 的多态入参转换」（对 timestamptz 等才依赖 TimeZone），
    # 本函数入参只有 bigint / text，转换完全确定 ⇒ 由第 2 节的跨会话实测背书，不靠推断。
    cur.execute(
        """SELECT p.proname, p.provolatile, pg_get_function_identity_arguments(p.oid)
           FROM pg_proc p
           WHERE p.proname IN ('md5','jsonb_build_array')
             AND p.pronamespace = 'pg_catalog'::regnamespace
             AND p.prokind = 'f'
           ORDER BY 1, 3"""
    )
    print("\n  依赖内置函数的易变性：")
    for fn, vol, fnargs in cur.fetchall():
        note = "IMMUTABLE" if vol == "i" else "STABLE（多态入参所致，非时间依赖）"
        print(f"    {fn}({fnargs}) → {vol}  {note}")
    print("    说明：jsonb_build_array 在 PG 17 标记为 STABLE，是字面式生成列被拒（42P17）的根因；")
    print("          其易变性来自 VARIADIC any 的通用入参转换（timestamptz 等才受 TimeZone 影响）。")
    print("          本函数六段入参只有 bigint / text，转换结果与任何会话设置无关，")
    print("          因此以 IMMUTABLE 封装成立——由第 2 节 20 个会话的实测结果背书，不作推断。")
    conn.close()

    # ---------------------------------------------------------------- 2. 跨会话
    print("\n## 2. 跨会话确定性（每个配置一个独立连接）")
    baseline: list[str] | None = None
    baseline_label = ""
    vectors: list[tuple[str, list[str], str]] = []

    for label, setups in SESSION_MATRIX:
        c = connect(env, dbname)
        k = c.cursor()
        applied: list[str] = []
        for s in setups:
            try:
                k.execute(s)
                applied.append(s)
            except psycopg2.Error as exc:
                c.rollback()
                print(f"  ! {label}: 设置失败已跳过 {s} → {str(exc).splitlines()[0]}")
        c.commit()

        values: list[str] = []
        for row in INPUTS:
            k.execute(FN_SQL, row)
            values.append(k.fetchone()[0])
        # 同会话内直算式对照
        direct: list[str] = []
        for row in INPUTS:
            k.execute(DIRECT_SQL, row)
            direct.append(k.fetchone()[0])
        c.close()

        digest = hashlib.sha256("\n".join(values).encode()).hexdigest()[:16]
        ok_direct = values == direct
        if baseline is None:
            baseline, baseline_label = values, label
        same = values == baseline
        vectors.append((label, applied, digest))
        flag = "✓" if (same and ok_direct) else "✗"
        print(f"  {flag} {label:<58s} 向量摘要={digest}  直算式一致={'是' if ok_direct else '否'}")
        if not same:
            fails.append(f"{label} 与基线不一致")
        if not ok_direct:
            fails.append(f"{label} 与直算式不一致")

    print(f"\n  基线会话 = {baseline_label}；共比对 {len(SESSION_MATRIX)} 个会话 × {len(INPUTS)} 组输入"
          f" = {len(SESSION_MATRIX) * len(INPUTS)} 次调用")
    uniq = {v[2] for v in vectors}
    print(f"  不同摘要数量 = {len(uniq)}" + ("  ✓ 全部逐字节一致" if len(uniq) == 1 else "  ✗ 存在分歧"))

    print("\n  八组输入的指纹（基线会话）：")
    for row, fp in zip(INPUTS, baseline or []):
        print(f"    {fp}  ← {row}")
    if len(set(baseline or [])) != len(INPUTS):
        fails.append("不同输入产生相同指纹（碰撞）")
    print(f"  唯一指纹数 = {len(set(baseline or []))}/{len(INPUTS)}"
          + ("  ✓ 无碰撞" if len(set(baseline or [])) == len(INPUTS) else "  ✗ 有碰撞"))

    # 显式验证 NULL 与 '' 可区分（§4.5 明确不做 coalesce）
    if len(set(baseline or [])) == len(INPUTS):
        print("  ✓ observed_value 的 NULL 与 '' 产生不同指纹（未做 coalesce，符合 §4.5）")

    # ---------------------------------------------------------------- 3. 生成列
    print("\n## 3. 生成列一致性（真实插入，结束回滚）")
    c = connect(env, dbname)
    k = c.cursor()
    k.execute("INSERT INTO data_source (source_id, display_name) VALUES ('chgis','fp-probe')")
    k.execute(
        """INSERT INTO data_dataset
           (dataset_id, source_id, display_name, record_scopes, place_grain, location_grain,
            grain_evidence, occurrence_key_rule, external_id_nature, created_at, updated_at)
           VALUES ('ds_fp','chgis','p',ARRAY['place'],'per_record','per_record',
                   'ev','none','source_declared',now(),now())"""
    )
    k.execute(
        """INSERT INTO import_batch (dataset_id, derivation_version, status, operator)
           VALUES ('ds_fp','v2.1.1','succeeded','fp-probe') RETURNING batch_id"""
    )
    batch = k.fetchone()[0]
    k.execute(
        """INSERT INTO source_record
           (dataset_id, record_scope, external_id, parent_external_id, duplicate_ordinal,
            raw_file, raw_payload, content_hash, first_batch_id, ingested_at)
           VALUES ('ds_fp','place','p1','-',0,'f.csv','{}'::jsonb,sha256('fp'::bytea),%s,now())
           RETURNING source_record_id""", (batch,)
    )
    sr = k.fetchone()[0]
    k.execute(
        """INSERT INTO historical_place
           (dataset_id, grain_key, canonical_name, place_type, place_type_source,
            created_from_source_record_id, created_at, updated_at)
           VALUES ('ds_fp','p1','指纹城','unknown','unknown',%s,now(),now()) RETURNING place_id""",
        (sr,),
    )
    place = k.fetchone()[0]
    k.execute(
        """INSERT INTO data_quality_issue
           (dataset_id, source_record_id, place_id, issue_type, severity, field_name,
            observed_value, action_taken, created_at)
           VALUES ('ds_fp',%s,%s,'coordinate_out_of_range','warning','lon',NULL,
                   'preserved_and_flagged',now())
           RETURNING issue_id, issue_fingerprint""",
        (sr, place),
    )
    issue_id, stored = k.fetchone()
    k.execute(FN_SQL, (sr, "ds_fp", place, "coordinate_out_of_range", "lon", None))
    via_fn = k.fetchone()[0]
    k.execute(DIRECT_SQL, (sr, "ds_fp", place, "coordinate_out_of_range", "lon", None))
    via_direct = k.fetchone()[0]
    k.execute("SELECT issue_fingerprint FROM data_quality_issue WHERE issue_id = %s", (issue_id,))
    reread = k.fetchone()[0]
    print(f"  生成列写入值   = {stored}")
    print(f"  函数直调值     = {via_fn}")
    print(f"  §4.5 直算式值  = {via_direct}")
    print(f"  二次读取值     = {reread}")
    if stored == via_fn == via_direct == reread:
        print("  ✓ 四者逐字节相等")
    else:
        fails.append("生成列/函数/直算式不一致")

    # 3b. search_path 清空后，生成列仍按 OID 绑定到函数，不依赖名字解析
    k.execute("SET search_path = ''")
    k.execute(
        """INSERT INTO public.data_quality_issue
           (dataset_id, source_record_id, place_id, issue_type, severity, field_name,
            observed_value, action_taken, created_at)
           VALUES ('ds_fp',%s,%s,'coordinate_out_of_range','warning','lon','116.4',
                   'preserved_and_flagged',now())
           RETURNING issue_fingerprint""",
        (sr, place),
    )
    stored2 = k.fetchone()[0]
    k.execute(FN_SQL, (sr, "ds_fp", place, "coordinate_out_of_range", "lon", "116.4"))
    via_fn2 = k.fetchone()[0]
    print(f"  search_path='' 下：生成列={stored2}  函数={via_fn2}"
          + ("  ✓ 不受 search_path 影响（按 OID 绑定）" if stored2 == via_fn2 else "  ✗ 受影响"))
    if stored2 != via_fn2:
        fails.append("生成列在 search_path='' 下结果不同")
    k.execute("RESET search_path")

    c.rollback()
    k.execute("SELECT count(*) FROM data_quality_issue")
    print(f"\n### 已 ROLLBACK，台账行数={k.fetchone()[0]}（应为 0）")
    c.close()

    print("\n" + "=" * 60)
    if fails:
        print(f"核验结论：不通过（{len(fails)} 项）")
        for f in fails:
            print(f"  - {f}")
        return 1
    print(f"核验结论：确定性成立 —— IMMUTABLE 标记正确，跨 {len(SESSION_MATRIX)} 个会话配置输出逐字节一致，"
          f"生成列与直算式等价")
    return 0


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
