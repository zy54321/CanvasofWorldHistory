"""Registry of imported datasets -- the single source for ``data_datasets.csv``.

Every row of ``source_records.csv`` carries a ``dataset_id`` that resolves to one
row here.  A *source* is an organisation or project (CHGIS, MCGD, Pleiades,
WHG); a *dataset* is one concrete file set with its own licence terms.  CHGIS
ships two independent layers with the same licence, so it contributes two
dataset rows; the WHG sample mixes three upstream gazetteers whose licences
differ, so it contributes three.

Nothing in this module is inferred at run time: every string below was read from
a file in the read-only sample tree and the ``evidence`` column names where.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

__all__ = [
    "DatasetInfo",
    "PLEIADES_ATTRIBUTION",
    "PLEIADES_LICENSE_ID",
    "MCGD_ATTRIBUTION",
    "CHGIS_CITATION_README",
    "CHGIS_CITATION_EULA",
    "DATASET_IDS",
    "DATASETS",
    "DATA_DATASETS_COLUMNS",
    "get_dataset",
    "iter_datasets",
]

#: Column order of ``data_datasets.csv``, fixed by the WB-002 specification.
DATA_DATASETS_COLUMNS: Sequence[str] = (
    "dataset_id",
    "source_id",
    "dataset_name",
    "homepage",
    "license_id",
    "license_url",
    "redistributable",
    "attribution_text",
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
      license_id: SPDX identifier or a verbatim ``unconfirmed``-style marker.
      license_url: Licence deed URL, empty when no licence text was located.
      redistributable: ``yes`` / ``yes_with_attribution`` / ``no`` /
        ``unconfirmed``.
      attribution_text: Verbatim attribution string that must travel with any
        redistribution.
      acquisition_method: How the bytes were obtained, e.g. HTTP Range slice.
      evidence: Project-relative path (and field path or line range) proving the
        licence and attribution values.
      notes: Caveats a reviewer must not miss.
    """

    dataset_id: str
    source_id: str
    dataset_name: str
    homepage: str
    license_id: str
    license_url: str
    redistributable: str
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
            "license_id": self.license_id,
            "license_url": self.license_url,
            "redistributable": self.redistributable,
            "attribution_text": self.attribution_text,
            "acquisition_method": self.acquisition_method,
            "evidence": self.evidence,
            "notes": self.notes,
        }


#: The two conflicting official CHGIS citation strings.  Both are recorded
#: because the pipeline must not silently pick a winner.
CHGIS_CITATION_README = (
    'CHGIS, Version: 6. (c) Fairbank Center for Chinese Studies of Harvard '
    "University and the Center for Historical Geographical Studies at Fudan "
    "University, 2016."
)
CHGIS_CITATION_EULA = (
    '"CHGIS Version 6." (c) Fairbank Center for Chinese Studies and the '
    "Institute for Chinese Historical Geography at Fudan University, Dec 2016."
)

#: Pleiades licence identifier and attribution.  ``CC-BY-3.0`` comes from
#: ``datasets_docs/LICENSE_CC-BY-3.0.txt`` ("Attribution 3.0 Unported") and the
#: repository README statement "All content is distributed under the terms of a
#: Creative Commons Attribution license (cc-by)".
PLEIADES_LICENSE_ID = "CC-BY-3.0"
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
        license_id="no_spdx_academic_noncommercial",
        license_url="https://doi.org/10.7910/DVN/FDLFJ3",
        redistributable="no",
        attribution_text=CHGIS_CITATION_README,
        acquisition_method="full DBF + sidecars read from the shipped V6 zip",
        evidence=(
            "sample_data/chgis/api/dataset_FDLFJ3_EULA.json -> termsOfUse clause (3) "
            "forbids redistribution and clause (4) mandates the citation string; "
            "data.latestVersion.license is null (no SPDX identifier exists); "
            "sample_data/chgis/CHGIS_V6_README.txt line 'Citation:' supplies a "
            "second, differently worded citation"
        ),
        notes=(
            "The README citation and the EULA mandatory citation disagree on three "
            "points (punctuation of 'Version 6', 'Center for Historical "
            "Geographical Studies' vs 'Institute for Chinese Historical "
            "Geography', and '2016' vs 'Dec 2016'). Both are recorded verbatim: "
            "source_records.attribution_text keeps the README form because that is "
            "what the shipped file says, and data_datasets.csv records the "
            "conflict. Local analysis only; never redistribute."
        ),
    ),
    DatasetInfo(
        dataset_id="chgis_v6_county_points",
        source_id="chgis",
        dataset_name="CHGIS V6 time_cnty_pts (county-level point layer)",
        homepage="https://sites.fas.harvard.edu/~chgis/",
        license_id="no_spdx_academic_noncommercial",
        license_url="https://doi.org/10.7910/DVN/FDLFJ3",
        redistributable="no",
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
        license_id="CC-BY-4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        redistributable="yes_with_attribution",
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
        license_id="CC-BY-3.0",
        license_url="https://creativecommons.org/licenses/by/3.0/",
        redistributable="yes_with_attribution",
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
        license_id="CC-BY-4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        redistributable="yes_with_attribution",
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
        license_id="ODC-By-1.0",
        license_url="https://opendatacommons.org/licenses/by/1-0/",
        redistributable="yes_with_attribution",
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
        license_id="unconfirmed",
        license_url="",
        redistributable="unconfirmed",
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
            "BLOCKING FOR PUBLICATION: 'can be redistributed' is confirmed, 'under "
            "which licence' is not. Rows are imported for local analysis with "
            "redistributable='unconfirmed'; they must not be published until the "
            "dataset's own licence is obtained. dates come from minmax, not from a "
            "documented time field."
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
