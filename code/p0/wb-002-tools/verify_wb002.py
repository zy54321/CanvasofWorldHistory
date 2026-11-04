#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WB-002 交付物自检脚本（可复现）

做四件事，全部只读，不联网、不改交付物：
  [1] 逐行校验 sample_data/MANIFEST.tsv：文件是否存在 / 字节数 / SHA256
  [2] 复算关键数字：CHGIS 两包 BEG_YR 区间与去重坐标数、跨源距离、
      SYS_ID ↔ 名称 配对、新兴郡坐标/记录数
  [3] 复算 FIELD_MAPPING.csv 数据行数
  [4] 检查文档中引用的关键数字与复算结果一致（防止改了文档忘了改数据）

用法：  python code/p0/wb-002-tools/verify_wb002.py
退出码：0 全部通过；1 有不一致
"""
import csv
import hashlib
import io
import math
import os
import re
import struct
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
WB = os.path.join(ROOT, "设计资料", "P0验证", "WB-002")
SAMPLE = os.path.join(WB, "sample_data")
MAN = os.path.join(SAMPLE, "MANIFEST.tsv")

FAILS = []


def ok(cond, msg):
    print(("  [OK]   " if cond else "  [FAIL] ") + msg)
    if not cond:
        FAILS.append(msg)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- [1] MANIFEST
def check_manifest():
    print("\n[1] 样本自检（MANIFEST 逐行）")
    rows = []
    with open(MAN, encoding="utf-8") as f:
        rd = csv.DictReader(f, delimiter="\t")
        for r in rd:
            rows.append(r)
    missing = mismatch = 0
    total = 0
    biggest = (0, "")
    for r in rows:
        p = os.path.join(SAMPLE, r["local_path"])
        if not os.path.exists(p):
            missing += 1
            print("    缺失：", r["local_path"])
            continue
        size = os.path.getsize(p)
        total += size
        if size > biggest[0]:
            biggest = (size, r["local_path"])
        if str(size) != r["bytes"] or sha256_file(p) != r["sha256"]:
            mismatch += 1
            print("    不符：", r["local_path"], "记录", r["bytes"], "实际", size)
    ok(missing == 0, "缺失文件 0 个（实际 %d）" % missing)
    ok(mismatch == 0, "字节数/SHA256 不符 0 个（实际 %d）" % mismatch)
    print("    合计 %d 个文件 / %d B (%.2f MiB) / 最大 %d B (%s)"
          % (len(rows), total, total / 1048576.0, biggest[0], biggest[1]))
    codes = {}
    for r in rows:
        codes[r["http_status"]] = codes.get(r["http_status"], 0) + 1
    print("    HTTP 状态分布：", dict(sorted(codes.items())))
    print("    MANIFEST 自身 SHA256：", sha256_file(MAN)[:16])
    ok(total < 50 * 1024 * 1024, "总量 < 50 MiB 上限")
    ok(biggest[0] < 10 * 1024 * 1024, "单文件 < 10 MiB 上限")
    return rows


# ------------------------------------------------------------------- [2] DBF
def read_dbf(zip_path, dbf_name):
    """最小 DBF 读取器（无第三方依赖），返回 dict 列表。"""
    with zipfile.ZipFile(zip_path) as z:
        data = z.read(dbf_name)
    nrec, hdrlen, reclen = struct.unpack("<IHH", data[4:12])
    fields, off = [], 32
    while data[off] != 0x0D:
        name = data[off:off + 11].split(b"\x00")[0].decode("ascii", "replace")
        ftype = chr(data[off + 11])
        flen = data[off + 16]
        fields.append((name, ftype, flen))
        off += 32
    out = []
    pos = hdrlen
    for _ in range(nrec):
        rec_raw = data[pos:pos + reclen]
        pos += reclen
        if not rec_raw or rec_raw[:1] == b"\x1a":
            break
        p = 1
        rec = {}
        for name, ftype, flen in fields:
            raw = rec_raw[p:p + flen]
            p += flen
            try:
                s = raw.decode("utf-8").strip()
            except UnicodeDecodeError:
                s = raw.decode("gbk", "replace").strip()
            rec[name] = s
        out.append(rec)
    return out


def haversine(lat1, lon1, lat2, lon2):
    R = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def check_chgis():
    print("\n[2] CHGIS 关键数字复算（从 sample_data 内的 zip 直接读 DBF）")
    pref_zip = os.path.join(SAMPLE, "chgis", "v6_time_pref_pts_utf_wgs84.zip")
    cnty_zip = os.path.join(SAMPLE, "chgis", "v6_time_cnty_pts_utf_wgs84.zip")
    pref = read_dbf(pref_zip, "v6_time_pref_pts_utf_wgs84.dbf")
    cnty = read_dbf(cnty_zip, "v6_time_cnty_pts_utf_wgs84.dbf")

    def stats(recs, code):
        yrs = []
        for r in recs:
            v = r.get("BEG_YR", "").strip()
            if v in ("", "-"):
                continue
            try:
                yrs.append(int(float(v)))
            except ValueError:
                pass
        coords = {(r.get("X_COOR", ""), r.get("Y_COOR", "")) for r in recs}
        names = {r.get("NAME_CH", "") for r in recs if r.get("NAME_CH")}
        print("    %s：%d 条 / %d 个去重坐标 / %d 个名称 / BEG_YR %d…%d"
              % (code, len(recs), len(coords), len(names), min(yrs), max(yrs)))
        return len(recs), len(coords), min(yrs), max(yrs)

    pr = stats(pref, "府级点")
    cr = stats(cnty, "县级点")
    # stats() 返回 (记录数, 去重坐标数, 最早BEG_YR, 最晚BEG_YR)
    ok(pr[0] == 5226 and pr[2] == -379 and pr[3] == 2151, "府级点 5,226 条、BEG_YR -379…2151")
    ok(cr[0] == 10522 and cr[2] == -763 and cr[3] == 1911, "县级点 10,522 条、BEG_YR -763…1911")

    # SYS_ID ↔ 名称 配对（QA D-04 同类错误的系统性复查）
    print("\n    SYS_ID ↔ 名称 抽样复核：")
    ALL = pref + cnty
    expect = {
        "212275": "京兆尹",
        "32598": "南昌州",
        "41139": "建昌县",
        "210001": "定羌军",
        "210012": "新兴郡",
        "34108": "新兴郡",
        "210009": "新兴郡",
        "210011": "新兴郡",
        "210014": "新兴郡",
        "94203": "新兴郡",
    }
    for sid, want in sorted(expect.items()):
        hits = [r for r in ALL if r.get("SYS_ID", "").strip() == sid]
        got = sorted({r.get("NAME_CH", "") for r in hits})
        ok(bool(hits) and got == [want],
           "SYS_ID %s → %s（实际 %d 条，名称 %s）" % (sid, want, len(hits), got or "无命中"))

    # 全部 SYS_ID 是否在同一名称下出现多个不同名称（同名异写除外，仅作提示）
    by_sid = {}
    for r in ALL:
        sid = r.get("SYS_ID", "").strip()
        if sid:
            by_sid.setdefault(sid, set()).add(r.get("NAME_CH", ""))
    dup = {k: v for k, v in by_sid.items() if len(v) > 1}
    print("    SYS_ID 唯一 %d 个，其中对应多个名称的 %d 个（多为异体字/异写，供人工复核）"
          % (len(by_sid), len(dup)))

    # 新兴郡：坐标数与记录数
    xinxing = [r for r in ALL if r.get("NAME_CH", "") == "新兴郡"]
    xs_coords = {(r["X_COOR"], r["Y_COOR"]) for r in xinxing}
    print("    新兴郡：%d 条记录 / %d 个坐标" % (len(xinxing), len(xs_coords)))
    ok(len(xs_coords) == 4 and len(xinxing) == 6, "新兴郡 6 条记录、4 个坐标")

    # 跨源距离：MCGD Aicheng ↔ CHGIS 建昌县
    jc = [r for r in cnty if r.get("SYS_ID", "").strip() == "41139"][0]
    d = haversine(29.088162, 115.761683, float(jc["Y_COOR"]), float(jc["X_COOR"]))
    print("    Aicheng ↔ 建昌县（DBF 精确坐标）= %.1f m" % d)
    ok(abs(d - 39.0) < 0.15, "距离 = 39.0 m（±0.15）")
    d4 = haversine(29.088162, 115.761683, 29.0878, 115.7618)
    print("    若用 4 位小数四舍五入值 = %.1f m（文档中作为对照保留）" % d4)

    # 坐标轴顺序反证：纬度必须 ≤ 90
    lat_chgis = float(jc["Y_COOR"])
    ok(abs(lat_chgis) <= 90, "CHGIS 县级点 建昌县 纬度 %.6f 落在 ±90 内（轴顺序 X=经度/Y=纬度）" % lat_chgis)


# ------------------------------------------------------------- [3] 字段映射表
def check_field_mapping():
    print("\n[3] FIELD_MAPPING.csv")
    p = os.path.join(WB, "FIELD_MAPPING.csv")
    with open(p, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    body = [r for r in rows[1:] if any(c.strip() for c in r)]
    print("    表头 %d 列，数据 %d 行" % (len(rows[0]), len(body)))
    ok(len(rows[0]) == 7, "表头 7 列")
    bad = [i for i, r in enumerate(body, 2) if len(r) != 7]
    ok(not bad, "所有数据行列数一致（异常行：%s）" % (bad or "无"))
    conf = {}
    for r in body:
        conf[r[5] if len(r) > 5 else "?"] = conf.get(r[5] if len(r) > 5 else "?", 0) + 1
    print("    置信度分布：", conf)


# ------------------------------------------------------------------ [4] 文档
def check_docs():
    print("\n[4] 文档关键数字一致性")
    def read(name):
        with open(os.path.join(WB, name), encoding="utf-8") as f:
            return f.read()

    dsm = read("DATA_SOURCE_MATRIX.md")
    rec = read("SAMPLE_RECONCILIATION.md")
    lic = read("LICENSE_REVIEW.md")

    ok("212275" in rec and "32598" not in rec, "SAMPLE_RECONCILIATION 用 212275（京兆尹），无 32598 残留")
    ok("39.0 m" in rec and "39.0 m" in dsm, "距离统一为 39.0 m")
    ok("府级点 **-379…2151**（来源 `chgis/v6_time_pref_pts_utf_wgs84.zip`" in dsm,
       "覆盖时期：府级 -379…2151 并注明来源包")
    ok("县级点 **-763…1911**（来源 `chgis/v6_time_cnty_pts_utf_wgs84.zip`" in dsm,
       "覆盖时期：县级 -763…1911 并注明来源包")
    ok("112.944084, 38.492717" in rec and "210012" in rec, "新兴郡第 4 个坐标已补（SYS_ID 210012）")
    ok("章号可复核性说明" in lic, "LICENSE_REVIEW 含章号可复核性说明")

    # 表格结构校验（防再次出现 | 备注 ||:-- 这类塌行）
    for name, txt in (("DATA_SOURCE_MATRIX.md", dsm), ("SAMPLE_RECONCILIATION.md", rec),
                      ("LICENSE_REVIEW.md", lic)):
        bad = re.findall(r"^\|.*\|\|:?-{2,}", txt, re.M)
        ok(not bad, "%s 无「表头与分隔行粘连」" % name)


def main():
    print("=" * 62)
    print(" WB-002 交付物自检　%s" % WB)
    print("=" * 62)
    check_manifest()
    check_chgis()
    check_field_mapping()
    check_docs()
    print("\n" + "=" * 62)
    if FAILS:
        print(" 结论：%d 项不通过" % len(FAILS))
        for f in FAILS:
            print("   -", f)
        return 1
    print(" 结论：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
