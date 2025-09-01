from http import HTTPStatus

import geopandas as gpd
import pytest
from geopandas.testing import assert_geodataframe_equal
from shapely import Point

from bikespace_data.resources.toronto_open_data import TODResponse, request_tod_gdf

mock_metadata_response = {
    "success": True,
    "result": {
        "resources": [
            {
                "id": "test-resource-one",
                "url": "test-url",
                "last_modified": "2025-01-01T01:23:45.123000",
            },
            {
                "id": "test-resource-two",
                "url": "test-url",
                "last_modified": "2025-01-01T01:23:45.123000",
            },
        ],
    },
}

mock_resource_response = gpd.GeoDataFrame(
    {"col1": ["name1", "name2"], "geometry": [Point(1, 2), Point(2, 1)]},
    crs="EPSG:4326",
)


def test_request_tod_gdf(mocker):
    """Should return a response in the expected format with a dict containing a geodataframe and a sub-dict of metadata properties."""
    mock_response = mocker.MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json = mocker.MagicMock(return_value=mock_metadata_response)
    mocker.patch("requests.get", return_value=mock_response)

    mocker.patch("geopandas.read_file", return_value=mock_resource_response)

    response: TODResponse = request_tod_gdf("test-dataset", "test-resource-two")

    assert_geodataframe_equal(
        response["gdf"],
        mock_resource_response.convert_dtypes(),
    )
    assert response["metadata"]["id"] == "test-resource-two"


def test_request_tod_gdf_failed_request(mocker):
    """Should return an informative error message on failure."""
    error_response = HTTPStatus.SERVICE_UNAVAILABLE
    mock_response = mocker.MagicMock()
    mock_response.status_code = error_response
    mocker.patch("requests.get", return_value=mock_response)

    with pytest.raises(Exception) as e:
        request_tod_gdf("test-dataset", "test-resource")
        for info in [str(error_response), "test-dataset", "test-resource"]:
            assert info in str(e.value)
