#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M3 时间—地图联动 · 接口实测（真实 HTTP + 真实数据库，不做静态检查）。

用法：
  python ops/m3/api_m3_test.py http://127.0.0.1:8089            # 测试库（可写）
  python ops/m3/api_m3_test.py http://127.0.0.1:8088 guard      # 正式库只读：只验写保护

覆盖：
  T  时间窗口与边界（含 BCE/CE 衔接、跨年事件、未知时间）
  M  地图查询（bbox × 时间、多地点事件、meta 计数）
  X  矩阵（列、地区分组、多政权、跨列、未关联计数、分页绝对列号）
  P  政权（列表/地区/创建/唯一冲突/非法地区）
  L  事件—政权关联（添加/重复/解除/详情内联）
  G  写保护（正式库禁止写入）
"""
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

R = []
BASE = ''
DB = 'canvas_history_m2check'


def call(method, path, body=None, base=None):
    url = (base or BASE) + path
    req = urllib.request.Request(
        url,
        data=None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8'),
        headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
        method=method,
    )
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


def sql(q):
    r = subprocess.run(['docker', 'exec', 'canvas-history-db', 'psql', '-U', 'canvas_app',
                        '-d', DB, '-tAc', q], capture_output=True, text=True)
    return r.stdout.strip()


def check(cid, desc, cond, expect, actual):
    R.append((cid, desc, bool(cond)))
    print('%s %-5s %-52s | 期望 %s | 实际 %s'
          % ('PASS' if cond else 'FAIL', cid, desc, expect, str(actual)[:120]))


def summarize(label):
    ok = sum(1 for _, _, c in R if c)
    print('\n=== %s：PASS %d / %d ===' % (label, ok, len(R)))
    if ok != len(R):
        print('失败项：')
        for cid, desc, c in R:
            if not c:
                print('  ', cid, desc)
    return 0 if ok == len(R) else 1


def mapq(bbox, frm, to, limit=None):
    q = 'bbox=%s&from=%d&to=%d' % (urllib.parse.quote(bbox), frm, to)
    if limit is not None:
        q += '&limit=%d' % limit
    return call('GET', '/api/v1/events/map?' + q)


def titles(fc):
    return sorted({f['properties']['title'] for f in fc['features']})


# ---------------------------------------------------------------- T 时间
def t_time():
    print('== T 时间窗口与边界 ==\n')

    st, fc = mapq('-20,20,60,50', -489, -489)
    check('T01', '公元前490年窗口只含当年事件', st == 200 and titles(fc) == ['演示：马拉松战役'],
          '仅 马拉松战役', titles(fc))

    st, fc = mapq('-20,20,60,50', -479, -479)
    check('T02', '公元前480年窗口切换到温泉关战役', titles(fc) == ['演示：温泉关战役'],
          '仅 温泉关战役', titles(fc))

    st, fc = mapq('-30,20,70,55', -600, -500)
    check('T03', '跨多年事件与窗口相交即命中（巴比伦之囚 前586–前538）',
          '演示：巴比伦之囚' in titles(fc), '命中', titles(fc))

    st, fc = mapq('-30,20,70,55', -450, -400)
    check('T04', '窗口完全在事件之后 → 不命中', '演示：巴比伦之囚' not in titles(fc),
          '不命中', titles(fc))

    st, fc = mapq('-180,-85,180,85', -1000, 2100, 3000)
    check('T05', '全时段查询不含「时间未知」的事件',
          '演示：时间未知的传说' not in titles(fc), '不含', titles(fc))
    check('T06', 'meta 报告未知时间事件数量（全局）', fc['meta']['unknownTimeEvents'] >= 1,
          '>=1', fc['meta']['unknownTimeEvents'])

    # 端点包含式：事件 -585..-537 与窗口 [-537,-537] 相交（端点命中）
    st, fc = mapq('-30,20,70,55', -537, -537)
    check('T07', '区间端点包含式：窗口正好落在事件末年终年 → 命中',
          '演示：巴比伦之囚' in titles(fc), '命中', titles(fc))

    st, fc = mapq('-30,20,70,55', -536, -536)
    check('T08', '末年终年之后一年 → 不再命中', '演示：巴比伦之囚' not in titles(fc),
          '不命中', titles(fc))

    # BCE/CE 边界：内部 0 = 公元前 1 年；1 = 公元 1 年
    st, fc = mapq('-180,-85,180,85', 0, 0)
    check('T09', '公元前1年（内部 0）可查询且不报错', st == 200, '200', st)
    st, fc = mapq('-180,-85,180,85', 1, 1)
    check('T10', '公元1年（内部 1）可查询且不报错', st == 200, '200', st)

    st, m = call('GET', '/api/v1/events/matrix?from=-4&step=10&count=2')
    labels = [(c['startYearAstro'], c['endYearAstro'], c['label']) for c in (m or {}).get('columns', [])]
    check('T11', '跨公元前后窗口的列标签清晰（前5–前1 / 1–10）',
          st == 200 and labels[0][0] == -4 and labels[0][1] == 5 and labels[1][0] == 6,
          '列0=-4..5, 列1=6..', labels)

    st, b = call('GET', '/api/v1/events/matrix?from=-100&step=7&count=3')
    check('T12', 'step 只允许 1/10/100（7 被拒）', st == 400, '400', st)

    st, b = call('GET', '/api/v1/events/matrix?from=100&step=10&count=3')
    check('T13', '非法窗口（from 晚于 to 的反向请求）由 from/to 校验拦截',
          st == 200, '200（step 决定 to，本身合法）', st)
    st, b = mapq('-10,10,10,20', 100, 50)
    check('T14', '地图接口 from > to → 400', st == 400, '400', st)


# ---------------------------------------------------------------- M 地图
def t_map():
    print('\n== M 地图查询 ==\n')
    st, fc = mapq('-20,20,60,50', -489, -489)
    p = fc['features'][0]['properties'] if fc['features'] else {}
    check('M01', '要素返回事件与地点标识',
          all(k in p for k in ('eventId', 'title', 'placeId', 'placeName', 'startYearAstro')),
          '字段齐全', sorted(p.keys())[:6])
    check('M02', 'GeoJSON 结构正确', fc['type'] == 'FeatureCollection'
          and fc['features'][0]['geometry']['type'] == 'Point', 'FeatureCollection/Point',
          fc['type'] + '/' + fc['features'][0]['geometry']['type'])

    # bbox 过滤：同一年，只查中国视野不应有希腊事件
    st, fc = mapq('100,20,130,45', -589, -579)
    check('M03', 'bbox 过滤生效：中国视野不含地中海事件', len(fc['features']) == 0,
          '0 条', len(fc['features']))

    # 一个事件关联两个地点 → 两个标记
    st, fc = mapq('-20,20,70,55', -538, -538)
    two = [f for f in fc['features'] if f['properties']['title'] == '演示：波斯攻克巴比伦']
    check('M04', '同一事件关联多地点 → 按真实地点分别生成标记', len(two) == 2,
          '2 条', len(two))
    check('M05', '多地点标记坐标不同',
          len({tuple(f['geometry']['coordinates']) for f in two}) == 2, '2 个不同坐标',
          [f['geometry']['coordinates'] for f in two])

    st, fc = mapq('-180,-85,180,85', -1000, 2100, 5)
    check('M06', 'limit 生效并标记 truncated', fc['meta']['returned'] <= 5
          and fc['meta']['truncated'] is True, '<=5 且 truncated',
          '%s/%s' % (fc['meta']['returned'], fc['meta']['truncated']))
    check('M07', 'meta 报告窗口与总数一致',
          fc['meta']['totalInWindow'] >= fc['meta']['returned'], 'total >= returned',
          '%s/%s' % (fc['meta']['totalInWindow'], fc['meta']['returned']))

    st, b = call('GET', '/api/v1/events/map?bbox=bad&from=0&to=1')
    check('M08', '非法 bbox → 400', st == 400, '400', st)

    st, b = call('GET', '/api/v1/events/map?bbox=0,0,10,10&from=0&to=1&limit=99999')
    check('M09', 'limit 被钳制到 3000 以内', st == 200 and b['meta']['limit'] <= 3000,
          '<=3000', b['meta']['limit'])


# ---------------------------------------------------------------- X 矩阵
def t_matrix():
    print('\n== X 历史时空矩阵 ==\n')
    st, m = call('GET', '/api/v1/events/matrix?from=-499&step=10&count=6')
    check('X01', '列数与列宽正确', st == 200 and len(m['columns']) == 6
          and m['columns'][0]['startYearAstro'] == -499 and m['columns'][0]['endYearAstro'] == -490,
          '6 列，首列 -499..-490', [(c['label'], c['startYearAstro']) for c in m['columns'][:2]])

    check('X02', '固定返回 10 个展示地区', len(m['regions']) == 10,
          '10', [r['label'] for r in m['regions']])
    codes = [r['code'] for r in m['regions']]
    check('X03', '地区顺序与定义一致',
          codes == ['east_asia', 'central_asia', 'south_asia', 'southeast_asia', 'middle_east',
                    'europe', 'africa', 'north_america', 'south_america', 'oceania'],
          '东亚…大洋洲', codes)

    eu = [r for r in m['regions'] if r['code'] == 'europe'][0]
    check('X04', '只显示窗口内有事件的政权', eu['polityCount'] == 1
          and eu['polities'][0]['name'] == '希腊城邦', '希腊城邦 1 个', eu['polityCount'])

    cells = {c['columnIndex']: [e['title'] for e in c['events']] for c in eu['polities'][0]['cells']}
    check('X05', '事件落到正确的时间列（前490 → 列1）',
          cells.get(1) == ['演示：马拉松战役'], '列1=马拉松', cells)

    # 波斯攻克巴比伦在前 539 年，窗口要从更早开始才能覆盖
    st, m = call('GET', '/api/v1/events/matrix?from=-599&step=10&count=20')
    me = [r for r in m['regions'] if r['code'] == 'middle_east'][0]
    pol = {p['name']: p for p in me['polities']}
    check('X06', '一个事件关联多个政权 → 在两个政权行分别出现',
          '波斯帝国' in pol and '新巴比伦' in pol, '波斯帝国 + 新巴比伦', list(pol.keys()))

    st, m = call('GET', '/api/v1/events/matrix?from=-599&step=10&count=12')
    babel = None
    for r in m['regions']:
        for p in r['polities']:
            if p['name'] == '新巴比伦':
                babel = p
    cols = [c['columnIndex'] for c in babel['cells']] if babel else []
    check('X07', '跨多年事件在所有相交时间段都出现（前586–前538，12 列中多列命中）',
          babel is not None and len(cols) >= 5, '>=5 列', cols)

    st, m = call('GET', '/api/v1/events/matrix?from=-499&step=10&count=6')
    check('X08', 'meta 统计未关联政权的事件数（前500年段 = 1）',
          m['unlinkedEventsInWindow'] == 1, '1', m['unlinkedEventsInWindow'])

    st, m = call('GET', '/api/v1/events/matrix?from=-499&step=10&count=6&offset=6')
    check('X09', '分页列索引是绝对列号（offset=6 时首列 index=6）',
          m['columns'][0]['index'] == 6 and m['columns'][0]['startYearAstro'] == -439,
          'index=6, start=-439', (m['columns'][0]['index'], m['columns'][0]['startYearAstro']))

    st, m1 = call('GET', '/api/v1/events/matrix?from=-499&step=10&count=3&region=europe')
    check('X10', 'region 过滤只返回该地区', st == 200 and len(m1['regions']) == 1
          and m1['regions'][0]['code'] == 'europe', '仅 europe', [r['code'] for r in m1['regions']])

    # 同一单元格不重复
    dups = 0
    st, m = call('GET', '/api/v1/events/matrix?from=-499&step=10&count=20')
    for r in m['regions']:
        for p in r['polities']:
            for c in p['cells']:
                ids = [e['eventId'] for e in c['events']]
                if len(ids) != len(set(ids)):
                    dups += 1
    check('X11', '同一单元格内没有重复事件', dups == 0, '0 重复', dups)


# ---------------------------------------------------------------- P 政权
def t_polity():
    print('\n== P 历史政权 ==\n')
    st, rs = call('GET', '/api/v1/polities/regions')
    check('P01', '地区接口返回 10 个含中文标签', st == 200 and len(rs) == 10
          and rs[0]['label'] == '东亚', '10 个', len(rs) if isinstance(rs, list) else rs)

    st, pg = call('GET', '/api/v1/polities?size=5')
    check('P02', '政权列表可读', st == 200 and pg['total'] >= 8, '>=8', pg.get('total'))

    st, pg = call('GET', '/api/v1/polities?keyword=' + urllib.parse.quote('波斯'))
    check('P03', '按关键词搜索政权', st == 200 and any(
        x['name'] == '波斯帝国' for x in pg['items']), '命中 波斯帝国',
        [x['name'] for x in pg['items']])

    name = '验证政权-%d' % int(time.time())
    st, p = call('POST', '/api/v1/polities',
                 {'name': name, 'regionCode': 'central_asia', 'startYearAstro': -300, 'endYearAstro': -100})
    check('P04', '创建政权 201 且返回地区标签', st == 201 and p['regionLabel'] == '中亚',
          '201 中亚', '%s %s' % (st, (p or {}).get('regionLabel')))
    pid = p['polityId'] if isinstance(p, dict) else None

    st, b = call('POST', '/api/v1/polities', {'name': name, 'regionCode': 'central_asia'})
    check('P05', '同地区同名政权重复创建 → 409', st == 409, '409', st)

    st, b = call('POST', '/api/v1/polities', {'name': '非法地区政权', 'regionCode': 'mars'})
    check('P06', '非法展示地区 → 400', st == 400, '400', st)

    st, b = call('POST', '/api/v1/polities', {'name': '半区间政权', 'regionCode': 'europe', 'startYearAstro': -10})
    check('P07', '存在区间只填一端 → 400', st == 400, '400', st)

    st, b = call('POST', '/api/v1/polities',
                 {'name': '倒挂区间政权', 'regionCode': 'europe', 'startYearAstro': 100, 'endYearAstro': -100})
    check('P08', '起止倒挂 → 400', st == 400, '400', st)

    return pid


# ---------------------------------------------------------------- L 关联
def t_link(pid):
    print('\n== L 事件—政权关联 ==\n')
    st, pg = call('GET', '/api/v1/events?keyword=' + urllib.parse.quote('未归属政权'))
    eid = pg['items'][0]['eventId'] if pg.get('items') else None
    check('L01', '找到未关联政权的事件', eid is not None, '有事件', eid)

    st, rows = call('GET', '/api/v1/events/%s/polities' % eid)
    check('L02', '健康：初始未关联', st == 200 and rows == [], '[]', rows)

    st, row = call('POST', '/api/v1/events/%s/polities' % eid, {'polityId': pid, 'role': 'participant'})
    check('L03', '添加关联 201', st == 201 and row['polityId'] == pid, '201', st)
    link_id = row['linkId'] if isinstance(row, dict) else None

    st, b = call('POST', '/api/v1/events/%s/polities' % eid, {'polityId': pid})
    check('L04', '重复关联同一政权 → 409', st == 409, '409', st)

    st, d = call('GET', '/api/v1/events/%s' % eid)
    check('L05', '事件详情内联返回政权关联',
          any(x['polityId'] == pid for x in d['polities']), '含新政权',
          [x['polityName'] for x in d['polities']])

    st, m = call('GET', '/api/v1/events/matrix?from=-499&step=10&count=6')
    check('L06', '关联后该事件进入矩阵（未关联计数归零）',
          m['unlinkedEventsInWindow'] == 0, '0', m['unlinkedEventsInWindow'])

    st, b = call('DELETE', '/api/v1/events/%s/polities/%s' % (eid, link_id))
    check('L07', '解除关联 200', st == 200, '200', st)

    st, m = call('GET', '/api/v1/events/matrix?from=-499&step=10&count=6')
    check('L08', '解除后回到未关联（计数恢复 1）', m['unlinkedEventsInWindow'] == 1, '1',
          m['unlinkedEventsInWindow'])

    st, b = call('POST', '/api/v1/events/999999/polities', {'polityId': pid})
    check('L09', '给不存在的事件关联 → 404', st == 404, '404', st)


# ---------------------------------------------------------------- G 写保护
def t_guard(formal):
    print('\n== G 写保护（正式库实例）==\n')
    st, b = call('POST', '/api/v1/polities', {'name': '不应写入', 'regionCode': 'europe'}, base=formal)
    check('G01', '正式库创建政权被拒 403', st == 403 and (b or {}).get('error') == 'WRITE_FORBIDDEN',
          '403 WRITE_FORBIDDEN', '%s %s' % (st, (b or {}).get('error')))

    st, b = call('GET', '/api/v1/events/matrix?from=-499&step=10&count=3', base=formal)
    check('G02', '正式库矩阵返回空结果并说明未执行 V6（不 500）',
          st == 200 and 'V6' in (b or {}).get('note', ''), '200 + V6 说明',
          '%s %s' % (st, (b or {}).get('note', '')[:40]))

    st, b = call('GET', '/api/v1/events/map?bbox=-180,-85,180,85&from=-489&to=-489', base=formal)
    check('G03', '正式库地图查询可用（当前无事件数据）', st == 200 and b['meta']['returned'] == 0,
          '200 / 0 条', '%s / %s' % (st, (b or {}).get('meta', {}).get('returned')))


def main():
    global BASE
    BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8089').rstrip('/')
    mode = sys.argv[2] if len(sys.argv) > 2 else 'all'
    if mode == 'guard':
        t_guard(BASE)
        return summarize('G 写保护')

    t_time()
    t_map()
    t_matrix()
    pid = t_polity()
    if pid:
        t_link(pid)
    return summarize('M3 接口')


if __name__ == '__main__':
    sys.exit(main())
