from datetime import datetime, timezone


import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

from bikespace_data.apartments.update_apartments import (
    get_building_evaluations,
    get_building_registrations,
    calculate_zoning_requirement,
    get_wards_gdf,
    get_neighbourhoods_gdf,
    get_bike_parking_info,
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


@pytest.mark.parametrize("optional_args", [True, False])
def test_get_building_registrations(
    optional_args,
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
        source_save_path=source_save_path if optional_args else None,
        archive_path=archive_path if optional_args else None,
        status_manager=mock_status_manager if optional_args else None,
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

    if optional_args:
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


@pytest.mark.parametrize("optional_args", [True, False])
def test_get_building_evaluations(
    optional_args, mocker, mock_evaluations_data, tmp_path
):
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
        source_save_path=source_save_path if optional_args else None,
        archive_path=archive_path if optional_args else None,
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

    if optional_args:
        # Assert source files were saved
        assert (source_save_path / "building_evaluations_2023_plus.csv").exists()
        assert (source_save_path / "building_evaluations_prior_to_2023.csv").exists()

        # Assert archive files were saved
        assert (archive_path / "building_evaluations_2023_plus.parquet").exists()
        assert (archive_path / "building_evaluations_prior_to_2023.parquet").exists()


@pytest.mark.parametrize(
    "test_case",
    [
        {
            "description": "zone 1, rounding-sensitive",
            "BICYCLE_ZONE": 1,
            "CONFIRMED_UNITS": 36,
            "short_term_min": 4,
            "short_term_max": 8,  # 7.2 -> 8
            "long_term_min": 17,
            "long_term_max": 33,  # 32.4 -> 33
            "long_term_oversized_min": 0,  # 0.85 -> 0
            "long_term_oversized_max": 1,  # 1.65 -> 1
        },
        {
            "description": "zone 2, rounding-sensitive",
            "BICYCLE_ZONE": 2,
            "CONFIRMED_UNITS": 46,
            "short_term_min": 2,
            "short_term_max": 4,  # 3.22 -> 4
            "long_term_min": 16,
            "long_term_max": 32,  # 31.28 -> 32
            "long_term_oversized_min": 0,  # 0.8 -> 0
            "long_term_oversized_max": 1,  # 1.6 -> 1
        },
    ],
)
def test_calculate_zoning_requirement(test_case):
    """Confirms that zoning requirement calculations match expected amounts and round outputs correctly based on key examples."""
    calculation = calculate_zoning_requirement(test_case)

    assert calculation["short_term_min"] == test_case["short_term_min"]
    assert calculation["short_term_max"] == test_case["short_term_max"]
    assert calculation["long_term_min"] == test_case["long_term_min"]
    assert calculation["long_term_max"] == test_case["long_term_max"]
    assert (
        calculation["long_term_oversized_min"] == test_case["long_term_oversized_min"]
    )
    assert (
        calculation["long_term_oversized_max"] == test_case["long_term_oversized_max"]
    )


@pytest.mark.parametrize(
    "test_case",
    [
        {
            "description": "both inputs are NA",
            "BICYCLE_ZONE": pd.NA,
            "CONFIRMED_UNITS": pd.NA,
        },
        {
            "description": "bicycle zone is NA",
            "BICYCLE_ZONE": pd.NA,
            "CONFIRMED_UNITS": 100,
        },
        {
            "description": "confirmed units is NA",
            "BICYCLE_ZONE": 1,
            "CONFIRMED_UNITS": pd.NA,
        },
    ],
)
def test_calculate_zoning_requirement_null_inputs(test_case):
    """Confirms that zoning requirement calculations return null values if one of the inputs (bicycle zone or number of units) is null."""
    calculation = calculate_zoning_requirement(test_case)

    assert pd.isna(calculation["short_term_min"])
    assert pd.isna(calculation["short_term_max"])
    assert pd.isna(calculation["long_term_min"])
    assert pd.isna(calculation["long_term_max"])
    assert pd.isna(calculation["long_term_oversized_min"])
    assert pd.isna(calculation["long_term_oversized_max"])


@pytest.mark.parametrize(
    "test_case",
    [
        {
            "description": "bicycle zone is wrong",
            "BICYCLE_ZONE": 3,
            "CONFIRMED_UNITS": 100,
        },
        {
            "description": "number of units is wrong type",
            "BICYCLE_ZONE": 1,
            "CONFIRMED_UNITS": 12.5,
        },
    ],
)
def test_calculate_zoning_requirement_input_errors(test_case):
    """Confirms that calculate_zoning_requirement raises a TypeError when an invalid input is provided."""
    with pytest.raises(TypeError):
        calculate_zoning_requirement(test_case)


@pytest.fixture
def mock_wards_gdf():
    """
    Fixture to provide a mock GeoDataFrame for wards.
    """
    data = {
        "AREA_SHORT_CODE": [1, 2],
        "AREA_NAME": ["Ward 1", "Ward 2"],
        "geometry": [
            Polygon([(0, 0), (1, 1), (1, 0)]),
            Polygon([(2, 2), (3, 3), (3, 2)]),
        ],
    }
    return gpd.GeoDataFrame(data, crs="EPSG:4326")


@pytest.mark.parametrize("optional_args", [True, False])
def test_get_wards_gdf(optional_args, mocker, mock_wards_gdf, tmp_path):
    """
    Test the get_wards_gdf function for correct data retrieval and processing.
    """
    # Mock the external dependencies
    mock_response = {"gdf": mock_wards_gdf}
    mock_request_tod_gdf = mocker.patch(
        "bikespace_data.apartments.update_apartments.request_tod_gdf",
        return_value=mock_response,
    )
    mock_save_geo_output = mocker.patch(
        "bikespace_data.apartments.update_apartments.save_geo_output"
    )

    source_save_path = tmp_path if optional_args else None
    archive_name = "archive/test" if optional_args else None

    # Call the function
    result_gdf = get_wards_gdf(
        source_save_path=source_save_path,
        archive_name=archive_name,
    )

    # Assert that the data is requested correctly
    mock_request_tod_gdf.assert_called_once_with(
        dataset_name="city-wards",
        resource_id="737b29e0-8329-4260-b6af-21555ab24f28",
    )

    # Assert the output is formatted correctly
    assert "ward_code" in result_gdf.columns
    assert "ward_name" in result_gdf.columns
    assert "ward_full" in result_gdf.columns
    assert "geometry" in result_gdf.columns
    assert len(result_gdf.columns) == 4
    assert result_gdf["ward_code"].tolist() == [1, 2]
    assert result_gdf["ward_name"].tolist() == ["Ward 1", "Ward 2"]
    assert result_gdf["ward_full"].tolist() == ["Ward 1 (1)", "Ward 2 (2)"]

    # Assert file saving is handled correctly
    if optional_args:
        mock_save_geo_output.assert_called_once_with(
            mock_wards_gdf,
            path=source_save_path,
            file_name="wards.geojson",
            archive_name=archive_name,
        )
    else:
        mock_save_geo_output.assert_not_called()


@pytest.fixture
def mock_neighbourhoods_gdf():
    """
    Fixture to provide a mock GeoDataFrame for neighbourhoods.
    """
    data = {
        "AREA_SHORT_CODE": [101, 102],
        "AREA_NAME": ["Neighbourhood A", "Neighbourhood B"],
        "CLASSIFICATION": ["Type 1", "Type 2"],
        "CLASSIFICATION_CODE": [1, 2],
        "geometry": [
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(2, 2), (3, 2), (3, 3), (2, 3)]),
        ],
    }
    return gpd.GeoDataFrame(data, crs="EPSG:4326")


