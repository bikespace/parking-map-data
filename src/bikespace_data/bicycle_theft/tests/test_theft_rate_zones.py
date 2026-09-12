import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

from bikespace_data.bicycle_theft.theft_rate_zones import (
    aggregate_theft_rates,
    assign_thefts_to_neighbourhoods,
    detect_tts_weight_col,
    filter_to_complete_years,
    load_thefts_gdf,
    load_tts_zones,
)


def make_point_gdf(coords):
    return gpd.GeoDataFrame(geometry=[Point(x, y) for x, y in coords], crs="EPSG:4326")


@pytest.fixture
def neighbourhoods_gdf():
    """Two adjacent square neighbourhoods covering (0,0)-(2,1)."""
    return gpd.GeoDataFrame(
        {
            "neighbourhood_number": [1, 2],
            "neighbourhood_name": ["West Zone", "East Zone"],
        },
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]),
        ],
        crs="EPSG:4326",
    )


def test_assign_thefts_to_neighbourhoods_within(neighbourhoods_gdf):
    thefts = make_point_gdf([(0.5, 0.5), (0.6, 0.5), (1.5, 0.5)])
    counts = assign_thefts_to_neighbourhoods(thefts, neighbourhoods_gdf)
    assert counts.loc[1] == 2
    assert counts.loc[2] == 1
    assert counts.sum() == 3


def test_assign_thefts_to_neighbourhoods_nearest_fallback(neighbourhoods_gdf):
    # a point just outside both polygons should still be assigned to the nearest one
    thefts = make_point_gdf([(0.5, 1.2)])
    counts = assign_thefts_to_neighbourhoods(thefts, neighbourhoods_gdf)
    assert counts.sum() == 1
    assert counts.loc[1] == 1


