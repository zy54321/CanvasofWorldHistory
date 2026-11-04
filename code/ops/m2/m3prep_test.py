#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M3 前置加固测试：数据库写入保护 / 地点列表排序 / 地点选项来源。

用法：
  python ops/m2/m3prep_test.py writeguard  http://127.0.0.1:8088   # A 正式库只读
  python ops/m2/m3prep_test.py writable    http://127.0.0.1:8089   # B 测试库可写
  python ops/m2/m3prep_test.py ordering    http://127.0.0.1:8089   # 排序
  python ops/m2/m3prep_test.py options     http://127.0.0.1:8089 8088  # 选项接口 vs 数据库 CHECK

所有判定都走真实 HTTP + 真实数据库，不做静态检查。
"""
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request

R = []


def call(base, method, path, body=None):
    req = urllib.request.Request(
        base + path,
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


def sql(q, db='canvas_history'):
    r = subprocess.run(['docker', 'exec', 'canvas-history-db', 'psql', '-U', 'canvas_app',
                        '-d', db, '-tAc', q], capture_output=True, text=True)
    return r.stdout.strip()


def check(cid, desc, cond, expect, actual):
    R.append((cid, desc, bool(cond)))
    print('%s %-5s %-46s | 期望 %s | 实际 %s'
          % ('PASS' if cond else 'FAIL', cid, desc, expect, str(actual)[:110]))


def summarize():
    ok = sum(1 for _, _, c in R if c)
    print('\n=== PASS %d / %d ===' % (ok, len(R)))
    return 0 if ok == len(R) else 1


# ---------------------------------------------------------------- A 只读实例
def t_writeguard(base):
    print('== A 正式库实例写保护  目标 %s ==\n' % base)
    st, pol = call(base, 'GET', '/api/v1/meta/write-policy')
    dbname = (pol or {}).get('database')
    check('A01', '写策略可读且指向 canvas_history',
          st == 200 and dbname == 'canvas_history', '200 + canvas_history', '%s %s' % (st, dbname))
    check('A02', '写策略判定为禁止写入', (pol or {}).get('writeAllowed') is False,
          'writeAllowed=false', (pol or {}).get('writeAllowed'))

    before = sql("select count(*) from historical_place")
    persons_before = sql("select count(*) from person")

    st, b = call(base, 'GET', '/api/v1/places?keyword=%E6%A1%82%E6%9E%97&size=2')
    check('A03', 'GET 查询不受影响', st == 200 and b['total'] > 0, '200 且有结果',
          '%s total=%s' % (st, b.get('total') if isinstance(b, dict) else b))

    pid = sql("select place_id from historical_place order by place_id limit 1")

    st, b = call(base, 'POST', '/api/v1/places', {'canonicalName': '写保护测试-应被拒'})
    check('A04', 'POST 创建地点被拒 403', st == 403 and (b or {}).get('error') == 'WRITE_FORBIDDEN',
          '403 WRITE_FORBIDDEN', '%s %s' % (st, (b or {}).get('error')))

    st, b = call(base, 'PUT', '/api/v1/places/%s' % pid, {'canonicalName': '写保护测试-改'})
    check('A05', 'PUT 编辑地点被拒 403', st == 403 and (b or {}).get('error') == 'WRITE_FORBIDDEN',
          '403 WRITE_FORBIDDEN', '%s %s' % (st, (b or {}).get('error')))

    st, b = call(base, 'DELETE', '/api/v1/places/%s' % pid)
    check('A06', 'DELETE 删除地点被拒 403', st == 403 and (b or {}).get('error') == 'WRITE_FORBIDDEN',
          '403 WRITE_FORBIDDEN', '%s %s' % (st, (b or {}).get('error')))

    st, b = call(base, 'POST', '/api/v1/persons', {'canonicalName': '写保护测试'})
    check('A07', 'POST 创建人物被拒 403', st == 403 and (b or {}).get('error') == 'WRITE_FORBIDDEN',
          '403 WRITE_FORBIDDEN', '%s %s' % (st, (b or {}).get('error')))

    st, b = call(base, 'POST', '/api/v1/events', {'title': '写保护测试'})
    check('A08', 'POST 创建事件被拒 403', st == 403 and (b or {}).get('error') == 'WRITE_FORBIDDEN',
          '403 WRITE_FORBIDDEN', '%s %s' % (st, (b or {}).get('error')))

    st, b = call(base, 'POST', '/api/v1/places/%s/names' % pid, {'nameText': 'x'})
    check('A09', '子资源写（地点名称）同样被拒', st == 403, '403', st)

    after = sql("select count(*) from historical_place")
    persons_after = sql("select count(*) from person")
    check('A10', '被拒后正式库数据量不变',
          before == after and persons_before == persons_after,
          '%s / %s 不变' % (before, persons_before),
          '%s / %s' % (after, persons_after))

    st, b = call(base, 'GET', '/api/v1/places/%s' % pid)
    check('A11', '目标地点仍可正常读取（未被误删/误改）', st == 200, '200', st)
    return summarize()


# ---------------------------------------------------------------- B 可写实例
def t_writable(base):
    print('== B 测试库实例写保护放行  目标 %s ==\n' % base)
    st, pol = call(base, 'GET', '/api/v1/meta/write-policy')
    dbname = (pol or {}).get('database')
    check('B01', '写策略指向测试库且允许写入',
          st == 200 and dbname == 'canvas_history_m2check' and (pol or {}).get('writeAllowed') is True,
          'canvas_history_m2check + true', '%s %s' % (dbname, (pol or {}).get('writeAllowed')))

    st, b = call(base, 'GET', '/api/v1/places/admin?size=1')
    check('B02', 'GET 正常', st == 200, '200', st)

    st, b = call(base, 'POST', '/api/v1/places', {'canonicalName': '写保护-可写实例新建'})
    pid = (b or {}).get('placeId') if isinstance(b, dict) else None
    check('B03', 'POST 创建成功 201', st == 201 and pid, '201 + placeId', '%s %s' % (st, pid))

    st, b = call(base, 'PUT', '/api/v1/places/%s' % pid, {'canonicalName': '写保护-可写实例改名'})
    check('B04', 'PUT 编辑成功', st == 200, '200', st)

    st, b = call(base, 'POST', '/api/v1/places/%s/names' % pid,
                 {'nameText': '别名测试', 'nameType': 'alternate', 'nameLang': 'zh'})
    check('B05', '子资源写（名称）成功', st == 201, '201', st)

    st, b = call(base, 'DELETE', '/api/v1/places/%s' % pid)
    check('B06', 'DELETE 成功', st == 200, '200', st)

    left = sql("select count(*) from historical_place where place_id=%s" % pid, 'canvas_history_m2check')
    check('B07', '删除后库中确无该行', left == '0', '0', left)
    return summarize()


# ---------------------------------------------------------------- 排序
def t_ordering(base):
    print('== 地点列表排序（最近更新优先）  目标 %s ==\n' % base)
    created = []
    for i in range(1, 4):
        st, b = call(base, 'POST', '/api/v1/places', {'canonicalName': '排序测试-%d' % i})
        if st != 201:
            check('O00', '准备数据失败', False, '201', st)
            return summarize()
        created.append(b['placeId'])

    st, page = call(base, 'GET', '/api/v1/places/admin?size=20')
    ids = [x['placeId'] for x in page['items'][:5]]
    check('O01', '新建的 3 条按创建时间倒序排在最前',
          ids[:3] == [created[2], created[1], created[0]],
          str([created[2], created[1], created[0]]), str(ids))

    # 编辑最早创建的那条 → 应跳到第一位
    st, _ = call(base, 'PUT', '/api/v1/places/%s' % created[0],
                 {'canonicalName': '排序测试-1（已编辑）'})
    st2, page2 = call(base, 'GET', '/api/v1/places/admin?size=20')
    check('O02', '编辑最早的一条后它排到第一（按 updated_at 倒序）',
          page2['items'][0]['placeId'] == created[0],
          '首位=%s' % created[0], '首位=%s' % page2['items'][0]['placeId'])

    check('O03', '列表带出 updated_at 之外的必要字段未受影响',
          all(k in page2['items'][0] for k in ('placeId', 'canonicalName', 'nameCount')),
          '字段齐全', list(page2['items'][0].keys())[:6])

    st, page3 = call(base, 'GET', '/api/v1/places/admin?keyword=%E6%8E%92%E5%BA%8F%E6%B5%8B%E8%AF%95&size=2')
    check('O04', '搜索 + 分页仍然可用', st == 200 and page3['total'] >= 3 and len(page3['items']) == 2,
          'total>=3 且每页 2 条', '%s %s' % (page3.get('total'), len(page3.get('items', []))))

    # 清理
    for cid in created:
        call(base, 'DELETE', '/api/v1/places/%s' % cid)
    return summarize()


# ---------------------------------------------------------------- 选项
def t_options(*bases):
    print('== 地点选项接口 vs 数据库 CHECK 约束\n')
    base = bases[0]
    st, opt = call(base, 'GET', '/api/v1/places/admin/options')
    check('P01', '选项接口可读 200', st == 200 and isinstance(opt, dict), '200 + 对象', st)
    if st != 200:
        return summarize()

    def parse_check(conname):
        raw = sql("select pg_get_constraintdef(oid) from pg_constraint where conname='%s'" % conname).strip()
        if 'CHECK' not in raw:
            return None
        vals = re.findall(r"'([^']+)'::text", raw)
        return sorted(vals) if vals else None

    pairs = [
        ('placeTypes', 'ck_historical_place_place_type'),
        ('nameTypes', 'ck_hpn_name_type'),
        ('timeBoundTypes', 'ck_hpn_time_bound_type'),
        ('locationPrecisions', 'ck_hpl_location_precision'),
        ('crsConfidences', 'ck_hpl_crs_confidence'),
        ('recordStatuses', 'ck_historical_place_record_status'),
    ]
    for field, con in pairs:
        db = parse_check(con)
        api = sorted(opt.get(field) or [])
        if db is None:
            print('SKIP  %-6s %-24s 未解析到 %s' % ('P05', field, con))
            continue
        invented = [x for x in api if x not in db]          # API 凭空造出的值 → 必须为 0
        narrowed = [x for x in db if x not in api]          # API 故意收窄的值 → 允许但要说明
        check('P-%s' % field, '%s 与 %s 一致' % (field, con),
              not invented, 'API 不出现 DB 之外的值',
              'API多出 %s' % invented if invented else
              ('一致' if not narrowed else '一致（收窄：%s）' % narrowed))
        if narrowed and not invented:
            print('      ↳ 说明：%s 收窄掉 %s（系统态/发布流程产出，不在表单手选）'
                  % (field, narrowed))
    return summarize()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'writeguard'
    args = sys.argv[2:]
    if mode == 'writeguard':
        sys.exit(t_writeguard(args[0].rstrip('/')))
    if mode == 'writable':
        sys.exit(t_writable(args[0].rstrip('/')))
    if mode == 'ordering':
        sys.exit(t_ordering(args[0].rstrip('/')))
    if mode == 'options':
        sys.exit(t_options(*[a.rstrip('/') for a in args]))
    print('未知模式：%s' % mode)
    sys.exit(2)


if __name__ == '__main__':
    main()
