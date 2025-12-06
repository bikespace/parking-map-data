from datetime import datetime, timezone


import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from bikespace_data.apartments.update_apartments import (
    get_building_evaluations,
    get_building_registrations,
)


@pytest.fixture
def mock_tod_df_response():
    """
    Fixture to provide a mock response for request_tod_df.
    """
    mock_df = pd.DataFrame(
        {
            "BIKE_PARKING": [
                "10 indoor parking spots and 5 outdoor parking spots",
                "2 indoor parking spots and 1 outdoor parking spots",
                "0 indoor parking spots and 0 outdoor parking spots",
                "Invalid data",
                "Not Available",
            ],
            "CONFIRMED_STOREYS": [10, 5, 2, 8, 12],
            "CONFIRMED_UNITS": [100, 50, 20, 80, 120],
            "RSN": [1, 2, 3, 4, 5],
            "SITE_ADDRESS": [
                "123 Main St",
                "456 Oak Ave",
                "789 Pine Rd",
                "101 Elm St",
                "202 Birch Blvd",
            ],
            "PROP_MANAGEMENT_COMPANY_NAME": [
                None,
                "Company A",
                "Company B",
                None,
                "Company C",
            ],
            "PROPERTY_TYPE": ["PRIVATE", "TCHC", "SOCIAL HOUSING", "PRIVATE", "TCHC"],
            "WARD": [1, 2, 3, 4, 5],
            "YEAR_BUILT": [1990, 2000, 2010, 1980, 2020],
            "YEAR_OF_REPLACEMENT": [None, None, 2022, None, None],
            "YEAR_REGISTERED": [2010, 2011, 2012, 2013, 2014],
        }
    )
    # Set nullable integer columns to Int64 dtype
    mock_df = mock_df.astype(
        {
            "YEAR_BUILT": "Int64",
            "YEAR_OF_REPLACEMENT": "Int64",
            "YEAR_REGISTERED": "Int64",
        }
    )

    mock_metadata = {"last_modified": "2023-10-26T10:00:00Z"}
    return {"df": mock_df, "metadata": mock_metadata}


@pytest.fixture
def mock_status_manager(mocker):
    """
    Fixture to provide a mock StatusManager.
    """
    mock_status_manager = mocker.patch(
        "bikespace_data.apartments.update_apartments.StatusManager"
    )
    sm_instance = mock_status_manager.return_value
    yield sm_instance


def test_get_building_registrations(
    mocker,
    mock_tod_df_response,
    mock_status_manager,
    tmp_path,
):
    """
    Test the get_building_registrations function for correct parsing and handling
    of various arguments.
    """
    mock_request_tod_df = mocker.patch(
        "bikespace_data.apartments.update_apartments.request_tod_df",
        return_value=mock_tod_df_response,
    )

    source_save_path = tmp_path / "source_files"
    source_save_path.mkdir()
    archive_path = tmp_path / "archive"
    archive_path.mkdir()

    # Test with all arguments
    result_df = get_building_registrations(
        source_save_path=source_save_path,
        archive_path=archive_path,
        status_manager=mock_status_manager,
    )

    # Assert request_tod_df was called
    mock_request_tod_df.assert_called_once_with(
        dataset_name="apartment-building-registration",
        resource_id="97b8b7a4-baca-49c7-915d-335322dbcf95",
    )

    # Assert columns were added and values are correct
    assert "bike_parking_indoor" in result_df.columns
    assert "bike_parking_outdoor" in result_df.columns
    assert result_df["bike_parking_indoor"].equals(pd.Series([10, 2, 0, None, None]))
    assert result_df["bike_parking_outdoor"].equals(pd.Series([5, 1, 0, None, None]))

    # Assert source file was saved
    assert (source_save_path / "building_registrations.csv").exists()

    # Assert archive file was saved
    assert (archive_path / "building_registrations.parquet").exists()

    # Assert StatusManager was called
    mock_status_manager.add.assert_called_once()
    call_args = mock_status_manager.add.call_args[1]
    assert call_args["dataset_name"] == "apartment-building-registration"
    assert call_args["last_updated"] == datetime(
        2023, 10, 26, 10, 0, 0, tzinfo=timezone.utc
    )
    assert call_args["num_features"] == len(mock_tod_df_response["df"])
    assert "last_checked" in call_args


