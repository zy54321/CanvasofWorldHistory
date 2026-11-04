#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
r2_verify_whg_mcgd_chgis.py
WB-002 P0收敛 第二轮：复算 LICENSE_STATUS.md / FIELD_MAPPING.csv 中 WHG、MCGD、CHGIS 的全部数字与引用。
只读本地样本（设计资料/P0验证/WB-002/sample_data/...），不联网、不下载。
用法（项目根目录下）:
    python code/p0/wb-002-tools/r2_verify_whg_mcgd_chgis.py
"""
import csv, io, json, os, re, struct, zipfile
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OLD = os.path.join(ROOT, "设计资料", "P0验证", "WB-002", "sample_data")


def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


# ---------------------------------------------------------------- WHG
def whg():
    hr("A. WHG 逐记录来源与许可")
    ap = os.path.join(OLD, "whg", "api", "place")
    files = sorted(os.listdir(ap))
    print(f"place 样本文件 {len(files)} 个\n")
    rows = []
    for f in files:
        d = json.load(open(os.path.join(ap, f), encoding="utf-8"))
        if "attribution" in d:                      # JSON-LD 单记录 shape
            a = d["attribution"]
            props = d.get("properties", {})
            rows.append(dict(
                file=f, schema="jsonld-single-record",
                source_id=props.get("source_id", ""),
                ns=a.get("id", ""),
                spdx=a.get("license__spdx_id", ""),
                lic_label=a.get("license__label", ""),
                lic_url=a.get("license__url", ""),
                attr_req=a.get("license__attribution_required"),
                commercial=a.get("license__permits_commercial"),
                share_alike=a.get("license__share_alike"),
                redistributable=a.get("redistributable"),
                downloadable=a.get("downloadable"),
                blocked=a.get("download_blocked_reason", ""),
                citation=a.get("citation_text", ""),
                rights_holder=a.get("rights_holder", ""),
                when=d.get("when"),
                evidence="JSON 顶层 attribution.*",
            ))
        else:                                        # 旧扁平 shape
            ds = d.get("datasets", [{}])
            rows.append(dict(
                file=f, schema="legacy-flat",
                source_id="", ns="(无 attribution)",
                spdx="", lic_label="", lic_url="", attr_req=None, commercial=None,
                share_alike=None, redistributable=None, downloadable=None, blocked="",
                citation="", rights_holder="",
                when={"minmax": d.get("minmax"), "attestation_years": d.get("attestation_years")},
                evidence=f"仅 datasets={ds}；无 attribution/license 键",
            ))

    for r in rows:
        print(f"[{r['file']}]  schema={r['schema']}")
        print(f"    source_id={r['source_id']!r}  namespace={r['ns']!r}")
        print(f"    license={r['spdx']!r} ({r['lic_label']})  url={r['lic_url']}")
        print(f"    attribution_required={r['attr_req']}  permits_commercial={r['commercial']}  share_alike={r['share_alike']}")
        print(f"    redistributable={r['redistributable']}  downloadable={r['downloadable']}  reason={r['blocked']!r}")
        print(f"    citation={r['citation']!r}  rights_holder={r['rights_holder']!r}")
        print(f"    when/minmax={json.dumps(r['when'], ensure_ascii=False)}")
        print(f"    evidence: {r['evidence']}")
        print()

    print("可确认许可的记录数（有 SPDX 级 license 字段）:",
          sum(1 for r in rows if r["spdx"]))
    print("无法从记录本身确认许可的记录数:", sum(1 for r in rows if not r["spdx"]),
          [r["file"] for r in rows if not r["spdx"]])

    # sources.json
    print("\n--- sources.json ---")
    src = json.load(open(os.path.join(OLD, "whg", "api", "sources.json"), encoding="utf-8"))["sources"]
    print(f"命名空间数: {len(src)}")
    spdx_keys = [k for s in src for k in s if "licen" in k.lower()]
    print("sources.json 中出现 license* 字段的键:", set(spdx_keys) or "无 —— 该文件不含 SPDX/许可字段")
    print("\n非 redistributable 的命名空间:")
    for s in src:
        if s.get("redistributable") is False:
            print(f"   {s['namespace']:10s} {s['name'][:50]:52s} downloadable={s['downloadable']} reason={s['download_blocked_reason']!r}")
    print("\n用户关心的命名空间:")
    for ns in ("gn", "tgn", "chgis", "kain_par", "nl", "hgis", "pl"):
        s = next((x for x in src if x["namespace"] == ns), None)
        if s:
            print(f"   {ns:10s} record_count={s['record_count']:>9} redistributable={s['redistributable']} "
                  f"downloadable={s['downloadable']} blocked={s['download_blocked_reason']!r}")
        else:
            print(f"   {ns}: 不在 sources.json")

    # 文档快照
    print("\n--- whg_apis_docs.html 关键原文 ---")
    t = open(os.path.join(OLD, "whg", "whg_apis_docs.html"), encoding="utf-8", errors="replace").read()
    t = re.sub(r"<script.*?</script>", "", t, flags=re.S)
    t = re.sub(r"<style.*?</style>", "", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    import html as _h
    t = _h.unescape(t)
    t = re.sub(r"\s+", " ", t)
    quotes = [
        ("redistributable 定义",
         r"redistributable answers a narrower question[^.]{0,400}\."),
        ("三源 451",
         r"For three sources on production today[^.]{0,300}\."),
        ("downloadable vs redistributable",
         r"downloadable: false alongside redistributable: true is normal[^.]{0,300}\."),
        ("attribution 出现位置",
         r"/api/place/… \(single record\) an attribution object on the record itself[^.]{0,80}"),
        ("attribution.whg overlay",
         r"attribution\.whg is WHG’s own licence[^.]{0,300}\."),
        ("contributor dataset 归属",
         r"Records served from WHG’s own database use the pseudo-namespace whg[^.]{0,300}\."),
    ]
    for label, pat in quotes:
        m = re.search(pat, t)
        print(f"  [{label}] " + (("..." + m.group(0) + "...") if m else "未在快照中检索到"))
    return rows


# ---------------------------------------------------------------- MCGD
def mcgd():
    hr("B. MCGD 960 行样本")
    p = os.path.join(OLD, "mcgd", "MCGD_Data2026_08_25.csv.head-960rows.sample.csv")
    raw = open(p, "rb").read()
    print(f"文件={os.path.basename(p)}  字节={len(raw)}  BOM={'有' if raw[:3] == b'\xef\xbb\xbf' else '无'}")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig", errors="replace"))))
    h, data = rows[0], [r for r in rows[1:] if r]
    ix = {n: i for i, n in enumerate(h)}
    print(f"字段数={len(h)}  字段={h}  数据行={len(data)}")

    print("\n-- Code 分布 --")
    cc = Counter(r[ix["Code"]] for r in data)
    print(f"  唯一值={len(cc)}  {dict(cc)}")
    print("  Zenodo 描述记录的取值域: A=Canonical Chinese name / C=Alternative Chinese name /")
    print("                          P=pinyin / W=other transliteration / PP,WW=未匹配到中文名")
    print("  样本中未出现: A(仅1条且值为拉丁转写, 存疑), C")
    print("  样本中出现但描述未记载: 'NA', 'J'")

    print("\n-- PROVID 分布 --")
    pc = Counter(r[ix["PROVID"]] for r in data)
    print(f"  唯一值={len(pc)}  {dict(sorted(pc.items(), key=lambda kv: (kv[0] == 'NA', kv[0])))}")
    m, m2 = defaultdict(set), defaultdict(set)
    for r in data:
        m[r[ix["PROVID"]]].add((r[ix["Prov_Zh"]], r[ix["Prov_Py"]]))
        m2[(r[ix["Prov_Zh"]], r[ix["Prov_Py"]])].add(r[ix["PROVID"]])
    print(f"  PROVID -> (Prov_Zh,Prov_Py) 是否 1:1: "
          f"一对多={sum(1 for v in m.values() if len(v) > 1)}, "
          f"反向一对多={sum(1 for v in m2.values() if len(v) > 1)}")
    print(f"  (Prov_Zh,Prov_Py) 唯一组合数={len(m2)}  PROVID 唯一值数={len(m)}")
    print("  PROVID 完整映射:")
    for k in sorted(m, key=lambda x: (x == "NA", int(x) if x.isdigit() else 999)):
        print(f"    {k:>4s} -> {sorted(m[k])}")

    print("\n-- LocID / NameID --")
    L = [r[ix["LocID"]] for r in data]
    N = [r[ix["NameID"]] for r in data]
    print(f"  LocID 唯一={len(set(L))} / {len(L)} 行")
    print(f"  NameID 唯一={len(set(N))} / {len(N)} 行  (Zenodo: NameID = H + 7 位)")
    print(f"  NameID 全部以 H 开头: {all(x.startswith('H') for x in N)}; 长度分布: {dict(Counter(len(x) for x in N))}")
    dl, dn = defaultdict(set), defaultdict(set)
    for r in data:
        dl[r[ix["LocID"]]].add(r[ix["NameID"]])
        dn[r[ix["NameID"]]].add(r[ix["LocID"]])
    print(f"  一个 LocID 挂多个 NameID: {sum(1 for v in dl.values() if len(v) > 1)} 个 LocID (名字多于地点 => 多对一)")
    print(f"  一个 NameID 挂多个 LocID: {sum(1 for v in dn.values() if len(v) > 1)} 个 NameID")
    mx = max(dl.items(), key=lambda kv: len(kv[1]))
    print(f"  挂名最多的 LocID: {mx[0]} -> {len(mx[1])} 个 NameID")
    print(f"  LocID 首字母: {dict(Counter(x[0] for x in L))}  "
          "(Zenodo: D=取自 CHGIS, E=取自 GeoNames 或地图资料)")
    print("  LocID 首字母 x Code 交叉: "
          + str(dict(sorted(Counter((r[ix['LocID']][0], r[ix['Code']]) for r in data).items()))))

    print("\n-- Name 转写风格（Wade-Giles 证据）--")
    for n, r in enumerate(data[:6], start=2):
        print(f"    行{n}: {r[ix['Name']]!r}  Code={r[ix['Code']]}  Prov_Py={r[ix['Prov_Py']]}")
    wg = [r[ix["Name"]] for r in data if "'" in r[ix["Name"]]]
    print(f"  含撇号(送气符)的 Name: {len(wg)} / {len(data)}  例: {wg[:8]}")

    print("\n-- LAT / LONG --")
    la = [float(r[ix["LAT"]]) for r in data]
    lo = [float(r[ix["LONG"]]) for r in data]
    print(f"  LAT 可解析 {len(la)}/{len(data)}  min={min(la)} max={max(la)}")
    print(f"  LONG 可解析 {len(lo)}/{len(data)}  min={min(lo)} max={max(lo)}")
    print(f"  落在 (18-54N,73-135E) 中国 bbox: "
          f"{sum(1 for a, b in zip(la, lo) if 18 <= a <= 54 and 73 <= b <= 135)}/{len(data)}")
    print("  越界 LONG:")
    for n, r in enumerate(data, start=2):
        if not -180 <= float(r[ix["LONG"]]) <= 180:
            print(f"    行{n}: {dict(zip(h, r))}")
    print("  非中国 bbox 的行:")
    for n, r in enumerate(data, start=2):
        a, b = float(r[ix["LAT"]]), float(r[ix["LONG"]])
        if not (18 <= a <= 54 and 73 <= b <= 135):
            print(f"    行{n}: Name={r[ix['Name']]!r} Prov_Py={r[ix['Prov_Py']]!r} Code={r[ix['Code']]!r} "
                  f"LAT={a} LONG={b} LocID={r[ix['LocID']]} PROVID={r[ix['PROVID']]!r}")

    print("\n-- 是否有 CRS / 坐标轴声明 --")
    print(f"  表头全部字段: {h}")
    print(f"  含 crs/coord/datum/srid/proj 的字段: "
          f"{[x for x in h if any(t in x.lower() for t in ('crs','coord','datum','srid','proj'))] or '无'}")
    print("  结论: 无任何 CRS 或轴序声明。'LAT/LONG' 只是列名，不构成 CRS 断言。")

    print("\n-- Zenodo 元数据 --")
    z = json.load(open(os.path.join(OLD, "mcgd", "zenodo_record_22094815.json"), encoding="utf-8"))
    md = z["metadata"]
    for k in ("title", "doi", "publication_date", "access_right", "license",
              "resource_type", "language", "version"):
        print(f"  metadata.{k} = {json.dumps(md.get(k), ensure_ascii=False) if k in md else '<<不存在该字段>>'}")
    print(f"  顶层 doi={z.get('doi')!r}  conceptdoi={z.get('conceptdoi')!r}")
    print(f"  files={[(f['key'], f['size'], f['checksum']) for f in z.get('files', [])]}")
    print(f"  metadata.relations.version={json.dumps(md.get('relations', {}).get('version'), ensure_ascii=False)}")
    print(f"  creators={json.dumps(md.get('creators'), ensure_ascii=False)}")
    desc = re.sub(r"<br\s*/?>", "\n", md["description"])
    desc = re.sub(r"</p>", "\n", desc)
    desc = re.sub(r"<[^>]+>", "", desc)
    import html as _h
    desc = _h.unescape(desc)
    for label, pat in [
        ("总条数", r"Altogether there are [\d,]+ entries"),
        ("域外地点说明", r"plus a number of locations outside of China[^.]*\."),
        ("域外剔除方法", r"Such place names can easily be removed[^.]*\."),
        ("LocID D/E 定义", r"Locations IDs that start with \"D\"[^.]*\."),
        ("NameID 定义", r"The Name IDs all start with H[^.]*\."),
        ("版本串", r"MCGD_Data_V2\.2[^\n]*"),
        ("Unknown 坐标", r"labelled in the Lat Long columns as \"Unknown\"[^.]*\."),
    ]:
        m = re.search(pat, desc)
        print(f"  [{label}] " + (repr(m.group(0)) if m else "未检索到"))


# ---------------------------------------------------------------- CHGIS
def chgis():
    hr("C. CHGIS 样本字段与许可")
    d = os.path.join(OLD, "chgis")
    for z, inner in [("v6_time_pref_pts_utf_wgs84.zip", "v6_time_pref_pts_utf_wgs84.dbf"),
                     ("v6_time_cnty_pts_utf_wgs84.zip", "v6_time_cnty_pts_utf_wgs84.dbf")]:
        with zipfile.ZipFile(os.path.join(d, z)) as zf:
            b = zf.read(inner)
            nrec = struct.unpack("<I", b[4:8])[0]
            hlen = struct.unpack("<H", b[8:10])[0]
            rlen = struct.unpack("<H", b[10:12])[0]
            fields, off = [], 32
            while b[off] != 0x0D:
                fields.append((b[off:off + 11].split(b"\x00")[0].decode("latin-1"),
                               chr(b[off + 11]), b[off + 16], b[off + 17]))
                off += 32
            print(f"\n[{z}]  记录数={nrec}  字段数={len(fields)}")
            print("  字段: " + ", ".join(f[0] for f in fields))
            for i in range(2):
                rec = b[hlen + i * rlen: hlen + (i + 1) * rlen]
                p, vals = 1, {}
                for (nm, ty, ln, dec) in fields:
                    vals[nm] = rec[p:p + ln].decode("utf-8", errors="replace").strip()
                    p += ln
                print(f"  记录{i}: " + str({k: v for k, v in vals.items() if v}))
            for n in zf.namelist():
                if n.endswith(".prj"):
                    print("  .prj: " + zf.read(n).decode("utf-8", errors="replace").strip())
                if n.endswith(".cpg"):
                    print("  .cpg: " + zf.read(n).decode("latin-1"))

    print("\n-- CHGIS 日期规则（CHGIS_data_dictionary.zip / xtra_date_rules.xlsx）--")
    with zipfile.ZipFile(os.path.join(d, "CHGIS_data_dictionary.zip")) as zf:
        z2 = zipfile.ZipFile(io.BytesIO(zf.read("xtra_date_rules.xlsx")))
        x = z2.read("xl/worksheets/sheet1.xml").decode("utf-8", errors="replace")
        import xml.etree.ElementTree as ET
        NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        for row in ET.fromstring(x).iter(f"{NS}row"):
            cells = []
            for c in row.findall(f"{NS}c"):
                txt = "".join(t.text or "" for t in c.iter(f"{NS}t"))
                if not txt:
                    v = c.find(f"{NS}v")
                    txt = v.text if v is not None else ""
                cells.append(txt)
            if any(cells):
                print("   " + " | ".join(cells))

    print("\n-- CHGIS EULA（api/dataset_FDLFJ3_EULA.json）--")
    e = json.load(open(os.path.join(d, "api", "dataset_FDLFJ3_EULA.json"), encoding="utf-8"))["data"]["latestVersion"]
    print(f"  license 字段 = {e.get('license')!r}   (即无 SPDX)")
    print(f"  persistentUrl = {json.load(open(os.path.join(d, 'api', 'dataset_FDLFJ3_EULA.json'), encoding='utf-8'))['data'].get('persistentUrl')}")
    tou = e.get("termsOfUse", "")
    for label, pat in [
        ("(3) 使用限制", r"\(3\) terms of use:.{0,420}"),
        ("(4) 强制引用", r"Mandatory Citation:.{0,220}"),
        ("(4) 修改说明义务", r"Clearly describe any changes.{0,160}"),
        ("(5) 再分发禁止", r"\(5\) redistribution:.{0,480}"),
    ]:
        m = re.search(pat, tou, re.S)
        print(f"  [{label}] " + (repr(m.group(0)) if m else "未检索到"))


if __name__ == "__main__":
    whg()
    mcgd()
    chgis()