def test_detect_tts_weight_col_computes_bike_trips_est():
    tts = gpd.GeoDataFrame(
        {"TTS2022": [1000.0], "mode_bike": [5.0]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )
    col, augmented = detect_tts_weight_col(tts)
    assert col == "bike_trips_est"
    assert augmented["bike_trips_est"].iloc[0] == 50.0


def test_detect_tts_weight_col_falls_back_to_known_column():
    tts = gpd.GeoDataFrame(
        {"trips": [42]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )
    col, _ = detect_tts_weight_col(tts)
    assert col == "trips"


def test_detect_tts_weight_col_none_found():
    tts = gpd.GeoDataFrame(
        {"some_other_col": ["a"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )
    col, _ = detect_tts_weight_col(tts)
    assert col is None


def test_aggregate_theft_rates_splits_weight_by_area(neighbourhoods_gdf):
    thefts = make_point_gdf([(0.5, 0.5), (0.5, 0.5), (1.5, 0.5)])

    # a single TTS zone spanning both neighbourhoods equally (x: 0 to 2)
    tts = gpd.GeoDataFrame(
        {"trips": [1000.0]},
        geometry=[Polygon([(0, 0), (2, 0), (2, 1), (0, 1)])],
        crs="EPSG:4326",
    )

    result = aggregate_theft_rates(neighbourhoods_gdf, thefts, tts, tts_weight_col="trips")

    west = result.set_index("neighbourhood_number").loc[1]
    east = result.set_index("neighbourhood_number").loc[2]

    assert west["theft_count"] == 2
    assert east["theft_count"] == 1
    # the TTS zone is split evenly between the two equal-area neighbourhoods
    assert west["bike_trips"] == pytest.approx(500.0, rel=0.05)
    assert east["bike_trips"] == pytest.approx(500.0, rel=0.05)
    assert west["theft_per_1000_trips"] == pytest.approx(
        2 / west["bike_trips"] * 1000
    )


def test_filter_to_complete_years_excludes_sparse_and_partial_years():
    # synthetic, arbitrary years chosen purely to exercise the relative-count heuristic —
    # unrelated to the current real-world date
    thefts = gpd.GeoDataFrame(
        {
            "OCC_YEAR": (
                [1999] * 1  # stray historical outlier
                + [2023] * 100  # complete year
                + [2024] * 100  # complete year
                + [2025] * 20  # in-progress/partial year
            )
        },
        geometry=[Point(0.5, 0.5)] * 221,
        crs="EPSG:4326",
    )

    filtered, num_years = filter_to_complete_years(thefts)

    assert num_years == 2
    assert set(filtered["OCC_YEAR"].unique()) == {2023, 2024}


def test_filter_to_complete_years_missing_year_column():
    thefts = make_point_gdf([(0.5, 0.5)])

    filtered, num_years = filter_to_complete_years(thefts, year_col="OCC_YEAR")

    assert num_years == 0
    assert len(filtered) == 1


def test_aggregate_theft_rates_annualizes_using_complete_years(neighbourhoods_gdf):
    # 20 thefts across two complete years, plus one stray historical outlier that should
    # count toward the raw total but not the annualized rate; years are synthetic fixture
    # data, not tied to the current real-world date
    thefts = gpd.GeoDataFrame(
        {"OCC_YEAR": [2023] * 10 + [2024] * 10 + [1999] * 1},
        geometry=[Point(0.5, 0.5)] * 21,
        crs="EPSG:4326",
    )
    # TTS zone exactly matches the West Zone polygon, so all 1000 trips go to West Zone
    tts = gpd.GeoDataFrame(
        {"trips": [1000.0]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )

    result = aggregate_theft_rates(neighbourhoods_gdf, thefts, tts, tts_weight_col="trips")
    west = result.set_index("neighbourhood_number").loc[1]

    assert west["theft_count"] == 21
    assert west["theft_years_of_data"] == 2
    expected_daily = (20 / 2) / 365
    assert west["daily_theft_estimate"] == pytest.approx(expected_daily)
    assert west["theft_per_1000_trips"] == pytest.approx(expected_daily)


def test_load_thefts_gdf_cleans_and_fixes_swapped_coords(tmp_path):
    # one point already in correct (lon, lat) order, one with lat/lon swapped
    raw = gpd.GeoDataFrame(
        geometry=[Point(-79.4, 43.7), Point(43.71, -79.41)],
        crs="EPSG:4326",
    )
    path = tmp_path / "thefts.geojson"
    raw.to_file(path, driver="GeoJSON")

    result = load_thefts_gdf(path)

    assert len(result) == 2
    # both points should end up in Toronto-area (lon, lat) order after the swap fix
    assert all(-130 <= x <= -50 for x in result.geometry.x)
    assert all(5 <= y <= 70 for y in result.geometry.y)


def test_load_thefts_gdf_converts_non_point_geometry_to_centroid(tmp_path):
    raw = gpd.GeoDataFrame(
        geometry=[Polygon([(-79.41, 43.7), (-79.39, 43.7), (-79.4, 43.71)])],
        crs="EPSG:4326",
    )
    path = tmp_path / "thefts.geojson"
    raw.to_file(path, driver="GeoJSON")

    result = load_thefts_gdf(path)

    assert len(result) == 1
    assert result.geometry.iloc[0].geom_type == "Point"


def test_load_tts_zones_reprojects_to_4326(tmp_path):
    raw = gpd.GeoDataFrame(
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])], crs="EPSG:3857"
    )
    path = tmp_path / "tts.geojson"
    raw.to_file(path, driver="GeoJSON")

    result = load_tts_zones(path)

    assert result.crs.to_epsg() == 4326


def test_aggregate_theft_rates_without_tts_data(neighbourhoods_gdf):
    thefts = make_point_gdf([(0.5, 0.5)])
    empty_tts = gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:4326")

    result = aggregate_theft_rates(neighbourhoods_gdf, thefts, empty_tts)

    assert (result["bike_trips"] == 0).all()
    assert result.set_index("neighbourhood_number").loc[1, "theft_count"] == 1
    assert pd.isna(
        result.set_index("neighbourhood_number").loc[1, "theft_per_1000_trips"]
    )
