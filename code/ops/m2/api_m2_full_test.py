#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M2 完整业务测试（真实 HTTP + 真实数据库，针对测试库 canvas_history_m2check）。

覆盖验收场景一~六：
  一 地点：新建（含无坐标）、多历史名称、坐标与精度、编辑、删除
  二 人物：新建、别名、生卒（BCE）、关联事件、活动地点、编辑、删除
  三 事件：新建（时间未知）、描述、关联多人物多地点、编辑、删除
  四 关联：新增/编辑/解除/重复关联
  五 时间：BCE/CE 边界、未知、开放区间、起止倒挂
  六 完整性：级联、RESTRICT、重复约束、孤儿扫描

用法：python ops/m2/api_m2_full_test.py [baseUrl]
"""
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8089').rstrip('/')
DB = 'canvas_history_m2check'
R = []


def call(method, path, body=None):
    req = urllib.request.Request(
        BASE + path,
        data=None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8'),
        headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read().decode('utf-8')
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8')
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def sql(q):
    r = subprocess.run(['docker', 'exec', 'canvas-history-db', 'psql', '-U', 'canvas_app',
                        '-d', DB, '-tAc', q], capture_output=True, text=True)
    return r.stdout.strip()


def check(cid, desc, cond, expect, actual):
    R.append((cid, desc, bool(cond)))
    print('%s %-6s %-44s | 期望 %s | 实际 %s'
          % ('PASS' if cond else 'FAIL', cid, desc, expect, str(actual)[:100]))


def main():
    print('== M2 完整业务测试  目标 %s  库 %s ==\n' % (BASE, DB))
    st, h = call('GET', '/api/v1/meta/health')
    check('S0', '实例指向测试库', st == 200 and h.get('database') == DB,
          '200 + ' + DB, '%s %s' % (st, h.get('database')))

    # ======================================================== 场景一：地点
    print('\n--- 场景一：地点管理 ---')
    st, r = call('POST', '/api/v1/places', {
        'canonicalName': '测试城', 'canonicalNameLang': 'zh',
        'placeType': 'settlement', 'description': '端到端测试地点'})
    pid = r.get('placeId') if isinstance(r, dict) else None
    check('P01', '新建地点（不含坐标）→ 201', st == 201 and pid, '201', '%s id=%s' % (st, pid))

    st, d = call('GET', '/api/v1/places/%s' % pid)
    check('P02', '未给坐标时保存为未定位（geom 为空、无经纬度）',
          st == 200 and d['locations'] == [] and d['canonicalName'] == '测试城',
          '200 且 locations 为空', '%s locs=%s' % (st, len(d.get('locations') or [])))

    n1 = call('POST', '/api/v1/places/%s/names' % pid,
              {'nameText': '测试城', 'nameLang': 'zh', 'nameType': 'primary',
               'timeBoundType': 'bounded', 'validFromYearAstro': -500, 'validToYearAstro': -400})[1]
    n2 = call('POST', '/api/v1/places/%s/names' % pid,
              {'nameText': 'Test City', 'nameLang': 'en', 'nameType': 'transliteration',
               'transliterationScheme': 'pinyin'})[1]
    st, d = call('GET', '/api/v1/places/%s' % pid)
    check('P03', '一个地点挂多个历史名称（含有效期与转写）',
          st == 200 and len(d['names']) == 2
          and any(x.get('validFromYear') == -500 for x in d['names']),
          '2 条名称，其一有效期 -500~-400',
          '%s names=%s' % (st, [(x['nameText'], x.get('validFromYear')) for x in d['names']]))

    st, _ = call('POST', '/api/v1/places/%s/names' % pid,
                 {'nameText': '测试城', 'nameLang': 'zh', 'nameType': 'primary'})
    check('P04', '同地点同类型同语言重名 → 409', st == 409, '409', '%s' % st)

    st, loc = call('POST', '/api/v1/places/%s/locations' % pid,
                   {'lon': 112.5, 'lat': 34.7, 'locationPrecision': 'approximate',
                    'uncertaintyM': 5000, 'crsConfidence': 'inferred'})
    lid = loc.get('locationId') if isinstance(loc, dict) else None
    st2, d = call('GET', '/api/v1/places/%s' % pid)
    L = d['locations'][0] if d['locations'] else {}
    check('P05', '添加坐标与定位精度', st == 201 and L.get('lon') == 112.5
          and L.get('locationPrecision') == 'approximate' and L.get('uncertaintyM') == 5000
          and L.get('hasGeom') is True,
          '201 且 lon=112.5 / approximate / ±5000 / hasGeom',
          '%s %s %s %s' % (st, L.get('lon'), L.get('locationPrecision'), L.get('hasGeom')))

    st, _ = call('POST', '/api/v1/places/%s/locations' % pid, {'lon': 200, 'lat': 34})
    check('P06', '经度越界 → 400', st == 400, '400', '%s' % st)
    st, _ = call('POST', '/api/v1/places/%s/locations' % pid, {'lon': 112.5})
    check('P07', '单侧坐标（只有经度）→ 400', st == 400, '400', '%s' % st)

    st, _ = call('PUT', '/api/v1/places/%s' % pid,
                 {'canonicalName': '测试城（改）', 'placeType': 'admin_center_county',
                  'description': '已编辑'})
    st2, d = call('GET', '/api/v1/places/%s' % pid)
    check('P08', '编辑地点主表', st == 200 and d['canonicalName'] == '测试城（改）'
          and d['description'] == '已编辑', '200 且名称/简介已改', '%s %s' % (st, d.get('canonicalName')))

    # ======================================================== 场景二：人物
    print('\n--- 场景二：人物管理 ---')
    st, p = call('POST', '/api/v1/persons', {
        'canonicalName': '测试人物', 'canonicalNameLang': 'zh', 'description': '端到端测试人物',
        'birthYearAstro': -550, 'birthPrecision': 'approximate', 'birthOriginalText': '约公元前六世纪',
        'deathYearAstro': -478, 'deathPrecision': 'approximate'})
    pid2 = p.get('personId') if isinstance(p, dict) else None
    check('H01', '新建人物（BCE 生卒）', st == 201 and pid2 and p['birthYearAstro'] == -550,
          '201 且 birth=-550', '%s id=%s' % (st, pid2))

    call('POST', '/api/v1/persons/%s/names' % pid2, {'nameText': '测试', 'nameLang': 'zh', 'nameType': 'courtesy'})
    call('POST', '/api/v1/persons/%s/names' % pid2,
         {'nameText': 'Test Person', 'nameLang': 'en', 'nameType': 'transliteration',
          'transliterationScheme': 'pinyin'})
    st, d = call('GET', '/api/v1/persons/%s' % pid2)
    check('H02', '人物别名/异体名/外文名多条', st == 200 and len(d['names']) == 2,
          '2 条名称', '%s names=%s' % (st, len(d.get('names') or [])))

    st, p3 = call('POST', '/api/v1/persons', {'canonicalName': '测试人物-资料残缺'})
    check('H03', '仅姓名即可创建（生卒/简介全缺失）', st == 201 and p3['birthYearAstro'] is None,
          '201 且 birth=null', '%s %s' % (st, p3.get('birthYearAstro') if isinstance(p3, dict) else '?'))
    pid3 = p3['personId']

    # ======================================================== 场景三：事件
    print('\n--- 场景三：事件管理 ---')
    st, e = call('POST', '/api/v1/events', {
        'title': '测试事件', 'summary': '端到端测试',
        'startYearAstro': -500, 'endYearAstro': -490, 'timePrecision': 'range',
        'eventType': 'cultural'})
    eid = e.get('eventId') if isinstance(e, dict) else None
    check('E01', '新建事件（区间）', st == 201 and eid and e['startYearAstro'] == -500,
          '201 且 -500~-490', '%s id=%s' % (st, eid))

    st, e2 = call('POST', '/api/v1/events', {'title': '测试事件-时间未知', 'eventType': 'unknown'})
    eid2 = e2['eventId']
    check('E02', '时间完全未知也可保存', st == 201 and e2['timePrecision'] == 'unknown'
          and e2['startYearAstro'] is None,
          '201 且 precision=unknown', '%s %s' % (st, e2.get('timePrecision')))

    st, e3 = call('POST', '/api/v1/events',
                  {'title': '测试事件-开放区间', 'startYearAstro': -770, 'timePrecision': 'range'})
    eid3 = e3['eventId']
    check('E03', '开放区间（只知起点，结束为显式 null）',
          st == 201 and e3['startYearAstro'] == -770 and e3['endYearAstro'] is None
          and 'endYearAstro' in e3,
          '201 且 endYearAstro 字段存在且为 null',
          '%s start=%s end=%r has_key=%s' % (st, e3.get('startYearAstro'), e3.get('endYearAstro'),
                                             'endYearAstro' in e3))

    # ======================================================== 场景四：关联
    print('\n--- 场景四：三类关联 ---')
    st, l1 = call('POST', '/api/v1/events/%s/persons' % eid, {'personId': pid2, 'role': 'participant'})
    st2, l2 = call('POST', '/api/v1/events/%s/persons' % eid, {'personId': pid3, 'role': 'witness'})
    check('L01', '一个事件关联多个人物', st == 201 and st2 == 201, '201/201', '%s/%s' % (st, st2))

    st, _ = call('POST', '/api/v1/events/%s/persons' % eid, {'personId': pid2, 'role': 'participant'})
    check('L02', '同事件同人物同角色重复 → 409', st == 409, '409', '%s' % st)

    st, _ = call('PUT', '/api/v1/events/%s/persons/%s' % (eid, l1['linkId']),
                 {'role': 'host', 'validFromYearAstro': -500, 'validToYearAstro': -495})
    st2, d = call('GET', '/api/v1/events/%s' % eid)
    row = next((x for x in d['persons'] if x['linkId'] == l1['linkId']), {})
    check('L03', '编辑关联角色与关系有效期', st == 200 and row.get('role') == 'host'
          and row.get('validFromYearAstro') == -500, '200 且 role=host / -500',
          '%s %s %s' % (st, row.get('role'), row.get('validFromYearAstro')))

    st, _ = call('POST', '/api/v1/events/%s/places' % eid, {'placeId': pid, 'locationRole': 'destination'})
    st2, _ = call('POST', '/api/v1/events/%s/places' % eid, {'placeId': 900002, 'locationRole': 'origin'})
    st3, d = call('GET', '/api/v1/events/%s' % eid)
    check('L04', '一个事件关联多个地点', st == 201 and st2 == 201 and len(d['places']) == 2,
          '201/201 且 places=2', '%s/%s places=%s' % (st, st2, len(d.get('places') or [])))

    st, _ = call('POST', '/api/v1/events/%s/places' % eid, {'placeId': pid, 'locationRole': 'destination'})
    check('L05', '同事件同地点同角色重复 → 409', st == 409, '409', '%s' % st)

    st, pp = call('POST', '/api/v1/persons/%s/places' % pid2,
                  {'placeId': 900003, 'relationType': 'residence',
                   'startYearAstro': -540, 'endYearAstro': -530, 'timePrecision': 'approximate',
                   'sequenceOrder': 1})
    st2, pp2 = call('POST', '/api/v1/persons/%s/places' % pid2,
                    {'placeId': 900002, 'relationType': 'activity',
                     'startYearAstro': -520, 'endYearAstro': -510, 'timePrecision': 'range',
                     'sequenceOrder': 2})
    st3, d = call('GET', '/api/v1/persons/%s' % pid2)
    check('L06', '人物关联多个活动地点（含时间范围与顺序）',
          st == 201 and st2 == 201 and len(d['places']) == 2
          and d['places'][0]['sequenceOrder'] == 1,
          '201/201 且 places=2 有序', '%s/%s places=%s' % (st, st2, len(d.get('places') or [])))

    st, _ = call('PUT', '/api/v1/persons/%s/places/%s' % (pid2, pp['linkId']),
                 {'placeId': 900003, 'relationType': 'birthplace',
                  'startYearAstro': -550, 'endYearAstro': -550, 'timePrecision': 'exact',
                  'sequenceOrder': 1})
    check('L07', '编辑人物-地点关系类型与区间', st == 200, '200', '%s' % st)

    st, _ = call('DELETE', '/api/v1/persons/%s/places/%s' % (pid2, pp2['linkId']))
    st2, d = call('GET', '/api/v1/persons/%s' % pid2)
    check('L08', '解除人物-地点关联后数量下降', st == 200 and len(d['places']) == 1,
          '200 且 places=1', '%s places=%s' % (st, len(d.get('places') or [])))

    # ======================================================== 场景五：时间
    print('\n--- 场景五：时间规则 ---')
    st, b0 = call('POST', '/api/v1/persons',
                  {'canonicalName': '测试-BCE1', 'birthYearAstro': 0, 'birthPrecision': 'exact'})
    st2, b1 = call('POST', '/api/v1/persons',
                   {'canonicalName': '测试-CE1', 'birthYearAstro': 1, 'birthPrecision': 'exact'})
    check('T01', '公元前 1 年 = 内部 0；公元 1 年 = 1（相邻不重叠）',
          st == 201 and b0['birthYearAstro'] == 0 and b1['birthYearAstro'] == 1,
          '0 / 1', '%s / %s' % (b0.get('birthYearAstro'), b1.get('birthYearAstro')))

    st, _ = call('POST', '/api/v1/events',
                 {'title': '倒挂', 'startYearAstro': -221, 'endYearAstro': -770, 'timePrecision': 'range'})
    check('T02', 'BCE 区间倒挂 → 400', st == 400, '400', '%s' % st)

    st, _ = call('POST', '/api/v1/events', {'title': '未知带年', 'startYearAstro': 5, 'timePrecision': 'unknown'})
    check('T03', 'precision=unknown 却带年份 → 400', st == 400, '400', '%s' % st)

    st, _ = call('POST', '/api/v1/persons',
                 {'canonicalName': '精度不符', 'birthYearAstro': 100, 'birthPrecision': 'unknown'})
    check('T04', '有年份但精度 unknown → 400', st == 400, '400', '%s' % st)

    st, _ = call('POST', '/api/v1/persons',
                 {'canonicalName': '生卒倒挂', 'birthYearAstro': 100, 'birthPrecision': 'exact',
                  'deathYearAstro': 50, 'deathPrecision': 'exact'})
    check('T05', '卒年早于生年 → 400', st == 400, '400', '%s' % st)

    st, _ = call('POST', '/api/v1/persons/%s/places' % pid2,
                 {'placeId': 900003, 'relationType': 'activity',
                  'startYearAstro': 100, 'timePrecision': 'unknown'})
    check('T06', '关联关系 timePrecision=unknown 却带年份 → 400', st == 400, '400', '%s' % st)

    # ======================================================== 场景六：完整性
    print('\n--- 场景六：数据完整性 ---')
    # 6.1 删除被引用地点 → RESTRICT
    st, body = call('DELETE', '/api/v1/places/%s' % pid)
    check('D01', '删除被事件引用（且自带位置行）的地点 → 拒绝', st in (409, 400),
          '409/400', '%s %s' % (st, str(body.get('message') if isinstance(body, dict) else body)[:60]))

    # 6.1b 专门证明 M2 外键自身的 RESTRICT：地点无位置行、只被事件引用
    st, pn = call('POST', '/api/v1/places', {'canonicalName': '测试-仅被事件引用的地点'})
    pnid = pn.get('placeId') if isinstance(pn, dict) else None
    call('POST', '/api/v1/events/%s/places' % eid, {'placeId': pnid, 'locationRole': 'refonly'})
    st2, body2 = call('DELETE', '/api/v1/places/%s' % pnid)
    cons = (body2 or {}).get('constraint') if isinstance(body2, dict) else None
    still = sql("select count(*) from historical_place where place_id=%s" % pnid)
    check('D01b', '删除仅被 event_place 引用（无位置行）的地点 → 被 M2 外键拒绝',
          st2 in (409, 400) and cons == 'fk_event_place_place' and still == '1',
          '409/400 + fk_event_place_place + 地点仍在',
          '%s %s place_left=%s' % (st2, cons, still))

    # 6.2 删除事件 → 关联清除，人物与地点保留
    st, _ = call('DELETE', '/api/v1/events/%s' % eid)
    st2, _ = call('GET', '/api/v1/events/%s' % eid)
    st3, pd = call('GET', '/api/v1/persons/%s' % pid2)
    st4, pl = call('GET', '/api/v1/places/%s' % pid)
    check('D02', '删除事件：事件 404，人物与地点主体保留',
          st == 200 and st2 == 404 and st3 == 200 and st4 == 200,
          '200 / 404 / 200 / 200', '%s/%s/%s/%s' % (st, st2, st3, st4))

    n_ep = sql("select count(*) from event_person where event_id = %s" % eid)
    n_epl = sql("select count(*) from event_place where event_id = %s" % eid)
    check('D03', '删除事件后其 event_person / event_place 级联清空',
          n_ep == '0' and n_epl == '0', '0 / 0', '%s / %s' % (n_ep, n_epl))

    # 6.3 删除人物 → 名称与关联清除，事件与地点保留
    st, _ = call('DELETE', '/api/v1/persons/%s' % pid2)
    st2, _ = call('GET', '/api/v1/persons/%s' % pid2)
    check('D04', '删除人物：人物 404，其名称与关联清除',
          st == 200 and st2 == 404
          and sql("select count(*) from person_name where person_id=%s" % pid2) == '0'
          and sql("select count(*) from person_place where person_id=%s" % pid2) == '0',
          '200 / 404 / 名称0 / 关联0', '%s/%s' % (st, st2))

    # 6.4 删除未被引用且无位置的地点 → 成功
    st, _ = call('POST', '/api/v1/places', {'canonicalName': '测试-可删地点'})
    pdel = sql("select max(place_id) from historical_place where canonical_name='测试-可删地点'")
    st2, _ = call('DELETE', '/api/v1/places/%s' % pdel)
    check('D05', '删除无引用且无位置的地点 → 200', st == 201 and st2 == 200, '201/200', '%s/%s' % (st, st2))

    # 6.5 孤儿扫描
    orphans = sql("""
        select
         (select count(*) from person_name x left join person p on p.person_id=x.person_id where p.person_id is null)
        +(select count(*) from event_place x left join event e on e.event_id=x.event_id where e.event_id is null)
        +(select count(*) from event_place x left join historical_place p on p.place_id=x.place_id where p.place_id is null)
        +(select count(*) from event_person x left join event e on e.event_id=x.event_id where e.event_id is null)
        +(select count(*) from event_person x left join person p on p.person_id=x.person_id where p.person_id is null)
        +(select count(*) from person_place x left join person p on p.person_id=x.person_id where p.person_id is null)
        +(select count(*) from person_place x left join historical_place p on p.place_id=x.place_id where p.place_id is null)
    """)
    check('D06', '七条外键全库孤儿扫描', orphans == '0', '0', orphans)

    print('\n== 汇总 ==')
    ok = sum(1 for x in R if x[2])
    print('PASS %d / %d' % (ok, len(R)))
    fails = [x for x in R if not x[2]]
    for cid, desc, _ in fails:
        print('  失败 %s %s' % (cid, desc))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
