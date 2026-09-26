from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from bikespace_data.bicycle_theft.run_theft_rate_zones import generate_theft_rate_zones


# a ~2 km x 1 km "city" near Toronto (the zone builder works in a Toronto UTM projection)
WEST, SOUTH, EAST, NORTH = -79.41, 43.65, -79.39, 43.66


def make_city_gdf():
    return gpd.GeoDataFrame(
        geometry=[Polygon([(WEST, SOUTH), (EAST, SOUTH), (EAST, NORTH), (WEST, NORTH)])],
        crs="EPSG:4326",
    )


def test_generate_theft_rate_zones_writes_expected_outputs(mocker, tmp_path):
    thefts = gpd.GeoDataFrame(
        geometry=[Point(-79.405, 43.655)] * 2 + [Point(-79.395, 43.655)],
        crs="EPSG:4326",
    )
    tts_zones = gpd.GeoDataFrame(
        {"trips": [1000.0]},
        geometry=[Polygon([(WEST, SOUTH), (EAST, SOUTH), (EAST, NORTH), (WEST, NORTH)])],
        crs="EPSG:4326",
    )

    mocker.patch(
        "bikespace_data.bicycle_theft.run_theft_rate_zones.load_thefts_gdf",
        return_value=thefts,
    )
    mocker.patch(
        "bikespace_data.bicycle_theft.run_theft_rate_zones.get_neighbourhoods_gdf",
        return_value=make_city_gdf(),
    )
    mocker.patch(
        "bikespace_data.bicycle_theft.run_theft_rate_zones.load_tts_zones",
        return_value=tts_zones,
    )

    output_dir = tmp_path / "output_files"
    display_dir = tmp_path / "display_files"

    result = generate_theft_rate_zones(
        thefts_path=Path("unused.geojson"),
        tts_source="unused",
        output_dir=output_dir,
        display_dir=display_dir,
        n_zones=4,
    )

    assert result["theft_count"].sum() == 3
    assert result["bike_trips"].sum() == pytest.approx(1000.0, rel=0.05)
    assert (output_dir / "theft-rate-zones.geojson").exists()
    assert (output_dir / "theft-rate-zones.png").exists()
    assert (display_dir / "theft-rate-zones-display.geojson").exists()

    display_gdf = gpd.read_file(display_dir / "theft-rate-zones-display.geojson")
    assert set(display_gdf.columns) == {
        "zone_id",
        "theft_count",
        "theft_years_of_data",
        "daily_theft_estimate",
        "bike_trips",
        "theft_per_1000_trips",
        "geometry",
    }


@pytest.mark.parametrize(
    "tts_patch",
    [
        {"side_effect": Exception("network error")},
        {"return_value": gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")},
        # a zone with no usable bike-trip column, e.g. after an upstream schema change
        {
            "return_value": gpd.GeoDataFrame(
                {"TTS2022": [1]}, geometry=[Point(-79.4, 43.655).buffer(0.01)], crs="EPSG:4326"
            )
        },
    ],
    ids=["unreachable", "empty", "no_weight_column"],
)
def test_generate_theft_rate_zones_bad_tts_source_writes_nothing(mocker, tmp_path, tts_patch):
    """Without usable TTS bike-trip data the rates are meaningless, so the script must fail
    before writing any output (the workflow then has nothing to commit to the data branch)."""
    thefts = gpd.GeoDataFrame(geometry=[Point(-79.4, 43.655)], crs="EPSG:4326")

    mocker.patch(
        "bikespace_data.bicycle_theft.run_theft_rate_zones.load_thefts_gdf",
        return_value=thefts,
    )
    mocker.patch(
        "bikespace_data.bicycle_theft.run_theft_rate_zones.get_neighbourhoods_gdf",
        return_value=make_city_gdf(),
    )
    mocker.patch(
        "bikespace_data.bicycle_theft.run_theft_rate_zones.load_tts_zones",
        **tts_patch,
    )

    with pytest.raises(Exception):
        generate_theft_rate_zones(
            thefts_path=Path("unused.geojson"),
            tts_source="unused",
            output_dir=tmp_path / "output_files",
            display_dir=tmp_path / "display_files",
            n_zones=4,
        )

    assert not (tmp_path / "output_files").exists()
    assert not (tmp_path / "display_files").exists()


def test_generate_theft_rate_zones_no_thefts_raises(mocker, tmp_path):
    mocker.patch(
        "bikespace_data.bicycle_theft.run_theft_rate_zones.load_thefts_gdf",
        return_value=gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"),
    )

    with pytest.raises(RuntimeError):
        generate_theft_rate_zones(
            thefts_path=Path("unused.geojson"),
            output_dir=tmp_path / "output_files",
            display_dir=tmp_path / "display_files",
        )