def test_get_building_registrations_no_optional_args(mocker, mock_tod_df_response):
    """
    Test get_building_registrations when no optional arguments are provided.
    """
    mock_request_tod_df = mocker.patch(
        "bikespace_data.apartments.update_apartments.request_tod_df",
        return_value=mock_tod_df_response,
    )

    result_df = get_building_registrations()

    # Assert request_tod_df was called
    mock_request_tod_df.assert_called_once()

    # Assert columns were added and values are correct
    assert "bike_parking_indoor" in result_df.columns
    assert "bike_parking_outdoor" in result_df.columns
    assert result_df["bike_parking_indoor"].equals(pd.Series([10, 2, 0, None, None]))
    assert result_df["bike_parking_outdoor"].equals(pd.Series([5, 1, 0, None, None]))


@pytest.fixture
def mock_evaluations_data():
    """
    Fixture to provide mock data for building evaluations.
    """
    # Data for 2023_plus (resource_id="7fa98ab2-7412-43cd-9270-cb44dd75b573")
    mock_xy_2023_plus = gpd.GeoSeries(
        [
            None,
            None,
            Point(-79.4, 43.4),
            Point(-79.5, 43.5),
            Point(-79.6, 43.6),
            None,
        ],  # type: ignore
        crs="EPSG:4326",
    )
    df_2023_plus = pd.DataFrame(
        {
            "RSN": [1, 2, 3, 4, 5, 6],
            "SITE ADDRESS": [
                "Address 1",
                "Address 2",
                "Address 3",
                "Address 4",
                "Address 5",
                "Invalid Address",
            ],
            "LATITUDE": [43.0, 43.1, None, 43.3, None, None],
            "LONGITUDE": [-79.0, -79.1, None, -79.3, None, None],
            "X": mock_xy_2023_plus.to_crs("EPSG:7991").x,
            "Y": mock_xy_2023_plus.to_crs("EPSG:7991").y,
        }
    )
    df_2023_plus = df_2023_plus.astype(
        {
            "RSN": "int64",
            "LATITUDE": "float64",
            "LONGITUDE": "float64",
            "X": "float64",
            "Y": "float64",
        }
    )

    # Data for prior (resource_id="979fb513-5186-41e9-bb23-7b5cc6b89915")
    mock_xy_prior = gpd.GeoSeries(
        [
            None,
            Point(-79.3, 43.3),
            None,
            None,
            Point(-79.6, 43.6),
            None,
        ],  # type: ignore
        crs="EPSG:4326",
    )
    df_prior = pd.DataFrame(
        {
            "RSN": [1, 7, 3, 8, 9, 6],  # RSN 1 and 3 are duplicates, 6 is invalid
            "SITE_ADDRESS": [
                "Address 1 Prior",
                "Address 7",
                "Address 3 Prior",
                "Address 8",
                "Address 9",
                "Invalid Address Prior",
            ],
            "LATITUDE": [43.1, None, 43.3, 43.4, None, None],
            "LONGITUDE": [-79.1, None, -79.3, -79.4, None, None],
            "X": mock_xy_prior.to_crs("EPSG:7991").x,
            "Y": mock_xy_prior.to_crs("EPSG:7991").y,
        }
    )
    df_prior = df_prior.astype(
        {
            "RSN": "int64",
            "LATITUDE": "float64",
            "LONGITUDE": "float64",
            "X": "float64",
            "Y": "float64",
        }
    )

    mock_metadata = {"last_modified": "2023-10-26T10:00:00Z"}

    return {
        "7fa98ab2-7412-43cd-9270-cb44dd75b573": {
            "df": df_2023_plus,
            "metadata": mock_metadata,
        },
        "979fb513-5186-41e9-bb23-7b5cc6b89915": {
            "df": df_prior,
            "metadata": mock_metadata,
        },
    }


