from pytest import raises
from tenacity import RetryError

from bikespace_data.bicycle_parking.wrappers import BikeDataToronto

mock_metadata_response = {
    "success": True,
    "result": {
        "resources": [
            {
                "name": "test-resource-one",
                "url": "test-url",
                "last_modified": "2025-01-01T01:23:45.123000",
            },
            {
                "name": "test-resource-two",
                "url": "test-url",
                "last_modified": "2025-01-01T01:23:45.123000",
            },
        ],
    },
}


def test_succeeds_after_retry(mocker):
    """BikeDataToronto should retry (at least once) if fetching from CKAN fails"""
    mocker.patch("tenacity.nap.time", mocker.MagicMock())
    mock_metadata_success = mocker.MagicMock()
    mock_metadata_success.json = mocker.MagicMock(return_value=mock_metadata_response)
    mock_requests = mocker.MagicMock(
        side_effect=[Exception(), mock_metadata_success, mocker.MagicMock()]
    )
    mocker.patch("requests.get", mock_requests)

    bdt = BikeDataToronto("test-dataset", "test-resource-one")
    assert mock_requests.call_count == 3


def test_fails_after_retry(mocker):
    """BikeDataToronto should retry (at least once) but fail once the retries are exhausted"""
    mocker.patch("tenacity.nap.time", mocker.MagicMock())
    mock_requests = mocker.MagicMock(side_effect=Exception())
    mocker.patch("requests.get", mock_requests)

    with raises(RetryError):
        bdt = BikeDataToronto("test-dataset", "test-resource-one")
    assert mock_requests.call_count > 1