@pytest.mark.parametrize("optional_args", [True, False])
def test_get_neighbourhoods_gdf(
    optional_args, mocker, mock_neighbourhoods_gdf, tmp_path
):
    """
    Test the get_neighbourhoods_gdf function for correct data retrieval and processing.
    """
    # Mock the external dependencies
    mock_response = {"gdf": mock_neighbourhoods_gdf}
    mock_request_tod_gdf = mocker.patch(
        "bikespace_data.apartments.update_apartments.request_tod_gdf",
        return_value=mock_response,
    )
    mock_save_geo_output = mocker.patch(
        "bikespace_data.apartments.update_apartments.save_geo_output"
    )

    source_save_path = tmp_path if optional_args else None
    archive_name = "archive/test_neighbourhoods" if optional_args else None

    # Call the function
    result_gdf = get_neighbourhoods_gdf(
        source_save_path=source_save_path,
        archive_name=archive_name,
    )

    # Assert that the data is requested correctly
    mock_request_tod_gdf.assert_called_once_with(
        dataset_name="neighbourhoods",
        resource_id="0719053b-28b7-48ea-b863-068823a93aaa",
    )

    # Assert the output is formatted correctly
    expected_columns = [
        "neighbourhood_number",
        "neighbourhood_name",
        "neighbourhood_classification",
        "neighbourhood_classification_code",
        "geometry",
    ]
    assert all(col in result_gdf.columns for col in expected_columns)
    assert len(result_gdf.columns) == len(expected_columns)
    assert result_gdf["neighbourhood_number"].tolist() == [101, 102]
    assert result_gdf["neighbourhood_name"].tolist() == [
        "Neighbourhood A",
        "Neighbourhood B",
    ]
    assert result_gdf["neighbourhood_classification"].tolist() == ["Type 1", "Type 2"]
    assert result_gdf["neighbourhood_classification_code"].tolist() == [1, 2]

    # Assert file saving is handled correctly
    if optional_args:
        mock_save_geo_output.assert_called_once_with(
            mock_neighbourhoods_gdf,
            path=source_save_path,
            file_name="neighbourhoods.geojson",
            archive_name=archive_name,
        )
    else:
        mock_save_geo_output.assert_not_called()


