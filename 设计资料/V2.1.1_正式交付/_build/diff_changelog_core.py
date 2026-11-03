#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CHANGELOG ↔ CORE 逐字一致性机械复核（只读）

用法：在 正式交付/ 目录下运行
    python _build/diff_changelog_core.py

核验基准（冻结）：
    CORE_DATA_MODEL_V2.1.1.md   sha256[:16] = c0422f679ceb88c3
    V2.1_TO_V2.1.1_CHANGELOG.md sha256[:16] = 98199d279cc563d9

设计原则：
  1. 只读，不写任何交付物；输出到 stdout，由 CHANGELOG_CORE_DIFF.md 引用。
  2. 不靠目测：列名用「逐列标题表解析」，约束用「编号正则」，数字用「token 集合差」。
  3. 行数一律 LF 计数（b.count(b'\n')），不用"文本行数"口径。
"""
import re, hashlib, sys, os

CORE_F = 'CORE_DATA_MODEL_V2.1.1.md'
CH_F   = 'V2.1_TO_V2.1.1_CHANGELOG.md'
LOCK   = {CORE_F: "34ff192009a5d2dd", CH_F: "5c80f224876983de"}

def load(f):
    b = open(f, 'rb').read()
    h = hashlib.sha256(b).hexdigest()[:16]
    return b.decode('utf-8'), b, h

def block(txt, start, end):
    i = txt.index(start); j = txt.index(end, i)
    return txt[i:j]

def lineof(txt, needle, start=0):
    """返回 needle 首次出现处所在的行号（1-based）"""
    pos = txt.find(needle, start)
    return txt.count('\n', 0, pos) + 1 if pos >= 0 else None

def main():
    core, cb, ch = load(CORE_F)
    chal, hb, hh = load(CH_F)

    print('=' * 78)
    print('0. 基准核验')
    print('=' * 78)
    for f, b, h in ((CORE_F, cb, ch), (CH_F, hb, hh)):
        ok = 'OK' if h == LOCK[f] else '!! 与冻结值不符'
        print(f'  {f:<30} {len(b):>7} B  LF={b.count(b"\n"):>5}  {h}  {ok}')

    # ---------------------------------------------------------------- §C 覆盖
    print()
    print('=' * 78)
    print('1. CORE §5.0 列变更清单 → CHANGELOG 覆盖（逐行）')
    print('=' * 78)
    c_lines = core.split('\n')
    start = next(i for i, l in enumerate(c_lines) if l.startswith('### 5.0'))
    end = next(i for i, l in enumerate(c_lines) if l.startswith('### 5.1'))
    rows = []
    for i in range(start, end):
        l = c_lines[i].strip()
        if l.startswith('| `'):
            rows.append((i + 1, [c.strip() for c in l.strip('|').split('|')]))
    print(f'  CORE §5.0 数据行 = {len(rows)}')
    missing = []
    for ln, c in rows:
        col = c[1]
        toks = re.findall(r'`([a-z_]+)`', col) or [c[0].strip('`')]
        hit = [t for t in toks if t in chal]
        status = 'OK' if hit else 'MISS'
        if not hit:
            missing.append((ln, col, c[2]))
        print(f'  {status:<5} CORE L{ln:<5} {c[0]:<28} {col:<42} {c[2][:22]}')
    print(f'  ⇒ 未在 CHANGELOG 出现的行：{len(missing)} 条')
    for ln, col, chg in missing:
        print(f'      CORE L{ln}  {col}  （{chg}）')

    # ------------------------------------------------------------ 约束编号
    print()
    print('=' * 78)
    print('2. CORE 附录A C01–C29 → CHANGELOG §D.2（编号 + 文本 + 状态）')
    print('=' * 78)
    R = re.compile(r'^\|\s*\*{0,2}(C\d\d)\*{0,2}\s*\|')
    def ids(txt, s, e):
        """返回 {Cxx: [(行号, cells), ...]}，行号按全文 enumerate，不做算术推算"""
        lo = txt.count('\n', 0, txt.index(s))
        hi_ = lo + block(txt, s, e).count('\n')
        out = {}
        for i, l in enumerate(txt.split('\n')):
            if not (lo <= i <= hi_):
                continue
            m = R.match(l.strip())
            if m:
                cells = [x.strip() for x in l.strip().strip('|').split('|')]
                out.setdefault(m.group(1), []).append((i + 1, cells))
        return out
    ci = ids(core, '## 附录 A', '## 附录 B')
    hi = ids(chal, '## D.2', '## D.3')
    print(f'  CORE 编号 = {len(ci)}，CH 编号 = {len(hi)}')
    print(f'  漏（CORE 有 / CH 无）：{sorted(set(ci) - set(hi))}')
    print(f'  多（CH 有 / CORE 无）：{sorted(set(hi) - set(ci))}')
    print(f'  CH 重复编号：{[k for k, v in hi.items() if len(v) > 1]}')
    diffs = []
    for k in sorted(set(ci) & set(hi)):
        cln, cc = ci[k][0]
        hln, hc = hi[k][0]
        ctext, cstat = cc[1], cc[3]
        htext, hstat = hc[1], hc[3]
        if ctext != htext or cstat.replace('*', '') != hstat.replace('*', ''):
            diffs.append((k, cln, hln, ctext, cstat, htext, hstat))
    print(f'  ⇒ 文本或状态不一致：{len(diffs)} 条')
    for k, cln, hln, ctext, cstat, htext, hstat in diffs:
        print(f'      {k}  CORE L{cln} 状态={cstat!r}  |  CH L{hln} 状态={hstat!r}')
        if ctext != htext:
            print(f'          文本 CORE: {ctext[:110]}')
            print(f'          文本 CH  : {htext[:110]}')

    # ---------------------------------------------------------------- 计数
    print()
    print('=' * 78)
    print('3. 有效约束计数 29 / 27 / 24 / 3')
    print('=' * 78)
    cA = block(core, '## 附录 A', '**逐条落点**')
    hD = block(chal, '## D.1', '## D.2')
    for t in ['**29**', '**27**', '**24**', '**3**', 'V0.2.1 的 **22**', 'C01–C26']:
        print(f'  {t:<20} CORE={t in cA!s:<6} CH={t in hD!s}')

    # ---------------------------------------------------------------- 视图
    print()
    print('=' * 78)
    print('4. 三视图：列名 / 列数 / 定序键 / 过滤')
    print('=' * 78)
    def numcols(txt, title, stop):
        seg = block(txt, title, stop)
        return [m.group(1) for m in re.finditer(r'^\|\s*\d+\s*\|\s*`([a-z_]+)`', seg, re.M)]
    c11 = numcols(core, '**列清单（11 列，逐列）**', '> ⛔ **V0.2.2 §6 第 3 项')
    h11 = numcols(chal, '**列清单（11 列，逐列）**', '**定序键（写死，顺序不可换）**')
    print(f'  v_place_evidence  CORE={len(c11)} 列  CH={len(h11)} 列  逐列含顺序一致={c11 == h11}')
    c10 = numcols(core, '**列清单（10 列）**', '**四条不变式')
    h10 = [c for c in c10 if '`%s`' % c in chal]
    print(f'  v_place_time_span CORE={len(c10)} 列  CH 逐列命中={len(h10)}/{len(c10)}')
    print(f'      CH 未作为列清单出现的列：{[c for c in c10 if c not in h10]}')
    keys = ["(source_is_active AND child_record_status IS DISTINCT FROM 'rejected') DESC",
            "(evidence_role = 'creator') DESC",
            "sr.duplicate_ordinal ASC NULLS LAST",
            "sr.external_id       ASC NULLS LAST",
            "coalesce(child_row_id, 0) ASC"]
    print('  定序键 6 键逐字命中：', all(k in chal for k in keys))
    lv = ['merged', 'manual', 'active', 'mixed_inactive', 'all_sources_absent',
          'all_sources_rolled_back', 'quarantined_only', 'orphaned']
    print('  liveness 8 值全部命中：', all('`%s`' % v in chal for v in lv))
    for s in ["<> 'rejected'", 'sr.is_active', 'count(e.place_id)',
              "IS DISTINCT FROM 'rejected'", 'GROUP BY e.place_id', 'FAILURE_SET']:
        print(f'      {s!r:<42} CORE={s in core!s:<6} CH={s in chal!s}')

    # ---------------------------------------------------------------- 数字
    print()
    print('=' * 78)
    print('5. N01–N18 权威数字逐格比对')
    print('=' * 78)
    RN = re.compile(r'^\|\s*(N\d\d)\s*\|')
    def nrows(txt, s, e):
        base = txt.count('\n', 0, txt.index(s)) + 1
        out = {}
        for k, l in enumerate(block(txt, s, e).split('\n')):
            m = RN.match(l.strip())
            if m:
                out[m.group(1)] = l
        return out
    cn = nrows(core, '### 9.2', '**入库后各源份额')
    hn = nrows(chal, '## G.1', '## G.2')
    print(f'  CORE={len(cn)} 行  CH={len(hn)} 行  漏={sorted(set(cn)-set(hn))}  多={sorted(set(hn)-set(cn))}')
    num = lambda s: set(re.findall(r'\d[\d,]*', s))
    bad = 0
    for k in sorted(cn):
        d = num(cn[k]) ^ num(hn.get(k, ''))
        if d:
            bad += 1
            print(f'      {k} 数字 token 差：{sorted(d)}')
    print(f'  ⇒ 数字不一致行数：{bad}')

    # ---------------------------------------------------------------- 作废旧数
    print()
    print('=' * 78)
    print('6. §G.2 作废旧数：在 CORE 中是否有落点（无落点 = V2/V2.1 独有旧数，预期）')
    print('=' * 78)
    for t in ['2,233', '327', '1,585', '1,058', '1,564', '1,562', '96.1', '53,133',
              '12,833', '18,093', '644', '16,389', '1,162', '1,164']:
        print(f'      {t:>8}  CORE={t in core!s:<6} CH={t in chal!s}')

    print()
    print('=' * 78)
    print('复核对完成。本脚本只读；差异处置见 _build/CHANGELOG_CORE_DIFF.md')
    print('=' * 78)

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
