from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pandera.pandas as pa
import pytest
from shapely.geometry import LineString, MultiLineString

from bikespace_data.cycling_network_conflation.region_config import (
    RegionConfig,
    TodMunicipalSource,
    UrlMunicipalSource,
)
from bikespace_data.cycling_network_conflation.update_conflation import (
    _build_combined_geojson,
    _build_conflation_props,
    _download_osm_gdf,
    _is_cycling_way,
    _is_na,
    _load_or_create_override_csv,
    _tag_series,
    run_region,
)


# --- Shared fixtures and helpers ---

_STUB_SCHEMA = pa.DataFrameSchema()


def _make_config(
    *,
    source=None,
    override_csv=None,
    crs="EPSG:32617",
):
    """Return a minimal RegionConfig suitable for unit tests."""
    if source is None:
        source = TodMunicipalSource(dataset_name="test", resource_id="test")
    return RegionConfig(
        name="test",
        display_name="Test Region",
        municipal_source=source,
        municipal_schema=_STUB_SCHEMA,
        municipal_id_col="SEGMENT_ID",
        municipal_infra_col="INFRA_HIGHORDER",
        municipal_license="test",
        municipal_license_url="http://example.com",
        osm_wikidata_id="Q1",
        crs=crs,
        override_csv=override_csv,
    )


@pytest.fixture()
def minimal_muni_gdf():
    # Real City of Toronto cycling-network data uses MultiLineString geometry;
    # run_region calls linemerge() on each row which requires MultiLineString input.
    return gpd.GeoDataFrame(
        {"SEGMENT_ID": [1], "INFRA_HIGHORDER": ["Bike Lane"]},
        geometry=[MultiLineString([[(0, 0), (0.001, 0)]])],
        crs="EPSG:4326",
    )


@pytest.fixture()
def minimal_osm_gdf():
    gdf = gpd.GeoDataFrame(
        index=[999],
        geometry=[LineString([(0, 0.0001), (0.001, 0.0001)])],
        crs="EPSG:4326",
    )
    gdf["_query"] = "cycling"
    gdf["_related_highway"] = False
    return gdf


@pytest.fixture()
def minimal_matches_df():
    return pd.DataFrame(
        [
            {
                "SEGMENT_ID": 1,
                "osm_way_id": "way/999",
                "match_type": "auto",
                "override_action": None,
                "flags": "",
            }
        ]
    )


# --- _tag_series ---

def test_tag_series_reads_from_nested_tags_dict():
    """_tag_series extracts a tag value from a nested 'tags' dict column.

    When the GeoDataFrame has a 'tags' column containing dicts (as returned by the
    overpass library), _tag_series should apply .get() on each dict and return the
    value for the requested key, or an empty string if the key is absent.
    """
    gdf = gpd.GeoDataFrame(
        {"tags": [{"highway": "cycleway"}, {"highway": "residential"}, {}]}
    )
    result = _tag_series(gdf, "highway")
    assert list(result) == ["cycleway", "residential", ""]


def test_tag_series_falls_back_to_flat_column():
    """_tag_series falls back to a flat column when no 'tags' dict column is present.

    When the GeoDataFrame has the tag as a top-level column (not nested under 'tags'),
    _tag_series should return that column cast to str, with None/NaN filled as empty
    strings.
    """
    gdf = gpd.GeoDataFrame({"highway": ["cycleway", None]})
    result = _tag_series(gdf, "highway")
    assert result.iloc[0] == "cycleway"
    assert result.iloc[1] == ""


def test_tag_series_returns_empty_strings_when_column_missing():
    """_tag_series returns a Series of empty strings when the tag key is not found anywhere.

    When neither a 'tags' dict column nor a matching flat column exists, every row
    should receive an empty string so downstream code can treat all rows uniformly.
    """
    gdf = gpd.GeoDataFrame({"unrelated": [1, 2]})
    result = _tag_series(gdf, "highway")
    assert list(result) == ["", ""]


# --- _is_cycling_way ---

def _cycling_row_gdf(**tags):
    """Build a single-row GDF with the given tag columns (used by _is_cycling_way tests)."""
    row = {"highway": "", "cycleway": "", "bicycle": "", "bicycle_road": ""}
    row.update(tags)
    return gpd.GeoDataFrame({k: [v] for k, v in row.items()})


