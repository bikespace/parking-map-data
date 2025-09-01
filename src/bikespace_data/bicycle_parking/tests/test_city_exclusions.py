from http import HTTPStatus

import pytest

from bikespace_data.bicycle_parking.sources.city_exclusions import (
    get_city_exclusions,
    city_exclusions_getids,
)

mock_exclusions = [
    {
        "survey_date": "2023-12-06",
        "ids": [
            {"ref:open.toronto.ca:street-furniture-bicycle-parking:id": "BP-12345"},
            {"ref:open.toronto.ca:street-furniture-bicycle-parking:id": "BP-54321"},
        ],
        "reason": "missing",
    }
]


def test_get_city_exclusions(mocker):
    """Should return the expected response on success."""
    mock_response = mocker.MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json = mocker.MagicMock(return_value=mock_exclusions)
    mocker.patch("requests.get", return_value=mock_response)

    exclusions = get_city_exclusions()

    assert exclusions[0] == mock_exclusions[0]


def test_get_city_exclusions_failed_request(mocker):
    """Should return an informative error message on failure."""
    error_response = HTTPStatus.SERVICE_UNAVAILABLE
    mock_response = mocker.MagicMock()
    mock_response.status_code = error_response
    mocker.patch("requests.get", return_value=mock_response)

    with pytest.raises(Exception) as e:
        get_city_exclusions()
        assert str(error_response) in str(e.value)


def test_city_exclusions_getids(mocker):
    """Should return a dict with lists of ids in the expected format."""
    mock_response = mocker.MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json = mocker.MagicMock(return_value=mock_exclusions)
    mocker.patch("requests.get", return_value=mock_response)

    exclusions = get_city_exclusions()
    ids = city_exclusions_getids(exclusions)

    assert ids == {
        "ref:open.toronto.ca:street-furniture-bicycle-parking:id": [
            "BP-12345",
            "BP-54321",
        ]
    }
