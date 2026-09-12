import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from bikespace_data.resources.toronto_boundaries import (
    get_neighbourhoods_gdf,
    get_wards_gdf,
)


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
        "bikespace_data.resources.toronto_boundaries.request_tod_gdf",
        return_value=mock_response,
    )
    mock_save_geo_output = mocker.patch(
        "bikespace_data.resources.toronto_boundaries.save_geo_output"
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
        "bikespace_data.resources.toronto_boundaries.request_tod_gdf",
        return_value=mock_response,
    )
    mock_save_geo_output = mocker.patch(
        "bikespace_data.resources.toronto_boundaries.save_geo_output"
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
