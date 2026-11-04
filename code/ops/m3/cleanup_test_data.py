#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试库临时数据清理（只针对 canvas_history_m2check，永不连正式库）。

背景（M3 封存轮）：
  自动化脚本每一轮都会新建「验证政权-<时间戳>」「验证政权UI-<随机>」以及若干固定
  名称的测试事件。早期脚本没有收尾删除，重复执行后测试库里堆了三批同名事件和三个
  验证政权，矩阵「未关联政权计数」等断言就容易受历史残留影响。

本脚本只做两件事，都可重复执行（幂等）：
  1. 删除名称以「验证政权」开头的政权（连带其事件关联，CASCADE）——这些只可能来自
     接口/UI 自动化测试，人工与演示数据不会用这个前缀；
  2. 对固定名称的 M2 测试事件做去重：同名只保留 event_id 最小的一条；
  3. 明确不动：M3 演示数据（标题前缀「演示：」）、M2 人工录入地点/数据集、以及
     人物与地点（它们不在本轮判定范围内，删除会连带破坏 M2 固件关系）。

用法：
  python ops/m3/cleanup_test_data.py            # 执行清理并打印前后数量
  python ops/m3/cleanup_test_data.py --dry-run  # 只打印将要删除的对象
"""
import subprocess
import sys

DB = 'canvas_history_m2check'  # 硬编码：任何情况下都不碰 canvas_history
TEST_EVENT_TITLES = (
    '孔子适周问礼',
    '测试-跨前后事件',
    '测试事件-时间未知',
    '测试事件-开放区间',
    '测试-级联删除事件',
)

COUNTS_SQL = """
SELECT 'event', count(*) FROM event
UNION ALL SELECT 'event_place', count(*) FROM event_place
UNION ALL SELECT 'event_person', count(*) FROM event_person
UNION ALL SELECT 'historical_polity', count(*) FROM historical_polity
UNION ALL SELECT 'event_polity', count(*) FROM event_polity
UNION ALL SELECT 'person', count(*) FROM person
UNION ALL SELECT 'historical_place', count(*) FROM historical_place
ORDER BY 1
"""


def psql(q):
    r = subprocess.run(
        ['docker', 'exec', 'canvas-history-db', 'psql', '-U', 'canvas_app',
         '-d', DB, '-v', 'ON_ERROR_STOP=1', '-tAc', q],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:400])
    return r.stdout.strip()


def counts():
    out = {}
    for line in psql(COUNTS_SQL).splitlines():
        k, v = line.split('|')
        out[k] = int(v)
    return out


def main():
    dry = '--dry-run' in sys.argv
    if psql('select current_database()') != DB:
        print('拒绝执行：当前连接不是 %s' % DB)
        return 2

    before = counts()
    print('清理前：', ' / '.join('%s=%d' % (k, v) for k, v in before.items()))

    titles = ','.join("'%s'" % t for t in TEST_EVENT_TITLES)
    dup_events = psql("""
        SELECT coalesce(string_agg(event_id::text, ','), '')
          FROM event e
         WHERE e.title IN (%s)
           AND e.event_id > (SELECT min(x.event_id) FROM event x WHERE x.title = e.title)
        """ % titles)
    dup_polities = psql(
        "SELECT coalesce(string_agg(polity_id::text, ','), '') FROM historical_polity "
        "WHERE name LIKE '验证政权%%'")

    print('待删重复测试事件 event_id:', dup_events or '(无)')
    print('待删验证政权 polity_id    :', dup_polities or '(无)')

    if dry:
        print('\n[dry-run] 未做任何修改')
        return 0

    psql("""
        BEGIN;
        DELETE FROM event e
         WHERE e.title IN (%s)
           AND e.event_id > (SELECT min(x.event_id) FROM event x WHERE x.title = e.title);
        DELETE FROM historical_polity WHERE name LIKE '验证政权%%';
        COMMIT;
        """ % titles)

    after = counts()
    print('清理后：', ' / '.join('%s=%d' % (k, v) for k, v in after.items()))
    print('变化：', ' / '.join('%s=%+d' % (k, after[k] - before[k]) for k in before))
    return 0


if __name__ == '__main__':
    sys.exit(main())
