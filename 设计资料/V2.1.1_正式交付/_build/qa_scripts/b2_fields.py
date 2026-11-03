# -*- coding: utf-8 -*-
"""ER 图 vs CORE §5 字段双向逐字比对（12 实体 = 9 表 + 3 视图）"""
import re,html,os,json
BASE=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
svg=open(os.path.join(BASE,"ER_DIAGRAM_V2.1.1.svg"),encoding='utf-8').read()
SL=svg.split('\n')

# 1) 用 y 坐标 + 卡片 rect 划分实体区块
# 卡片标题行：font-size="12.5" font-weight="700"
cards=[]
for i,l in enumerate(SL,1):
    m=re.search(r'<text x="(\d+)" y="(\d+)"[^>]*font-size="12\.5"[^>]*font-weight="700"[^>]*>([^<]+)</text>',l)
    if m: cards.append(dict(line=i,x=int(m.group(1)),y=int(m.group(2)),name=m.group(3).strip()))
print("### 卡片标题（%d 个） ###"%len(cards))
for c in cards: print(f"  L{c['line']:4d} y={c['y']:4d} x={c['x']:4d} {c['name']}")

# 2) 每个卡片读取其 rect 高度范围，抽取内部所有 text 行
rects=[]
for l in SL:
    m=re.search(r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)" rx="8"',l)
    if m: rects.append(tuple(int(g) for g in m.groups()))
print("\n### 卡片 rect ###")
for r in rects: print("  ",r)

def region(c):
    # 找标题 y 之前最近且包含它的 rect
    best=None
    for (x,y,w,h) in rects:
        if x<=c['x']<=x+w and y<=c['y']<=y+h:
            if best is None or h>best[3]: best=(x,y,w,h)
    return best
for c in cards:
    r=region(c); c['rect']=r
print("\n### 卡片 -> rect 映射 ###")
for c in cards: print(f"  {c['name']:28s} rect={c['rect']}")