def test_is_cycling_way_cycleway_highway():
    """_is_cycling_way returns True for ways tagged highway=cycleway.

    A dedicated cycleway in OSM uses highway=cycleway. These are unambiguously
    cycling infrastructure and should always be classified as cycling ways.
    """
    assert _is_cycling_way(_cycling_row_gdf(highway="cycleway")).iloc[0]


def test_is_cycling_way_cycleway_tag():
    """_is_cycling_way returns True for ways tagged with a cycling-specific cycleway value.

    Tags like cycleway=track, cycleway=lane, cycleway=shared_lane etc. indicate that
    a road has some form of cycling infrastructure alongside it.
    """
    assert _is_cycling_way(_cycling_row_gdf(cycleway="track")).iloc[0]
    assert _is_cycling_way(_cycling_row_gdf(cycleway="lane")).iloc[0]
    assert _is_cycling_way(_cycling_row_gdf(cycleway="shared_lane")).iloc[0]


def test_is_cycling_way_bicycle_designated_on_path():
    """_is_cycling_way returns True for path/footway/pedestrian ways designated for bicycles.

    A shared-use path tagged as highway=path or highway=footway with bicycle=designated
    is a valid cycling facility, so it should be classified as a cycling way.
    """
    assert _is_cycling_way(_cycling_row_gdf(highway="path", bicycle="designated")).iloc[0]
    assert _is_cycling_way(_cycling_row_gdf(highway="footway", bicycle="designated")).iloc[0]
    assert _is_cycling_way(_cycling_row_gdf(highway="pedestrian", bicycle="designated")).iloc[0]


def test_is_cycling_way_bicycle_road():
    """_is_cycling_way returns True for ways tagged bicycle_road=yes.

    In some countries, roads designated as bicycle roads use the bicycle_road=yes tag.
    """
    assert _is_cycling_way(_cycling_row_gdf(bicycle_road="yes")).iloc[0]


def test_is_cycling_way_false_for_plain_road():
    """_is_cycling_way returns False for a plain road with no cycling tags.

    A residential road with no cycleway, bicycle, or bicycle_road tags does not
    qualify as a cycling way and should be classified as an lts_road instead.
    """
    assert not _is_cycling_way(_cycling_row_gdf(highway="residential")).iloc[0]


# --- _is_na ---

def test_is_na_with_none():
    """_is_na returns True for Python None, which pandas treats as NA."""
    assert _is_na(None) is True


def test_is_na_with_nan():
    """_is_na returns True for float NaN, which pandas treats as NA."""
    assert _is_na(float("nan")) is True


def test_is_na_with_string_value():
    """_is_na returns False for a normal string value."""
    assert _is_na("hello") is False


def test_is_na_with_array_like():
    """_is_na returns False for array-like values where pd.isna raises ValueError.

    pd.isna([1, 2]) returns an array; bool(array) raises ValueError because
    the truth value of an array is ambiguous. _is_na catches this and returns
    False, treating array-like values as non-NA.
    """
    assert _is_na([1, 2]) is False


# --- _load_or_create_override_csv ---

def test_load_or_create_override_csv_none_path():
    """_load_or_create_override_csv returns an empty DataFrame when override_csv is None.

    When the RegionConfig has no override CSV path configured, the function should
    return an empty DataFrame with the correct columns without creating any files.
    """
    config = _make_config(override_csv=None)
    df = _load_or_create_override_csv(config)
    assert df.empty
    assert "SEGMENT_ID" in df.columns
    assert "osm_way_id" in df.columns


def test_load_or_create_override_csv_creates_empty_file(tmp_path):
    """_load_or_create_override_csv creates an empty CSV when the path does not yet exist.

    When the configured override CSV path does not exist, the function should create
    the file (and any missing parent directories), write the header row, and return
    an empty DataFrame so subsequent runs can populate it manually.
    """
    csv_path = tmp_path / "overrides" / "test_overrides.csv"
    config = _make_config(override_csv=csv_path)
    df = _load_or_create_override_csv(config)
    assert df.empty
    assert csv_path.exists()
    header_df = pd.read_csv(csv_path)
    assert "SEGMENT_ID" in header_df.columns


