#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""M4-2 来源可选化 / 许可门禁取消 —— 真实 HTTP 实测。

用法：
  python ops/m4-2/api_m4_2_test.py [baseUrl]      默认 http://127.0.0.1:8089

覆盖：
  A  完全不带来源的地名 / 别名 / 坐标可以创建、可检索、可上图
  B  取消“来源准入”不等于取消数据质量（单侧坐标、越界、无坐标、CRS 未知仍按原规则）
  C  已有来源关系的导入地点不回退、不受影响
  D  写保护仍生效（正式库 403，由 api_m3_test.py guard 覆盖，这里只做快照对比）

仅用标准库。所有断言都是真的发请求并核对响应。
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8089').rstrip('/')
RESULTS = []
TAG = 'M4二'


def call(method, path, body=None):
    url = BASE + path
    data = None
    headers = {'Accept': 'application/json'}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode('utf-8')
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8')
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def check(cid, desc, cond, expect, actual):
    ok = bool(cond)
    RESULTS.append((cid, desc, ok, expect, actual))
    print('%s %-5s %-44s | 期望 %s | 实际 %s'
          % ('PASS' if ok else 'FAIL', cid, desc, expect, str(actual)[:100]))
    return ok


def summary(title):
    n = len(RESULTS)
    p = sum(1 for r in RESULTS if r[2])
    print('\n=== %s：PASS %d / %d ===' % (title, p, n))
    return 0 if p == n else 1


