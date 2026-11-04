#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
V7 迁移验证：历史政权存在区间「任意端点可选」。

两组判定，都跑真实数据库 / 真实接口，不做静态检查：

  D 数据库层（直接 SQL，每个用例各自 BEGIN … ROLLBACK，不留任何数据）
    D01 只填起始年      → 允许
    D02 只填结束年      → 允许
    D03 两端都空        → 允许
    D04 两端都填且有序  → 允许
    D05 两端都填且倒挂  → 违反 ck_polity_time_order（23514）

  A 接口层（POST /api/v1/polities）
    A01 只填起始年 → 201，end = null
    A02 只填结束年 → 201，start = null
    A03 两端都空   → 201，两字段均为 null
    A04 两端都填   → 201，原样存取
    A05 倒挂       → 400
    A06 详情/列表回读与写入一致

  C 清理：删除本轮创建的「验证政权-…」，脚本可重复执行。

用法：
  python ops/m3/v7_polity_time_test.py            # 默认 http://127.0.0.1:8089
  python ops/m3/v7_polity_time_test.py http://127.0.0.1:8089
"""
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

DB = 'canvas_history_m2check'
BASE = 'http://127.0.0.1:8089'
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


def psql(stmt):
    """返回 (ok, combined_output)。ON_ERROR_STOP=1 让 SQL 错误直接体现为返回码非 0。"""
    r = subprocess.run(
        ['docker', 'exec', 'canvas-history-db', 'psql', '-U', 'canvas_app',
         '-d', DB, '-v', 'ON_ERROR_STOP=1', '-tAc', stmt],
        capture_output=True, text=True)
    return r.returncode == 0, (r.stdout or '') + (r.stderr or '')


def rec(cid, desc, ok, expect, actual):
    R.append((cid, desc, bool(ok)))
    print('%s %-4s %-54s | 期望 %s | 实际 %s'
          % ('PASS' if ok else 'FAIL', cid, desc, expect, str(actual)[:110]))


def db_case(cid, desc, name, start, end, should_pass):
    vals = '%s, %s' % ('NULL' if start is None else start, 'NULL' if end is None else end)
    stmt = ("BEGIN; INSERT INTO historical_polity (name, region_code, start_year_astro, end_year_astro) "
            "VALUES ('V7-DB-%s', 'oceania', %s); ROLLBACK;" % (cid, vals))
    ok, out = psql(stmt)
    if should_pass:
        rec(cid, desc, ok, '插入成功（回滚）', '成功' if ok else out.strip()[:90])
    else:
        rec(cid, desc, (not ok) and 'ck_polity_time_order' in out,
            '违反 ck_polity_time_order（23514）',
            (out.strip().splitlines() or [''])[-1][:110])


def api_case(cid, desc, body, expect_status, checks):
    st, b = call('POST', '/api/v1/polities', body)
    ok = st == expect_status
    detail = '%s' % st
    if ok and isinstance(b, dict):
        for field, want in checks.items():
            got = b.get(field, '<missing>')
            ok = ok and got == want
            detail += ' / %s=%r' % (field, got)
    rec(cid, desc, ok, '%s %s' % (expect_status, checks or ''), detail)
    return b if isinstance(b, dict) else {}


def main():
    global BASE
    if len(sys.argv) > 1:
        BASE = sys.argv[1].rstrip('/')

    print('== V7 数据库约束（每条用例单独事务并回滚）==\n')
    db_case('D01', '只填起始年（-221）', 'only-start', -221, None, True)
    db_case('D02', '只填结束年（-539）', 'only-end', None, -539, True)
    db_case('D03', '两端都空', 'none', None, None, True)
    db_case('D04', '两端都填且有序（-221..-206）', 'both-ok', -221, -206, True)
    db_case('D05', '两端都填但倒挂（-206..-221）', 'both-bad', -206, -221, False)

    print('\n== V7 接口行为（测试库可写实例）==\n')
    tag = 'AT%d' % (int(__import__('time').time()) % 10000)
    only_start = api_case('A01', '只填起始年 → 201 且 end 为 null',
                          {'name': '验证政权-仅起点-%s' % tag, 'regionCode': 'east_asia',
                           'startYearAstro': -221},
                          201, {'startYearAstro': -221, 'endYearAstro': None})
    only_end = api_case('A02', '只填结束年 → 201 且 start 为 null',
                        {'name': '验证政权-仅终点-%s' % tag, 'regionCode': 'middle_east',
                         'endYearAstro': -539},
                        201, {'startYearAstro': None, 'endYearAstro': -539})
    empty = api_case('A03', '两端都空 → 201',
                     {'name': '验证政权-无区间-%s' % tag, 'regionCode': 'oceania'},
                     201, {'startYearAstro': None, 'endYearAstro': None})
    both = api_case('A04', '两端都填 → 201 且原样存取',
                    {'name': '验证政权-双端-%s' % tag, 'regionCode': 'east_asia',
                     'startYearAstro': -221, 'endYearAstro': -206},
                    201, {'startYearAstro': -221, 'endYearAstro': -206})
    st, b = call('POST', '/api/v1/polities',
                 {'name': '验证政权-倒挂-%s' % tag, 'regionCode': 'europe',
                  'startYearAstro': -206, 'endYearAstro': -221})
    rec('A05', '两端倒挂 → 400', st == 400, '400', st)

    pid = only_end.get('polityId')
    if pid:
        st, d = call('GET', '/api/v1/polities?keyword=%s' % urllib.parse.quote('仅终点-%s' % tag))
        item = next((x for x in d.get('items', []) if x['polityId'] == pid), None) if isinstance(d, dict) else None
        rec('A06', '列表回读：只有结束年的政权两端状态一致',
            st == 200 and item is not None and item['startYearAstro'] is None
            and item['endYearAstro'] == -539,
            'start=null end=-539', item)
    else:
        rec('A06', '列表回读：只有结束年的政权两端状态一致', False, 'start=null end=-539', '未取到 polityId')

    # 清理：只删本轮创建的验证政权（CASCADE 带走关联）
    removed = psql("DELETE FROM historical_polity WHERE name LIKE '验证政权-%%' RETURNING polity_id")
    left = psql("SELECT count(*) FROM historical_polity WHERE name LIKE '验证政权-%%'")[1].strip()
    rec('C01', '清理本轮测试政权，库内无残留', left == '0', '0 行', left)

    ok = sum(1 for _, _, c in R if c)
    print('\n=== V7：PASS %d / %d ===' % (ok, len(R)))
    if ok != len(R):
        print('失败项：', [cid for cid, _, c in R if not c])
    return 0 if ok == len(R) else 1


if __name__ == '__main__':
    sys.exit(main())