def test_load_or_create_override_csv_reads_valid_file(tmp_path):
    """_load_or_create_override_csv reads and returns rows from a valid override CSV.

    Given a CSV file with one include override row, the function should return a
    DataFrame with that row and the correct column types.
    """
    csv_path = tmp_path / "overrides.csv"
    pd.DataFrame(
        [{"SEGMENT_ID": 1, "osm_way_id": "way/1", "action": "include", "note": "test"}]
    ).to_csv(csv_path, index=False)
    config = _make_config(override_csv=csv_path)
    df = _load_or_create_override_csv(config)
    assert len(df) == 1
    assert df.iloc[0]["action"] == "include"


def test_load_or_create_override_csv_raises_for_missing_id_column(tmp_path):
    """_load_or_create_override_csv raises ValueError when the expected ID column is absent.

    If the CSV file exists but uses the wrong ID column name (e.g. 'WRONG_ID' instead
    of 'SEGMENT_ID'), the function should raise ValueError with a message identifying
    the expected column name so the user knows how to fix the file.
    """
    csv_path = tmp_path / "overrides.csv"
    pd.DataFrame(
        [{"WRONG_ID": 1, "osm_way_id": "way/1", "action": "include", "note": ""}]
    ).to_csv(csv_path, index=False)
    config = _make_config(override_csv=csv_path)
    with pytest.raises(ValueError, match="SEGMENT_ID"):
        _load_or_create_override_csv(config)


def test_load_or_create_override_csv_raises_for_invalid_action(tmp_path):
    """_load_or_create_override_csv raises ValueError when 'action' contains invalid values.

    Only 'include', 'exclude', and empty/NaN are valid action values. Any other string
    (e.g. 'force') should cause ValueError listing the bad values so the user can
    correct the CSV.
    """
    csv_path = tmp_path / "overrides.csv"
    pd.DataFrame(
        [{"SEGMENT_ID": 1, "osm_way_id": "way/1", "action": "force", "note": ""}]
    ).to_csv(csv_path, index=False)
    config = _make_config(override_csv=csv_path)
    with pytest.raises(ValueError, match="invalid values"):
        _load_or_create_override_csv(config)


# --- _build_conflation_props ---

def test_build_conflation_props_auto_match():
    """_build_conflation_props populates algo_matches for a plain auto-matched row.

    Given a matches DataFrame with one auto match (not excluded), the returned
    properties should contain the OSM way ID in _conflation_algo_matches and empty
    strings for the override fields.
    """
    df = pd.DataFrame(
        [{"SEGMENT_ID": 1, "osm_way_id": "way/1", "match_type": "auto", "override_action": None, "flags": ""}]
    )
    props = _build_conflation_props(
        1, "SEGMENT_ID", df, source_col="municipal", match_col="osm_way_id"
    )
    assert props["_conflation_algo_matches"] == "way/1"
    assert props["_conflation_override_excluded"] == ""
    assert props["_conflation_override_included"] == ""


def test_build_conflation_props_excluded_match():
    """_build_conflation_props excludes an auto match that is marked override_action='exclude'.

    A row with match_type='auto' and override_action='exclude' should appear in
    _conflation_override_excluded but NOT in _conflation_algo_matches (the algo
    match is suppressed by the override).
    """
    df = pd.DataFrame(
        [{"SEGMENT_ID": 1, "osm_way_id": "way/1", "match_type": "auto", "override_action": "exclude", "flags": ""}]
    )
    props = _build_conflation_props(
        1, "SEGMENT_ID", df, source_col="municipal", match_col="osm_way_id"
    )
    assert props["_conflation_algo_matches"] == ""
    assert props["_conflation_override_excluded"] == "way/1"


def test_build_conflation_props_override_include():
    """_build_conflation_props lists a manually included pair in _conflation_override_included.

    A row with match_type='override' represents a pair that the algorithm missed but
    was added manually. It should appear in _conflation_override_included.
    """
    df = pd.DataFrame(
        [{"SEGMENT_ID": 1, "osm_way_id": "way/1", "match_type": "override", "override_action": "include", "flags": ""}]
    )
    props = _build_conflation_props(
        1, "SEGMENT_ID", df, source_col="municipal", match_col="osm_way_id"
    )
    assert props["_conflation_override_included"] == "way/1"


