from datetime import datetime, timezone

import pandas as pd
import pytest

from bikespace_data.apartments.update_apartments import get_building_registrations


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
