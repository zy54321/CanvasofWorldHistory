#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
政权 record_status 规则验证（M3 封存轮）。

统一后的规则只有三条：
  staging   个人矩阵正常显示
  published 个人矩阵正常显示
  rejected  不进入矩阵（事件本身、事件—政权关联、地图标记全部保留）

本脚本用真实接口 + 真实数据库验证这三条，并确认管理侧仍能识别与修改状态：
  S01 新建政权默认 staging，且关联演示事件后进入矩阵
  S02 改为 published → 仍在矩阵
  S03 改为 rejected → 矩阵不再出现该政权行
  S04 rejected 后事件与关联仍在（事件详情、政权列表都可读，列表带状态）
  S05 改回 staging → 重新进入矩阵
  S06 非法状态值 → 400；不存在的政权 → 404
  S07 矩阵里其它政权不受影响（罗马共和国仍在）
  S08 清理：删除本轮验证政权，矩阵回到初始状态

用法：
  python ops/m3/polity_status_test.py [http://127.0.0.1:8089]
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# 目标库可被环境变量覆盖：本轮跑在 V10 结构的隔离库上
DB = os.environ.get('TEST_DB', 'canvas_history_m2check')
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


def psql(q):
    r = subprocess.run(['docker', 'exec', 'canvas-history-db', 'psql', '-U', 'canvas_app',
                        '-d', DB, '-tAc', q], capture_output=True, text=True)
    return r.stdout.strip()


def rec(cid, desc, ok, expect, actual):
    R.append((cid, desc, bool(ok)))
    print('%s %-4s %-52s | 期望 %s | 实际 %s'
          % ('PASS' if ok else 'FAIL', cid, desc, expect, str(actual)[:110]))


def matrix_polities():
    """当前窗口（前500 起 6 列，覆盖前490）内所有政权名。"""
    st, m = call('GET', '/api/v1/events/matrix?from=-499&step=10&count=6')
    names = []
    for rg in (m or {}).get('regions', []):
        for p in rg.get('polities', []):
            names.append(p['name'])
    return st, names


def main():
    global BASE
    if len(sys.argv) > 1:
        BASE = sys.argv[1].rstrip('/')

    name = '验证政权-状态-%d' % int(time.time())
    st, ev = call('GET', '/api/v1/events?keyword=' + urllib.parse.quote('马拉松战役'))
    eid = ev['items'][0]['eventId'] if ev.get('items') else None
    rec('S00', '取到演示事件「马拉松战役」', eid is not None, '有事件', eid)
    if eid is None:
        return 1

    st, p = call('POST', '/api/v1/polities',
                 {'name': name, 'regionCode': 'europe', 'startYearAstro': -500, 'endYearAstro': -400})
    pid = p.get('polityId') if isinstance(p, dict) else None
    rec('S01a', '新建政权默认 staging', st == 201 and p.get('recordStatus') == 'staging',
        '201 + staging', '%s %s' % (st, (p or {}).get('recordStatus')))

    st, _ = call('POST', '/api/v1/events/%s/polities' % eid, {'polityId': pid, 'role': 'defender'})
    st, names = matrix_polities()
    rec('S01b', 'staging 政权关联事件后进入矩阵', name in names, '矩阵含该政权',
        [n for n in names if n.startswith('验证政权')])

    st, p = call('PATCH', '/api/v1/polities/%s/status' % pid, {'recordStatus': 'published'})
    st2, names = matrix_polities()
    rec('S02', '改为 published → 仍在矩阵', st == 200 and p.get('recordStatus') == 'published'
        and name in names, '200 + 矩阵含该政权', '%s %s' % (st, name in names))

    st, p = call('PATCH', '/api/v1/polities/%s/status' % pid, {'recordStatus': 'rejected'})
    st2, names = matrix_polities()
    rec('S03', '改为 rejected → 矩阵不再出现该政权行',
        st == 200 and p.get('recordStatus') == 'rejected' and name not in names,
        '200 + 矩阵不含该政权', '%s %s' % (st, name in names))

    st, d = call('GET', '/api/v1/events/%s' % eid)
    link = next((x for x in (d.get('polities') or []) if x['polityId'] == pid), None)
    rec('S04a', 'rejected 后事件—政权关联仍保留',
        st == 200 and link is not None and link.get('recordStatus') == 'rejected',
        '关联在且状态 rejected', link)

    st, pg = call('GET', '/api/v1/polities?keyword=' + urllib.parse.quote(name))
    item = next((x for x in pg.get('items', []) if x['polityId'] == pid), None) if isinstance(pg, dict) else None
    rec('S04b', '管理侧列表仍能识别该政权及其状态',
        st == 200 and item is not None and item.get('recordStatus') == 'rejected',
        '列表含 rejected', item)

    st, p = call('PATCH', '/api/v1/polities/%s/status' % pid, {'recordStatus': 'staging'})
    st2, names = matrix_polities()
    rec('S05', '改回 staging → 重新进入矩阵', st == 200 and name in names,
        '200 + 矩阵含该政权', '%s %s' % (st, name in names))

    st, b = call('PATCH', '/api/v1/polities/%s/status' % pid, {'recordStatus': 'draft'})
    rec('S06a', '非法状态值 → 400', st == 400, '400', st)
    st, b = call('PATCH', '/api/v1/polities/99999999/status', {'recordStatus': 'staging'})
    rec('S06b', '不存在的政权改状态 → 404', st == 404, '404', st)

    st, names = matrix_polities()
    rec('S07', '矩阵里其它政权不受影响（同窗口的希腊城邦仍在）', '希腊城邦' in names,
        '含 希腊城邦', names)

    # 清理：删政权（CASCADE 带走关联），矩阵回到初始
    psql("DELETE FROM historical_polity WHERE polity_id = %d" % pid)
    st, names = matrix_polities()
    rec('S08', '清理后矩阵恢复原状（无验证政权残留）',
        not any(n.startswith('验证政权') for n in names), '无 验证政权*', names)

    ok = sum(1 for _, _, c in R if c)
    print('\n=== 政权状态：PASS %d / %d ===' % (ok, len(R)))
    if ok != len(R):
        print('失败项：', [cid for cid, _, c in R if not c])
    return 0 if ok == len(R) else 1


if __name__ == '__main__':
    sys.exit(main())