def test_build_conflation_props_no_matches():
    """_build_conflation_props returns empty strings for a feature with no matches.

    When the matches DataFrame contains no rows for the given feature ID, all three
    _conflation_* properties should be empty strings (not None).
    """
    df = pd.DataFrame(
        columns=["SEGMENT_ID", "osm_way_id", "match_type", "override_action", "flags"]
    )
    props = _build_conflation_props(
        99, "SEGMENT_ID", df, source_col="municipal", match_col="osm_way_id"
    )
    assert props["_conflation_algo_matches"] == ""
    assert props["_conflation_override_excluded"] == ""
    assert props["_conflation_override_included"] == ""


# --- _build_combined_geojson ---

def test_build_combined_geojson_returns_valid_feature_collection(minimal_muni_gdf, minimal_osm_gdf, minimal_matches_df):
    """_build_combined_geojson returns a GeoJSON FeatureCollection with municipal and OSM features.

    Given minimal municipal and OSM GeoDataFrames and a matches DataFrame, the output
    should be a dict with type='FeatureCollection', the correct municipal_id_key, and
    features from both sources, each annotated with _source, _conflation_algo_matches,
    _conflation_override_excluded, and _conflation_override_included properties.
    """
    config = _make_config()
    result = _build_combined_geojson(minimal_muni_gdf, minimal_osm_gdf, minimal_matches_df, config)
    assert result["type"] == "FeatureCollection"
    assert result["municipal_id_key"] == "SEGMENT_ID"
    sources = {f["properties"]["_source"] for f in result["features"]}
    assert sources == {"municipal", "osm"}
    muni_feat = next(f for f in result["features"] if f["properties"]["_source"] == "municipal")
    assert "_conflation_algo_matches" in muni_feat["properties"]


def test_build_combined_geojson_none_geometry_produces_null(minimal_muni_gdf, minimal_matches_df):
    """_build_combined_geojson outputs null geometry for OSM rows that have no geometry.

    When an OSM GeoDataFrame row has a None geometry (e.g. a way whose geometry
    was not downloaded), the resulting GeoJSON Feature should have geometry=None
    rather than raising an error.
    """
    config = _make_config()
    empty_matches = pd.DataFrame(
        columns=["SEGMENT_ID", "osm_way_id", "match_type", "override_action", "flags"]
    )
    osm_no_geom = gpd.GeoDataFrame(index=[888], geometry=[None], crs="EPSG:4326")
    result = _build_combined_geojson(minimal_muni_gdf, osm_no_geom, empty_matches, config)
    osm_feat = next(f for f in result["features"] if f["properties"]["_source"] == "osm")
    assert osm_feat["geometry"] is None


# --- run_region ---

def _patch_run_region_deps(mocker, muni_gdf, osm_gdf, matches_df, tod_metadata=None):
    """Patch all network/IO-touching dependencies used by run_region."""
    if tod_metadata is None:
        tod_metadata = {"last_modified": "2024-01-01T00:00:00+00:00"}
    mocker.patch(
        "bikespace_data.cycling_network_conflation.update_conflation.request_tod_gdf",
        return_value={"gdf": muni_gdf, "metadata": tod_metadata},
    )
    mocker.patch(
        "bikespace_data.cycling_network_conflation.update_conflation._download_osm_gdf",
        return_value=(osm_gdf, datetime.now(timezone.utc)),
    )
    mocker.patch(
        "bikespace_data.cycling_network_conflation.update_conflation.match_cycling_network",
        return_value=matches_df,
    )
    mocker.patch(
        "bikespace_data.cycling_network_conflation.update_conflation.StatusManager"
    )


