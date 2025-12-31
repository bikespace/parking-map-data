from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from bikespace_data.bicycle_theft.update_bicycle_theft import (
    update_bicycle_thefts,
)


def generate_mock_status(last_fresh: str) -> str:
    return "\n".join(
        [
            ",".join(
                [
                    "dataset_name",
                    "last_updated",
                    "num_features",
                    "last_checked",
                    "days_since_source_update",
                ]
            ),
            ",".join(["bicycle-thefts", last_fresh, "123", last_fresh, "123"]),
        ]
    )


def test_update_bicycle_thefts_geojson(mocker, tmp_path):
    # prepare a small GeoDataFrame
    gdf = gpd.GeoDataFrame(
        {
            "OCCURRENCE_DATE": ["2025-01-01" for _ in range(3)],
            "OFFENCE_TYPE": ["THEFT" for _ in range(3)],
        },
        geometry=[Point(-79.3, 43.7), Point(-79.4, 43.8), Point(-79.35, 43.75)],
        crs="EPSG:4326",
    )

    last_fresh = "2025-01-02T00:00:00.000000+00:00"

    # mock package/resource selection to avoid network calls
    mocker.patch(
        "bikespace_data.bicycle_theft.update_bicycle_theft._pick_resource_id",
        return_value="test-resource",
    )

    # mock the Toronto Open Data request that returns a GeoDataFrame
    mocker.patch(
        "bikespace_data.bicycle_theft.update_bicycle_theft.request_tod_gdf",
        return_value={"gdf": gdf, "metadata": {"last_modified": last_fresh}},
    )

    # mock prior status fetched by StatusManager
    mock_prior_status_response = mocker.MagicMock()
    mock_prior_status_response.status_code = HTTPStatus.OK
    mock_prior_status_response.text = generate_mock_status("2025-01-01T00:00:00.000000+00:00")
    mocker.patch(
        "bikespace_data.utilities.status_manager.requests.get",
        return_value=mock_prior_status_response,
    )

    # run updater
    update_bicycle_thefts(
        status_path=tmp_path / "statuses/bicycle_theft_statuses.csv",
        output_dir=tmp_path / "bicycle_theft",
        archive=True,
    )

    # assert files created
    assert (tmp_path / "bicycle_theft" / "source_files" / "bicycle-thefts.geojson").exists()
    assert (tmp_path / "bicycle_theft" / "output_files" / "bicycle-thefts-normalized.geojson").exists()
    assert (tmp_path / "bicycle_theft" / "display_files" / "bicycle-thefts-display.geojson").exists()

    # assert output archive parquet exists
    archive_parquet = tmp_path / "bicycle_theft" / "output_files" / "archive" / datetime.now(timezone.utc).date().isoformat() / "bicycle-thefts-normalized.parquet"
    assert archive_parquet.exists()

    # assert status file was written
    assert (tmp_path / "statuses" / "bicycle_theft_statuses.csv").exists()


def test_update_bicycle_thefts_csv_fallback(mocker, tmp_path):
    # prepare a small DataFrame with lat/lon columns
    df = pd.DataFrame(
        {
            "latitude": [43.7, 43.8],
            "longitude": [-79.3, -79.4],
            "OFFENCE_TYPE": ["THEFT", "THEFT"],
        }
    )

    last_fresh = "2025-01-02T00:00:00.000000+00:00"

    # avoid calling the network to pick resources
    mocker.patch(
        "bikespace_data.bicycle_theft.update_bicycle_theft._pick_resource_id",
        return_value="test-resource",
    )

    # force the geojson request to fail so code falls back to CSV
    mocker.patch(
        "bikespace_data.bicycle_theft.update_bicycle_theft.request_tod_gdf",
        side_effect=Exception("not geojson"),
    )
    mocker.patch(
        "bikespace_data.bicycle_theft.update_bicycle_theft.request_tod_df",
        return_value={"df": df, "metadata": {"last_modified": last_fresh}},
    )

    mock_prior_status_response = mocker.MagicMock()
    mock_prior_status_response.status_code = HTTPStatus.OK
    mock_prior_status_response.text = generate_mock_status("2025-01-01T00:00:00.000000+00:00")
    mocker.patch(
        "bikespace_data.utilities.status_manager.requests.get",
        return_value=mock_prior_status_response,
    )

    update_bicycle_thefts(
        status_path=tmp_path / "statuses/bicycle_theft_statuses.csv",
        output_dir=tmp_path / "bicycle_theft",
        archive=True,
    )

    # source csv should exist
    assert (tmp_path / "bicycle_theft" / "source_files" / "bicycle-thefts.csv").exists()
    # normalized output should exist
    assert (tmp_path / "bicycle_theft" / "output_files" / "bicycle-thefts-normalized.geojson").exists()
    assert (tmp_path / "bicycle_theft" / "display_files" / "bicycle-thefts-display.geojson").exists()
    # source archive parquet should exist
    src_archive = tmp_path / "bicycle_theft" / "source_files" / "archive" / datetime.now(timezone.utc).date().isoformat() / "bicycle-thefts.parquet"
    assert src_archive.exists()


def test_update_bicycle_thefts_already_up_to_date(mocker, tmp_path):
    last_fresh = "2025-01-02T00:00:00.000000+00:00"

    mocker.patch(
        "bikespace_data.bicycle_theft.update_bicycle_theft._pick_resource_id",
        return_value="test-resource",
    )

    mocker.patch(
        "bikespace_data.bicycle_theft.update_bicycle_theft.request_tod_gdf",
        return_value={"gdf": gpd.GeoDataFrame(geometry=[]), "metadata": {"last_modified": last_fresh}},
    )

    mock_prior_status_response = mocker.MagicMock()
    mock_prior_status_response.status_code = HTTPStatus.OK
    mock_prior_status_response.text = generate_mock_status(last_fresh)
    mocker.patch(
        "bikespace_data.utilities.status_manager.requests.get",
        return_value=mock_prior_status_response,
    )

    update_bicycle_thefts(
        status_path=tmp_path / "statuses/bicycle_theft_statuses.csv",
        output_dir=tmp_path / "bicycle_theft",
        archive=True,
    )

    # no files created
    assert not any(tmp_path.iterdir())
