#!/usr/bin/env python
"""M4-5 · 地点级时间包络的针对性单元测试

覆盖两件事（其余行为由「其余六张 CSV 逐字节不变」这条更强的证据守住）：

1. **connection 子记录被排除**。这是本轮唯一的行为改动，也是 820 行差异的成因。
2. **地点自身的时间记录照常计算**。包括 name/location 混合、``time_bound_type``
   过滤、两侧都无证据时回到 ``unknown`` + ``none``。

运行：
    python ops/m4-5/test_time_envelope.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_ROOT / "p0" / "wb-002-normalize"))

from extra_record import ExtraRecord  # noqa: E402
from normalize import PlaceGroup, _place_time_bounds  # noqa: E402

DATASET = "pleiades_gis_4_1"


def child(
    kind: str,
    from_year=None,
    to_year=None,
    bound_type: str = "tpq_taq",
    index: int = 1,
) -> ExtraRecord:
    """Build one child row of the requested kind.

    Args:
      kind: ``name`` / ``location`` / ``connection``.
      from_year: Historical (no year zero) lower bound, e.g. ``-330`` for 331 BCE.
      to_year: Historical upper bound.
      bound_type: ``tpq_taq`` / ``bounded`` / ``unknown``.
      index: Record index, only used to keep rows distinguishable.
    """
    return ExtraRecord(
        dataset_id=DATASET,
        source_id="pleiades",
        source_dataset=DATASET,
        record_kind=kind,
        record_index=index,
        raw_file=f"{kind}s.csv",
        raw={},
        external_id=f"{kind}-{index}",
        external_id_type=f"pleiades_{kind}_id",
        parent_external_id="1000",
        time_bound_type=bound_type,
        valid_from_year=from_year,
        valid_to_year=to_year,
    )


def group(dataset: str = DATASET) -> PlaceGroup:
    """A bare place group; the envelope function only reads ``source_dataset``."""
    return PlaceGroup(source_dataset=dataset, external_id="1000", dataset_id=dataset)


class ConnectionExclusionTest(unittest.TestCase):
    """connection 的时间声明不得改变地点的时间跨度。"""

    def test_connection_wider_than_place_is_ignored(self):
        """连接比地点本身早 900 年、晚 500 年时，地点包络取地点自己的值。"""
        children = [
            child("name", -200, -100, index=1),
            # 一条"属于某帝国"的关系，把年代拉到 -899..401
            child("connection", -900, 400, index=2),
        ]
        result = _place_time_bounds(group(), children)
        # hist -200 -> astro -199；hist -100 -> astro -99
        self.assertEqual(result, ("-199", "-99", "derived_tpq_taq", "tpq_taq_of_children"))

    def test_connection_narrower_than_place_is_also_ignored(self):
        """连接比地点窄时同样不参与：包络不是"取交集"，是完全不看 connection。"""
        children = [
            child("location", -500, 300, index=1),
            child("connection", 100, 150, index=2),
        ]
        self.assertEqual(
            _place_time_bounds(group(), children),
            ("-499", "300", "derived_tpq_taq", "tpq_taq_of_children"),
        )

    def test_place_with_only_connections_has_no_time(self):
        """只有连接、没有任何名称/位置纪年的地点：地点级时间必须留空。"""
        children = [child("connection", -29, 300, index=1)]
        self.assertEqual(_place_time_bounds(group(), children), ("", "", "unknown", "none"))

    def test_many_connections_do_not_widen(self):
        """多条连接叠加也不得把包络拉开。"""
        children = [child("name", 100, 200, index=1)]
        children += [child("connection", -6499, 651, index=i) for i in range(2, 12)]
        self.assertEqual(
            _place_time_bounds(group(), children),
            ("100", "200", "derived_tpq_taq", "tpq_taq_of_children"),
        )


class OwnRecordsTest(unittest.TestCase):
    """地点自身的时间记录照常聚合（不得因本轮改动而失效）。"""

    def test_name_and_location_are_unioned(self):
        """name 与 location 取并集的最宽处：最早 TPQ、最晚 TAQ。"""
        children = [
            child("name", -500, -400, index=1),
            child("location", -450, 200, index=2),
        ]
        self.assertEqual(
            _place_time_bounds(group(), children),
            ("-499", "200", "derived_tpq_taq", "tpq_taq_of_children"),
        )

    def test_bound_types_outside_the_pair_are_skipped(self):
        """``time_bound_type='unknown'`` 的子行不参与包络（既有行为，保持）。"""
        children = [
            child("name", 100, 200, index=1),
            child("location", 50, 900, bound_type="unknown", index=2),
        ]
        self.assertEqual(
            _place_time_bounds(group(), children),
            ("100", "200", "derived_tpq_taq", "tpq_taq_of_children"),
        )

    def test_bounded_children_are_included(self):
        """``bounded`` 与 ``tpq_taq`` 一视同仁。"""
        children = [
            child("name", 100, 200, index=1),
            child("location", 150, 300, bound_type="bounded", index=2),
        ]
        self.assertEqual(
            _place_time_bounds(group(), children),
            ("100", "300", "derived_tpq_taq", "tpq_taq_of_children"),
        )

    def test_year_zero_is_rejected_not_silently_used(self):
        """历史纪年没有 0 年；出现 0 时该侧不参与，而不是当作公元 0 年。"""
        children = [child("name", 0, 200, index=1)]
        self.assertEqual(
            _place_time_bounds(group(), children),
            ("", "200", "derived_tpq_taq", "tpq_taq_of_children"),
        )


class UntouchedSourcesTest(unittest.TestCase):
    """本轮只动 Pleiades 分支，其余数据集的返回必须原样。

    MCGD 走自己的分支、没有子行时间可聚合；WHG 本来就在
    ``EXTRA_SOURCE_DATASETS`` 里，靠自己的子行派生——这两条都不受本轮影响，
    在此钉住，防止"顺手扩大修复范围"。
    """

    def test_mcgd_still_has_no_place_time(self):
        self.assertEqual(
            _place_time_bounds(group("mcgd_zenodo_22094815_head960"),
                               [child("location", 100, 200)]),
            ("", "", "unknown", "none"),
        )

    def test_whg_still_derives_from_its_own_children(self):
        self.assertEqual(
            _place_time_bounds(group("whg_api_sample"), [child("location", 100, 200)]),
            ("100", "200", "derived_tpq_taq", "tpq_taq_of_children"),
        )

    def test_chgis_keeps_min_max_of_children(self):
        """CHGIS 分支读的是 ``group.chgis_records``，与 children 无关，本轮未动。"""
        from normalize import _place_time_bounds as fn  # noqa: PLC0415

        bare = PlaceGroup(source_dataset="chgis_pref", external_id="1", dataset_id="chgis_pref")
        self.assertEqual(fn(bare, []), ("", "", "unknown", "none"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
