import hashlib, os, sys, json, time

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
files = [
 ("CORE_DATA_MODEL_V2.1.1.md", 149607, 1720, "34ff192009a5d2dd"),
 ("ER_DIAGRAM_V2.1.1.svg", 60681, 458, "0fafbee24fbf720b"),
 ("IMPORT_RULES_V2.1.1.md", 52925, 773, "efbbe99b19e83e4d"),
 ("FIELD_MAPPING_V2.1.1.csv", 44248, 222, "d06e7d47dc37b6e5"),
 ("ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md", 74963, 1060, "15089fb35715b4b9"),
 ("DATA_PROVENANCE_V2.1.1.md", 41084, 561, "05164fc50c8e1385"),
 ("V2.1_TO_V2.1.1_CHANGELOG.md", 150397, 1294, "5c80f224876983de"),
]
out=[]
for name, eb, el, eh in files:
    p = os.path.join(BASE, name)
    b = open(p,'rb').read()
    h = hashlib.sha256(b).hexdigest()[:16]
    lf = b.count(b'\n')
    st = os.stat(p)
    ok = (h==eh)
    out.append(dict(file=name, bytes=len(b), exp_bytes=eb, lf=lf, exp_lf=el,
                    sha=h, exp_sha=eh, hash_ok=ok, bytes_ok=len(b)==eb, lf_ok=lf==el,
                    mtime=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))))
print(json.dumps(out, ensure_ascii=False, indent=1))
print("ALL_HASH_OK=", all(o['hash_ok'] for o in out))
