"""Registry of imported datasets -- the single source for ``data_datasets.csv``.

Every row of ``source_records.csv`` carries a ``dataset_id`` that resolves to one
row here.  A *source* is an organisation or project (CHGIS, MCGD, Pleiades,
WHG); a *dataset* is one concrete file set obtained and imported as a unit.
CHGIS ships two independent layers, so it contributes two dataset rows; the WHG
sample mixes three upstream gazetteers, so it contributes three.

M4-2：本模块不再记录许可字段（license_id / license_url / redistributable /
attribution_text 已从 ``data_datasets.csv`` 删除）。系统不建设许可门禁、许可审核
或任何许可完整性检查，数据授权由 Owner 自行负责；``attribution_text`` 只作为
引用串写入 ``source_records``，不参与任何准入判定。

Nothing in this module is inferred at run time: every string below was read from
a file in the read-only sample tree and the ``evidence`` column names where.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

__all__ = [
    "DatasetInfo",
    "PLEIADES_ATTRIBUTION",
    "MCGD_ATTRIBUTION",
    "CHGIS_CITATION_README",
    "DATASET_IDS",
    "DATASETS",
    "DATA_DATASETS_COLUMNS",
    "get_dataset",
    "iter_datasets",
]

#: Column order of ``data_datasets.csv``, fixed by the WB-002 specification.
#: M4-2：``license_id`` / ``license_url`` / ``redistributable`` / ``attribution_text`` 四列已按
#: Owner 决策删除（系统不建设许可门禁、不做许可完整性检查；授权由 Owner 自行负责）。
DATA_DATASETS_COLUMNS: Sequence[str] = (
    "dataset_id",
    "source_id",
    "dataset_name",
    "homepage",
    "acquisition_method",
    "evidence",
    "notes",
)


@dataclass(frozen=True)
class DatasetInfo:
    """One imported dataset.

    Attributes:
      dataset_id: Stable identifier referenced by ``source_records.dataset_id``.
      source_id: Owning source, matching ``source_records.source_id``.
      dataset_name: Human name of the concrete file set.
      homepage: Canonical human-facing URL.
      attribution_text: Verbatim citation string carried with each record in
        ``source_records.attribution_text``. Retained as provenance; it is not a
        licence assertion and gates nothing (M4-2).
      acquisition_method: How the bytes were obtained, e.g. HTTP Range slice.
      evidence: Project-relative path (and field path or line range) proving the
        acquisition method and values.
      notes: Caveats a reviewer must not miss.
    """

    dataset_id: str
    source_id: str
    dataset_name: str
    homepage: str
    attribution_text: str
    acquisition_method: str
    evidence: str
    notes: str

    def as_row(self) -> Dict[str, str]:
        """Render the dataset as a ``data_datasets.csv`` row."""
        return {
            "dataset_id": self.dataset_id,
            "source_id": self.source_id,
            "dataset_name": self.dataset_name,
            "homepage": self.homepage,
            "acquisition_method": self.acquisition_method,
            "evidence": self.evidence,
            "notes": self.notes,
        }


#: Official CHGIS citation string, carried verbatim into
#: ``source_records.attribution_text``. M4-2 removed the EULA/SPDX bookkeeping:
#: licensing is the Owner's responsibility and gates nothing here.
CHGIS_CITATION_README = (
    'CHGIS, Version: 6. (c) Fairbank Center for Chinese Studies of Harvard '
    "University and the Center for Historical Geographical Studies at Fudan "
    "University, 2016."
)

#: Pleiades attribution, carried verbatim into ``source_records.attribution_text``.
PLEIADES_ATTRIBUTION = (
    "Pleiades: A community-built gazetteer and graph of ancient places. "
    "Copyright (c) Institute for the Study of the Ancient World. "
    "Licensed CC BY 3.0."
)

#: MCGD attribution, from the cached Zenodo record 22094815.
MCGD_ATTRIBUTION = "Christian Henriot / ENP-China, MCGD (Zenodo 22094815), CC BY 4.0"

#: GeoNames attribution string, copied verbatim from
#: ``whg/api/place/gn_*.json`` -> ``attribution.citation_text``.
WHG_GN_ATTRIBUTION = "GeoNames geographical database, Unxos GmbH."

#: Getty TGN attribution string, copied verbatim from
#: ``whg/api/place/tgn_7011781_london.json`` -> ``attribution.citation_text``.
WHG_TGN_ATTRIBUTION = "Getty Thesaurus of Geographic Names (TGN), J. Paul Getty Trust."

#: WHG sample datasets in the fixed order used for stable id allocation.
DATASETS: Tuple[DatasetInfo, ...] = (
    DatasetInfo(
        dataset_id="chgis_v6_prefecture_points",
        source_id="chgis",
        dataset_name="CHGIS V6 time_pref_pts (prefecture-level point layer)",
        homepage="https://sites.fas.harvard.edu/~chgis/",
        attribution_text=CHGIS_CITATION_README,
        acquisition_method="full DBF + sidecars read from the shipped V6 zip",
        evidence=(
            "sample_data/chgis/CHGIS_V6_README.txt line 'Citation:' supplies the "
            "verbatim citation string carried into source_records.attribution_text"
        ),
        notes=(
            "The V6 zip's own EULA carries a second, differently worded citation "
            "(differences in the punctuation of 'Version 6', 'Center for Historical "
            "Geographical Studies' vs 'Institute for Chinese Historical Geography', "
            "and '2016' vs 'Dec 2016'). Only the README form is emitted, because that "
            "is what ships with the point layers this dataset is built from. "
            "Licensing is the Owner's responsibility (M4-2); nothing here gates import."
        ),
    ),
    DatasetInfo(
        dataset_id="chgis_v6_county_points",
        source_id="chgis",
        dataset_name="CHGIS V6 time_cnty_pts (county-level point layer)",
        homepage="https://sites.fas.harvard.edu/~chgis/",
        attribution_text=CHGIS_CITATION_README,
        acquisition_method="full DBF + sidecars read from the shipped V6 zip",
        evidence=(
            "same zip family and same EULA as chgis_v6_prefecture_points; the "
            ".prj sidecar inside the county zip is GEOGCS[\"GCS_WGS_1984\"]"
        ),
        notes=(
            "Second CHGIS layer, listed separately because LEV_RANK, field order "
            "and BEG_RULE completeness differ from the prefecture layer. Licence "
            "terms identical."
        ),
    ),
    DatasetInfo(
        dataset_id="mcgd_zenodo_22094815_head960",
        source_id="mcgd",
        dataset_name="MCGD (Modern China Geospatial Database) 2026-08-25, first 960 rows",
        homepage="https://doi.org/10.5281/zenodo.22094815",
        attribution_text=MCGD_ATTRIBUTION,
        acquisition_method="head slice of the CSV, 960 data rows, taken upstream",
        evidence=(
            "sample_data/mcgd/zenodo_record_22094815.json -> metadata.license.id = "
            "'cc-by-4.0'; metadata.access_right = 'open'"
        ),
        notes=(
            "Row count is a fixed head slice, not the full dataset: any frequency "
            "computed here describes the slice, not MCGD."
        ),
    ),
    DatasetInfo(
        dataset_id="pleiades_gis_4_1_slice",
        source_id="pleiades",
        dataset_name="Pleiades GIS CSV export (data/gis), 1 MB head slices",
        homepage="https://pleiades.stoa.org/",
        attribution_text=PLEIADES_ATTRIBUTION,
        acquisition_method="from_slice=1MB_head; HTTP Range bytes=0-1048575 per file",
        evidence=(
            "sample_data_pleiades/FETCH_LOG.tsv records the URL, HTTP 206, the "
            "returned range and the sha256 of each slice; "
            "sample_data/pleiades/datasets_docs/LICENSE_CC-BY-3.0.txt is the "
            "Attribution 3.0 Unported text; datasets_docs/README.md states 'All "
            "content is distributed under the terms of a Creative Commons "
            "Attribution license (cc-by)'"
        ),
        notes=(
            "Five files were sliced (places, names, location_points, connections, "
            "time_periods). Each slice is truncated mid-record at 1,048,576 bytes, "
            "so the last CSV row of four of the five files is incomplete and is "
            "discarded as issue_type='truncated_slice_tail'. Frequencies describe "
            "the slice, not Pleiades. time_periods.csv is a reference vocabulary "
            "and is counted but not turned into place rows."
        ),
    ),
    DatasetInfo(
        dataset_id="whg_geoname_s_gn_sample",
        source_id="whg",
        dataset_name="WHG API place records, GeoNames (gn) namespace sample",
        homepage="https://whgazetteer.org/",
        attribution_text=WHG_GN_ATTRIBUTION,
        acquisition_method="whg_api_single_record_get (/entity/place:gn:<id>/api)",
        evidence=(
            "sample_data/whg/api/place/gn_*.json -> attribution.license__spdx_id = "
            "'CC-BY-4.0', attribution.redistributable = true, "
            "attribution.license__attribution_required = true, "
            "attribution.citation_text = 'GeoNames geographical database, Unxos "
            "GmbH.'; identical across all four gn samples"
        ),
        notes=(
            "Licence is asserted per record by WHG, not by this pipeline: the "
            "sample carries attribution.license__spdx_id on every gn record."
        ),
    ),
    DatasetInfo(
        dataset_id="whg_getty_tgn_sample",
        source_id="whg",
        dataset_name="WHG API place records, Getty TGN (tgn) namespace sample",
        homepage="https://whgazetteer.org/",
        attribution_text=WHG_TGN_ATTRIBUTION,
        acquisition_method="whg_api_single_record_get (/entity/place:tgn:<id>/api)",
        evidence=(
            "sample_data/whg/api/place/tgn_7011781_london.json -> "
            "attribution.license__spdx_id = 'ODC-By-1.0', "
            "attribution.license__label = 'Open Data Commons Attribution License "
            "v1.0', attribution.citation_text = 'Getty Thesaurus of Geographic "
            "Names (TGN), J. Paul Getty Trust.'"
        ),
        notes=(
            "ODC-By-1.0 requires attribution and a notice of modifications; it is "
            "not share-alike. One sample record only."
        ),
    ),
    DatasetInfo(
        dataset_id="whg_hgis_de_las_indias_sample",
        source_id="whg",
        dataset_name="WHG API place records, HGIS de las Indias (hgis) dataset sample",
        homepage="https://www.hgis-indias.net/",
        attribution_text="",
        acquisition_method="whg_api_single_record_get (/entity/place:<id>/api)",
        evidence=(
            "sample_data/whg/api/place/169687.json and 169687-169688.json contain "
            "no 'attribution' key and no key matching licen/right/attribut; they "
            "use the older flat schema (top-level keys id, title, names, types, "
            "fclasses, geoms, extent, minmax, countries, datasets, ...). Falling "
            "back to sample_data/whg/api/sources.json -> namespace 'hgis' gives "
            "redistributable: true, downloadable: true, but that file contains no "
            "SPDX or licence field for any of its 28 namespaces."
        ),
        notes=(
            "No attribution block: the flat HGIS records carry no 'attribution' key. "
            "Per-record attribution is therefore empty and the two records surface as "
            "issue_type='attribution_missing' (severity info) in the quality ledger — "
            "this does not gate import (M4-2: attribution is optional provenance, "
            "licensing is the Owner's responsibility). dates come from minmax, not "
            "from a documented time field."
        ),
    ),
    DatasetInfo(
        dataset_id="pleiades_gis_4_1",
        source_id="pleiades",
        dataset_name="Pleiades Datasets v4.1 — GIS CSV (complete package)",
        homepage="https://doi.org/10.5281/zenodo.15540082",
        attribution_text=PLEIADES_ATTRIBUTION,
        acquisition_method=(
            "Zenodo record 15540082, file pleiades.datasets-v4.1.zip "
            "(286,621,469 B, md5 ad339c92c6b895f0eb9a52228da498c4), unpacked to "
            "code/data/raw/pleiades_gis_4_1/gis/"
        ),
        evidence=(
            "code/ops/m4-3/audit.json: 19 files, 128,705,151 B, per-file sha256; "
            "code/data/raw/pleiades_gis_4_1/gis_sha256.txt is the same digest list; "
            "verification and coverage analysis in "
            "code/ops/reports/M4_3_PLEIADES_GIS_ACQUISITION_REPORT.md"
        ),
        notes=(
            "M4-4a 全量接入。与 pleiades_gis_4_1_slice 是同一来源的两个快照："
            "41,480 个地点中 2,552 个已由切片快照承载，本数据集只为它们写 "
            "is_active=false 的源记录，不重复建点（增量方案 A）。"
            "四个词表文件与 places_accuracy / places_place_types 不逐行入表，"
            "承载方式见 code/ops/reports/M4_3_FILE_BEARING_MATRIX.md。"
        ),
    ),
)

#: Ordered dataset identifiers.
DATASET_IDS: Tuple[str, ...] = tuple(dataset.dataset_id for dataset in DATASETS)

_BY_ID: Dict[str, DatasetInfo] = {dataset.dataset_id: dataset for dataset in DATASETS}


def get_dataset(dataset_id: str) -> DatasetInfo:
    """Look a dataset up by id.

    Args:
      dataset_id: One of :data:`DATASET_IDS`.

    Returns:
      The matching :class:`DatasetInfo`.

    Raises:
      KeyError: If the identifier is unknown, which would mean a record was
        emitted without a registry entry.
    """
    return _BY_ID[dataset_id]


def iter_datasets() -> List[DatasetInfo]:
    """Return every dataset in declaration order."""
    return list(DATASETS)