def test_run_region_creates_output_files_for_tod_source(
    tmp_path, minimal_muni_gdf, minimal_osm_gdf, minimal_matches_df, mocker
):
    """run_region writes all expected output files when using a TodMunicipalSource.

    Given a TodMunicipalSource config and mocked network dependencies, run_region
    should create the matches.csv, combined_with_matches.geojson, display matches.csv,
    municipal_with_matches.json, and osm_with_matches.json files under the output root.
    """
    _patch_run_region_deps(mocker, minimal_muni_gdf, minimal_osm_gdf, minimal_matches_df)
    config = _make_config(source=TodMunicipalSource(dataset_name="x", resource_id="y"))
    run_region(config, output_root=tmp_path)

    region_root = tmp_path / config.name
    assert (region_root / "output_files" / "matches.csv").exists()
    assert (region_root / "output_files" / "combined_with_matches.geojson").exists()
    assert (region_root / "display_files" / "matches.csv").exists()
    assert (region_root / "display_files" / "municipal_with_matches.json").exists()
    assert (region_root / "display_files" / "osm_with_matches.json").exists()


def test_run_region_handles_tz_naive_municipal_datetime(
    tmp_path, minimal_muni_gdf, minimal_osm_gdf, minimal_matches_df, mocker
):
    """run_region attaches UTC timezone to a tz-naive last_modified datetime.

    The Toronto Open Data API can return last_modified without a timezone indicator.
    When datetime.fromisoformat produces a tz-naive datetime, run_region should
    replace tzinfo with UTC before passing it to StatusManager.add(), rather than
    raising an error.
    """
    _patch_run_region_deps(
        mocker,
        minimal_muni_gdf,
        minimal_osm_gdf,
        minimal_matches_df,
        tod_metadata={"last_modified": "2024-01-01T00:00:00"},  # no timezone
    )
    config = _make_config(source=TodMunicipalSource(dataset_name="x", resource_id="y"))
    # Should not raise even though the datetime string has no timezone
    run_region(config, output_root=tmp_path)


def test_run_region_url_source(
    tmp_path, minimal_muni_gdf, minimal_osm_gdf, minimal_matches_df, mocker
):
    """run_region downloads municipal data via gpd.read_file for a UrlMunicipalSource.

    When the config uses a UrlMunicipalSource, run_region should call gpd.read_file
    with the configured URL instead of the Toronto Open Data API, and still produce
    the expected output files.
    """
    mocker.patch("geopandas.read_file", return_value=minimal_muni_gdf)
    mocker.patch(
        "bikespace_data.cycling_network_conflation.update_conflation._download_osm_gdf",
        return_value=(minimal_osm_gdf, datetime.now(timezone.utc)),
    )
    mocker.patch(
        "bikespace_data.cycling_network_conflation.update_conflation.match_cycling_network",
        return_value=minimal_matches_df,
    )
    mocker.patch("bikespace_data.cycling_network_conflation.update_conflation.StatusManager")

    config = _make_config(source=UrlMunicipalSource(url="http://example.com/data.geojson"))
    run_region(config, output_root=tmp_path)
    assert (tmp_path / config.name / "output_files" / "matches.csv").exists()


def test_run_region_raises_for_unknown_source_type(
    tmp_path, minimal_muni_gdf, minimal_osm_gdf, minimal_matches_df, mocker
):
    """run_region raises ValueError when municipal_source is not a recognised type.

    If a RegionConfig is constructed with an unsupported source type (not
    TodMunicipalSource or UrlMunicipalSource), run_region should raise ValueError
    immediately after downloading — so misconfigured regions fail loudly.
    """
    mocker.patch("bikespace_data.cycling_network_conflation.update_conflation.StatusManager")

    class _UnknownSource:
        pass

    config = _make_config(source=_UnknownSource())
    with pytest.raises(ValueError, match="Unknown municipal source type"):
        run_region(config, output_root=tmp_path)


def test_run_region_archive_creates_timestamped_parquet(
    tmp_path, minimal_muni_gdf, minimal_osm_gdf, minimal_matches_df, mocker
):
    """run_region creates timestamped parquet archive files when archive=True.

    With archive=True, run_region should create archive sub-directories inside
    output_files/archive/ and display_files/archive/, each containing a matches.parquet
    file, in addition to the standard CSV and GeoJSON outputs.
    """
    _patch_run_region_deps(mocker, minimal_muni_gdf, minimal_osm_gdf, minimal_matches_df)
    config = _make_config(source=TodMunicipalSource(dataset_name="x", resource_id="y"))
    run_region(config, output_root=tmp_path, archive=True)

    region_root = tmp_path / config.name
    archive_dirs = list((region_root / "output_files" / "archive").iterdir())
    assert len(archive_dirs) == 1
    assert (archive_dirs[0] / "matches.parquet").exists()

    display_archive_dirs = list((region_root / "display_files" / "archive").iterdir())
    assert len(display_archive_dirs) == 1
    assert (display_archive_dirs[0] / "matches.parquet").exists()