def test_get_building_evaluations(mocker, mock_evaluations_data, tmp_path):
    """
    Test the get_building_evaluations function.
    """
    # Mock request_tod_df to return appropriate data based on resource_id
    mock_request_tod_df = mocker.patch(
        "bikespace_data.apartments.update_apartments.request_tod_df",
        side_effect=lambda dataset_name, resource_id: mock_evaluations_data[
            resource_id
        ],
    )

    source_save_path = tmp_path / "source_files"
    source_save_path.mkdir()
    archive_path = tmp_path / "archive"
    archive_path.mkdir()

    result_df = get_building_evaluations(
        source_save_path=source_save_path,
        archive_path=archive_path,
    )

    # Assert request_tod_df was called for both resource IDs
    calls = [
        mocker.call(
            dataset_name="apartment-building-evaluation",
            resource_id="7fa98ab2-7412-43cd-9270-cb44dd75b573",
        ),
        mocker.call(
            dataset_name="apartment-building-evaluation",
            resource_id="979fb513-5186-41e9-bb23-7b5cc6b89915",
        ),
    ]
    mock_request_tod_df.assert_has_calls(calls, any_order=True)

    # Assert output DataFrame structure and content
    assert "RSN" == result_df.index.name
    assert "SITE_ADDRESS" in result_df.columns
    assert "LATITUDE" in result_df.columns
    assert "LONGITUDE" in result_df.columns
    assert "X" not in result_df.columns
    assert "Y" not in result_df.columns

    # Verify RSNs present (6 and invalid ones should be dropped)
    expected_rsns = pd.Index([1, 2, 3, 4, 5, 7, 8, 9]).sort_values()
    assert result_df.index.sort_values().equals(expected_rsns)

    # Verify coordinate merging and conversion (median is used for duplicates)
    # RSN 1: (43.0, -79.0) and (43.1, -79.1) -> median is (43.05, -79.05)
    assert result_df.loc[1, "LATITUDE"] == pytest.approx(43.05)
    assert result_df.loc[1, "LONGITUDE"] == pytest.approx(-79.05)
    # RSN 2: (43.1, -79.1) -> (43.1, -79.1)
    assert result_df.loc[2, "LATITUDE"] == pytest.approx(43.1)
    assert result_df.loc[2, "LONGITUDE"] == pytest.approx(-79.1)
    # RSN 3: X/Y for (43.4, -79.4) and (43.3, -79.3) -> Lat/Long preferred
    assert result_df.loc[3, "LATITUDE"] == pytest.approx(43.3)
    assert result_df.loc[3, "LONGITUDE"] == pytest.approx(-79.3)
    # RSN 4: (43.3, -79.3) and X/Y for (43.5, -79.5) also available, but LAT/LONG preferred
    assert result_df.loc[4, "LATITUDE"] == pytest.approx(43.3)
    assert result_df.loc[4, "LONGITUDE"] == pytest.approx(-79.3)
    # RSN 5: Only X/Y for (43.6, -79.6) in 2023_plus
    assert result_df.loc[5, "LATITUDE"] == pytest.approx(43.6)
    assert result_df.loc[5, "LONGITUDE"] == pytest.approx(-79.6)
    # RSN 7: Only X/Y for (43.3, -79.3) in prior
    assert result_df.loc[7, "LATITUDE"] == pytest.approx(43.3)
    assert result_df.loc[7, "LONGITUDE"] == pytest.approx(-79.3)
    # RSN 8: Only (43.4, -79.4) in prior
    assert result_df.loc[8, "LATITUDE"] == pytest.approx(43.4)
    assert result_df.loc[8, "LONGITUDE"] == pytest.approx(-79.4)
    # RSN 9: Only X/Y for (43.6, -79.6) in prior
    assert result_df.loc[9, "LATITUDE"] == pytest.approx(43.6)
    assert result_df.loc[9, "LONGITUDE"] == pytest.approx(-79.6)

    # Assert source files were saved
    assert (source_save_path / "building_evaluations_2023_plus.csv").exists()
    assert (source_save_path / "building_evaluations_prior_to_2023.csv").exists()

    # Assert archive files were saved
    assert (archive_path / "building_evaluations_2023_plus.parquet").exists()
    assert (archive_path / "building_evaluations_prior_to_2023.parquet").exists()
