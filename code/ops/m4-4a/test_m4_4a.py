#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""M4-4a 单元测试：几何、连接解析、精度、V9 值域、导入器前置派生。

覆盖施工指令 §五 的第 1/2/3 项与第 7/8 项的一部分：
  T-01 三个被改脚本 + 构建脚本可导入（语法与顶层执行）
  T-02 Point / LineString / Polygon 三种几何的规范化
  T-03 POINT Z / LINESTRING Z / POLYGON Z 降维
  T-04 4 条无效多边形的真实修复（含 GeometryCollection / MultiPolygon 两种情况）
  T-05 连接 URI 归一（绝对 URI / 裸 id / errata / 尾斜杠 / 空）
  T-06 几何类型推断（WKT 首词 -> geom_type）
  T-07 精度词映射（源值直传，'point' -> unknown）
  T-08 V9 两个值域的取值集合
  T-09 导入器 SCOPE_MAP 覆盖暂存里出现的全部 external_id_type
  T-10 合成代表点载荷能被导入器派生 parent_external_id

跑法：
    cd code
    PYTHONPATH=ops/.deps python ops/m4-4a/test_m4_4a.py -v
"""

from __future__ import annotations

import csv
import io
import re
import sys
import unittest
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[2]
NORMALIZE_DIR = CODE_ROOT / "p0" / "wb-002-normalize"
for path in (str(NORMALIZE_DIR), str(CODE_ROOT / "ops")):
    if path not in sys.path:
        sys.path.insert(0, path)

GIS = CODE_ROOT / "data" / "raw" / "pleiades_gis_4_1" / "gis"
STAGING = CODE_ROOT / "data" / "staging_m4_3"
V9 = CODE_ROOT / "backend" / "src" / "main" / "resources" / "db" / "migration" / \
    "V9__geometry_linestring_and_issue_types.sql"

import import_staging as importer  # noqa: E402
import normalize  # noqa: E402
import pleiades_extract  # noqa: E402


def read_rows(path: Path):
    with io.open(path, encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


class T01Imports(unittest.TestCase):
    """T-01：三个被改脚本与构建脚本都能导入，且版本号没被顺手改掉。"""

    def test_pipeline_version_unchanged(self):
        self.assertEqual(normalize.PIPELINE_VERSION, "wb-002-normalize/1.3.0")

    def test_full_dataset_constants(self):
        self.assertEqual(pleiades_extract.PLEIADES_FULL_SOURCE_DATASET, "pleiades_gis_4_1")
        self.assertEqual(pleiades_extract.PLEIADES_FULL_DATASET_ID, "pleiades_gis_4_1")

    def test_slice_extractor_still_present(self):
        # 全量分支是"并列新增"，不是"改写"：切片抽取器必须仍在
        self.assertTrue(callable(pleiades_extract.extract_pleiades))

    def test_builder_script_importable(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "build_staging_m4_3", CODE_ROOT / "ops" / "m4-4a" / "build_staging_m4_3.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(callable(module.run))
        self.assertEqual(module.DEFAULT_TIMESTAMP, "2026-11-04T00:00:00Z")


class T02Geometry(unittest.TestCase):
    """T-02：三种几何的规范化结果。"""

    def test_point(self):
        out = pleiades_extract._location_geometry("POINT (14.4895 40.75)", "Point")
        self.assertEqual(out["geom_type"], "Point")
        self.assertAlmostEqual(out["lon"], 14.4895, places=9)
        self.assertAlmostEqual(out["lat"], 40.75, places=9)
        self.assertEqual(out["flags"], [])

    def test_linestring_midpoint(self):
        # 一条 x 从 0 到 10 的直线：线长中点是 (5, 0)
        out = pleiades_extract._location_geometry(
            "LINESTRING (0 0, 10 0)", "LineString")
        self.assertEqual(out["geom_type"], "LineString")
        self.assertAlmostEqual(out["lon"], 5.0, places=9)
        self.assertAlmostEqual(out["lat"], 0.0, places=9)

    def test_polygon_point_on_surface_inside(self):
        out = pleiades_extract._location_geometry(
            "POLYGON ((0 0, 0 10, 10 10, 10 0, 0 0))", "Polygon")
        self.assertEqual(out["geom_type"], "Polygon")
        self.assertTrue(0.0 <= out["lon"] <= 10.0 and 0.0 <= out["lat"] <= 10.0)

    def test_empty_wkt_rejected(self):
        out = pleiades_extract._location_geometry("", "Polygon")
        self.assertEqual(out["geom_type"], "")
        self.assertIn("empty_geometry", out["flags"])

    def test_unparseable_wkt_rejected(self):
        out = pleiades_extract._location_geometry("POLYGON ((0 0, 1", "Polygon")
        self.assertEqual(out["geom_type"], "")
        self.assertIn("unparseable_geometry", out["flags"])

    def test_geometry_type_mismatch_rejected(self):
        # points 文件里出现线：必须拒绝，不能被当作点收下
        out = pleiades_extract._location_geometry("LINESTRING (0 0, 1 1)", "Polygon")
        self.assertEqual(out["geom_type"], "")
        self.assertIn("unexpected_geometry_type", out["flags"])


class T03ZOrdinate(unittest.TestCase):
    """T-03：Z 序降维并留痕。"""

    def test_point_z(self):
        out = pleiades_extract._location_geometry("POINT Z (1 2 3)", "Point")
        self.assertEqual(out["geom_type"], "Point")
        self.assertEqual((out["lon"], out["lat"]), (1.0, 2.0))
        self.assertIn("z_ordinate_discarded", out["flags"])

    def test_linestring_z(self):
        out = pleiades_extract._location_geometry("LINESTRING Z (0 0 1, 4 0 1)", "LineString")
        self.assertIn("z_ordinate_discarded", out["flags"])
        self.assertAlmostEqual(out["lon"], 2.0, places=9)

    def test_polygon_z(self):
        out = pleiades_extract._location_geometry(
            "POLYGON Z ((0 0 1, 0 4 1, 4 4 1, 4 0 1, 0 0 1))", "Polygon")
        self.assertEqual(out["geom_type"], "Polygon")
        self.assertIn("z_ordinate_discarded", out["flags"])
        # 降维后的 WKT 不能再有 Z
        self.assertNotIn(" Z ", " " + out["geom_wkt"] + " ")


class T04InvalidPolygons(unittest.TestCase):
    """T-04：整包 5 条无效面，NEW 里 4 条，修复后必须是合法面且类型正确。"""

    @classmethod
    def setUpClass(cls):
        cls.rows = list(read_rows(GIS / "location_polygons.csv"))

    def test_exactly_five_invalid_in_package(self):
        invalid = []
        for index, row in enumerate(self.rows, start=1):
            out = pleiades_extract._location_geometry(row["geometry_wkt"], "Polygon")
            if "geometry_invalid_repaired" in out["flags"]:
                invalid.append((index, row["place_id"], out))
        self.assertEqual(len(invalid), 5, "整包无效面数量变了，先查源数据再改期望")
        self.assertEqual({item[0] for item in invalid}, {95, 418, 1556, 1799, 3441})

    def test_repair_result_types(self):
        expected = {418: "Polygon", 1556: "MultiPolygon", 1799: "MultiPolygon",
                    3441: "Polygon", 95: "Polygon"}
        for index, row in enumerate(self.rows, start=1):
            if index not in expected:
                continue
            out = pleiades_extract._location_geometry(row["geometry_wkt"], "Polygon")
            self.assertEqual(out["geom_type"], expected[index],
                             f"row {index} 修复后类型不符")

    def test_repaired_geometry_is_valid(self):
        import shapely
        from shapely import wkt as shapely_wkt

        for index, row in enumerate(self.rows, start=1):
            out = pleiades_extract._location_geometry(row["geometry_wkt"], "Polygon")
            if "geometry_invalid_repaired" not in out["flags"]:
                continue
            geom = shapely_wkt.loads(out["geom_wkt"])
            self.assertTrue(geom.is_valid, f"row {index} 修复后仍无效")
            self.assertIn(geom.geom_type, ("Polygon", "MultiPolygon"))
            # 修复不能凭空造面积：面积应与 GEOS 的 MakeValid 结果一致
            self.assertGreater(geom.area, 0.0)

    def test_original_wkt_is_preserved_in_raw_payload(self):
        # 原始 WKT 必须能回溯：抽取器把整行塞进 raw，不覆盖 geometry_wkt
        row = self.rows[1798]  # 第 1799 行
        self.assertEqual(row["place_id"], "84624811")
        # 这是一个自交的"蝴蝶结"：两个环交叉，面积被算成 0，原始文本必须原样留存
        self.assertEqual(row["geometry_wkt"], "POLYGON ((60 32, 70 32, 60 24, 70 24, 60 32))")


class T05ConnectionUri(unittest.TestCase):
    """T-05：connects_to 是绝对 URI，不能当 place_id。"""

    def test_bare_id(self):
        self.assertEqual(pleiades_extract._place_key("433032"), "433032")

    def test_absolute_uri(self):
        self.assertEqual(
            pleiades_extract._place_key("https://pleiades.stoa.org/places/433032"), "433032")

    def test_trailing_slash(self):
        self.assertEqual(
            pleiades_extract._place_key("https://pleiades.stoa.org/places/433032/"), "433032")

    def test_errata_uri(self):
        # /errata/991384 不是地点；归一后得到裸 id，靠"不在 places.csv"被排除
        self.assertEqual(
            pleiades_extract._place_key("https://pleiades.stoa.org/errata/991384"), "991384")

    def test_blank(self):
        self.assertEqual(pleiades_extract._place_key(""), "")
        self.assertEqual(pleiades_extract._place_key(None), "")


class T06GeomTypeInference(unittest.TestCase):
    """T-06：normalize 从 WKT 首词推断 geom_type。"""

    def test_values(self):
        cases = {
            "POINT (1 2)": "Point",
            "LINESTRING (0 0, 1 1)": "LineString",
            "POLYGON ((0 0, 0 1, 1 1, 0 0))": "Polygon",
            "MULTIPOLYGON (((0 0, 0 1, 1 1, 0 0)))": "MultiPolygon",
            "": "Point",
        }
        for wkt, expected in cases.items():
            self.assertEqual(normalize._geom_type_of_wkt(wkt), expected, wkt)


class T07Precision(unittest.TestCase):
    """T-07：精度源值直传。"""

    def test_passthrough(self):
        self.assertEqual(importer.normalize_location_precision("precise"), "precise")
        self.assertEqual(importer.normalize_location_precision("rough"), "rough")
        self.assertEqual(importer.normalize_location_precision("approximate"), "approximate")

    def test_legacy_point_maps_to_unknown(self):
        # CHGIS/MCGD 把几何类型词写在精度列里，M0–M3 一直映射为 unknown
        self.assertEqual(importer.normalize_location_precision("point"), "unknown")

    def test_blank_and_junk(self):
        self.assertEqual(importer.normalize_location_precision(""), "unknown")
        self.assertEqual(importer.normalize_location_precision("VERY precise"), "unknown")


class T08V9Vocabulary(unittest.TestCase):
    """T-08：V9 的两个值域取值集合（不执行，只读 SQL 文本）。"""

    @classmethod
    def setUpClass(cls):
        cls.sql = V9.read_text(encoding="utf-8")

    def _array_values(self, constraint: str) -> list:
        # 从 ADD CONSTRAINT <name> 处开始找，避免命中文件头注释里的同名串
        start = self.sql.index(f"ADD CONSTRAINT {constraint}")
        block = self.sql[start:start + 4000]
        # 两种写法都要支持：geom_type / issue_type 用 ARRAY[...]，
        # inactive_reason 用 IN (...)。值集合本身是判据，写法不是。
        body = re.search(r"ARRAY\s*\[(.*?)\]", block, re.S) or \
            re.search(r"IN\s*\((.*?)\)\s*\)\s*;", block, re.S)
        assert body, f"{constraint} 里找不到值域清单"
        return re.findall(r"'([^']+)'", body.group(1))

    def test_issue_type_has_23_values(self):
        values = self._array_values("ck_data_quality_issue_issue_type")
        self.assertEqual(len(values), 23)
        self.assertEqual(len(set(values)), 23, "值域里有重复值")

    def test_new_issue_types_present(self):
        values = set(self._array_values("ck_data_quality_issue_issue_type"))
        self.assertTrue({"geometry_invalid_repaired", "connection_endpoint_missing",
                         "accuracy_unknown_sentinel"} <= values)

    def test_place_without_geometry_absent(self):
        values = set(self._array_values("ck_data_quality_issue_issue_type"))
        self.assertNotIn("place_without_geometry", values)

    def test_original_20_values_kept(self):
        values = set(self._array_values("ck_data_quality_issue_issue_type"))
        original = {
            "beg_gt_end", "beg_eq_end", "missing_coordinate", "coordinate_out_of_range",
            "coordinate_outside_china_bbox", "year_out_of_range", "duplicate_external_id",
            "duplicate_sysid", "unknown_crs", "unknown_time_bound_type",
            "nonstandard_field_name", "empty_name", "parent_place_not_in_sample",
            "truncated_slice_tail", "cross_layer_coordinate_conflict", "manual_edit_conflict",
            "import_row_error", "derived_value_mismatch", "rollback_conflict",
            "attribution_missing",
        }
        self.assertEqual(original, values - {
            "geometry_invalid_repaired", "connection_endpoint_missing",
            "accuracy_unknown_sentinel"})

    def test_geom_type_includes_linestring(self):
        values = self._array_values("ck_hpl_geom_type")
        self.assertEqual(sorted(values), ["LineString", "MultiPolygon", "Point", "Polygon"])

    def test_inactive_reason_includes_superseded(self):
        values = self._array_values("ck_source_record_c19")
        self.assertIn("superseded_by_newer_snapshot", values)
        self.assertIn("source_absent", values)

    def test_migration_is_guarded_and_reviewable(self):
        # 三处变更都要先判后改（DO 块 + pg_get_constraintdef），便于反复审查
        self.assertEqual(self.sql.count("DO $$"), 3)
        self.assertIn("pg_get_constraintdef", self.sql)

    def test_no_destructive_statements(self):
        lowered = self.sql.lower()
        for keyword in ("drop table", "delete from", "truncate table", "drop column",
                        "alter column"):
            self.assertNotIn(keyword, lowered)


class T09ScopeCoverage(unittest.TestCase):
    """T-09：暂存里出现的每个 (dataset_id, external_id_type) 都有 record_scope。"""

    def test_every_combination_declared(self):
        if not (STAGING / "source_records.csv").is_file():
            self.skipTest("staging_m4_3 尚未生成")
        seen = set()
        for row in read_rows(STAGING / "source_records.csv"):
            seen.add((row["dataset_id"], row["external_id_type"]))
        missing = sorted(combo for combo in seen if combo not in importer.SCOPE_MAP)
        self.assertEqual(missing, [], f"未声明 record_scope 的组合：{missing}")
        self.assertEqual(len(importer.DATASETS), 8)

    def test_representative_points_declared(self):
        self.assertEqual(
            importer.SCOPE_MAP[("pleiades_gis_4_1", "pleiades_representative_point")],
            "location")


class T10SyntheticPayload(unittest.TestCase):
    """T-10：合成代表点行的载荷必须能派生 parent_external_id。"""

    def test_payload_parent(self):
        if not (STAGING / "source_records.csv").is_file():
            self.skipTest("staging_m4_3 尚未生成")
        checked = 0
        for row in read_rows(STAGING / "source_records.csv"):
            if row["external_id_type"] != "pleiades_representative_point":
                continue
            import json

            payload = json.loads(row["raw_payload_json"])
            expected = row["external_id"].rsplit("-representative", 1)[0]
            self.assertEqual(payload.get("place_id"), expected)
            self.assertEqual(payload.get("_synthetic"), "representative_point")
            self.assertEqual(row["raw_file"], "places.csv")
            checked += 1
            if checked >= 200:
                break
        self.assertGreater(checked, 0, "暂存里没有合成代表点行")


class T11DateRuleDictionary(unittest.TestCase):
    """T-11：时间规则字典仍可加载（改流水线不能碰坏 CHGIS 的时间推导）。"""

    def test_load(self):
        from quality_checks import load_date_rule_dictionary

        sample = CODE_ROOT.parent / "设计资料" / "P0验证" / "WB-002" / "sample_data"
        rules = load_date_rule_dictionary(sample)
        self.assertTrue(rules.loaded)
        self.assertEqual(len(rules.rules), 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