def test_run_region_null_osm_way_id_row_is_skipped_in_lookups(
    tmp_path, minimal_muni_gdf, minimal_osm_gdf, mocker
):
    """run_region skips rows with null osm_way_id when building the lookup JSON files.

    When the matches DataFrame contains a row where osm_way_id is None (i.e. a
    municipal segment with no OSM match), the conditional guards at the loop body
    in the municipal_with_matches.json and osm_with_matches.json sections should
    skip those rows rather than appending None values. The output files should still
    be written successfully.
    """
    matches_with_null = pd.DataFrame(
        [
            {
                "SEGMENT_ID": 1,
                "osm_way_id": None,
                "match_type": "auto",
                "override_action": None,
                "flags": "",
            }
        ]
    )
    _patch_run_region_deps(mocker, minimal_muni_gdf, minimal_osm_gdf, matches_with_null)
    config = _make_config(source=TodMunicipalSource(dataset_name="x", resource_id="y"))
    run_region(config, output_root=tmp_path)

    import json as _json

    display_dir = tmp_path / config.name / "display_files"
    with open(display_dir / "municipal_with_matches.json") as f:
        muni_data = _json.load(f)
    # The null osm_way_id row should be skipped → lookup list stays empty for SEGMENT_ID=1
    assert muni_data["matches"]["1"] == []

    with open(display_dir / "osm_with_matches.json") as f:
        osm_data = _json.load(f)
    # The null row should not populate any osm entry either
    assert all(v == [] for v in osm_data["matches"].values())


# --- _download_osm_gdf ---


_TORONTO_LON, _TORONTO_LAT = -79.38, 43.65  # downtown Toronto, inside EPSG:32617 domain


def _make_overpass_response(*ways):
    """Build a minimal GeoJSON response as returned by the overpass library.

    Each entry in ways is a tuple of (id, highway_tag, coords). coords is a list
    of (lon, lat) pairs for the LineString geometry.
    """
    features = [
        {
            "type": "Feature",
            "properties": {"id": way_id, "highway": highway},
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
        }
        for way_id, highway, coords in ways
    ]
    return {"features": features}


def _make_muni_for_download():
    """Return a minimal municipal GDF in WGS84 with Toronto-area coordinates.

    Uses downtown Toronto coordinates so that reprojection to EPSG:32617 (UTM Zone 17N)
    is valid — (0,0) in WGS84 would land outside the UTM zone and cause geometry errors.
    """
    return gpd.GeoDataFrame(
        {"SEGMENT_ID": [1]},
        geometry=gpd.GeoSeries.from_wkt(
            [f"LINESTRING({_TORONTO_LON} {_TORONTO_LAT}, {_TORONTO_LON + 0.001} {_TORONTO_LAT})"]
        ),
        crs="EPSG:4326",
    )


def test_download_osm_gdf_returns_cycling_ways_and_filters_lts_road(mocker):
    """_download_osm_gdf keeps cycling ways and drops lts_road ways outside the buffer.

    Given one highway=cycleway way (always kept) and one highway=residential way
    well outside the municipal buffer, the function should return only the cycling
    way. This covers the main execution path including the lts_road spatial filter.
    """
    lon, lat = _TORONTO_LON, _TORONTO_LAT
    response = _make_overpass_response(
        (1, "cycleway", [[lon, lat], [lon + 0.001, lat]]),  # cycling → always kept
        (2, "residential", [[lon + 5.0, lat + 5.0], [lon + 5.001, lat + 5.0]]),  # far away → dropped
    )
    mock_api = mocker.MagicMock()
    mock_api.get.return_value = response
    mocker.patch(
        "bikespace_data.cycling_network_conflation.update_conflation.overpass.API",
        return_value=mock_api,
    )
    mocker.patch("bikespace_data.cycling_network_conflation.update_conflation.load_dotenv")

    config = _make_config()
    muni_gdf = _make_muni_for_download()
    osm_gdf, last_updated = _download_osm_gdf(config, muni_gdf)

    assert 1 in osm_gdf.index
    assert 2 not in osm_gdf.index
    assert osm_gdf.loc[1, "_query"] == "cycling"
    assert isinstance(last_updated, datetime)


