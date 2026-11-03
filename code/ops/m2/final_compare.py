#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""M2-1 最终数据完整性对比（只读，不改任何数据）"""
import hashlib
import subprocess

DB = ['docker', 'exec', 'canvas-history-db', 'psql', '-U', 'canvas_app', '-d', 'canvas_history', '-tAc']


def q(sql):
    return subprocess.run(DB + [sql], capture_output=True, text=True).stdout.strip()


# 注意：data_dataset / data_source 在 V5 迁移里各新增 1 行种子
# （manual_entry / manual 数据源），属刻意变更，不是数据损坏。下面分开核对。
BEFORE = {
    'source_record': 29391,
    'historical_place': 19039,
    'historical_place_name': 47499,
    'historical_place_location': 18101,
    'candidate_match': 53131,
    'data_quality_issue': 12831,
    'import_batch': 7,
}

# V5 种子行（人工录入落点），必须存在且只有这一条
SEED = {
    'data_dataset': ('manual_entry', 8),
    'data_source': ('manual', 5),
}

CSV_BASE = {
    'data_datasets.csv': 'fa44197e54b4da4a8af78b589d10a63a668184397f63dbdf842b5051a2ef636f',
    'source_records.csv': '30fed0e40ba124960ba008b030948394398a418a9cc58b333095614469771c5d',
    'historical_places.csv': '86db3ce6b94f9e31036a3785a55510d48eb43bd4ce998aaa5cad2f59b068533f',
    'historical_place_names.csv': '80674c0ded553241c6f4745db0d6957d4dd6617acdfa7918d503128c1690ebbd',
    'historical_place_locations.csv': '9e987ba578e933ed9bdb11564487125783b22623abf348b9201a74d562d637a2',
    'candidate_matches.csv': '4e29c2ec64ebe263c325bab5f0eb70dc922116dd737542cf234373d86c98ab12',
    'data_quality_issues.csv': '7a8ab3916e00dcb04308d89c816c7c8771c6f71ec598ee3e4188c6b643263602',
}

print('## M2-1 最终数据完整性对比')
print('')
print('%s %10s %10s  结论' % ('table'.ljust(28), '施工前', '当前'))
bad = 0
for t, exp in BEFORE.items():
    n = int(q('select count(*) from %s' % t))
    ok = n == exp
    bad += 0 if ok else 1
    print('%s %10d %10d  %s' % (t.ljust(28), exp, n, '一致' if ok else '不一致 ✗'))
# 种子表单独核对
for t, (key, exp) in SEED.items():
    n = int(q('select count(*) from %s' % t))
    col = 'dataset_id' if t == 'data_dataset' else 'source_id'
    has = q("select count(*) from %s where %s = '%s'" % (t, col, key))
    ok = n == exp and has == '1'
    bad += 0 if ok else 1
    print('%s %10s %10d  %s' % (t.ljust(28), '7/4+种子', n,
                                '一致（含 V5 种子 %s）' % key if ok else '不一致 ✗'))
print('→ %s' % ('七张导入表与两张种子表全部符合预期' if bad == 0 else '%d 张表不一致' % bad))

print('')
print('Flyway（V1–V3 校验和必须与施工前相同）')
EXP_V = {'1': '882334605', '2': '966227528', '3': '-2058740630'}
okv = True
for row in q("select version||','||checksum||','||success from flyway_schema_history "
             "where version is not null order by installed_rank").split('\n'):
    v, c, s = row.split(',')
    if v in EXP_V:
        good = c == EXP_V[v] and s == 'true'
        okv = okv and good
        print('  V%s: checksum=%s success=%s  %s' % (v, c, s, '未变 ✓' if good else '已变 ✗'))
    else:
        print('  V%s: checksum=%s success=%s（本阶段新增）' % (v, c, s))
print('→ %s' % ('V1–V3 记录与校验和未变' if okv else 'V1–V3 发生变化'))

print('')
print('序列与主键区间（不得重置；只允许因测试夹具前进，不得回退）')
seq = q("select string_agg(k||'='||v, ' ' order by k) from ("
        "select 'place' k, last_value::text v from historical_place_place_id_seq union all "
        "select 'name', last_value::text from historical_place_name_name_id_seq union all "
        "select 'batch', last_value::text from import_batch_batch_id_seq) x")
print('  ' + seq)
BASE_SEQ = {'place': 38084, 'name': 94998, 'batch': 20}
cur = {
    'place': int(q('select last_value from historical_place_place_id_seq')),
    'name': int(q('select last_value from historical_place_name_name_id_seq')),
    'batch': int(q('select last_value from import_batch_batch_id_seq')),
}
rolled_back = [k for k in BASE_SEQ if cur[k] < BASE_SEQ[k]]
print('  施工前基线：place=38084 name=94998 batch=20')
if rolled_back:
    print('→ 序列被回退（疑似重置）✗：%s' % rolled_back)
else:
    adv = {k: cur[k] - BASE_SEQ[k] for k in BASE_SEQ if cur[k] > BASE_SEQ[k]}
    print('→ 未回退、未重置 ✓' + ('；place 前进 %d（测试夹具曾用自增 id，现已改为显式负 id 不再消耗）' % adv['place']
                              if adv else ''))

print('')
print('主键区间（真实数据的主键不得被改动）')
mx = q('select coalesce(max(place_id),0) from historical_place')
mx_name = q('select coalesce(max(name_id),0) from historical_place_name')
print('  max(place_id)=%s（施工前 38084）  max(name_id)=%s（施工前 94998）' % (mx, mx_name))
print('→ %s' % ('真实数据主键区间未变 ✓' if mx == '38084' and mx_name == '94998'
                else '真实数据主键区间发生变化 ✗'))

print('')
print('六张新表当前行数')
print('  ' + q("select string_agg(k||'='||v, ' ' order by k) from ("
              "select 'person' k, count(*)::text v from person union all "
              "select 'person_name', count(*)::text from person_name union all "
              "select 'event', count(*)::text from event union all "
              "select 'event_place', count(*)::text from event_place union all "
              "select 'event_person', count(*)::text from event_person union all "
              "select 'person_place', count(*)::text from person_place) x"))

print('')
print('七张原始 CSV 指纹（必须与 R1.2 基线一致）')
badc = 0
for f, exp in CSV_BASE.items():
    h = hashlib.sha256(open('data/staging/' + f, 'rb').read()).hexdigest()
    ok = h == exp
    badc += 0 if ok else 1
    print('  %s %s' % ('OK ' if ok else 'BAD', f))
print('→ %s' % ('7/7 与基线一致（未被修改）' if badc == 0 else '%d 个文件被改动' % badc))
