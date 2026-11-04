#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 MCGD 的 HTTP Range 原始前缀派生出「只含完整行」的干净样本。

背景：MCGD 主文件 MCGD_Data2026_08_25.csv 为 31,953,904 字节，超过 WB-002 单文件 10MB 上限，
      因此只取 Range 0-65535（HTTP 206）。该前缀末尾可能截断在一行中间，
      直接当样本使用会引入一条不完整记录，故派生出只保留完整行的样本。

用法： python code/p0/wb-002-tools/derive_mcgd_sample.py
产物： sample_data/mcgd/MCGD_Data2026_08_25.csv.head-960rows.sample.csv
      并在 MANIFEST.tsv 追加一行（http_status 记为 derived，url 记为 local:raw）
"""
import csv
import hashlib
import os

ROOT = r"E:/01_Work/01_PersonalProjects/014-CanvasofWorldHistory"
OUT = os.path.join(ROOT, "设计资料", "P0验证", "WB-002", "sample_data")
RAW = os.path.join(OUT, "mcgd", "MCGD_Data2026_08_25.csv.range-0-65535.raw")
CLEAN = os.path.join(OUT, "mcgd", "MCGD_Data2026_08_25.csv.head-960rows.sample.csv")
MANIFEST = os.path.join(OUT, "MANIFEST.tsv")

EXPECTED_HEADER = "Name,Prov_Zh,Prov_Py,Code,LAT,LONG,LocID,NameID,PROVID"


def main():
    raw = open(RAW, "rb").read()
    text = raw.decode("utf-8", "strict")
    lines = text.split("\n")

    header = lines[0].strip("\r")
    assert header == EXPECTED_HEADER, f"表头不符：{header!r}"

    complete = []
    truncated = None
    for idx, line in enumerate(lines[1:]):
        if not line.strip():
            continue
        # 只有以换行结束的行才是完整行；文件最后一个片段若不以换行结束则视为截断
        if idx == len(lines[1:]) - 1 and not text.endswith("\n"):
            truncated = line
            continue
        complete.append(line.rstrip("\r"))

    with open(CLEAN, "w", encoding="utf-8", newline="") as f:
        f.write(header + "\n")
        for line in complete:
            f.write(line + "\n")

    size = os.path.getsize(CLEAN)
    sha = hashlib.sha256(open(CLEAN, "rb").read()).hexdigest()

    # 追加 manifest 行（幂等：先删除同名旧行）
    with open(MANIFEST, encoding="utf-8") as f:
        rows = f.read().splitlines()
    rows = [r for r in rows if not r.endswith("mcgd/MCGD_Data2026_08_25.csv.head-960rows.sample.csv")]
    with open(MANIFEST, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(rows) + "\n")
        f.write(
            "derived\tmcgd_derived\tlocal:MCGD_Data2026_08_25.csv.range-0-65535.raw\tderived\t"
            f"{size}\t{sha}\tmcgd/MCGD_Data2026_08_25.csv.head-960rows.sample.csv\n"
        )

    print(f"原始前缀： {len(raw)} 字节（HTTP 206 Range 0-65535）")
    print(f"完整数据行： {len(complete)} 行（已剔除末尾截断行）")
    print(f"截断行（未采用）： {truncated!r}")
    print(f"派生样本： {os.path.relpath(CLEAN, OUT)} | {size} 字节 | sha256={sha}")
    # 字段一致性抽检
    with open(CLEAN, encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd)
        n = sum(1 for r in rd if len(r) == 9)
    print(f"9 字段齐全的行： {n}")


if __name__ == "__main__":
    main()