def test_download_osm_gdf_all_cycling_ways_skips_lts_filter(mocker):
    """_download_osm_gdf skips the spatial lts_road filter when all ways are cycling ways.

    When every feature returned by Overpass is classified as a cycling way
    (e.g. highway=cycleway), is_lts.any() is False and the spatial buffer filter
    is not applied. All features should be retained in the output. This covers the
    False branch of the `if is_lts.any():` guard.
    """
    lon, lat = _TORONTO_LON, _TORONTO_LAT
    response = _make_overpass_response(
        (1, "cycleway", [[lon, lat], [lon + 0.001, lat]]),
        (2, "cycleway", [[lon + 0.002, lat], [lon + 0.003, lat]]),
    )
    mock_api = mocker.MagicMock()
    mock_api.get.return_value = response
    mocker.patch(
        "bikespace_data.cycling_network_conflation.update_conflation.overpass.API",
        return_value=mock_api,
    )
    mocker.patch("bikespace_data.cycling_network_conflation.update_conflation.load_dotenv")

    config = _make_config()
    muni_gdf = _make_muni_for_download()
    osm_gdf, _ = _download_osm_gdf(config, muni_gdf)

    assert len(osm_gdf) == 2
    assert (osm_gdf["_query"] == "cycling").all()


def test_download_osm_gdf_empty_features_skips_index_assignment(mocker):
    """_download_osm_gdf skips setting the GeoDataFrame index when no features are returned.

    When the Overpass response contains an empty feature list, `ids` is empty
    and the `if ids:` guard at line 93 evaluates to False, leaving the GDF index
    at its default (covering branch 93->98). The current geopandas version raises
    ValueError for `from_features([], crs=...)`, so `from_features` is patched to
    return a valid empty GeoDataFrame, isolating the branch under test.
    """
    mock_api = mocker.MagicMock()
    mock_api.get.return_value = {"features": []}
    mocker.patch(
        "bikespace_data.cycling_network_conflation.update_conflation.overpass.API",
        return_value=mock_api,
    )
    mocker.patch("bikespace_data.cycling_network_conflation.update_conflation.load_dotenv")
    empty_gdf = gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs="EPSG:4326"))
    mocker.patch.object(gpd.GeoDataFrame, "from_features", return_value=empty_gdf)

    config = _make_config()
    muni_gdf = _make_muni_for_download()
    osm_gdf, _ = _download_osm_gdf(config, muni_gdf)

    assert len(osm_gdf) == 0


def test_download_osm_gdf_uses_custom_overpass_endpoint(mocker, monkeypatch):
    """_download_osm_gdf uses the OVERPASS_API_URL and OVERPASS_API_NAME env vars when set.

    When OVERPASS_API_URL is set in the environment, the function should construct
    the overpass.API instance with that URL rather than the default. When
    OVERPASS_API_NAME is also set, that name is used in the print output (covered
    by ensuring no exception is raised and the API constructor received the custom URL).
    """
    monkeypatch.setenv("OVERPASS_API_URL", "http://my-overpass.example.com/api/interpreter")
    monkeypatch.setenv("OVERPASS_API_NAME", "my-overpass")

    lon, lat = _TORONTO_LON, _TORONTO_LAT
    mock_api = mocker.MagicMock()
    mock_api.get.return_value = _make_overpass_response(
        (1, "cycleway", [[lon, lat], [lon + 0.001, lat]]),
    )
    api_constructor = mocker.patch(
        "bikespace_data.cycling_network_conflation.update_conflation.overpass.API",
        return_value=mock_api,
    )
    mocker.patch("bikespace_data.cycling_network_conflation.update_conflation.load_dotenv")

    config = _make_config()
    muni_gdf = _make_muni_for_download()
    _download_osm_gdf(config, muni_gdf)

    api_constructor.assert_called_once()
    call_kwargs = api_constructor.call_args
    assert "http://my-overpass.example.com" in str(call_kwargs)
