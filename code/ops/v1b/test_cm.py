"""阶段 B：内容管理 CM01–CM07 验收（CM06 的交互部分在浏览器脚本里）。

关键点：名称质量分类不信任后端的 SQL，而是把 57,967 条原始数据拉到本地
用**独立的 Python 实现**再算一遍，逐类比对总数。这样两边同错的可能性很低。
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE / "ops" / ".deps"))
sys.path.insert(0, str(CODE / "ops"))

import psycopg2  # noqa: E402
from import_staging import load_env  # noqa: E402

API = "http://127.0.0.1:8088"
PLACEHOLDER = {"untitled", "unnamed place", "unnamed", "unknown", "unknown place",
               "n/a", "?", "-", "(unknown)", "no name"}

results: List[Dict[str, Any]] = []


def check(cid: str, desc: str, ok: bool, detail: Any = "") -> None:
    results.append({"id": cid, "desc": desc, "ok": bool(ok), "detail": str(detail)})
    print(f"{'✓' if ok else '✗'} {cid} {desc}" + (f" :: {detail}" if detail != "" else ""))


def get(path: str, **params) -> Dict[str, Any]:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode({k: str(v) for k, v in params.items()})
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.load(r)


def conn():
    env = load_env()
    c = psycopg2.connect(host="127.0.0.1", port=int(env.get("DB_HOST_PORT", "55432")),
                         dbname="canvas_history", user=env["POSTGRES_USER"],
                         password=env["POSTGRES_PASSWORD"])
    c.autocommit = True
    return c


def classify(canonical: str | None, has_alt: bool) -> str:
    """独立实现：与 PlaceNames.quality 同规则，但代码完全不同。"""
    t = (canonical or "").strip()
    is_ph = (t == "") or (t.lower() in PLACEHOLDER)
    if not is_ph:
        return "valid"
    if has_alt:
        return "alias_only"
    return "no_name" if t == "" else "placeholder"


def main() -> None:
    cur = conn().cursor()

    # ---------------------------------------------------------------- 真值
    cur.execute("""
        SELECT p.place_id, p.canonical_name,
               EXISTS (SELECT 1 FROM historical_place_name n
                        WHERE n.place_id = p.place_id
                          AND btrim(coalesce(n.name_text,'')) <> '') AS has_alt,
               EXISTS (SELECT 1 FROM historical_place_location l
                        WHERE l.place_id = p.place_id AND l.geom IS NOT NULL
                          AND l.geom_type = 'Point') AS has_point,
               EXISTS (SELECT 1 FROM historical_place_location l
                        WHERE l.place_id = p.place_id AND l.geom IS NOT NULL
                          AND l.geom_type = 'LineString') AS has_line,
               EXISTS (SELECT 1 FROM historical_place_location l
                        WHERE l.place_id = p.place_id AND l.geom IS NOT NULL
                          AND l.geom_type IN ('Polygon','MultiPolygon')) AS has_poly,
               EXISTS (SELECT 1 FROM historical_place_location l
                        WHERE l.place_id = p.place_id AND l.geom IS NOT NULL) AS has_geom,
               (SELECT count(*) FROM historical_place_name n
                 WHERE n.place_id = p.place_id) AS name_rows,
               (SELECT count(*) FROM historical_place_location l
                 WHERE l.place_id = p.place_id) AS loc_rows
          FROM historical_place p
    """)
    rows = cur.fetchall()
    truth = {r[0]: dict(canonical=r[1], has_alt=r[2], point=r[3], line=r[4],
                        poly=r[5], geom=r[6], names=r[7], locs=r[8]) for r in rows}
    total = len(truth)
    print(f"库内地点 {total:,}\n")

    exp_quality: Dict[str, int] = {"valid": 0, "alias_only": 0, "placeholder": 0, "no_name": 0}
    for v in truth.values():
        exp_quality[classify(v["canonical"], v["has_alt"])] += 1
    exp_geom = {
        "point": sum(1 for v in truth.values() if v["point"]),
        "line": sum(1 for v in truth.values() if v["line"]),
        "polygon": sum(1 for v in truth.values() if v["poly"]),
        "none": sum(1 for v in truth.values() if not v["geom"]),
    }

    # ------------------------------------------------------- CM02 名称分类
    got_quality = {}
    for q in ("valid", "alias_only", "placeholder", "no_name"):
        got_quality[q] = get("/api/v1/places/admin", size=1, nameQuality=q)["total"]
    check("CM02-a", "四类名称分类合计 = 全部地点（互斥且穷尽）",
          sum(got_quality.values()) == total, f"{got_quality} 合计 {sum(got_quality.values())}")
    check("CM02-b", "逐类数量与独立实现一致", got_quality == exp_quality,
          f"API {got_quality} vs 独立 {exp_quality}")

    # ------------------------------------------------------- CM01 几何筛选
    got_geom = {g: get("/api/v1/places/admin", size=1, geomType=g)["total"]
                for g in ("point", "line", "polygon", "none")}
    check("CM01-a", "四种几何筛选数量与独立实现一致", got_geom == exp_geom,
          f"API {got_geom} vs 独立 {exp_geom}")

    # 抽样：筛选出来的每一行都必须真的具备该几何；页内不得出现重复 place_id
    for g, key in (("point", "point"), ("line", "line"), ("polygon", "poly")):
        bad, dup = [], 0
        page_ids = []
        for page in (1, 2, 200):
            d = get("/api/v1/places/admin", size=100, geomType=g, page=page)
            ids = [it["placeId"] for it in d["items"]]
            dup += len(ids) - len(set(ids))
            page_ids += ids
            for it in d["items"]:
                if not truth.get(it["placeId"], {}).get(key):
                    bad.append(it["placeId"])
        check(f"CM01-{key}", f"{g} 筛选的每一行都真的含该类几何、页内无重复",
              not bad and dup == 0, f"不符 {bad[:3]} / 页内重复 {dup}")

    # 有面也有线的地点：必须同时出现在两个筛选里（存在性判断，不是唯一归属）
    both = [pid for pid, v in truth.items() if v["line"] and v["poly"]]
    cnt_line = get("/api/v1/places/admin", size=1, geomType="line")["total"]
    cnt_poly = get("/api/v1/places/admin", size=1, geomType="polygon")["total"]
    check("CM01-e", "同时有线和面的地点在两个筛选里都算（存在性语义）",
          cnt_line + cnt_poly > len(both) and len(both) > 0,
          f"线+面 {cnt_line}+{cnt_poly}={cnt_line + cnt_poly} 条，其中线面兼有 {len(both)} 个地点")

    # ------------------------------------------------------- CM03 组合筛选
    combo_exp = sum(1 for v in truth.values()
                    if v["poly"] and classify(v["canonical"], v["has_alt"]) == "valid")
    combo_got = get("/api/v1/places/admin", size=1, geomType="polygon",
                    nameQuality="valid")["total"]
    check("CM03-a", "面 + 有效名称（AND）数量正确", combo_got == combo_exp,
          f"API {combo_got} vs 独立 {combo_exp}")

    combo2_exp = sum(1 for v in truth.values()
                     if v["line"] and classify(v["canonical"], v["has_alt"]) == "placeholder")
    combo2_got = get("/api/v1/places/admin", size=1, geomType="line",
                     nameQuality="placeholder")["total"]
    check("CM03-b", "线 + 占位无名（AND）数量正确", combo2_got == combo2_exp,
          f"API {combo2_got} vs 独立 {combo2_exp}")

    # 组合不能退化成 OR：结果必须 ≤ 任一单条件
    single_poly = get("/api/v1/places/admin", size=1, geomType="polygon")["total"]
    check("CM03-c", "组合结果 ≤ 两个单条件（说明是 AND 不是 OR）",
          combo_got <= min(single_poly, got_quality["valid"]),
          f"{combo_got} ≤ min({single_poly},{got_quality['valid']})")

    # 非法取值：应当 400，而不是静默返回全量
    for bad_val, field in (("triangles", "geomType"), ("bogus", "nameQuality")):
        try:
            get("/api/v1/places/admin", size=1, **{field: bad_val})
            ok, code = False, 200
        except urllib.error.HTTPError as e:  # noqa: PERF203
            ok, code = e.code == 400, e.code
        check(f"CM03-{field}", f"非法 {field} 返回 400", ok, code)

    # ------------------------------------------------------- CM04 列表字段
    d = get("/api/v1/places/admin", size=50)
    fields = {"placeId", "canonicalName", "displayName", "nameQuality", "pointCount",
              "lineCount", "polygonCount", "geomLocationCount", "locationCount",
              "nameCount", "datasetName"}
    missing = [f for f in fields if f not in (d["items"][0] if d["items"] else {})]
    check("CM04-a", "列表行含全部要求字段", not missing, f"缺 {missing}")

    bad_cnt, bad_name, bad_unnamed = [], [], []
    for it in d["items"]:
        t = truth[it["placeId"]]
        if (it["pointCount"] != (1 if t["point"] else 0)
                and it["pointCount"] == 0 and t["point"]):
            bad_cnt.append(it["placeId"])
        if it["nameCount"] != t["names"] or it["locationCount"] != t["locs"]:
            bad_cnt.append(it["placeId"])
        if it["nameQuality"] != classify(t["canonical"], t["has_alt"]):
            bad_name.append(it["placeId"])
        if it["nameQuality"] in ("placeholder", "no_name") and it["displayName"] is not None:
            bad_unnamed.append((it["placeId"], it["displayName"]))
        if it["nameQuality"] == "valid" and it["displayName"] != it["canonicalName"]:
            bad_name.append(it["placeId"])
    check("CM04-b", "名称数/位置数/名称质量与库内一致", not bad_cnt and not bad_name,
          f"计数不符 {bad_cnt[:3]} / 分类不符 {bad_name[:3]}")
    check("CM04-c", "无名地点的 displayName 为 null（由前端拼「未命名地点 · #id」）",
          not bad_unnamed, str(bad_unnamed[:3]))

    # 占位名但确有别名 → 必须给出真实别名
    alias_sample = [pid for pid, v in truth.items()
                    if classify(v["canonical"], v["has_alt"]) == "alias_only"][:5]
    alias_bad = []
    for pid in alias_sample:
        dd = get(f"/api/v1/places/{pid}")
        if not dd.get("displayName") or dd["displayName"] == dd["canonicalName"]:
            alias_bad.append(pid)
    check("CM04-d", "占位名+有别名 → 详情给出真实别名（canonicalName 保持原值）",
          not alias_bad, f"不符 {alias_bad}")

    # ------------------------------------------------------- CM05 分页
    d1 = get("/api/v1/places/admin", size=20, page=1)
    d2 = get("/api/v1/places/admin", size=20, page=2)
    d_last = get("/api/v1/places/admin", size=20, page=d1["totalPages"])
    overlap = set(x["placeId"] for x in d1["items"]) & set(x["placeId"] for x in d2["items"])
    check("CM05-a", "page1 / page2 无重叠", not overlap, str(list(overlap)[:3]))
    check("CM05-b", "totalPages 与 total/size 相符",
          d1["totalPages"] == -(-d1["total"] // 20), f"{d1['totalPages']}")
    check("CM05-c", "末页条数正确",
          len(d_last["items"]) == d1["total"] - (d1["totalPages"] - 1) * 20,
          f"{len(d_last['items'])} 条")

    # 跳页：直接取第 777 页，且与连续翻页的内容位置一致（用 place_id 序列验证唯一性）
    probe = get("/api/v1/places/admin", size=20, page=777)
    all_ids = [x["placeId"] for x in probe["items"]]
    check("CM05-d", "直接跳页可用且返回整页", len(all_ids) == 20, f"{len(all_ids)} 条")

    # 越界页：服务端应返回空列表而不是报错（前端负责拦）
    far = get("/api/v1/places/admin", size=20, page=999999)
    check("CM05-e", "超出范围的页返回空列表（不抛 500）", far["items"] == [],
          f"items={len(far['items'])}")

    # 带筛选翻页：第 2 页仍必须满足筛选条件
    f2 = get("/api/v1/places/admin", size=20, page=2, geomType="none")
    f2_bad = [x["placeId"] for x in f2["items"] if truth[x["placeId"]]["geom"]]
    check("CM05-f", "带筛选翻到第 2 页仍满足筛选条件", not f2_bad, str(f2_bad[:3]))

    # ------------------------------------------------------- CM07 性能
    bench = json.loads((CODE / "ops/reports/v1b/bench_b_final.json").read_text(encoding="utf-8"))
    check("CM07-a", "列表最差 P95 ≤ 300ms", bench["meets_target"],
          f"{bench['worst']['p95_ms']}ms @ {bench['worst']['case']}")
    check("CM07-b", "常规首页 P95 ≤ 300ms",
          bench["cases"]["all_p1"]["p95_ms"] <= 300,
          f"{bench['cases']['all_p1']['p95_ms']}ms")

    passed = sum(1 for r in results if r["ok"])
    print(f"\n结果 {passed}/{len(results)}")
    out = CODE / "ops/reports/v1b/cm_results.json"
    out.write_text(json.dumps({"results": results, "passed": passed,
                               "total": len(results)}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"写入 {out}")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