@pytest.mark.parametrize("archive", [True, False])
def test_get_bike_parking_info(
    archive,
    mocker,
    tmp_path,
):
    """
    Test the main get_bike_parking_info orchestration function to ensure it correctly calls dependencies and produces the expected final output.
    """
    # Mock datetime to have a predictable date for archive paths
    mock_datetime = mocker.patch("bikespace_data.apartments.update_apartments.datetime")
    mock_datetime.now.return_value.strftime.return_value = "2024-01-01"

    # Mock dependencies of get_bike_parking_info
    mock_sm_instance = mocker.Mock()
    mocker.patch(
        "bikespace_data.apartments.update_apartments.StatusManager",
        return_value=mock_sm_instance,
    )

    mock_registrations_df = pd.DataFrame(
        {
            "RSN": [1, 2],
            "CONFIRMED_UNITS": [100, 50],
            "SITE_ADDRESS": ["Address 1", "Address 2"],
            "bike_parking_indoor": pd.to_numeric([10, 2], downcast="integer"),
            "bike_parking_outdoor": pd.to_numeric([5, 1], downcast="integer"),
        }
    )
    mock_get_building_registrations = mocker.patch(
        "bikespace_data.apartments.update_apartments.get_building_registrations",
        return_value=mock_registrations_df,
    )
    mock_evaluations_df = pd.DataFrame(
        {
            "LATITUDE": [43.0, None],
            "LONGITUDE": [-79.0, None],
            "SITE_ADDRESS": ["Address 1", "Address 2"],
        },
        index=pd.Series([1, 2], name="RSN"),
    )
    mock_get_building_evaluations = mocker.patch(
        "bikespace_data.apartments.update_apartments.get_building_evaluations",
        return_value=mock_evaluations_df,
    )
    mock_address_cache_instance = mocker.Mock()
    mock_address_cache_instance.cache = {"Address 2": (43.1, -79.1)}
    mocker.patch(
        "bikespace_data.apartments.update_apartments.AddressCache",
        return_value=mock_address_cache_instance,
    )

    def geocode_side_effect(df, lat_col, lon_col, address_col, cache):
        df.loc[df["RSN"] == 2, lat_col] = 43.1
        df.loc[df["RSN"] == 2, lon_col] = -79.1
        return {"df": df, "address_cache": {**cache, "Address 1": (43.0, -79.0)}}

    mocker.patch(
        "bikespace_data.apartments.update_apartments.geocode_missing",
        side_effect=geocode_side_effect,
    )

    # Create processed mock for wards
    wards_data = {
        "AREA_SHORT_CODE": [1],
        "AREA_NAME": ["Ward 1"],
        "geometry": [Polygon([(-80, 40), (-78, 40), (-78, 44), (-80, 44)])],
    }
    wards_gdf = gpd.GeoDataFrame(wards_data, crs="EPSG:4326")
    processed_wards_gdf = wards_gdf.copy()
    processed_wards_gdf["ward_full"] = [
        f"{x.AREA_NAME} ({x.AREA_SHORT_CODE})" for x in processed_wards_gdf.itertuples()
    ]
    processed_wards_gdf = processed_wards_gdf.rename(
        columns={"AREA_SHORT_CODE": "ward_code", "AREA_NAME": "ward_name"}
    )
    mocker.patch(
        "bikespace_data.apartments.update_apartments.get_wards_gdf",
        return_value=processed_wards_gdf,
    )

    # Create processed mock for neighbourhoods
    neighbourhoods_data = {
        "AREA_SHORT_CODE": [101],
        "AREA_NAME": ["Neighbourhood A"],
        "CLASSIFICATION": ["Type 1"],
        "CLASSIFICATION_CODE": [1],
        "geometry": [Polygon([(-80, 40), (-78, 40), (-78, 44), (-80, 44)])],
    }
    neighbourhoods_gdf = gpd.GeoDataFrame(neighbourhoods_data, crs="EPSG:4326")
    processed_neighbourhoods_gdf = neighbourhoods_gdf.rename(
        columns={
            "AREA_SHORT_CODE": "neighbourhood_number",
            "AREA_NAME": "neighbourhood_name",
            "CLASSIFICATION": "neighbourhood_classification",
            "CLASSIFICATION_CODE": "neighbourhood_classification_code",
        }
    )
    mocker.patch(
        "bikespace_data.apartments.update_apartments.get_neighbourhoods_gdf",
        return_value=processed_neighbourhoods_gdf,
    )

    mock_bicycle_zones_gdf = gpd.GeoDataFrame(
        {
            "BICYCLE_ZONE": [1],
            "geometry": [Polygon([(-80, 40), (-78, 40), (-78, 44), (-80, 44)])],
        },
        crs="EPSG:4326",
    )
    mocker.patch(
        "geopandas.GeoDataFrame.from_file", return_value=mock_bicycle_zones_gdf
    )

    mock_save_geo_output = mocker.patch(
        "bikespace_data.apartments.update_apartments.save_geo_output"
    )
    mock_to_csv = mocker.patch("geopandas.geodataframe.GeoDataFrame.to_csv")

    # Call the function under test
    output_path = tmp_path / "apartments"
    get_bike_parking_info(
        output_path=output_path,
        archive=archive,
    )

    # Assertions
    assert (output_path / "source_files").is_dir()
    assert (output_path / "output_files").is_dir()
    assert (output_path / "display_files").is_dir()
    mock_get_building_registrations.assert_called_once()
    mock_get_building_evaluations.assert_called_once()
    mock_address_cache_instance.save_cache.assert_called_once()

    # Two calls to save_geo_output for the final results
    assert mock_save_geo_output.call_count == 2
    mock_to_csv.assert_called_once()

    # Inspect the final GeoDataFrame passed to save_geo_output
    final_gdf = None
    for call in mock_save_geo_output.call_args_list:
        if call.kwargs["file_name"] == "apartments.geojson":
            final_gdf = call.args[0]
            break

    assert final_gdf is not None

    # Check for columns from all merged sources
    assert "bike_parking_indoor" in final_gdf.columns
    assert "LATITUDE" in final_gdf.columns
    assert "ward_full" in final_gdf.columns
    assert "neighbourhood_name" in final_gdf.columns
    assert "BICYCLE_ZONE" in final_gdf.columns
    assert "short_term_min" in final_gdf.columns
    assert "long_term_min" in final_gdf.columns
    assert "total_unmet_min" in final_gdf.columns

    # Check calculations for a specific row
    row1 = final_gdf[final_gdf["RSN"] == 1].iloc[0]

    # Based on calculate_zoning_requirement test cases and our inputs:
    # 100 units, zone 1 -> short_term_min=10, long_term_min=45
    # Parking: outdoor=5, indoor=10
    assert row1["short_term_min_unmet"] == 5
    assert row1["long_term_min_unmet"] == 35
    assert row1["total_unmet_min"] == 40
