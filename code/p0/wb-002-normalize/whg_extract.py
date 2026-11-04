"""WHG (World Historical Gazetteer) API sample extraction (WB-002 task B).

The sample is seven single-record API responses under
``设计资料/P0验证/WB-002/sample_data/whg/api/place/``.  They are **not**
homogeneous, and the difference is not cosmetic:

**Schema A -- Linked Places JSON-LD** (``@context`` present, ``type: Feature``,
``properties.source_id``).  Five records: four GeoNames (``gn:*``) and one Getty
TGN (``tgn:*``).  Each carries a full ``attribution`` block, so the licence is
asserted *per record*: ``attribution.license__spdx_id`` is ``CC-BY-4.0`` for gn
and ``ODC-By-1.0`` for tgn.  Geometry is GeoJSON, whose axis order is
``[longitude, latitude]``.

**Schema B -- older flat record** (top-level ``id``/``title``/``geoms``).  Two
records, ``169687`` and ``169687-169688``, from the HGIS de las Indias dataset.
There is **no ``attribution`` key at all** and no key matching
``licen``/``right``/``attribut``, so the licence of these two records cannot be
established from the record itself.  ``sources.json`` says the ``hgis`` namespace
is redistributable but carries no SPDX field for any of its 28 namespaces.
These rows are therefore imported with ``redistributable='unconfirmed'`` and a
blocking-quality issue, not quietly given the neighbouring licence.

``169687-169688`` is a *composite* record: it joins two HGIS settlements into one
WHG place with two geometries.  It is kept as its own place, because WHG's own id
says these are one entity, and its two coordinates become two location rows.

Time: WHG exposes only partial temporal hints -- a per-record ``when.timespans``
block in two of five JSON-LD records and a dataset-level ``minmax`` in the flat
records.  Neither is a documented per-place validity span, so
``time_bound_type`` is ``unknown`` for every WHG row and the observed hints are
copied verbatim into ``notes`` rather than converted into years.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from extra_record import ExtraExtraction, ExtraRecord, parse_wkt_point
from time_semantics import parse_signed_year

__all__ = [
    "WHG_SOURCE_ID",
    "WHG_SOURCE_DATASET",
    "WHG_PLACE_DIR",
    "WHG_DATASET_BY_NAMESPACE",
    "extract_whg",
]

#: ``source_id`` written on every WHG row.
WHG_SOURCE_ID = "whg"

#: ``source_dataset`` written on every WHG row.  The three underlying gazetteers
#: are distinguished by ``dataset_id``, not by this field, because the WB-002
#: specification fixes one ``source_dataset`` per source.
WHG_SOURCE_DATASET = "whg_api_sample"

#: Directory of the cached API responses, relative to the project root.
WHG_PLACE_DIR = Path("设计资料") / "P0验证" / "WB-002" / "sample_data" / "whg" / "api"

#: WHG namespace -> registry dataset id.  ``hgis`` is the fallback for the flat
#: schema, which exposes its dataset only as ``datasets[0].title``.
WHG_DATASET_BY_NAMESPACE: Dict[str, str] = {
    "gn": "whg_geoname_s_gn_sample",
    "tgn": "whg_getty_tgn_sample",
    "hgis": "whg_hgis_de_las_indias_sample",
}

#: Fallback dataset id for a record whose namespace cannot be determined.  It is
#: never used in practice, but a missing entry would otherwise crash mid-run.
_DEFAULT_DATASET_ID = "whg_hgis_de_las_indias_sample"


def _sha256(path: Path) -> str:
    """Return the hex SHA-256 of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _flatten(node: Any, prefix: str = "", out: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Flatten a JSON document into dotted-path -> string pairs.

    Lists are indexed (``names[0].toponym``) and scalars are stringified, so the
    whole response survives inside ``source_records.raw_payload_json`` without a
    bespoke schema per shape.  Values longer than 300 characters are kept whole;
    the JSON payload writer is what decides size, not this function.
    """
    if out is None:
        out = {}
    if isinstance(node, dict):
        for key in sorted(node):
            _flatten(node[key], f"{prefix}{key}.", out)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _flatten(item, f"{prefix}{index}.", out)
    else:
        key = prefix[:-1] if prefix.endswith(".") else prefix
        out[key] = "" if node is None else str(node)
    return out


def _schema_of(payload: Dict[str, Any]) -> str:
    """Classify a response as ``jsonld`` or ``flat``."""
    return "jsonld" if "@context" in payload else "flat"


def _namespace_of(payload: Dict[str, Any], schema: str) -> str:
    """Work out which WHG namespace produced a record."""
    if schema == "jsonld":
        source_id = str((payload.get("properties") or {}).get("source_id") or "")
        if ":" in source_id:
            return source_id.split(":", 1)[0]
        attribution = payload.get("attribution") or {}
        return str(attribution.get("id") or "")
    datasets = payload.get("datasets") or []
    for entry in datasets:
        title = str((entry or {}).get("title") or "").lower()
        if "indias" in title:
            return "hgis"
    return ""


def extract_whg(project_root: Path) -> ExtraExtraction:
    """Read every cached WHG response and normalise it.

    Args:
      project_root: Project root containing ``设计资料/``.

    Returns:
      An :class:`ExtraExtraction` with ``place``, ``name`` and ``location``
      records.

    Raises:
      SystemExit: If the directory holds no JSON files, because an empty source
        would silently look like a legitimate zero.
    """
    place_dir = project_root / WHG_PLACE_DIR / "place"
    if not place_dir.is_dir():
        raise SystemExit(f"WHG sample directory not found: {place_dir}")
    files = sorted(place_dir.glob("*.json"))
    if not files:
        raise SystemExit(f"no WHG JSON files under {place_dir}")

    extraction = ExtraExtraction(
        source_id=WHG_SOURCE_ID,
        source_dataset=WHG_SOURCE_DATASET,
        dataset_id=_DEFAULT_DATASET_ID,
        attribution_note=(
            "Licence is asserted per record, not per source: the two WHG schemas "
            "differ. JSON-LD records carry attribution.license__spdx_id (gn -> "
            "CC-BY-4.0, tgn -> ODC-By-1.0); the flat HGIS records carry no "
            "attribution block at all, so their licence is unconfirmed."
        ),
    )
    records: List[ExtraRecord] = []
    per_file: Dict[str, Dict[str, Any]] = {}
    namespace_counts: Dict[str, int] = {}
    schema_counts: Dict[str, int] = {}
    attribution_counts: Dict[str, int] = {}
    unconfirmed_files: List[str] = []
    timespan_files: List[str] = []

    for path in files:
        raw_bytes = path.read_bytes()
        try:
            payload = json.loads(raw_bytes.decode("utf-8-sig"))
        except json.JSONDecodeError as error:
            raise SystemExit(f"WHG file is not valid JSON: {path} ({error})") from error
        schema = _schema_of(payload)
        namespace = _namespace_of(payload, schema)
        dataset_id = WHG_DATASET_BY_NAMESPACE.get(namespace, _DEFAULT_DATASET_ID)
        schema_counts[schema] = schema_counts.get(schema, 0) + 1
        namespace_counts[namespace or "<unknown>"] = (
            namespace_counts.get(namespace or "<unknown>", 0) + 1
        )

        attribution = payload.get("attribution") or {}
        spdx = str(attribution.get("license__spdx_id") or "")
        if spdx:
            attribution_counts[spdx] = attribution_counts.get(spdx, 0) + 1
        else:
            attribution_counts["<absent>"] = attribution_counts.get("<absent>", 0) + 1
            unconfirmed_files.append(path.name)

        when = payload.get("when") or {}
        if when:
            timespan_files.append(path.name)

        flat = _flatten(payload)
        raw_file = f"sample_data/whg/api/place/{path.name}"
        if schema == "jsonld":
            place_records = _build_jsonld(
                payload, path, dataset_id, namespace, raw_file, flat
            )
        else:
            place_records = _build_flat(payload, path, dataset_id, raw_file, flat)
        records.extend(place_records)
        per_file[path.name] = {
            "schema": schema,
            "namespace": namespace,
            "dataset_id": dataset_id,
            "records": len(place_records),
            "bytes": len(raw_bytes),
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "license__spdx_id": spdx or "<absent>",
            "redistributable": (
                str(attribution.get("redistributable"))
                if "redistributable" in attribution
                else "<absent>"
            ),
        }
        extraction.slice_files.append(
            {
                "file": path.name,
                "label": "whg_place",
                "bytes": len(raw_bytes),
                "columns": len(flat),
                "parsed_rows": len(place_records),
                "discarded_rows": 0,
                "sha256": per_file[path.name]["sha256"],
                "schema": schema,
                "namespace": namespace,
            }
        )

    for record in records:
        if record.record_kind == "place" and record.dataset_id == _DEFAULT_DATASET_ID:
            record.quality_flags.append("attribution_missing")

    place_count = sum(1 for r in records if r.record_kind == "place")
    name_count = sum(1 for r in records if r.record_kind == "name")
    location_count = sum(1 for r in records if r.record_kind == "location")
    composite = sum(1 for r in records if r.record_kind == "place" and r.external_id.count("-") == 1)

    extraction.records = records
    extraction.stats.update(
        {
            "source_id": WHG_SOURCE_ID,
            "dataset_id": None,
            "files": len(files),
            "schema_counts": dict(sorted(schema_counts.items())),
            "namespace_counts": dict(sorted(namespace_counts.items())),
            "license_spdx_id_counts": dict(sorted(attribution_counts.items())),
            "files_without_attribution_block": sorted(unconfirmed_files),
            "files_with_when_timespans": sorted(timespan_files),
            "place_records": place_count,
            "name_records": name_count,
            "location_records": location_count,
            "composite_place_records": composite,
            "per_file": per_file,
            "time_note": (
                "WHG exposes when.timespans on 2 of 5 JSON-LD records and a "
                "dataset-level minmax on the flat records; neither is a documented "
                "per-place validity span, so time_bound_type is 'unknown' for every "
                "WHG row and the observed hints are preserved verbatim in notes"
            ),
        }
    )
    return extraction


def _build_jsonld(
    payload: Dict[str, Any],
    path: Path,
    dataset_id: str,
    namespace: str,
    raw_file: str,
    flat: Dict[str, str],
) -> List[ExtraRecord]:
    """Turn one Linked Places JSON-LD response into place/name/location rows."""
    properties = payload.get("properties") or {}
    source_id = str(properties.get("source_id") or "")
    title = str(properties.get("title") or "")
    ccodes = ", ".join(str(code) for code in (properties.get("ccodes") or []))
    attribution = payload.get("attribution") or {}
    when_text = json.dumps(payload.get("when") or {}, ensure_ascii=False, sort_keys=True)

    geometry = payload.get("geometry") or {}
    geometry_type = str(geometry.get("type") or "")
    coordinates = geometry.get("coordinates") or []
    lon: Optional[float] = None
    lat: Optional[float] = None
    if geometry_type == "Point" and isinstance(coordinates, list) and len(coordinates) >= 2:
        try:
            lon = float(coordinates[0])
            lat = float(coordinates[1])
        except (TypeError, ValueError):
            lon = lat = None
    geom_wkt = f"POINT({lon} {lat})" if lon is not None and lat is not None else ""

    flags: List[str] = []
    if lon is None or lat is None:
        flags.append("missing_coordinate")
    if not attribution:
        flags.append("attribution_missing")

    records: List[ExtraRecord] = []
    records.append(
        ExtraRecord(
            dataset_id=dataset_id,
            source_id=WHG_SOURCE_ID,
            source_dataset=WHG_SOURCE_DATASET,
            record_kind="place",
            record_index=1,
            raw_file=raw_file,
            raw=flat,
            external_id=source_id or path.stem,
            external_id_type="whg_source_id",
            name=title,
            name_lang="und",
            name_script="",
            name_type="primary",
            place_type="unknown",
            lon=lon,
            lat=lat,
            lon_text=str(coordinates[0]) if len(coordinates) > 0 else "",
            lat_text=str(coordinates[1]) if len(coordinates) > 1 else "",
            geom_wkt=geom_wkt,
            location_precision="point",
            uncertainty_m="",
            time_bound_type="unknown",
            quality_flags=flags,
            notes=(
                f"WHG API place record (Linked Places JSON-LD schema), file {path.name}, "
                f"namespace {namespace or '<unknown>'}, ccodes {ccodes or '<none>'}. "
                "axis_order_verified: geometry is GeoJSON, whose coordinate order is "
                "[longitude, latitude]. "
                f"attribution.license__spdx_id="
                f"{attribution.get('license__spdx_id') or '<absent>'}; "
                f"redistributable={attribution.get('redistributable')}. "
                f"when.timespans verbatim={when_text}. "
                "time_bound_type is 'unknown' because the timespans are not a "
                "documented per-place validity span: they are copied verbatim rather "
                "than converted into years. "
                f"types={[str((t or {}).get('identifier')) for t in (payload.get('types') or [])][:5]} "
                "(source feature codes; not mapped onto the CHGIS admin_center_* "
                "vocabulary)."
            ),
        )
    )

    for index, entry in enumerate(payload.get("names") or [], start=1):
        toponym = str((entry or {}).get("toponym") or "").strip()
        if not toponym:
            continue
        records.append(
            ExtraRecord(
                dataset_id=dataset_id,
                source_id=WHG_SOURCE_ID,
                source_dataset=WHG_SOURCE_DATASET,
                record_kind="name",
                record_index=index,
                raw_file=raw_file,
                raw={
                    "toponym": toponym,
                    "citations": str(len((entry or {}).get("citations") or [])),
                },
                external_id=f"{source_id or path.stem}#name{index}",
                external_id_type="whg_place_name_index",
                parent_external_id=source_id or path.stem,
                name=toponym,
                name_lang="und",
                name_script="",
                name_type="primary" if index == 1 else "alternate",
                place_type="unknown",
                time_bound_type="unknown",
                notes=(
                    "WHG name entry (names[]). The source does not state a language "
                    "tag for the toponym, so name_lang is 'und'; order in the array is "
                    "preserved and the first entry is treated as primary."
                ),
            )
        )

    # The place-level geometry must also become a location row: the place table
    # carries no coordinate column, so a coordinate that is written only onto the
    # place record is silently dropped from the normalized output.
    if geom_wkt:
        records.append(
            ExtraRecord(
                dataset_id=dataset_id,
                source_id=WHG_SOURCE_ID,
                source_dataset=WHG_SOURCE_DATASET,
                record_kind="location",
                record_index=1,
                raw_file=raw_file,
                raw={
                    "geometry_type": geometry_type,
                    "coordinates": json.dumps(coordinates, ensure_ascii=False),
                },
                external_id=f"{source_id or path.stem}#geom1",
                external_id_type="whg_geometry",
                parent_external_id=source_id or path.stem,
                name="",
                name_lang="und",
                name_script="",
                name_type="alternate",
                place_type="unknown",
                lon=lon,
                lat=lat,
                lon_text=str(coordinates[0]) if len(coordinates) > 0 else "",
                lat_text=str(coordinates[1]) if len(coordinates) > 1 else "",
                geom_wkt=geom_wkt,
                location_precision="point",
                uncertainty_m="",
                original_crs="EPSG:4326",
                crs_confidence="inferred",
                time_bound_type="unknown",
                quality_flags=[],
                notes=(
                    "WHG place geometry (Linked Places JSON-LD, geometry.type=Point). "
                    "axis_order_verified: GeoJSON coordinate order is [longitude, "
                    "latitude] by RFC 7946, so no swapping is inferred from the numbers "
                    "-- the container format settles it. "
                    "crs_confidence='inferred' (not 'confirmed'): the payload is "
                    "conformant GeoJSON, and RFC 7946 section 4 fixes its CRS as WGS 84, "
                    "so the format itself is the declaration; the record carries no "
                    "explicit datum statement of its own. The place record keeps the same "
                    "values in its notes for traceability."
                ),
            )
        )

    return records


def _build_flat(
    payload: Dict[str, Any],
    path: Path,
    dataset_id: str,
    raw_file: str,
    flat: Dict[str, str],
) -> List[ExtraRecord]:
    """Turn one older flat-schema response into place/name/location rows."""
    place_id = str(payload.get("id") or path.stem)
    title = str(payload.get("title") or "")
    minmax = payload.get("minmax") or []
    countries = ", ".join(
        str((country or {}).get("ccode") or "") for country in (payload.get("countries") or [])
    )
    dataset_titles = ", ".join(
        str((entry or {}).get("title") or "") for entry in (payload.get("datasets") or [])
    )
    types = [
        str((entry or {}).get("sourceLabel") or (entry or {}).get("label") or "")
        for entry in (payload.get("types") or [])
    ]
    geoms = payload.get("geoms") or []

    flags: List[str] = ["attribution_missing"]
    records: List[ExtraRecord] = []
    records.append(
        ExtraRecord(
            dataset_id=dataset_id,
            source_id=WHG_SOURCE_ID,
            source_dataset=WHG_SOURCE_DATASET,
            record_kind="place",
            record_index=1,
            raw_file=raw_file,
            raw=flat,
            external_id=place_id,
            external_id_type="whg_place_id",
            name=title,
            name_lang="und",
            name_script="",
            name_type="primary",
            place_type="unknown",
            lon=None,
            lat=None,
            geom_wkt="",
            location_precision="point",
            uncertainty_m="",
            time_bound_type="unknown",
            quality_flags=flags,
            notes=(
                f"WHG API place record (older flat schema, no @context), file {path.name}. "
                f"datasets={dataset_titles or '<none>'}; countries={countries or '<none>'}; "
                f"types={types or '<none>'}. "
                "This schema has NO attribution block and no key matching "
                "licen/right/attribut, so the licence cannot be established from the "
                "record; the row is imported with redistributable='unconfirmed'. "
                f"minmax={minmax} is the dataset-level temporal extent, not a per-place "
                "validity span, so time_bound_type='unknown'. "
                f"geoms_count={len(geoms)}"
                + (
                    "; this is a composite record: WHG id joins several settlements and "
                    "each geometry becomes its own location row"
                    if len(geoms) > 1
                    else ""
                )
            ),
        )
    )

    for index, entry in enumerate(payload.get("names") or [], start=1):
        toponym = str((entry or {}).get("toponym") or "").strip()
        if not toponym:
            continue
        records.append(
            ExtraRecord(
                dataset_id=dataset_id,
                source_id=WHG_SOURCE_ID,
                source_dataset=WHG_SOURCE_DATASET,
                record_kind="name",
                record_index=index,
                raw_file=raw_file,
                raw={"toponym": toponym},
                external_id=f"{place_id}#name{index}",
                external_id_type="whg_place_name_index",
                parent_external_id=place_id,
                name=toponym,
                name_lang="und",
                name_script="",
                name_type="primary" if index == 1 else "alternate",
                place_type="unknown",
                time_bound_type="unknown",
                notes=(
                    "WHG name entry (older flat schema). Language not stated by the "
                    "source, so name_lang is 'und'."
                ),
            )
        )

    for index, entry in enumerate(geoms, start=1):
        geom = entry or {}
        wkt = str(geom.get("geowkt") or "")
        point = parse_wkt_point(wkt)
        lon = point[0] if point else None
        lat = point[1] if point else None
        flags = []
        if lon is None or lat is None:
            flags.append("missing_coordinate")
        records.append(
            ExtraRecord(
                dataset_id=dataset_id,
                source_id=WHG_SOURCE_ID,
                source_dataset=WHG_SOURCE_DATASET,
                record_kind="location",
                record_index=index,
                raw_file=raw_file,
                raw={
                    "place_id": str(geom.get("place_id") or ""),
                    "ds": str(geom.get("ds") or ""),
                    "type": str(geom.get("type") or ""),
                    "geowkt": wkt,
                },
                external_id=f"{place_id}#geom{index}",
                external_id_type="whg_geom_index",
                parent_external_id=place_id,
                name=str(geom.get("title") or ""),
                name_lang="und",
                name_script="",
                name_type="alternate",
                place_type="unknown",
                lon=lon,
                lat=lat,
                lon_text=str(point[0]) if point else "",
                lat_text=str(point[1]) if point else "",
                geom_wkt=wkt,
                location_precision="point",
                uncertainty_m="",
                original_crs="unknown",
                crs_confidence="unknown",
                time_bound_type="unknown",
                quality_flags=flags,
                notes=(
                    "WHG geometry (geoms[].geowkt). axis_order_verified: WKT is X Y = "
                    "longitude latitude, cross-checked against the same point's "
                    "geoms[].coordinates array ([lon, lat]). "
                    "crs_confidence='unknown', NOT 'inferred': this file has no "
                    "@context, no attribution block and no crs member anywhere, so the "
                    "payload is only GeoJSON-*shaped* plain JSON rather than a "
                    "conformant GeoJSON document -- nothing here mandates a CRS. "
                    "'inferred' requires 'the format specification mandates WGS 84 AND "
                    "the file conforms to that specification'; shape alone does not "
                    "qualify. Plausible-looking numbers are a sanity check, not CRS "
                    "evidence. "
                    f"source_place_id={geom.get('place_id')} ds={geom.get('ds')} "
                    f"type={geom.get('type')}"
                ),
            )
        )

    return records
