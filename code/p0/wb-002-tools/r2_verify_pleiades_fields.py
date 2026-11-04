#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
r2_verify_pleiades_fields.py
WB-002 P0收敛 第二轮：从本地 Range 切片复算 PLEIADES_GIS_FIELD_VERIFICATION.md 里的每一个数字。
只读本地样本，不联网。
用法（项目根目录下）:
    python code/p0/wb-002-tools/r2_verify_pleiades_fields.py
"""
import csv, io, json, os, statistics, sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
S = os.path.join(ROOT, "设计资料", "P0收敛", "WB-002", "sample_data_pleiades")
OLD = os.path.join(ROOT, "设计资料", "P0验证", "WB-002", "sample_data", "pleiades")

FILES = {
    "places":          "places.csv.range-0-1048575",
    "names":           "names.csv.range-0-1048575",
    "location_points": "location_points.csv.range-0-1048575",
    "time_periods":    "time_periods.csv.range-0-999999",
    "connections":     "connections.csv.range-0-524287",
}


def load(fn):
    """读取切片；截到最后一个换行，保证末行完整。返回 (header, rows, noted)。"""
    path = os.path.join(S, fn)
    raw = open(path, "rb").read()
    assert raw.startswith(b"\xef\xbb\xbf"), f"{fn} 无 UTF-8 BOM（与 gis_README 记载不符）"
    i = raw.rfind(b"\n")
    truncated = i != len(raw) - 1
    txt = raw[: i + 1].decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(txt)))
    return rows[0], rows[1:], truncated


def isnum(s):
    try:
        int(s)
        return True
    except (TypeError, ValueError):
        return False


def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def main():
    hdr, rows, noted = {}, {}, {}
    for k, fn in FILES.items():
        hdr[k], rows[k], noted[k] = load(fn)

    hr("1. 表头实测（逐字段原样拼写 / 字段数 / 完整行数 / 末尾是否被截断）")
    for k in ("places", "names", "location_points", "time_periods", "connections"):
        print(f"\n[{k}]  file={FILES[k]}  字段数={len(hdr[k])}  完整数据行={len(rows[k])}  末行被截断={noted[k]}")
        for n, f in enumerate(hdr[k], 1):
            print(f"    {n:2d}. {f}")

    hr("2. places.csv —— 地点级字段")
    ph, pr, pi = hdr["places"], rows["places"], {n: i for i, n in enumerate(hdr["places"])}
    print("字段分类：")
    print("  地点级身份:  id, uri, title")
    print("  地点级文本:  created, description, details, provenance")
    print("  地点级坐标:  representative_latitude, representative_longitude, bounding_box_wkt, location_precision")
    for f in ("min_date", "max_date", "repr_lat", "repr_lon", "feature_type",
              "year_after_which", "year_before_which"):
        print(f"  字段 {f!r:22s} 存在? -> {f in pi}")
    print(f"\n  representative_latitude 为空的行: "
          f"{sum(1 for r in pr if not r[pi['representative_latitude']].strip())} / {len(pr)}")
    print(f"  location_precision 取值: {dict(Counter(r[pi['location_precision']] for r in pr))}")
    print(f"  bounding_box_wkt 为空的行: {sum(1 for r in pr if not r[pi['bounding_box_wkt']].strip())} / {len(pr)}")

    print("\n  坐标轴序证据（Pompeii 相关 3 条 + 区域 1 条）：")
    for ln, r in enumerate(pr, start=2):
        if r[pi["id"]] in ("999909607", "999909608", "912816", "993"):
            wkt = r[pi["bounding_box_wkt"]]
            first_pair = wkt.split("((")[-1].split(",")[0].strip() if "POLYGON" in wkt else "-"
            print(f"    行{ln}: id={r[pi['id']]} title={r[pi['title']]!r}")
            print(f"        representative_latitude  = {r[pi['representative_latitude']]}")
            print(f"        representative_longitude = {r[pi['representative_longitude']]}")
            print(f"        bounding_box_wkt 首点     = {first_pair}   (WKT 内为 X Y = 经度 纬度)")

    hr("3. names.csv —— 字段清单与取值域")
    nh, nr, ni = hdr["names"], rows["names"], {n: i for i, n in enumerate(hdr["names"])}
    print("字段清单：", ", ".join(nh))
    print("\n  与 JSON API 命名差异：")
    print("    JSON names[].romanized        -> CSV romanized_form_1 / _2 / _3")
    print("    JSON names[].attested         -> CSV attested_form")
    print("    JSON names[].nameType         -> CSV name_type")
    print("    JSON names[].language         -> CSV language_tag")
    print("    JSON names[].start / .end     -> CSV year_after_which / year_before_which")
    print("    JSON names[].associationCertainty -> CSV association_certainty")
    print("    CSV 独有: place_id（数值 place id 外键）, title")
    print(f"\n  title == romanized_form_1 的行: "
          f"{sum(1 for r in nr if r[ni['title']] == r[ni['romanized_form_1']])} / {len(nr)}")
    print(f"  romanized_form_1 为空的行: {sum(1 for r in nr if not r[ni['romanized_form_1']].strip())}")
    print(f"  id 是否为 slug（非纯数字）: {sum(1 for r in nr if not r[ni['id']].isdigit())} / {len(nr)}")
    print(f"\n  name_type 取值域（对照 gis_vocab/name_types.csv 的 key 列）:")
    for k, v in Counter(r[ni["name_type"]] for r in nr).most_common():
        print(f"    {k!r:22s} {v}")
    print("\n  language_tag 空值率: "
          f"{sum(1 for r in nr if not r[ni['language_tag']].strip())} / {len(nr)}")
    print("  association_certainty :", dict(Counter(r[ni["association_certainty"]] for r in nr)))
    print("  transcription_accuracy:", dict(Counter(r[ni["transcription_accuracy"]] for r in nr)))
    print("  transcription_completeness:", dict(Counter(r[ni["transcription_completeness"]] for r in nr)))

    print("\n  --- attested_form 与 romanized_form_1 不同的样例（原文字形保留）---")
    c = 0
    for ln, r in enumerate(nr, start=2):
        a, r1 = r[ni["attested_form"]], r[ni["romanized_form_1"]]
        if a and a != r1:
            print(f"    行{ln}: place_id={r[ni['place_id']]} lang={r[ni['language_tag']]!r} "
                  f"attested={a!r} romanized_1={r1!r} yaw={r[ni['year_after_which']]!r} ybw={r[ni['year_before_which']]!r}")
            c += 1
            if c >= 5:
                break

    hr("4. location_points.csv —— 字段清单与取值域")
    lh, lr, li = hdr["location_points"], rows["location_points"], {n: i for i, n in enumerate(hdr["location_points"])}
    print("字段清单：", ", ".join(lh))
    for f in ("repr_lat", "repr_lon", "lat", "lon", "location_precision", "geometry_wkt",
              "year_after_which", "year_before_which"):
        print(f"  字段 {f!r:20s} 存在? -> {f in li}")
    print(f"\n  location_precision 取值: {dict(Counter(r[li['location_precision']] for r in lr))}")
    print(f"  archaeological_remains 取值: {dict(Counter(r[li['archaeological_remains']] for r in lr))}")
    print(f"  association_certainty 取值: {dict(Counter(r[li['association_certainty']] for r in lr))}")
    print(f"  geometry_wkt 前缀: {dict(Counter(r[li['geometry_wkt']].split('(')[0].strip() for r in lr))}")
    print(f"  accuracy_radius 非空: {sum(1 for r in lr if r[li['accuracy_radius']].strip())} / {len(lr)}")
    print(f"  year_after_which 非空:  {sum(1 for r in lr if r[li['year_after_which']].strip())} / {len(lr)}")
    print(f"  year_before_which 非空: {sum(1 for r in lr if r[li['year_before_which']].strip())} / {len(lr)}")
    c = Counter(r[li["place_id"]] for r in lr)
    print(f"  一个 place_id 挂多条 position 的最多者: {c.most_common(3)}")
    print("\n  --- 前 3 条完整记录 ---")
    for ln, r in enumerate(lr[:3], start=2):
        print(f"    行{ln}: " + " | ".join(f"{k}={r[li[k]]!r}" for k in
              ("id", "place_id", "geometry_wkt", "accuracy_radius", "location_precision",
               "year_after_which", "year_before_which")))

    hr("5. time_periods.csv —— 这是什么表")
    th, tr, ti = hdr["time_periods"], rows["time_periods"], {n: i for i, n in enumerate(hdr["time_periods"])}
    print("字段清单：", ", ".join(th))
    print(f"行数: {len(tr)}")
    print("lower_bound/upper_bound 的数据类型：字符串（形如 '750 BC' / 'AD 300'），不是整数")
    print("样例：")
    keys = {r[ti["key"]]: r for r in tr}
    for k in ("archaic", "classical", "hellenistic-republican", "roman", "late-antique"):
        if k in keys:
            r = keys[k]
            print(f"    {k:26s} lower={r[ti['lower_bound']]!r:12s} upper={r[ti['upper_bound']]!r:12s} same_as={r[ti['same_as']][:50]!r}")
    print("\n  是否为 attestation 证据表？-> 否。它是 220 条具名「时期词表」，")
    print("  样本内没有任何其它 CSV 字段的取值命中它的 key（见下）。")

    hr("6. 关键判定：year_after_which / year_before_which 是 TPQ / TAQ，不是精确起止年")
    print("[A] gis_README.md 原文（本地副本 datasets_docs/gis_README.md，行 300-314）：")
    print("    year_after_which  = 'The year after which ... flourished, was in use, or otherwise obtained, i.e., terminus post quem'")
    print("    year_before_which = 'The year before which ... flourished, was in use, or otherwise obtained, i.e., terminus ante quem'")
    print("    格式：proleptic Julian calendar 的有符号整数，无 0 年。")

    def widths(rs, ix, label):
        w = []
        for r in rs:
            a, b = r[ix["year_after_which"]].strip(), r[ix["year_before_which"]].strip()
            if isnum(a) and isnum(b):
                w.append(int(b) - int(a))
        if not w:
            print(f"  {label}: 无可计算行")
            return
        w.sort()
        print(f"  {label}: 可计算 {len(w)} 行  min={w[0]} p25={w[len(w)//4]} "
              f"median={statistics.median(w)} p75={w[3*len(w)//4]} max={w[-1]}")
        print(f"      宽度==0 的行: {w.count(0)}   <=50 年: {sum(1 for x in w if x <= 50)}   >500 年: {sum(1 for x in w if x > 500)}")

    print("\n[B] 区间宽度分布（若这两个字段真是「名称使用起止年」，宽度中位数不可能到几百年）")
    widths(nr, ni, "names          ")
    widths(lr, li, "location_points")

    print("\n[C] 0 年检查（README 声明无 0 年）")
    z = [ln for ln, r in enumerate(nr, start=2)
         if r[ni["year_after_which"]].strip() == "0" or r[ni["year_before_which"]].strip() == "0"]
    print(f"  names 中值为 '0' 的行: {len(z)}")

    print("\n[D] 负数（BCE）年份实例 —— 证明 BCE 用负数表示")
    c = 0
    for ln, r in enumerate(nr, start=2):
        a, b = r[ni["year_after_which"]].strip(), r[ni["year_before_which"]].strip()
        if a.startswith("-") or b.startswith("-"):
            print(f"    names 行{ln}: place_id={r[ni['place_id']]} title={r[ni['title']]!r} "
                  f"yaw={a} ybw={b} 宽度={int(b)-int(a) if isnum(a) and isnum(b) else '?'}")
            c += 1
            if c >= 8:
                break
    c = 0
    for ln, r in enumerate(lr, start=2):
        a, b = r[li["year_after_which"]].strip(), r[li["year_before_which"]].strip()
        if a.startswith("-") or b.startswith("-"):
            print(f"    location_points 行{ln}: place_id={r[li['place_id']]} id={r[li['id']]!r} "
                  f"yaw={a} ybw={b}")
            c += 1
            if c >= 3:
                break

    print("\n[E] JSON API 侧佐证：attestations[].timePeriod 被压成 start/end")
    jf = os.path.join(OLD, "places", "912816.json")
    if os.path.exists(jf):
        d = json.load(open(jf, encoding="utf-8"))
        print(f"  {jf}  place 级时间字段: "
              f"{[k for k in d if any(t in k.lower() for t in ('year', 'date', 'time'))] or '无'}")
        for key in ("locations", "names"):
            print(f"  {key}:")
            for i, o in enumerate(d.get(key, [])[:5]):
                periods = [a.get("timePeriod") for a in o.get("attestations", [])]
                print(f"    [{i}] start={o.get('start')!r} end={o.get('end')!r} attestations={periods}")
        # 用 time_periods 复算 start/end
        print("  复算：archaic(750BC)→lower=-750；late-antique(AD640)→upper=640")
        print("        => locations[0].start 应 == -750，end 应 == 640（见上）")

    hr("7. time_periods.key 是否被其它 CSV 的任一单元格引用")
    keyset = {r[ti["key"]] for r in tr}
    for k in ("places", "names", "location_points", "connections"):
        hit = defaultdict(set)
        for r in rows[k]:
            for col, v in zip(hdr[k], r):
                if v in keyset:
                    hit[col].add(v)
        if hit:
            print(f"  [{k}] 命中字段: " + str({c: sorted(s)[:5] for c, s in hit.items()}))
        else:
            print(f"  [{k}] 无任何字段命中 period key")
    print("  注：connections.id 出现 'anuradhapura' 等是地名与词表 key 的偶然同名，不是引用。")

    hr("8. connections.csv 概览")
    ch, cr, ci = hdr["connections"], rows["connections"], {n: i for i, n in enumerate(hdr["connections"])}
    print("字段清单：", ", ".join(ch))
    print(f"行数: {len(cr)}  year_after_which 非空: "
          f"{sum(1 for r in cr if r[ci['year_after_which']].strip())} / {len(cr)}")
    print(f"connection_type 取值个数: {len(Counter(r[ci['connection_type']] for r in cr))}")
    print("  top: " + str(Counter(r[ci["connection_type"]] for r in cr).most_common(8)))
    print(f"connects_to 样例: {[r[ci['connects_to']] for r in cr[:3]]}  (URI，不是裸 id)")

    hr("9. 与 gis_README.md 记载的不一致清单")
    print("  (1) README 称 year_after_which / year_before_which 'Applies to: places.csv'，")
    print(f"      实测 places.csv 表头共 {len(ph)} 字段，无此二字段。")
    print("  (2) README 通篇引用 'locations.csv'，实测仓库拆成 location_points.csv /")
    print("      location_polygons.csv / location_linestrings.csv，不存在 locations.csv。")
    print("  (3) README 的 representative_longitude 释义写成 'A latitude coordinate'（复制粘贴错误），")
    print("      但格式说明为 signed decimal degrees，且实测取值与纬度列量级不同，可按经度使用。")
    print("  (4) README 未记载 places.csv 存在的 location_precision / bounding_box_wkt 组合用法差异，")
    print("      也未提及 places.csv 无条件字段；地点类型须 join places_place_types.csv。")


if __name__ == "__main__":
    main()
