#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M2-2A 后端 API 实测脚本。

用法：
  python ops/m2/api_test.py [baseUrl]        默认 http://127.0.0.1:8089

仅使用标准库（urllib），不引入新依赖。
所有断言都是"真的发 HTTP 请求并检查响应"，不做静态检查。
针对 **canvas_history_m2check** 测试库运行；不连正式库。
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8089').rstrip('/')
RESULTS = []


def call(method, path, body=None):
    """返回 (status, json_or_text)。"""
    url = BASE + path
    data = None
    headers = {'Accept': 'application/json'}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
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
    print('%s %-6s %-46s | 期望 %s | 实际 %s'
          % ('PASS' if ok else 'FAIL', cid, desc, expect, str(actual)[:110]))
    return ok


def main():
    print('== M2-2A API 实测  目标 %s ==' % BASE)
    st, health = call('GET', '/api/v1/meta/health')
    check('S00', '目标实例健康且指向测试库', st == 200 and health.get('database') == 'canvas_history_m2check',
          '200 + database=canvas_history_m2check', '%s %s' % (st, health))

    # ============================================================ A. 人物 CRUD
    print('\n--- A. 人物 CRUD ---')
    st, p = call('POST', '/api/v1/persons', {
        'canonicalName': '孔丘', 'canonicalNameLang': 'zh',
        'description': '春秋思想家',
        'birthYearAstro': -550, 'birthPrecision': 'approximate',
        'birthOriginalText': '鲁襄公二十二年',
        'deathYearAstro': -478, 'deathPrecision': 'approximate',
        'recordStatus': 'staging'})
    pid = p.get('personId') if isinstance(p, dict) else None
    check('A01', '创建人物 → 201 且回读字段一致',
          st == 201 and pid and p['canonicalName'] == '孔丘'
          and p['birthYearAstro'] == -550 and p['deathYearAstro'] == -478,
          '201 且 birth=-550 death=-478',
          '%s id=%s birth=%s death=%s' % (st, pid, p.get('birthYearAstro') if isinstance(p, dict) else '?',
                                          p.get('deathYearAstro') if isinstance(p, dict) else '?'))

    st, body = call('GET', '/api/v1/persons?keyword=%E5%AD%94&size=10')
    hit = next((x for x in (body or {}).get('items', []) if x['personId'] == pid), None)
    check('A02', '按规范名搜索命中', st == 200 and hit is not None,
          '200 且含该人物', '%s total=%s' % (st, (body or {}).get('total')))

    st, body = call('PUT', '/api/v1/persons/%s' % pid, {
        'canonicalName': '孔丘（仲尼）', 'canonicalNameLang': 'zh',
        'description': '春秋思想家、教育家',
        'birthYearAstro': -550, 'birthPrecision': 'approximate',
        'deathYearAstro': -478, 'deathPrecision': 'approximate',
        'notes': '更新测试'})
    check('A03', '编辑人物（整体替换）', st == 200 and body['canonicalName'] == '孔丘（仲尼）'
          and body['notes'] == '更新测试', '200 且名称/备注已更新',
          '%s name=%s' % (st, body.get('canonicalName') if isinstance(body, dict) else '?'))

    st, body = call('GET', '/api/v1/persons/%s' % pid)
    check('A04', '详情返回三组子集合字段', st == 200 and isinstance(body.get('names'), list)
          and isinstance(body.get('events'), list) and isinstance(body.get('places'), list),
          '200 且 names/events/places 均为数组',
          '%s names=%s events=%s places=%s' % (st, len(body.get('names') or []),
                                               len(body.get('events') or []),
                                               len(body.get('places') or [])))

    st, body = call('GET', '/api/v1/persons?page=1&size=2')
    check('A05', '列表分页字段正确', st == 200 and body['size'] == 2 and body['page'] == 1
          and len(body['items']) <= 2, '200 且 size=2 返回 ≤2 条',
          '%s page=%s size=%s items=%s total=%s'
          % (st, body.get('page'), body.get('size'), len(body.get('items') or []), body.get('total')))

    # ============================================================ B. 名称 CRUD
    print('\n--- B. 人物名称 CRUD ---')
    st, n1 = call('POST', '/api/v1/persons/%s/names' % pid,
                  {'nameText': '仲尼', 'nameLang': 'zh', 'nameType': 'courtesy'})
    nid = n1.get('personNameId') if isinstance(n1, dict) else None
    check('B01', '新增别名（字）→ 201', st == 201 and nid, '201 且返回 id', '%s id=%s' % (st, nid))

    st, dup = call('POST', '/api/v1/persons/%s/names' % pid,
                   {'nameText': '仲尼', 'nameLang': 'zh', 'nameType': 'courtesy'})
    check('B02', '同类型同文本同语言重复 → 409', st == 409,
          '409 且提示唯一约束', '%s %s' % (st, str(dup.get('constraint') if isinstance(dup, dict) else dup)[:40]))

    st, bad = call('POST', '/api/v1/persons/%s/names' % pid,
                   {'nameText': 'x', 'nameType': 'nickname'})
    check('B03', '非法 nameType → 400', st == 400, '400', '%s %s' % (st, str(bad.get('message') if isinstance(bad, dict) else bad)[:60]))

    st, body = call('PUT', '/api/v1/persons/%s/names/%s' % (pid, nid),
                    {'nameText': '仲尼（修订）', 'nameLang': 'zh', 'nameType': 'courtesy'})
    check('B04', '编辑名称', st == 200 and body['nameText'] == '仲尼（修订）', '200 且文本已改',
          '%s %s' % (st, body.get('nameText') if isinstance(body, dict) else '?'))

    st, bad = call('POST', '/api/v1/persons/%s/names' % pid,
                   {'nameText': 'Kong Qiu', 'nameType': 'primary', 'transliterationScheme': 'pinyin'})
    check('B05', '非 transliteration 类型带转写方案 → 400', st == 400, '400',
          '%s %s' % (st, str(bad.get('message') if isinstance(bad, dict) else bad)[:60]))

    st, n2 = call('POST', '/api/v1/persons/%s/names' % pid,
                  {'nameText': 'Kong Qiu', 'nameLang': 'en', 'nameType': 'transliteration',
                   'transliterationScheme': 'pinyin'})
    check('B06', '转写名称（带 pinyin）→ 201', st == 201 and n2.get('transliterationScheme') == 'pinyin',
          '201 且 scheme=pinyin', '%s %s' % (st, n2.get('transliterationScheme') if isinstance(n2, dict) else '?'))

    st, body = call('GET', '/api/v1/persons?keyword=%s&size=5' % urllib.parse.quote('Kong'))
    check('B07', '按别名搜索命中（走 person_name）', st == 200 and any(x['personId'] == pid for x in body['items']),
          '200 且命中该人物', '%s total=%s' % (st, body.get('total')))

    st, body = call('DELETE', '/api/v1/persons/%s/names/%s' % (pid, nid))
    st2, body2 = call('GET', '/api/v1/persons/%s/names' % pid)
    names_now = [x['nameText'] for x in body2] if isinstance(body2, list) else body2
    check('B08', '删除名称后列表不再包含',
          st == 200 and isinstance(body2, list) and all(x['personNameId'] != nid for x in body2),
          '200 且列表已移除', 'del=%s 剩余=%s' % (st, names_now))

    # ============================================================ C. 事件 CRUD
    print('\n--- C. 事件 CRUD ---')
    st, ev = call('POST', '/api/v1/events', {
        'title': '孔子适周问礼', 'summary': '赴洛邑问礼于老子',
        'startYearAstro': -517, 'endYearAstro': -517, 'timePrecision': 'exact',
        'timeOriginalText': '约鲁昭公二十五年', 'eventType': 'cultural'})
    eid = ev.get('eventId') if isinstance(ev, dict) else None
    check('C01', '创建事件 → 201 且时间为天文纪年整数',
          st == 201 and eid and ev['startYearAstro'] == -517 and ev['endYearAstro'] == -517,
          '201 且 start=end=-517', '%s id=%s' % (st, eid))

    st, body = call('GET', '/api/v1/events?keyword=%s' % urllib.parse.quote('问礼'))
    check('C02', '按标题搜索命中', st == 200 and any(x['eventId'] == eid for x in body['items']),
          '200 且命中', '%s total=%s' % (st, body.get('total')))

    st, body = call('PUT', '/api/v1/events/%s' % eid, {
        'title': '孔子适周问礼', 'summary': '赴洛邑问礼于老子',
        'startYearAstro': -517, 'endYearAstro': None, 'timePrecision': 'range',
        'eventType': 'cultural'})
    check('C03', '编辑为开放区间（只知起点）', st == 200 and body['endYearAstro'] is None
          and body['timePrecision'] == 'range', '200 且 end=null precision=range',
          '%s end=%s tp=%s' % (st, body.get('endYearAstro') if isinstance(body, dict) else '?',
                               body.get('timePrecision') if isinstance(body, dict) else '?'))

    st, bad = call('POST', '/api/v1/events', {'title': '无精度事件', 'startYearAstro': 100})
    check('C04', '有年份缺 timePrecision → 400', st == 400, '400',
          '%s %s' % (st, str(bad.get('message') if isinstance(bad, dict) else bad)[:60]))

    st, bad = call('POST', '/api/v1/events',
                   {'title': '倒挂事件', 'startYearAstro': -221, 'endYearAstro': -770, 'timePrecision': 'range'})
    check('C05', '公元前区间倒挂 → 400', st == 400, '400',
          '%s %s' % (st, str(bad.get('message') if isinstance(bad, dict) else bad)[:70]))

    st, bad = call('POST', '/api/v1/events', {'title': '精度未知但带年份', 'startYearAstro': 5,
                                              'timePrecision': 'unknown'})
    check('C06', 'precision=unknown 却带年份 → 400', st == 400, '400',
          '%s %s' % (st, str(bad.get('message') if isinstance(bad, dict) else bad)[:60]))

    # ============================================================ D. 三类关联
    print('\n--- D. 关联关系（增删改查） ---')
    st, link = call('POST', '/api/v1/events/%s/persons' % eid,
                    {'personId': pid, 'role': 'participant', 'note': '问礼者'})
    lk_ep = link.get('linkId') if isinstance(link, dict) else None
    check('D01', '事件挂人物（带角色）→ 201', st == 201 and lk_ep and link['role'] == 'participant',
          '201 且 role=participant', '%s link=%s' % (st, lk_ep))

    st, dup = call('POST', '/api/v1/events/%s/persons' % eid, {'personId': pid, 'role': 'participant'})
    check('D02', '同事件同人物同角色重复 → 409', st == 409, '409',
          '%s %s' % (st, str(dup.get('constraint') if isinstance(dup, dict) else dup)[:40]))

    st, body = call('PUT', '/api/v1/events/%s/persons/%s' % (eid, lk_ep),
                    {'role': 'questioner', 'validFromYearAstro': -517, 'validToYearAstro': -517})
    check('D03', '修改人物角色与关系有效期', st == 200 and body['role'] == 'questioner'
          and body['validFromYearAstro'] == -517, '200 且 role=questioner',
          '%s role=%s' % (st, body.get('role') if isinstance(body, dict) else '?'))

    st, pl = call('POST', '/api/v1/events/%s/places' % eid,
                  {'placeId': 900001, 'locationRole': 'destination', 'note': '洛邑'})
    lk_epl = pl.get('linkId') if isinstance(pl, dict) else None
    check('D04', '事件挂地点（带地点角色）→ 201',
          st == 201 and lk_epl and pl['placeName'] == '洛邑' and pl['locationRole'] == 'destination',
          '201 且 placeName=洛邑 role=destination',
          '%s %s/%s' % (st, pl.get('placeName') if isinstance(pl, dict) else '?',
                        pl.get('locationRole') if isinstance(pl, dict) else '?'))

    st, dup = call('POST', '/api/v1/events/%s/places' % eid,
                   {'placeId': 900001, 'locationRole': 'destination'})
    check('D05', '同事件同地点同角色重复 → 409', st == 409, '409',
          '%s %s' % (st, str(dup.get('constraint') if isinstance(dup, dict) else dup)[:40]))

    st, pp = call('POST', '/api/v1/persons/%s/places' % pid,
                  {'placeId': 900002, 'relationType': 'residence',
                   'startYearAstro': -551, 'endYearAstro': -500, 'timePrecision': 'approximate',
                   'sequenceOrder': 1, 'note': '生于曲阜'})
    lk_pp = pp.get('linkId') if isinstance(pp, dict) else None
    check('D06', '人物挂活动地点（含时间范围与顺序）→ 201',
          st == 201 and lk_pp and pp['relationType'] == 'residence'
          and pp['startYearAstro'] == -551 and pp['sequenceOrder'] == 1,
          '201 且 relation=residence start=-551 seq=1',
          '%s %s/%s/%s' % (st, pp.get('relationType') if isinstance(pp, dict) else '?',
                           pp.get('startYearAstro') if isinstance(pp, dict) else '?',
                           pp.get('sequenceOrder') if isinstance(pp, dict) else '?'))

    st, body = call('PUT', '/api/v1/persons/%s/places/%s' % (pid, lk_pp),
                    {'placeId': 900002, 'relationType': 'birthplace',
                     'startYearAstro': -551, 'endYearAstro': -551, 'timePrecision': 'approximate',
                     'sequenceOrder': 1})
    check('D07', '修改人物地点关系类型与区间', st == 200 and body['relationType'] == 'birthplace'
          and body['endYearAstro'] == -551, '200 且 relation=birthplace end=-551',
          '%s %s' % (st, body.get('relationType') if isinstance(body, dict) else '?'))

    st, det = call('GET', '/api/v1/persons/%s' % pid)
    ok = (st == 200 and any(e['eventId'] == eid for e in det['events'])
          and any(x['placeId'] == 900002 for x in det['places']))
    check('D08', '人物详情内联返回关联事件与地点', ok, '详情 events 含该事件、places 含该地点',
          '%s events=%s places=%s' % (st, len(det.get('events') or []), len(det.get('places') or [])))

    st, det2 = call('GET', '/api/v1/events/%s' % eid)
    ok2 = (st == 200 and any(x['personId'] == pid for x in det2['persons'])
           and any(x['placeId'] == 900001 for x in det2['places']))
    check('D09', '事件详情内联返回关联人物与地点', ok2, '详情 persons/places 均含关联',
          '%s persons=%s places=%s' % (st, len(det2.get('persons') or []), len(det2.get('places') or [])))

    st, many = call('POST', '/api/v1/events/%s/places' % eid, {'placeId': 900003, 'locationRole': 'origin'})
    st2, det3 = call('GET', '/api/v1/events/%s' % eid)
    check('D10', '一个事件可关联多个地点', st == 201 and len(det3['places']) >= 2,
          '201 且 places ≥ 2', '%s places=%s' % (st, len(det3.get('places') or [])))

    st, b1 = call('DELETE', '/api/v1/persons/%s/places/%s' % (pid, lk_pp))
    st2, b2 = call('DELETE', '/api/v1/events/%s/places/%s' % (eid, many.get('linkId')))
    check('D11', '解除两类关联 → 200', st == 200 and st2 == 200, '200/200', '%s/%s' % (st, st2))

    # ============================================================ E. BCE/CE 读写
    print('\n--- E. BCE/CE 时间读写 ---')
    st, per = call('POST', '/api/v1/persons', {
        'canonicalName': '测试-跨前后人物',
        'birthYearAstro': -99, 'birthPrecision': 'exact',
        'deathYearAstro': 50, 'deathPrecision': 'exact'})
    check('E01', '跨公元前后人物：-99 与 50 原样存取',
          st == 201 and per['birthYearAstro'] == -99 and per['deathYearAstro'] == 50,
          '201 且 -99 / 50', '%s %s/%s' % (st, per.get('birthYearAstro') if isinstance(per, dict) else '?',
                                           per.get('deathYearAstro') if isinstance(per, dict) else '?'))

    st, ev2 = call('POST', '/api/v1/events', {
        'title': '测试-跨前后事件', 'startYearAstro': -99, 'endYearAstro': 100,
        'timePrecision': 'range'})
    check('E02', '跨公元前后事件区间 -99~100 原样存取',
          st == 201 and ev2['startYearAstro'] == -99 and ev2['endYearAstro'] == 100,
          '201 且 -99~100', '%s %s~%s' % (st, ev2.get('startYearAstro') if isinstance(ev2, dict) else '?',
                                          ev2.get('endYearAstro') if isinstance(ev2, dict) else '?'))

    st, per0 = call('POST', '/api/v1/persons', {'canonicalName': '测试-公元前1年', 'birthYearAstro': 0,
                                                'birthPrecision': 'exact'})
    check('E03', '公元前 1 年 = 内部 0 可原样存取', st == 201 and per0['birthYearAstro'] == 0,
          '201 且 birth=0', '%s %s' % (st, per0.get('birthYearAstro') if isinstance(per0, dict) else '?'))

    st, bad = call('POST', '/api/v1/persons', {'canonicalName': '测试-精度不符', 'birthYearAstro': 100,
                                               'birthPrecision': 'unknown'})
    check('E04', '有年份但 precision=unknown → 400', st == 400, '400',
          '%s %s' % (st, str(bad.get('message') if isinstance(bad, dict) else bad)[:60]))

    # ============================================================ F. 错误处理
    print('\n--- F. 必填 / 枚举 / 404 ---')
    st, bad = call('POST', '/api/v1/persons', {'canonicalName': '   '})
    check('F01', '空名称 → 400', st == 400, '400', '%s' % st)

    st, bad = call('POST', '/api/v1/persons', {'canonicalName': 'x', 'recordStatus': 'draft'})
    check('F02', '非法 recordStatus → 400', st == 400, '400',
          '%s %s' % (st, str(bad.get('message') if isinstance(bad, dict) else bad)[:60]))

    st, _ = call('GET', '/api/v1/persons/99999999')
    st2, _ = call('GET', '/api/v1/events/99999999')
    check('F03', '不存在的 id → 404', st == 404 and st2 == 404, '404/404', '%s/%s' % (st, st2))

    st, bad = call('POST', '/api/v1/persons/%s/events' % pid, {'eventId': 99999999, 'role': 'x'})
    check('F04', '关联不存在的事件 → 404', st == 404, '404', '%s' % st)

    st, bad = call('POST', '/api/v1/persons/%s/places' % pid,
                   {'placeId': 900002, 'relationType': 'residence', 'startYearAstro': 100,
                    'timePrecision': 'unknown'})
    check('F05', '人物地点 unknown 却带年份 → 400', st == 400, '400', '%s' % st)

    # ============================================================ G. 删除级联
    print('\n--- G. 删除与级联 ---')
    st, g_ev = call('POST', '/api/v1/events', {'title': '测试-级联删除事件'})
    gid = g_ev['eventId']
    call('POST', '/api/v1/events/%s/persons' % gid, {'personId': pid, 'role': 'tester'})
    call('POST', '/api/v1/events/%s/places' % gid, {'placeId': 900001, 'locationRole': 'tmp'})
    st, _ = call('DELETE', '/api/v1/events/%s' % gid)
    st2, det4 = call('GET', '/api/v1/events/%s' % gid)
    st3, det5 = call('GET', '/api/v1/persons/%s' % pid)
    ok = (st == 200 and st2 == 404 and all(e['eventId'] != gid for e in det5['events'])
          and det5['places'] is not None)
    check('G01', '删除事件：关联清除，人物与地点不受影响', ok,
          '200 + 事件 404 + 人物仍在且不含该事件',
          'del=%s get=%s person_events=%s' % (st, st2, len(det5.get('events') or [])))

    st, g_p = call('POST', '/api/v1/persons', {'canonicalName': '测试-级联删除人物'})
    gpid = g_p['personId']
    call('POST', '/api/v1/persons/%s/names' % gpid, {'nameText': '别名A', 'nameType': 'alternate'})
    call('POST', '/api/v1/persons/%s/places' % gpid,
         {'placeId': 900003, 'relationType': 'activity'})
    st, _ = call('DELETE', '/api/v1/persons/%s' % gpid)
    st2, _ = call('GET', '/api/v1/persons/%s' % gpid)
    st3, det6 = call('GET', '/api/v1/persons/%s' % pid)
    check('G02', '删除人物：名称与关联级联清除', st == 200 and st2 == 404,
          '200 + 人物 404', '%s/%s' % (st, st2))

    # M2 收尾新增了地点删除接口；被引用时库层 RESTRICT 会拒绝（409），这正是期望行为
    # M3 前置收尾后，删除入口多了一层"导入数据集地点不允许在管理界面删除"的保护，
    # 900001 属于测试库自建数据集 m2check_ds，因此在这里由应用层先拒（409 + 原因）。
    # 数据库 RESTRICT 本身的证明见 api_m2_full_test.py 的 D01 / D01b（人工录入地点 + event_place 引用）。
    st, bad = call('DELETE', '/api/v1/places/900001')
    cons = (bad or {}).get('constraint') if isinstance(bad, dict) else None
    msg = (bad or {}).get('message', '') if isinstance(bad, dict) else ''
    check('G03', '删除被引用地点 → 被拒绝且给出可读原因',
          st in (409, 400) and (cons is not None or '导入数据集' in msg),
          '409/400 + constraint 或导入数据集说明', '%s %s' % (st, cons or msg[:46]))

    print('\n== 汇总 ==')
    passed = sum(1 for r in RESULTS if r[2])
    print('PASS %d / %d' % (passed, len(RESULTS)))
    fails = [r for r in RESULTS if not r[2]]
    if fails:
        print('失败项：')
        for cid, desc, _, exp, act in fails:
            print('  %s %s | 期望 %s | 实际 %s' % (cid, desc, exp, act))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
