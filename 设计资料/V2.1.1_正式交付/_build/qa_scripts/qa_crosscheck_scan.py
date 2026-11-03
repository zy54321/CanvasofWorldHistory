# -*- coding: utf-8 -*-
"""QA 独立交叉检查 · 只读扫描脚本（不修改任何被检文件/参照物/CSV）。
用法: python qa_crosscheck_scan.py
输出: 纯文本，供 QA_CROSSCHECK_BATCH1.md 引用行号。
"""
import hashlib
import os
import re
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CORE = os.path.join(ROOT, 'CORE_DATA_MODEL_V2.1.1.md')
BASE = os.path.join(ROOT, '_build', 'SHARED_BASELINE_V2.1.1.md')
NORM = os.path.abspath(os.path.join(
    ROOT, '..', '..', '..', 'WB-002', 'normalized'))


def load(path):
    b = open(path, 'rb').read()
    return b, b.decode('utf-8').splitlines()


def snap(path, b):
    st = os.stat(path)
    return 'sha256[:16]=%s / %d bytes / mtime=%s' % (
        hashlib.sha256(b).hexdigest()[:16], len(b),
        time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)))


def hits(L, pattern, flags=0):
    rx = re.compile(pattern, flags)
    return [(i + 1, x.strip()) for i, x in enumerate(L) if rx.search(x)]


def section(title):
    print('\n' + '=' * 78)
    print(title)
    print('=' * 78)


core_b, CORE_L = load(CORE)
base_b, BASE_L = load(BASE)

section('0. 快照（sha256 原始字节口径）')
print('CORE:', snap(CORE, core_b), ' lines=', len(CORE_L))
print('BASE:', snap(BASE, base_b), ' lines=', len(BASE_L))

FILES = [('CORE', CORE_L), ('BASE', BASE_L)]

section('1. 许可/授权管理禁用串（精确子串，逐处列行号）')
BANNED = ['LICENSE_GATE', 'attribution_text', 'citation_text',
          'licence_unconfirmed', 'license_url', 'license_evidence']
for name, L in FILES:
    for s in BANNED:
        h = hits(L, re.escape(s))
        print('%-4s %-22s count=%d lines=%s' % (
            name, s, len(h), [n for n, _ in h]))
        for n, x in h:
            print('      L%-4d %s' % (n, x[:190]))

section('2. 禁用词 connection / place_record / published')
for name, L in FILES:
    for s in ['connection', 'place_record', "'published'", 'published']:
        h = hits(L, re.escape(s))
        print('%-4s %-14s count=%d lines=%s' % (name, s, len(h), [n for n, _ in h]))

section('3. 五段业务键逐字串')
KEY = r'\(dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal\)'
for name, L in FILES:
    h = hits(L, KEY)
    print(name, '五段键完整串 count=', len(h), 'lines=', [n for n, _ in h])
    key4 = hits(L, r'UNIQUE \(dataset_id, record_scope, external_id, occurrence_key\)')
    print(name, 'V2.1 四段键（须带作废标注） lines=', [n for n, _ in key4])

section('4. issue_fingerprint 算法与 place_id')
for name, L in FILES:
    print('--', name)
    for n, x in hits(L, r'issue_fingerprint'):
        print('   L%-4d %s' % (n, x[:190]))
    for n, x in hits(L, r'md5\(jsonb_build_array'):
        print('   MD5EXPR L%-4d %s' % (n, x[:190]))
    for n, x in hits(L, r'sha256'):
        print('   SHA256 L%-4d %s' % (n, x[:190]))

section('5. content_hash 规范串 + 指纹复算')
S = r"sha256\(json.dumps\(payload, sort_keys=True, ensure_ascii=False, separators=\(',',':'\)\)\)"
for name, L in FILES:
    h = hits(L, S)
    print(name, '规范串 count=', len(h), 'lines=', [n for n, _ in h])
s = "sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':')))"
print('RECALC len=%d sha1=%s' % (len(s), hashlib.sha1(s.encode()).hexdigest()))
inner = "json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':'))"
print('RECALC inner len=%d sha1=%s' % (len(inner), hashlib.sha1(inner.encode()).hexdigest()))

section('6. C01–C29 编号全集')
for name, L in FILES:
    txt = '\n'.join(L)
    ids = sorted(set(re.findall(r'\bC(\d{2})\b', txt)))
    print(name, '出现的 C 编号:', ids)
    print(name, '缺失:', [f'{i:02d}' for i in range(1, 30) if f'{i:02d}' not in ids])
    # 每个编号出现次数
    from collections import Counter
    c = Counter(re.findall(r'\bC(\d{2})\b', txt))
    print(name, '次数:', dict(sorted(c.items())))

section('7. 隔离判据 / ordinal=1 旧规则')
for name, L in FILES:
    print('--', name)
    for n, x in hits(L, r'ordinal\s*=\s*1|ordinal = 1|只比|同一 hash 子组|最小 ordinal|不同 hash'):
        print('   L%-4d %s' % (n, x[:200]))

section('8. 三种视图名 / 11 列 / 9 列 / 10 列')
for name, L in FILES:
    print('--', name)
    for v in ['v_place_evidence', 'v_place_liveness', 'v_place_time_span']:
        print('   %-20s count=%d' % (v, sum(1 for x in L if v in x)))
    for n, x in hits(L, r'11 列|10 列|9 列|8 列'):
        print('   COLNUM L%-4d %s' % (n, x[:190]))

section('9. 过滤条件 published / <> rejected / sr.is_active')
for name, L in FILES:
    print('--', name)
    for n, x in hits(L, r"record_status\s*(=|<>|!=)\s*'rejected'|record_status\s*=\s*'published'|sr\.is_active"):
        print('   L%-4d %s' % (n, x[:190]))

section('10. 新列计数 +2 / +3')
for name, L in FILES:
    print('--', name)
    for n, x in hits(L, r'\+2|\+3|＋2|＋3|新列'):
        print('   L%-4d %s' % (n, x[:190]))

section('11. place_grain 归属标注')
for name, L in FILES:
    print('--', name)
    for n, x in hits(L, r'place_grain'):
        print('   L%-4d %s' % (n, x[:190]))

section('12. 七张暂存 CSV 实测行数（D5-6 依据层①）')
FILES_CSV = [
    'source_records.csv', 'historical_places.csv', 'historical_place_names.csv',
    'historical_place_locations.csv', 'data_quality_issues.csv',
    'candidate_matches.csv', 'data_datasets.csv']
for f in FILES_CSV:
    p = os.path.join(NORM, f)
    if not os.path.exists(p):
        print(f, 'MISSING', p)
        continue
    with open(p, 'rb') as fh:
        raw = fh.read()
    # 行数 = 数据行数（不含表头），按 \n 计；末行可能无换行
    lines = raw.split(b'\n')
    if lines and lines[-1] == b'':
        lines = lines[:-1]
    hdr = lines[0].decode('utf-8-sig').split(',')
    print('%-38s datarows=%-8d cols=%-3d bytes=%-10d sha16=%s' % (
        f, len(lines) - 1, len(hdr), len(raw),
        hashlib.sha256(raw).hexdigest()[:16]))
    print('    header=', ','.join(hdr[:14]))

section('13. 七张 CSV 表头（供 D5-1 逐列核对）')
for f in FILES_CSV:
    p = os.path.join(NORM, f)
    if not os.path.exists(p):
        continue
    with open(p, 'rb') as fh:
        first = fh.readline().decode('utf-8-sig').rstrip('\r\n')
    print('%-38s %s' % (f, first))
