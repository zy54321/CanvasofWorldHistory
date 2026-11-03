#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
暂存 CSV 字段实测清单生成器 (Task A)

用途：对 WB-002/normalized/ 下七张暂存 CSV 做逐列实测统计，
产出机器可读的 staging_field_inventory.csv 与人读的 STAGING_FIELD_BASELINE.md 第一节。

设计约束：
  * 严格只读：仅 open(mode='r')，绝不写入源文件目录。
  * 大字段安全：csv.field_size_limit(10**9)，样例值截断。
  * 所有统计均为「逐行实算」（来源层级①），不引用任何上游脚本产物或文档结论。

PEP8 合规。
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import os
import re
import sys

# --------------------------------------------------------------------------
# 配置
# --------------------------------------------------------------------------

SRC_DIR = (
    r"E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory"
    r"\设计资料\P0收敛\WB-002\normalized"
)

BUILD_DIR = (
    r"E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory"
    r"\设计资料\P0收敛\架构\V2.1.1\正式交付\_build"
)

OUT_CSV = os.path.join(BUILD_DIR, "staging_field_inventory.csv")
OUT_MD = os.path.join(BUILD_DIR, "STAGING_FIELD_BASELINE.md")

TABLES = [
    "data_datasets",
    "source_records",
    "historical_places",
    "historical_place_names",
    "historical_place_locations",
    "candidate_matches",
    "data_quality_issues",
]

SAMPLE_LIMIT = 3          # 每张表每列取 3 个样例值
SAMPLE_TRUNC = 120        # 单个样例值截断长度
FIELD_LIMIT = 10 ** 9     # 允许超大字段（raw_payload_json 等）

# V0.2.2-r2 §0 权威行数（仅用于「对照」，不参与统计）
AUTHORITATIVE_ROWS = {
    "source_records": 29391,
    "historical_places": 19039,
    "historical_place_names": 47503,
    "historical_place_locations": 18103,
    "data_quality_issues": 12631,
}

