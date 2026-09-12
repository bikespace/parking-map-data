from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from bikespace_data.bicycle_theft.run_theft_rate_zones import generate_theft_rate_zones


def make_neighbourhoods_gdf():
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


def test_generate_theft_rate_zones_writes_expected_outputs(mocker, tmp_path):
    thefts = gpd.GeoDataFrame(
        geometry=[Point(0.25, 0.5), Point(0.25, 0.5), Point(1.5, 0.5)],
        crs="EPSG:4326",
    )
    tts_zones = gpd.GeoDataFrame(
        {"trips": [1000.0]},
        geometry=[Polygon([(0, 0), (2, 0), (2, 1), (0, 1)])],
        crs="EPSG:4326",
    )

    mocker.patch(
        "bikespace_data.bicycle_theft.run_theft_rate_zones.load_thefts_gdf",
        return_value=thefts,
    )
    mocker.patch(
        "bikespace_data.bicycle_theft.run_theft_rate_zones.get_neighbourhoods_gdf",
        return_value=make_neighbourhoods_gdf(),
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
    )

    assert result.set_index("neighbourhood_number").loc[1, "theft_count"] == 2
    assert (output_dir / "theft-rate-by-neighbourhood.geojson").exists()
    assert (output_dir / "theft-rate-by-neighbourhood.png").exists()
    assert (display_dir / "theft-rate-by-neighbourhood-display.geojson").exists()

    display_gdf = gpd.read_file(display_dir / "theft-rate-by-neighbourhood-display.geojson")
    assert set(display_gdf.columns) == {
        "neighbourhood_number",
        "neighbourhood_name",
        "theft_count",
        "theft_years_of_data",
        "daily_theft_estimate",
        "bike_trips",
        "theft_per_1000_trips",
        "geometry",
    }


def test_generate_theft_rate_zones_survives_unreachable_tts_source(mocker, tmp_path):
    """If the TTS source can't be loaded (e.g. network error), the script should still
    produce output with bike_trips=0 for every zone rather than crashing."""
    thefts = gpd.GeoDataFrame(geometry=[Point(0.5, 0.5)], crs="EPSG:4326")

    mocker.patch(
        "bikespace_data.bicycle_theft.run_theft_rate_zones.load_thefts_gdf",
        return_value=thefts,
    )
    mocker.patch(
        "bikespace_data.bicycle_theft.run_theft_rate_zones.get_neighbourhoods_gdf",
        return_value=make_neighbourhoods_gdf(),
    )
    mocker.patch(
        "bikespace_data.bicycle_theft.run_theft_rate_zones.load_tts_zones",
        side_effect=Exception("network error"),
    )

    result = generate_theft_rate_zones(
        thefts_path=Path("unused.geojson"),
        tts_source="unused",
        output_dir=tmp_path / "output_files",
        display_dir=tmp_path / "display_files",
    )

    assert (result["bike_trips"] == 0).all()


def test_generate_theft_rate_zones_update_thefts_flag(mocker, tmp_path):
    mock_update = mocker.patch(
        "bikespace_data.bicycle_theft.update_bicycle_theft.update_bicycle_thefts"
    )
    thefts = gpd.GeoDataFrame(geometry=[Point(0.5, 0.5)], crs="EPSG:4326")

    mocker.patch(
        "bikespace_data.bicycle_theft.run_theft_rate_zones.load_thefts_gdf",
        return_value=thefts,
    )
    mocker.patch(
        "bikespace_data.bicycle_theft.run_theft_rate_zones.get_neighbourhoods_gdf",
        return_value=make_neighbourhoods_gdf(),
    )
    mocker.patch(
        "bikespace_data.bicycle_theft.run_theft_rate_zones.load_tts_zones",
        side_effect=Exception("skip TTS for this test"),
    )

    generate_theft_rate_zones(
        thefts_path=Path("unused.geojson"),
        output_dir=tmp_path / "output_files",
        display_dir=tmp_path / "display_files",
        update_thefts=True,
        no_archive=True,
    )

    mock_update.assert_called_once_with(archive=False)


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
