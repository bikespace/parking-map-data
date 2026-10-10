import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from bikespace_data.bicycle_theft.manhattan_zones import build_manhattan_zones

# a ~10 km x 4 km "city" near Toronto, in degrees
CITY = Polygon([(-79.5, 43.6), (-79.38, 43.6), (-79.38, 43.64), (-79.5, 43.64)])


@pytest.fixture
def city_gdf():
    return gpd.GeoDataFrame(geometry=[CITY], crs="EPSG:4326")


@pytest.fixture
def lopsided_tts():
    # all the bike trips are in the eastern quarter of the city
    return gpd.GeoDataFrame(
        {"trips": [9000.0, 10.0]},
        geometry=[
            Polygon([(-79.41, 43.6), (-79.38, 43.6), (-79.38, 43.64), (-79.41, 43.64)]),
            Polygon([(-79.5, 43.6), (-79.41, 43.6), (-79.41, 43.64), (-79.5, 43.64)]),
        ],
        crs="EPSG:4326",
    )


def test_build_manhattan_zones_partitions_the_city(city_gdf, lopsided_tts):
    zones = build_manhattan_zones(city_gdf, lopsided_tts, "trips", n_zones=8, cell_m=200)

    assert zones.crs.to_epsg() == 4326
    assert len(zones) == 8
    assert zones["zone_id"].is_unique
    # no gaps and no overlaps: the zones add up to the whole city
    zone_area = zones.to_crs(3857).area.sum()
    city_area = city_gdf.to_crs(3857).area.sum()
    assert zone_area == pytest.approx(city_area, rel=0.01)


def test_build_manhattan_zones_puts_more_zones_where_the_trips_are(city_gdf, lopsided_tts):
    zones = build_manhattan_zones(city_gdf, lopsided_tts, "trips", n_zones=8, cell_m=200)

    # the busy quarter of the city would get 2 of 8 zones if split by area
    busy_side = sum(zones.to_crs(3857).geometry.centroid.to_crs(4326).x > -79.41)
    assert busy_side >= 5


def test_build_manhattan_zones_without_trip_data_balances_by_area(city_gdf):
    empty_tts = gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:4326")

    zones = build_manhattan_zones(city_gdf, empty_tts, None, n_zones=4, cell_m=200)

    areas = zones.to_crs(3857).area
    assert len(zones) == 4
    assert areas.max() / areas.min() < 2
