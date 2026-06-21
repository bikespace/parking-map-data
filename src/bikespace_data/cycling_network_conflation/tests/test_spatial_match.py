import math

import geopandas as gpd
import pandas as pd
import pandera.pandas as pa
import pytest
from shapely.geometry import LineString

from bikespace_data.cycling_network_conflation.region_config import (
    RegionConfig,
    TodMunicipalSource,
)
from bikespace_data.cycling_network_conflation.spatial_match import (
    acute_angle_between,
    compute_linestring_bearing,
    core_buffer,
    match_cycling_network,
)

# --- Helpers ---

_STUB_SCHEMA = pa.DataFrameSchema(columns={"geometry": pa.Column("geometry")})

_CONFIG = RegionConfig(
    name="test",
    display_name="Test Region",
    municipal_source=TodMunicipalSource(dataset_name="test", resource_id="test"),
    municipal_schema=_STUB_SCHEMA,
    municipal_id_col="SEGMENT_ID",
    municipal_infra_col="INFRA_HIGHORDER",
    municipal_license="test",
    municipal_license_url="test",
    osm_wikidata_id="Q1",
    crs="EPSG:32617",
    buffer_m=15.0,
    orthogonality_threshold_deg=45.0,
    endpoint_trim_m=10.0,
)


def _make_muni_gdf(segments: list[tuple[int, LineString]]) -> gpd.GeoDataFrame:
    ids, geoms = zip(*segments)
    return gpd.GeoDataFrame(
        {"SEGMENT_ID": list(ids)},
        geometry=list(geoms),
        crs="EPSG:32617",
    )


def _make_osm_gdf(ways: list[tuple[int, LineString]]) -> gpd.GeoDataFrame:
    ids, geoms = zip(*ways)
    return gpd.GeoDataFrame(
        index=list(ids),
        geometry=list(geoms),
        crs="EPSG:32617",
    )


def _empty_overrides() -> pd.DataFrame:
    return pd.DataFrame(columns=["SEGMENT_ID", "osm_way_id", "action", "note"])


# --- Unit tests ---

def test_parallel_linestrings_match():
    """OSM way parallel to and within buffer of municipal segment → match found."""
    muni = _make_muni_gdf([(1, LineString([(0, 0), (100, 0)]))])
    osm = _make_osm_gdf([(999, LineString([(0, 10), (100, 10)]))])  # 10 m north, parallel

    result = match_cycling_network(muni, osm, _CONFIG, _empty_overrides())
    auto = result[(result["SEGMENT_ID"] == 1) & (result["osm_way_id"] == "way/999")]
    assert len(auto) == 1
    assert auto.iloc[0]["match_type"] == "auto"


def test_perpendicular_linestrings_excluded():
    """OSM way perpendicular to municipal segment → excluded by angle filter."""
    muni = _make_muni_gdf([(1, LineString([(0, 0), (100, 0)]))])
    osm = _make_osm_gdf([(999, LineString([(50, -10), (50, 10)]))])  # vertical crossing

    result = match_cycling_network(muni, osm, _CONFIG, _empty_overrides())
    matched = result[(result["SEGMENT_ID"] == 1) & (result["osm_way_id"] == "way/999")]
    assert len(matched) == 0


def test_endpoint_only_flag():
    """OSM way that only overlaps the endpoint zone is flagged endpoint_only."""
    # Municipal segment: 100 m long; endpoint trim = 10 m each end; buffer = 15 m
    # Core buffer's left end cap extends to x = 10 - 15 = -5.
    # OSM way from (-12, 0) to (-6, 0) is in the municipal buffer (within 15 m of (0,0))
    # but entirely outside the core buffer (which reaches only to x = -5).
    muni = _make_muni_gdf([(1, LineString([(0, 0), (100, 0)]))])
    osm = _make_osm_gdf([(999, LineString([(-12, 0), (-6, 0)]))])  # in tip of start cap only

    result = match_cycling_network(muni, osm, _CONFIG, _empty_overrides())
    matched = result[(result["SEGMENT_ID"] == 1) & (result["osm_way_id"] == "way/999")]
    assert len(matched) == 1
    assert "endpoint_only" in matched.iloc[0]["flags"]


