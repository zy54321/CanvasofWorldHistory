# -*- coding: utf-8 -*-
"""E1–E7 工程边界：对照 ACCEPTANCE §9 基线哈希表"""
import hashlib,os,time,json
ARCH=r"E:/01_Work/01_PersonalProjects/014-CanvasofWorldHistory/设计资料/P0收敛/架构"
NORM=r"E:/01_Work/01_PersonalProjects/014-CanvasofWorldHistory/设计资料/P0收敛/WB-002/normalized"
NORMZ=r"E:/01_Work/01_PersonalProjects/014-CanvasofWorldHistory/code/p0/wb-002-normalize/normalize.py"
BASE=[
 ("架构/CORE_DATA_MODEL_V2.md", os.path.join(ARCH,"CORE_DATA_MODEL_V2.md"), 128784, "91b459a8070364df"),
 ("架构/V2.1/CORE_DATA_MODEL_V2.1.md", os.path.join(ARCH,"V2.1","CORE_DATA_MODEL_V2.1.md"), 70016, "ec118b60638244c8"),
 ("架构/V2.1/IMPORT_RULES_V2.1.md", os.path.join(ARCH,"V2.1","IMPORT_RULES_V2.1.md"), 25677, "6cbcefedc212ec2d"),
 ("架构/V2.1/ER_DIAGRAM_V2.1.svg", os.path.join(ARCH,"V2.1","ER_DIAGRAM_V2.1.svg"), 28295, "3853eeba963b3501"),
 ("架构/V2.1/FIELD_MAPPING_V2.1.csv", os.path.join(ARCH,"V2.1","FIELD_MAPPING_V2.1.csv"), 25625, "50fca40335f40066"),
 ("架构/V2.1/FIELD_MAPPING_V2.1.md", os.path.join(ARCH,"V2.1","FIELD_MAPPING_V2.1.md"), 7577, "043ba35adb7fb7ac"),
 ("架构/V2.1/ROLLBACK...V2.1.md", os.path.join(ARCH,"V2.1","ROLLBACK_AND_MANUAL_PROTECTION_V2.1.md"), 15078, "efb934d94bed9aac"),
 ("架构/V2.1/LICENSE_GATE_V2.1.md", os.path.join(ARCH,"V2.1","LICENSE_GATE_V2.1.md"), 16040, "b2ab5754eeff475d"),
 ("架构/V2.1/V2.1_QA_REPORT.md", os.path.join(ARCH,"V2.1","V2.1_QA_REPORT.md"), 14164, "b30eeb24b061b449"),
 ("架构/V2.1/V2_TO_V2.1_CHANGELOG.md", os.path.join(ARCH,"V2.1","V2_TO_V2.1_CHANGELOG.md"), 15601, "acf35d865cc3d68a"),
 ("架构/V2.1.1/00_PROBLEM_LIST_AND_PLAN.md", os.path.join(ARCH,"V2.1.1","00_PROBLEM_LIST_AND_PLAN.md"), 190222, "0a9c56fbfc002769"),
 ("架构/V2.1.1/V0.2.2/...V0.2.2.md", os.path.join(ARCH,"V2.1.1","V0.2.2","00_PROBLEM_LIST_AND_PLAN_V0.2.2.md"), 105526, "0356ff721a7fb4f1"),
 ("架构/V2.1.1/V0.2.2/V0.2.1_TO_V0.2.2_CHANGELOG.md", os.path.join(ARCH,"V2.1.1","V0.2.2","V0.2.1_TO_V0.2.2_CHANGELOG.md"), 69320, "881087457b59d38a"),
 ("WB-002/normalized/data_datasets.csv", os.path.join(NORM,"data_datasets.csv"), 6018, "fa44197e54b4da4a"),
 ("WB-002/normalized/source_records.csv", os.path.join(NORM,"source_records.csv"), 26942777, "30fed0e40ba12496"),
 ("WB-002/normalized/historical_places.csv", os.path.join(NORM,"historical_places.csv"), 4953976, "86db3ce6b94f9e31"),
 ("WB-002/normalized/historical_place_names.csv", os.path.join(NORM,"historical_place_names.csv"), 8937942, "80674c0ded553241"),
 ("WB-002/normalized/historical_place_locations.csv", os.path.join(NORM,"historical_place_locations.csv"), 11698567, "9e987ba578e933ed"),
 ("WB-002/normalized/candidate_matches.csv", os.path.join(NORM,"candidate_matches.csv"), 17315204, "4e29c2ec64ebe263"),
 ("WB-002/normalized/data_quality_issues.csv", os.path.join(NORM,"data_quality_issues.csv"), 5277273, "7a8ab3916e00dcb0"),
 ("code/p0/wb-002-normalize/normalize.py", NORMZ, 102275, "4a0a6fed7f656de5"),
]
print("### E1–E7 工程边界复核（sha256 原始字节前 16 位） ###")
bad=[]
for label,p,eb,eh in BASE:
    if not os.path.exists(p):
        print(f"  ❌ 文件不存在: {p}"); bad.append(label); continue
    b=open(p,'rb').read(); h=hashlib.sha256(b).hexdigest()[:16]
    okb = len(b)==eb; okh = h==eh
    flag='✅' if (okb and okh) else '❌'
    if not(okb and okh): bad.append(label)
    print(f"  {flag} {label:52s} 字节={len(b):>9,}/{eb:>9,} sha={h}/{eh}")
print(f"\n  边界违例 = {len(bad)}  {'PASS ✅' if not bad else 'FAIL ❌'}")
for x in bad: print("     ",x)
print("\n### E7：DDL/Migration/Git 痕迹（交付目录内不应有） ###")
vdir=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for root,dirs,files in os.walk(ARCH):
    for fn in files:
        if fn.lower().endswith(('.sql','.migration','.bak')) and 'V2.1.1' in root:
            print("   可疑:",os.path.join(root,fn))
print("   （无输出=未发现）")