# UUID v4 形态
RE_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
# ISO-8601 时间戳（含 Z 或 +08:00 偏移）
RE_ISO_TS = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$"
)
# 纯日期
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# 整数
RE_INT = re.compile(r"^-?\d+$")
# 十进制数（含科学计数法）
RE_NUM = re.compile(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$")
# 布尔文本
RE_BOOL = re.compile(r"^(true|false|t|f|yes|no|y|n|0|1)$", re.IGNORECASE)


# --------------------------------------------------------------------------
# 工具函数
# --------------------------------------------------------------------------

def sha256_file(path: str) -> str:
    """计算文件 SHA256（只读流式读取，26MB 文件不会吃内存）。"""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_bom(path: str) -> str:
    """读取首 3 字节判断 BOM。"""
    with open(path, "rb") as fh:
        head = fh.read(3)
    if head == b"\xef\xbb\xbf":
        return "UTF-8 BOM (EF BB BF)"
    if head[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "UTF-16 BOM"
    return "无 BOM"


def detect_line_ending(path: str, sample_bytes: int = 262144) -> str:
    """在文件前 sample_bytes 字节内统计行尾风格。"""
    with open(path, "rb") as fh:
        blob = fh.read(sample_bytes)
    crlf = blob.count(b"\r\n")
    lone_lf = blob.count(b"\n") - crlf
    lone_cr = blob.count(b"\r") - crlf
    parts = []
    if crlf:
        parts.append("CRLF x%d" % crlf)
    if lone_lf:
        parts.append("LF x%d" % lone_lf)
    if lone_cr:
        parts.append("CR x%d" % lone_cr)
    return "; ".join(parts) if parts else "未检出"


def detect_delimiter(header_line: str) -> str:
    """按候选分隔符在表头行中的出现次数择优。"""
    candidates = {",": "逗号 ,", ";": "分号 ;", "\t": "制表符 \\t", "|": "竖线 |"}
    best, best_n = ",", header_line.count(",")
    for d in (";", "\t", "|"):
        n = header_line.count(d)
        if n > best_n:
            best, best_n = d, n
    return candidates[best]


def infer_type(non_empty_values: list, max_probe: int = 5000) -> str:
    """基于前 max_probe 个非空值推断类型。

    返回形如 uuid / integer / numeric / boolean / timestamp / date /
          json_like / text(短) / text(长) / empty。
    """
    probe = non_empty_values[:max_probe]
    if not probe:
        return "empty(全空)"

    def ratio(fn) -> float:
        return sum(1 for v in probe if fn(v)) / float(len(probe))

    if ratio(lambda v: RE_UUID.match(v) is not None) >= 0.98:
        return "uuid"
    if ratio(lambda v: RE_INT.match(v) is not None) >= 0.98:
        return "integer"
    if ratio(lambda v: RE_BOOL.match(v) is not None) >= 0.98:
        return "boolean"
    if ratio(lambda v: RE_ISO_TS.match(v) is not None) >= 0.98:
        return "timestamp"
    if ratio(lambda v: RE_DATE.match(v) is not None) >= 0.98:
        return "date"
    if ratio(lambda v: RE_NUM.match(v) is not None) >= 0.98:
        return "numeric"
    if ratio(
        lambda v: (v.startswith("{") and v.endswith("}"))
        or (v.startswith("[") and v.endswith("]"))
    ) >= 0.90:
        return "json_like"

    maxlen = max(len(v) for v in probe)
    if maxlen <= 64:
        return "text(短,<=64字符)"
    if maxlen <= 512:
        return "text(中,<=512字符)"
    return "text(长,>512字符)"


def normalize_for_sample(text: str) -> str:
    """样例值清洗：压缩空白 + 截断 + Markdown 表格竖线转义。

    实测样例中出现 `4|5`、`1384|1640`、`BEG_RULE|END_RULE` 等含竖线的值，
    直接写进 Markdown 表格会撑破列数，必须转义为 `\\|`。
    """
    flat = re.sub(r"\s+", " ", text).strip()
    if len(flat) > SAMPLE_TRUNC:
        flat = flat[:SAMPLE_TRUNC] + "…[截断]"
    return flat.replace("|", "\\|")


def esc_csv_cell(text: str) -> str:
    """样例值中若含逗号/引号会破坏 CSV，统一转义后再入格。"""
    flat = re.sub(r"\s+", " ", str(text)).strip()
    if len(flat) > SAMPLE_TRUNC:
        flat = flat[:SAMPLE_TRUNC] + "…"
    # 双引号转义
    return flat.replace('"', "'")


# --------------------------------------------------------------------------
# 核心：扫描单张表
# --------------------------------------------------------------------------

class ColumnStat:
    """单列累计统计（避免把整列值全部驻留内存）。"""

    def __init__(self, name: str):
        self.name = name
        self.total = 0
        self.non_empty = 0
        self.empty = 0
        self.samples: list[str] = []
        self._seen: set[str] = set()
        self.unique = 0
        self.max_len = 0
        self._type_probe: list[str] = []

    def add(self, value: str) -> None:
        self.total += 1
        if value is None or value == "":
            self.empty += 1
            return
        self.non_empty += 1

        if len(value) > self.max_len:
            self.max_len = len(value)

        # 唯一值：用完整值哈希，避免长文本吃内存
        key = hashlib.md5(value.encode("utf-8", "replace")).digest()
        if key not in self._seen:
            self._seen.add(key)
            self.unique += 1
            if len(self.samples) < SAMPLE_LIMIT:
                self.samples.append(value)
            if len(self._type_probe) < 5000:
                self._type_probe.append(value)

    @property
    def null_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.empty * 100.0 / self.total, 2)


def scan_table(path: str, table: str) -> dict:
    """逐行扫描一张表，返回统计字典。"""
    csv.field_size_limit(FIELD_LIMIT)

    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            return {"table": table, "error": "空文件，无表头"}

        header = [h.strip() for h in header]
        cols = [ColumnStat(h) for h in header]
        ncol = len(header)

        row_count = 0
        ragged = 0
        embedded_newline = 0
        max_cell_len = 0

        for row in reader:
            # 末尾空行 csv 会给出 []，跳过
            if not row:
                continue
            row_count += 1
            if len(row) != ncol:
                ragged += 1
                # 补齐/截断，保证与列对齐
                if len(row) < ncol:
                    row = row + [""] * (ncol - len(row))
                else:
                    row = row[:ncol]
            for idx, cell in enumerate(row):
                cols[idx].add(cell)
                if "\n" in cell or "\r" in cell:
                    embedded_newline += 1
                if len(cell) > max_cell_len:
                    max_cell_len = len(cell)

    return {
        "table": table,
        "file": os.path.basename(path),
        "size_bytes": os.path.getsize(path),
        "sha256": sha256_file(path),
        "mtime": datetime.datetime.fromtimestamp(
            os.path.getmtime(path)
        ).strftime("%Y-%m-%d %H:%M:%S"),
        "bom": detect_bom(path),
        "line_ending": detect_line_ending(path),
        "delimiter": detect_delimiter(",".join(header)),
        "columns": header,
        "row_count": row_count,
        "ragged_rows": ragged,
        "embedded_newline_cells": embedded_newline,
        "max_cell_len": max_cell_len,
        "stats": cols,
    }


# --------------------------------------------------------------------------
# 输出：机器可读 CSV
# --------------------------------------------------------------------------

INVENTORY_HEADER = [
    "staging_table",
    "staging_column",
    "column_index",
    "row_count_total",
    "non_empty_rows",
    "empty_rows",
    "null_rate_pct",
    "unique_values",
    "max_value_length",
    "sample_1",
    "sample_2",
    "sample_3",
    "inferred_type",
]


def write_inventory_csv(results: list, out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(INVENTORY_HEADER)
        for res in results:
            for idx, col in enumerate(res["stats"]):
                samples = [esc_csv_cell(s) for s in col.samples]
                while len(samples) < SAMPLE_LIMIT:
                    samples.append("")
                w.writerow([
                    res["table"],
                    col.name,
                    idx + 1,
                    col.total,
                    col.non_empty,
                    col.empty,
                    "%.2f" % col.null_rate,
                    col.unique,
                    col.max_len,
                    samples[0],
                    samples[1],
                    samples[2],
                    infer_type(col._type_probe),
                ])


# --------------------------------------------------------------------------
# 输出：人读 Markdown
# --------------------------------------------------------------------------

def build_md_section1(results: list) -> list:
    """构造 STAGING_FIELD_BASELINE.md 第一节文本。"""
    L = []
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    L.append("# 暂存字段基线 STAGING_FIELD_BASELINE")
    L.append("")
    L.append("> 版本：V2.1.1 准备性基线  ")
    L.append("> 生成时间：%s  " % now)
    L.append("> 生成脚本：`_build/qa_scripts/staging_field_inventory.py`  ")
    L.append("> 数据来源（只读）：`P0收敛/WB-002/normalized/` 七张暂存 CSV  ")
    L.append("> **本文件全部数字均为「①原始 CSV 逐行实算」层级**，"
             "未引用上游脚本产物或上游文档结论。")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 第一节 七张暂存 CSV 字段实测清单")
    L.append("")
    L.append("### 1.0 文件级总览")
    L.append("")
    L.append("| # | 暂存表 | 文件 | 字节数 | 数据行数 | 字段数 | "
             "编码/BOM | 分隔符 | 行尾 | 嵌入换行单元格 | 不规则行 |")
    L.append("|---|--------|------|--------|----------|--------|"
             "---------|-------|------|----------------|----------|")
    for i, r in enumerate(results, 1):
        L.append(
            "| %d | `%s` | `%s` | %s | **%s** | %d | %s | %s | %s | %s | %d |"
            % (
                i, r["table"], r["file"],
                "{:,}".format(r["size_bytes"]),
                "{:,}".format(r["row_count"]),
                len(r["columns"]),
                r["bom"], r["delimiter"], r["line_ending"],
                "{:,}".format(r["embedded_newline_cells"]),
                r["ragged_rows"],
            )
        )
    L.append("")
    L.append("**文件指纹（原始字节 SHA256）**")
    L.append("")
    L.append("| 暂存表 | SHA256（完整） | SHA256 前 16 位 | mtime |")
    L.append("|--------|----------------|-----------------|-------|")
    for r in results:
        L.append("| `%s` | `%s` | `%s` | %s |" % (
            r["table"], r["sha256"], r["sha256"][:16], r["mtime"]))
    L.append("")

    # ---- 行数与权威数字对照 ----
    L.append("### 1.1 数据行数 vs V0.2.2-r2 §0 权威数字对照")
    L.append("")
    L.append("| 暂存表 | 实测行数（①逐行实算） | V0.2.2-r2 §0 权威数 | 差值 | 判定 |")
    L.append("|--------|----------------------|---------------------|------|------|")
    mismatch = []
    for key, auth in AUTHORITATIVE_ROWS.items():
        res = next((r for r in results if r["table"] == key), None)
        if res is None:
            continue
        actual = res["row_count"]
        delta = actual - auth
        ok = (delta == 0)
        if not ok:
            mismatch.append((key, actual, auth, delta))
        L.append("| `%s` | %s | %s | %+d | %s |" % (
            key, "{:,}".format(actual), "{:,}".format(auth), delta,
            "一致" if ok else "**不一致**"))
    L.append("")
    tbl_names = {r["table"]: r["row_count"] for r in results}
    L.append("未列入权威对照的表（实测值，供后续比对）：")
    L.append("")
    for k in ("data_datasets", "candidate_matches"):
        if k in tbl_names:
            L.append("- `%s`：%s 行" % (k, "{:,}".format(tbl_names[k])))
    L.append("")
    if mismatch:
        L.append("> **⚠ 行数不一致，已点名：** " + "；".join(
            "`%s` 实测 %s ≠ 权威 %s（差 %+d）" % (m[0], "{:,}".format(m[1]),
                                                 "{:,}".format(m[2]), m[3])
            for m in mismatch))
        L.append("")
    else:
        L.append("> ✅ 五张列入权威对照的表实测行数与 V0.2.2-r2 §0 完全一致。")
        L.append("")

    # ---- 逐表逐列明细 ----
    L.append("### 1.2 逐表逐列实测明细")
    L.append("")
    for i, r in enumerate(results, 1):
        L.append("#### 1.2.%d `%s` — %s 行 × %d 列"
                 % (i, r["table"], "{:,}".format(r["row_count"]),
                    len(r["columns"])))
        L.append("")
        L.append("- 文件：`%s`（%s 字节，SHA256 前 16 位 `%s`）"
                 % (r["file"], "{:,}".format(r["size_bytes"]),
                    r["sha256"][:16]))
        L.append("- 编码/分隔符/行尾：%s / %s / %s"
                 % (r["bom"], r["delimiter"], r["line_ending"]))
        L.append("- 嵌入换行单元格：%s 个；最大单元格长度：%s 字符"
                 % ("{:,}".format(r["embedded_newline_cells"]),
                    "{:,}".format(r["max_cell_len"])))
        L.append("")
        L.append("| # | staging_column | 总行数 | 非空 | 空值 | 空值率 | "
                 "唯一值 | 推断类型 | 样例值（最多 3 个，截断 %d 字符） |"
                 % SAMPLE_TRUNC)
        L.append("|---|----------------|--------|------|------|--------|"
                 "--------|----------|-----------------------------------|")
        for idx, col in enumerate(r["stats"], 1):
            samples = " ｜ ".join(
                "`%s`" % normalize_for_sample(s) for s in col.samples
            ) if col.samples else "（无非空值）"
            L.append("| %d | `%s` | %s | %s | %s | %.2f%% | %s | %s | %s |"
                     % (idx, col.name,
                        "{:,}".format(col.total),
                        "{:,}".format(col.non_empty),
                        "{:,}".format(col.empty),
                        col.null_rate,
                        "{:,}".format(col.unique),
                        infer_type(col._type_probe),
                        samples))
        L.append("")

    # ---- 全字段扁平索引（便于后续核对映射）----
    L.append("### 1.3 全字段扁平索引（供 FIELD_MAPPING_V2.1.1 校验用）")
    L.append("")
    L.append("共 %d 个暂存字段，形如 `staging_table.staging_column`："
             % sum(len(r["columns"]) for r in results))
    L.append("")
    for r in results:
        L.append("- **`%s`**（%d 列）：%s" % (
            r["table"], len(r["columns"]),
            "、".join("`%s`" % c for c in r["columns"])))
    L.append("")
    return L


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------

def main() -> int:
    os.makedirs(BUILD_DIR, exist_ok=True)

    print("=" * 72)
    print("暂存 CSV 字段实测清单生成器 — 严格只读扫描")
    print("源目录：%s" % SRC_DIR)
    print("=" * 72)

    results = []
    for t in TABLES:
        path = os.path.join(SRC_DIR, t + ".csv")
        if not os.path.exists(path):
            print("[缺失] %s" % path)
            continue
        print("[扫描] %-32s ..." % t, end="", flush=True)
        res = scan_table(path, t)
        results.append(res)
        print(" %s 行 × %d 列" % ("{:,}".format(res["row_count"]),
                                 len(res["columns"])))

    if not results:
        print("错误：未扫描到任何表")
        return 1

    # 机器可读产出
    write_inventory_csv(results, OUT_CSV)
    print("\n[产出] %s (%d 字节)" % (OUT_CSV, os.path.getsize(OUT_CSV)))

    # 人读产出（第一节）。若第二节已由 build_section2.py 追加，重跑本脚本时保留它。
    preserved_tail = ""
    marker = "## 第二节 V2.1 → V2.1.1 映射差异预判"
    if os.path.exists(OUT_MD):
        with open(OUT_MD, "r", encoding="utf-8") as fh:
            old = fh.read()
        pos = old.find(marker)
        if pos >= 0:
            cut = old.rfind("---", 0, pos)
            preserved_tail = old[cut:] if cut >= 0 else old[pos:]

    section1 = build_md_section1(results)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(section1) + preserved_tail)
    if preserved_tail:
        print("[保留] 已检测到第二节，重跑后原样保留")
    print("[产出] %s (%d 字节)" % (OUT_MD, os.path.getsize(OUT_MD)))

    # 控制台摘要
    print("\n" + "=" * 72)
    print("行数对照（实测 vs V0.2.2-r2 §0 权威）")
    print("=" * 72)
    for key, auth in AUTHORITATIVE_ROWS.items():
        res = next((r for r in results if r["table"] == key), None)
        if res is None:
            continue
        delta = res["row_count"] - auth
        flag = "OK " if delta == 0 else "!!! "
        print("%s%-32s 实测 %8s  权威 %8s  差 %+d"
              % (flag, key, "{:,}".format(res["row_count"]),
                 "{:,}".format(auth), delta))
    for k in ("data_datasets", "candidate_matches"):
        res = next((r for r in results if r["table"] == k), None)
        if res:
            print("    %-32s 实测 %8s  （无权威对照数）"
                  % (k, "{:,}".format(res["row_count"])))

    print("\n完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
