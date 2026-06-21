import math

import geopandas as gpd
import pandas as pd
import pandera.pandas as pa
import pytest
from shapely.geometry import LineString, MultiLineString, Point

from bikespace_data.cycling_network_conflation.region_config import (
    RegionConfig,
    TodMunicipalSource,
    build_osm_cycling_query,
)
from bikespace_data.cycling_network_conflation.spatial_match import (
    _longest_linestring,
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
    """A parallel OSM way within the buffer distance of a municipal segment is auto-matched.

    Given a municipal segment running east from (0,0) to (100,0) and an OSM way
    10 m north running the same direction, the spatial match should produce exactly
    one row for (SEGMENT_ID=1, way/999) with match_type='auto'.
    """
    muni = _make_muni_gdf([(1, LineString([(0, 0), (100, 0)]))])
    osm = _make_osm_gdf([(999, LineString([(0, 10), (100, 10)]))])  # 10 m north, parallel

    result = match_cycling_network(muni, osm, _CONFIG, _empty_overrides())
    auto = result[(result["SEGMENT_ID"] == 1) & (result["osm_way_id"] == "way/999")]
    assert len(auto) == 1
    assert auto.iloc[0]["match_type"] == "auto"


def test_perpendicular_linestrings_excluded():
    """A perpendicular OSM way is excluded by the angle filter even when inside the buffer.

    Given a municipal segment running east and an OSM way crossing it at 90 degrees
    (north-south), the acute angle between them is 90° which exceeds the 45° threshold.
    No match row should be produced for this pair.
    """
    muni = _make_muni_gdf([(1, LineString([(0, 0), (100, 0)]))])
    osm = _make_osm_gdf([(999, LineString([(50, -10), (50, 10)]))])  # vertical crossing

    result = match_cycling_network(muni, osm, _CONFIG, _empty_overrides())
    matched = result[(result["SEGMENT_ID"] == 1) & (result["osm_way_id"] == "way/999")]
    assert len(matched) == 0


def test_endpoint_only_flag():
    """An OSM way that overlaps only the endpoint zone is flagged 'endpoint_only'.

    Given a 100 m municipal segment with endpoint_trim_m=10 and buffer_m=15, the
    core buffer covers x=10 to x=90. An OSM way at x=[-12, -6] lies within the
    buffer (within 15 m of the (0,0) endpoint) but entirely outside the core buffer,
    so core_overlap / buffer_overlap < 0.10 → the match is flagged endpoint_only.
    """
    muni = _make_muni_gdf([(1, LineString([(0, 0), (100, 0)]))])
    osm = _make_osm_gdf([(999, LineString([(-12, 0), (-6, 0)]))])  # in tip of start cap only

    result = match_cycling_network(muni, osm, _CONFIG, _empty_overrides())
    matched = result[(result["SEGMENT_ID"] == 1) & (result["osm_way_id"] == "way/999")]
    assert len(matched) == 1
    assert "endpoint_only" in matched.iloc[0]["flags"]


def test_override_include_rescues_excluded_pair():
    """An override include entry forces a match even when the angle filter rejects the pair.

    Given a perpendicular OSM way (which the angle filter drops) and an override CSV
    with action='include' for that pair, the output should contain exactly one row
    for that pair with match_type='override' and override_action='include'.
    """
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
    """An override exclude entry marks an auto-matched pair with override_action='exclude'.

    Given a parallel OSM way that auto-matches and an override CSV with action='exclude'
    for that pair, the pair should still appear in the output (for debugging) but with
    override_action='exclude' so downstream consumers can filter it out.
    """
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
    """An empty overrides DataFrame and an empty-schema DataFrame produce identical results.

    Both `_empty_overrides()` and a manually constructed empty DataFrame with the
    correct columns represent the state of having no override rules. The match output
    should be identical regardless of which is passed.
    """
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
    """compute_linestring_bearing returns the atan2 bearing from first to last coordinate.

    A horizontal east-going segment should have bearing ≈ 0 radians; a vertical
    north-going segment should have bearing ≈ π/2 radians.
    """
    east = LineString([(0, 0), (1, 0)])
    assert abs(compute_linestring_bearing(east)) < 1e-9

    north = LineString([(0, 0), (0, 1)])
    assert abs(compute_linestring_bearing(north) - math.pi / 2) < 1e-9


def test_acute_angle_between():
    """acute_angle_between always returns an angle in [0, π/2] regardless of direction.

    Opposite-direction bearings (0 and π) should yield 0 (parallel lines); a 90°
    difference should yield π/2; a 45° difference should yield π/4.
    """
    assert acute_angle_between(0, math.pi / 2) == pytest.approx(math.pi / 2)
    assert acute_angle_between(0, math.pi) == pytest.approx(0.0)
    assert acute_angle_between(0, math.pi / 4) == pytest.approx(math.pi / 4)


def test_core_buffer_returns_none_for_short_segment():
    """core_buffer returns None when the segment is too short to trim from both ends.

    A 5 m segment with trim_m=10 would require removing 20 m total — more than the
    segment length — so core_buffer returns None rather than producing a degenerate
    or negative-length substring.
    """
    short = LineString([(0, 0), (5, 0)])  # 5 m < 2 * 10 m trim
    assert core_buffer(short, trim_m=10.0, buffer_m=15.0) is None


def test_core_buffer_returns_polygon_for_long_segment():
    """core_buffer returns a non-empty polygon for a segment longer than 2 × trim_m.

    Given a 100 m LineString with trim_m=10 and buffer_m=15, the core buffer is
    the 80 m middle portion buffered by 15 m — a valid, non-empty polygon.
    """
    long_seg = LineString([(0, 0), (100, 0)])
    result = core_buffer(long_seg, trim_m=10.0, buffer_m=15.0)
    assert result is not None
    assert not result.is_empty


# --- Additional branch-coverage tests ---

def test_build_osm_cycling_query_with_custom_template(tmp_path):
    """build_osm_cycling_query substitutes the Wikidata ID into a custom template.

    Given a custom .overpass file containing the $wikidata_id placeholder, when
    called with a specific ID and that template path, the returned query string
    should contain the substituted ID and no unresolved placeholder.
    """
    template = tmp_path / "query.overpass"
    template.write_text("[out:json]; area[wikidata=$wikidata_id]; out;")
    result = build_osm_cycling_query("Q172", template_path=template)
    assert "Q172" in result
    assert "$wikidata_id" not in result


def test_core_buffer_returns_none_for_unmerged_multilinestring():
    """core_buffer returns None when a MultiLineString cannot be merged into one line.

    Given two disconnected line segments that share no endpoints, linemerge cannot
    produce a single LineString. core_buffer detects the result is still a
    MultiLineString and returns None rather than attempting to substring it.
    """
    disjoint = MultiLineString([[(0, 0), (5, 0)], [(10, 0), (15, 0)]])
    assert core_buffer(disjoint, trim_m=1.0, buffer_m=5.0) is None


def test_longest_linestring_picks_longest_from_multilinestring():
    """_longest_linestring returns the longest component of a MultiLineString.

    Given a MultiLineString containing a 100-unit segment and a 10-unit segment,
    the function should return the 100-unit segment as the longest sub-geometry.
    """
    multi = MultiLineString([[(0, 0), (100, 0)], [(200, 0), (210, 0)]])
    result = _longest_linestring(multi)
    assert result is not None
    assert abs(result.length - 100.0) < 1e-9


def test_longest_linestring_returns_none_for_non_line_geometry():
    """_longest_linestring returns None for geometry types that are not lines.

    Given a Point geometry (which can arise when an OSM way intersects a municipal
    buffer only at a single boundary point), the function should return None so
    the caller can skip this candidate via the clipped-is-None guard.
    """
    assert _longest_linestring(Point(0, 0)) is None


def test_related_highway_ways_excluded_from_candidates():
    """match_cycling_network filters out OSM ways flagged as _related_highway.

    When the OSM GeoDataFrame contains a _related_highway=True column for a way
    that would otherwise auto-match (parallel, within buffer), that way should not
    appear in the output. This flag marks roads whose cycling infrastructure is
    mapped as a separate parallel OSM way.
    """
    muni = _make_muni_gdf([(1, LineString([(0, 0), (100, 0)]))])
    osm = _make_osm_gdf([(999, LineString([(0, 10), (100, 10)]))])
    osm["_related_highway"] = True

    result = match_cycling_network(muni, osm, _CONFIG, _empty_overrides())
    assert len(result[result["osm_way_id"] == "way/999"]) == 0


def test_clipped_point_intersection_is_skipped():
    """match_cycling_network skips OSM ways whose intersection with the buffer is a Point.

    When an OSM way approaches the municipal segment buffer from outside and its
    endpoint lies exactly on the buffer boundary, the intersection is a single
    Point rather than a LineString. _longest_linestring returns None for a Point,
    triggering the `clipped is None` guard so the candidate is silently skipped.
    """
    muni = _make_muni_gdf([(1, LineString([(0, 0), (100, 0)]))])
    # The buffer around (0,0) has radius 15; the OSM way ends exactly at (-15, 0)
    # — on the boundary — so its intersection with the buffer polygon is a Point.
    osm = _make_osm_gdf([(999, LineString([(-20, 0), (-15, 0)]))])

    result = match_cycling_network(muni, osm, _CONFIG, _empty_overrides())
    matched = result[(result["SEGMENT_ID"] == 1) & (result["osm_way_id"] == "way/999")]
    assert len(matched) == 0


def test_muni_multilinestring_skips_angle_check_and_flags_endpoint_only():
    """match_cycling_network skips the angle check when the muni geometry is a MultiLineString.

    A municipal segment stored as an unmerged MultiLineString (two disconnected
    parts) bypasses the angle filter as a safety measure (line 103 condition).
    Because the corresponding core buffer is also None (the MultiLineString cannot
    be trimmed via linemerge), any OSM match is flagged endpoint_only.

    Given a disjoint muni MultiLineString and a parallel OSM way within the buffer,
    the output should contain exactly one match row with flags='endpoint_only'.
    """
    multi_muni = MultiLineString([[(0, 0), (40, 0)], [(60, 0), (100, 0)]])
    muni = gpd.GeoDataFrame(
        {"SEGMENT_ID": [1]},
        geometry=[multi_muni],
        crs="EPSG:32617",
    )
    osm = _make_osm_gdf([(999, LineString([(0, 10), (100, 10)]))])

    result = match_cycling_network(muni, osm, _CONFIG, _empty_overrides())
    matched = result[(result["SEGMENT_ID"] == 1) & (result["osm_way_id"] == "way/999")]
    assert len(matched) == 1
    assert "endpoint_only" in matched.iloc[0]["flags"]


def test_short_muni_segment_flags_endpoint_only_via_none_core_buffer():
    """match_cycling_network flags matches as endpoint_only when muni_core_buf is None.

    When the municipal segment is shorter than 2 × endpoint_trim_m (here 15 m < 20 m),
    core_buffer returns None. The OSM candidate still matches (the angle check
    passes for parallel ways), but the result is flagged endpoint_only with
    core_overlap=0 because no core buffer zone exists to compare against.
    """
    muni = _make_muni_gdf([(1, LineString([(0, 0), (15, 0)]))])  # 15 m < 2 × 10 m
    osm = _make_osm_gdf([(999, LineString([(0, 10), (15, 10)]))])

    result = match_cycling_network(muni, osm, _CONFIG, _empty_overrides())
    matched = result[(result["SEGMENT_ID"] == 1) & (result["osm_way_id"] == "way/999")]
    assert len(matched) == 1
    assert "endpoint_only" in matched.iloc[0]["flags"]


def test_core_buffer_merges_connectable_multilinestring():
    """core_buffer processes a MultiLineString that linemerge can merge into a single LineString.

    Two adjacent segments that share an endpoint form a connectable MultiLineString.
    linemerge merges them into a single LineString, so the inner isinstance check
    at line 26 is False and the function proceeds to compute and return the buffer
    polygon rather than returning None.
    """
    connected = MultiLineString([[(0, 0), (50, 0)], [(50, 0), (100, 0)]])
    result = core_buffer(connected, trim_m=10.0, buffer_m=15.0)
    assert result is not None
    assert not result.is_empty


def test_override_include_does_not_duplicate_existing_auto_match():
    """override include for a pair already auto-matched does not create a duplicate row.

    When a (muni_id, osm_way_id) pair is already in the auto-matched results and
    an override CSV also marks the same pair as 'include', the pair should appear
    exactly once in the output. The override is a no-op for pairs that are
    already present (checked via a set lookup at line 152).
    """
    muni = _make_muni_gdf([(1, LineString([(0, 0), (100, 0)]))])
    osm = _make_osm_gdf([(999, LineString([(0, 10), (100, 10)]))])

    overrides = pd.DataFrame(
        [{"SEGMENT_ID": 1, "osm_way_id": "way/999", "action": "include", "note": ""}]
    )
    result = match_cycling_network(muni, osm, _CONFIG, overrides)
    matching_rows = result[(result["SEGMENT_ID"] == 1) & (result["osm_way_id"] == "way/999")]
    assert len(matching_rows) == 1
