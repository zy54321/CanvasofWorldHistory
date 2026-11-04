#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""M4-4a 可重复性测试：同输入 + 同时间戳 ⇒ 逐字节相同的七张 CSV。

做法：把流水线跑到两个临时目录（不碰 ``code/data/staging_m4_3``），
再与已交付的目录三方比对 sha256。

为什么可以做到逐字节相同
------------------------
只有三个不确定源，全部被按住：
  1. ``ingested_at``：默认固定为 ``2026-11-04T00:00:00Z``（``--timestamp`` 可覆盖）；
  2. 字典/集合迭代顺序：``build_bundle`` 内部处处先排序再输出；
  3. id 分配：``_IdAllocator`` 按固定顺序递增，数据集顺序写死在 ``DATASET_ORDER``。

用法：
    cd code
    PYTHONPATH=ops/.deps python ops/m4-4a/check_reproducibility.py

退出码：0 三方一致；1 有不一致（会打印哪个文件、差在哪）。
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[2]
DELIVERED = CODE_ROOT / "data" / "staging_m4_3"
FILES = [
    "historical_places.csv",
    "historical_place_names.csv",
    "historical_place_locations.csv",
    "source_records.csv",
    "data_quality_issues.csv",
    "candidate_matches.csv",
    "data_datasets.csv",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_into(target: Path) -> None:
    """Run the builder into ``target``; raises on a non-zero exit."""
    result = subprocess.run(
        [sys.executable, str(CODE_ROOT / "ops" / "m4-4a" / "build_staging_m4_3.py"),
         "--out-dir", str(target), "--quiet"],
        cwd=str(CODE_ROOT), capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"构建失败（{target}）：\n{result.stdout}\n{result.stderr}")


def main() -> int:
    print("M4-4a 可重复性测试（两次独立构建 + 与交付目录三方比对）")
    if not DELIVERED.is_dir():
        raise SystemExit(f"交付目录不存在：{DELIVERED}")

    roots = []
    try:
        for round_no in (1, 2):
            target = Path(tempfile.mkdtemp(prefix=f"m4-4a-repro-{round_no}-"))
            roots.append(target)
            print(f"  第 {round_no} 次构建 → {target}")
            build_into(target)

        reference = {name: sha256(DELIVERED / name) for name in FILES}
        failures = 0
        for round_no, target in enumerate(roots, start=1):
            for name in FILES:
                got = sha256(target / name)
                same = got == reference[name]
                print(f"  {'✓' if same else '✗'} 第 {round_no} 次 {name:34s} {got[:16]}…"
                      + ("" if same else f"  交付={reference[name][:16]}…"))
                if not same:
                    failures += 1
        for name in FILES:
            a = sha256(roots[0] / name)
            b = sha256(roots[1] / name)
            if a != b:
                print(f"  ✗ 两次构建彼此不同：{name}")
                failures += 1
        print()
        print(f"结论：{'三方逐字节一致' if failures == 0 else f'{failures} 处不一致'}")
        return 0 if failures == 0 else 1
    finally:
        for target in roots:
            shutil.rmtree(target, ignore_errors=True)


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