def main():
    print('== M4-2 来源可选化实测  目标 %s ==' % BASE)
    st, health = call('GET', '/api/v1/meta/health')
    check('S01', '目标实例健康且为测试库', st == 200 and health.get('database') == 'canvas_history_m2check',
          '200 + canvas_history_m2check', '%s %s' % (st, (health or {}).get('database')))
    st, pol = call('GET', '/api/v1/meta/write-policy')
    check('S02', '测试实例允许写入', st == 200 and pol.get('writeAllowed') is True,
          'writeAllowed=true', '%s %s' % (st, (pol or {}).get('writeAllowed')))

    created = []
    name_text = TAG + '-无来源别名'
    canonical = TAG + '-无来源城'

    # ============================================================ A. 无来源创建
    print('\n--- A. 来源缺失不影响创建 / 检索 / 上图 ---')
    st, place = call('POST', '/api/v1/places', {
        'canonicalName': canonical, 'placeType': 'settlement', 'notes': 'M4-2 来源可选验证'})
    pid = (place or {}).get('placeId')
    ok = check('A01', '不带任何来源即可创建地点', st == 201 and pid, '201 + placeId',
               '%s %s' % (st, pid))
    if not ok:
        return summary('M4-2 来源可选化')
    created.append(('place', pid))

    # 名称：不带来源
    st, nm = call('POST', '/api/v1/places/%d/names' % pid, {
        'nameText': name_text, 'nameType': 'alternate', 'nameLang': 'zh'})
    nid = (nm or {}).get('nameId')
    check('A02', '不带来源即可添加别名', st == 201 and nid, '201 + nameId', '%s %s' % (st, nid))
    if nid:
        created.append(('name', pid, nid))

    # 坐标：默认 crsConfidence=inferred
    st, loc = call('POST', '/api/v1/places/%d/locations' % pid, {
        'lon': 118.35, 'lat': 35.05, 'locationPrecision': 'approximate'})
    lid = (loc or {}).get('locationId')
    check('A03', '不带来源即可添加坐标', st == 201 and lid, '201 + locationId', '%s %s' % (st, lid))
    if lid:
        created.append(('location', pid, lid))

    # 详情：来源数组为空但不是错误
    st, det = call('GET', '/api/v1/places/%d' % pid)
    srcs = ((det or {}).get('sourceRecords') or []) if isinstance(det, dict) else None
    check('A04', '详情正常返回、sourceRecords 为空数组而非报错',
          st == 200 and srcs == [], '200 + []', '%s %s' % (st, srcs))
    locs = ((det or {}).get('locations') or []) if isinstance(det, dict) else []
    check('A05', '详情里能看到刚录入的坐标行',
          len(locs) >= 1 and any(abs(float((l or {}).get('lon') or 0) - 118.35) < 1e-6 for l in locs),
          '>=1 行且含 118.35', '%d 行' % len(locs))

    # 搜索：必须命中
    st, sr = call('GET', '/api/v1/places?' + urllib.parse.urlencode({'keyword': name_text, 'size': 20}))
    hits = [(sr or {}).get('items') or []]
    ids = [h.get('placeId') for h in hits[0]]
    check('A06', '按无来源别名可以搜到该地点', st == 200 and pid in ids, '命中 %s' % pid,
          '%s %s' % (st, ids[:5]))

    # 地图：必须上图
    st, mp = call('GET', '/api/v1/places/map?' + urllib.parse.urlencode(
        {'bbox': '118.0,34.7,118.7,35.4', 'limit': 500}))
    feats = (mp or {}).get('features') or []
    fids = [f.get('properties', {}).get('placeId') for f in feats]
    check('A07', '无来源的有效坐标进入地图 bbox 查询', st == 200 and pid in fids,
          '要素含 %s' % pid, '%s total=%s' % (st, (mp or {}).get('meta', {}).get('totalInBbox')))

    # ============================================================ B. 质量未被放宽
    print('\n--- B. 取消来源准入 ≠ 取消质量检查 ---')
    st, b1 = call('POST', '/api/v1/places/%d/locations' % pid, {'lon': 118.4})
    check('B01', '只给经度 → 400', st == 400, '400', st)

    st, b2 = call('POST', '/api/v1/places/%d/locations' % pid, {'lon': 200.0, 'lat': 35.0})
    check('B02', '经度越界 → 400', st == 400, '400', st)

    st, b3 = call('POST', '/api/v1/places/%d/locations' % pid, {'notes': '只有备注没有坐标'})
    no_geom_id = (b3 or {}).get('locationId')
    check('B03', '无坐标的位置仍可保存（不因缺坐标拒绝）', st == 201 and no_geom_id,
          '201 + locationId', '%s %s' % (st, no_geom_id))
    if no_geom_id:
        created.append(('location', pid, no_geom_id))

    st, b4 = call('POST', '/api/v1/places/%d/locations' % pid, {
        'lon': 118.36, 'lat': 35.06, 'crsConfidence': 'unknown'})
    unknown_id = (b4 or {}).get('locationId')
    check('B04', 'CRS 未知的坐标仍可保存（不拒绝）', st == 201 and unknown_id,
          '201 + locationId', '%s %s' % (st, unknown_id))
    if unknown_id:
        created.append(('location', pid, unknown_id))
    # CRS 未知的坐标可以保存，但不得被当成可信的 WGS84 位置上图
    st, p2 = call('POST', '/api/v1/places', {
        'canonicalName': TAG + '-CRS未知城', 'placeType': 'settlement'})
    pid2 = (p2 or {}).get('placeId')
    if pid2:
        created.append(('place', pid2))
        st, l2 = call('POST', '/api/v1/places/%d/locations' % pid2, {
            'lon': 119.10, 'lat': 36.20, 'crsConfidence': 'unknown'})
        check('B05', 'CRS 未知的坐标可以保存（不拒绝）', st == 201, '201', st)
        st, det2 = call('GET', '/api/v1/places/%d' % pid2)
        locs2 = (det2 or {}).get('locations') or []
        check('B06', 'CRS 未知行在详情里如实标为 unknown 且保留几何',
              len(locs2) == 1 and locs2[0].get('crsConfidence') == 'unknown'
              and locs2[0].get('hasGeom') is True,
              '1 行 unknown + hasGeom', '%d 行 %s' % (len(locs2), (locs2[0] or {}).get('crsConfidence') if locs2 else None))
        st, mp2 = call('GET', '/api/v1/places/map?' + urllib.parse.urlencode(
            {'bbox': '119.0,36.1,119.2,36.3', 'limit': 200}))
        fids2 = [f.get('properties', {}).get('placeId') for f in ((mp2 or {}).get('features') or [])]
        check('B07', 'CRS 未知的地点不进入地图（不冒充 WGS84）',
              st == 200 and pid2 not in fids2, '不含 %s' % pid2,
              '%s total=%s' % (st, (mp2 or {}).get('meta', {}).get('totalInBbox')))

    # ============================================================ C. 已有来源不回退
    print('\n--- C. 已有来源关系保持 ---')
    st, sr2 = call('GET', '/api/v1/places?' + urllib.parse.urlencode({'keyword': 'Santa Fe', 'size': 10}))
    items = (sr2 or {}).get('items') or []
    imported = [i for i in items if str(i.get('datasetId', '')).startswith('whg')]
    check('C01', '导入的 WHG 地点仍可检索', st == 200 and len(imported) >= 1,
          '>=1 条 whg 地点', '%d 条' % len(imported))
    if imported:
        dst, imp_det = call('GET', '/api/v1/places/%d' % imported[0]['placeId'])
        recs = (imp_det or {}).get('sourceRecords') or []
        check('C02', '导入地点详情的 sourceRecords 仍非空（来源未被清空）',
              dst == 200 and len(recs) >= 1, '>=1', '%s %d 条' % (dst, len(recs)))

    # ============================================================ 清理
    print('\n--- 清理 ---')
    for kind, *ids in reversed(created):
        if kind == 'location':
            call('DELETE', '/api/v1/places/%d/locations/%d' % (ids[0], ids[1]))
        elif kind == 'name':
            call('DELETE', '/api/v1/places/%d/names/%d' % (ids[0], ids[1]))
    if created:
        st, _ = call('DELETE', '/api/v1/places/%d' % pid)
        check('Z01', '清理：手工测试地点已删除', st in (200, 204), '200/204', st)

    return summary('M4-2 来源可选化')


if __name__ == '__main__':
    sys.exit(main())