def test_override_include_rescues_excluded_pair():
    """Override include adds a pair that the angle filter would reject."""
    muni = _make_muni_gdf([(1, LineString([(0, 0), (100, 0)]))])
    osm = _make_osm_gdf([(999, LineString([(50, -10), (50, 10)]))])  # perpendicular

    # Without override: no match
    no_override = match_cycling_network(muni, osm, _CONFIG, _empty_overrides())
    assert len(no_override[no_override["osm_way_id"] == "way/999"]) == 0

    overrides = pd.DataFrame(
        [{"SEGMENT_ID": 1, "osm_way_id": "way/999", "action": "include", "note": ""}]
    )
    result = match_cycling_network(muni, osm, _CONFIG, overrides)
    included = result[
        (result["SEGMENT_ID"] == 1) & (result["osm_way_id"] == "way/999")
    ]
    assert len(included) == 1
    assert included.iloc[0]["match_type"] == "override"
    assert included.iloc[0]["override_action"] == "include"


def test_override_exclude_marks_pair():
    """Override exclude marks a pair with override_action=exclude but keeps it in output."""
    muni = _make_muni_gdf([(1, LineString([(0, 0), (100, 0)]))])
    osm = _make_osm_gdf([(999, LineString([(0, 10), (100, 10)]))])  # parallel → auto match

    overrides = pd.DataFrame(
        [{"SEGMENT_ID": 1, "osm_way_id": "way/999", "action": "exclude", "note": ""}]
    )
    result = match_cycling_network(muni, osm, _CONFIG, overrides)
    row = result[(result["SEGMENT_ID"] == 1) & (result["osm_way_id"] == "way/999")]
    assert len(row) == 1
    assert row.iloc[0]["override_action"] == "exclude"


def test_empty_overrides_same_as_no_overrides():
    """Empty override CSV produces identical result to calling with an empty DataFrame."""
    muni = _make_muni_gdf([(1, LineString([(0, 0), (100, 0)]))])
    osm = _make_osm_gdf([(999, LineString([(0, 10), (100, 10)]))])

    result_empty_df = match_cycling_network(muni, osm, _CONFIG, _empty_overrides())
    empty_csv_overrides = pd.DataFrame(
        columns=["SEGMENT_ID", "osm_way_id", "action", "note"]
    )
    result_csv = match_cycling_network(muni, osm, _CONFIG, empty_csv_overrides)

    pd.testing.assert_frame_equal(
        result_empty_df.reset_index(drop=True),
        result_csv.reset_index(drop=True),
    )


# --- Helper function unit tests ---

def test_compute_linestring_bearing():
    east = LineString([(0, 0), (1, 0)])
    assert abs(compute_linestring_bearing(east)) < 1e-9

    north = LineString([(0, 0), (0, 1)])
    assert abs(compute_linestring_bearing(north) - math.pi / 2) < 1e-9


def test_acute_angle_between():
    assert acute_angle_between(0, math.pi / 2) == pytest.approx(math.pi / 2)
    assert acute_angle_between(0, math.pi) == pytest.approx(0.0)
    assert acute_angle_between(0, math.pi / 4) == pytest.approx(math.pi / 4)


def test_core_buffer_returns_none_for_short_segment():
    short = LineString([(0, 0), (5, 0)])  # 5 m < 2 * 10 m trim
    assert core_buffer(short, trim_m=10.0, buffer_m=15.0) is None


def test_core_buffer_returns_polygon_for_long_segment():
    long_seg = LineString([(0, 0), (100, 0)])
    result = core_buffer(long_seg, trim_m=10.0, buffer_m=15.0)
    assert result is not None
    assert not result.is_empty
