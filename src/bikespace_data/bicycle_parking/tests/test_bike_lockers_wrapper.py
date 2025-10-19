from http import HTTPStatus

from pytest import raises
from tenacity import RetryError

from bikespace_data.bicycle_parking.wrappers import BikeLockersToronto


def init_live_url():
    """Utility for manual testing"""
    blt = BikeLockersToronto(
        "toronto_lockers",
        "https://www.toronto.ca/services-payments/streets-parking-transportation/cycling-in-toronto/bicycle-parking/bicycle-lockers/locker-locations/",
    )
    last_updated = blt.last_updated
    gdf = blt.response_gdf

    print(last_updated)
    print(gdf.describe())
    breakpoint()


mock_success_content = """
<!DOCTYPE html>
<html lang="en-CA">
<head>
    <meta name="datemodified" content="2025-01-01T00:00:00-04:00">
</head>
<body>
    <table class="cotui-map">
        <thead>
            <tr>
                <th scope="col">Title</th>
                <th scope="col">Description</th>
            </tr>
        </thead>
        <tbody>
			<tr data-lat="43.7670186" data-lng="-79.3871427">
				<td>Bayview Subway Station</td>
				<td>
                    <p>North side of Sheppard Ave., east of Bayview Ave.</p>
                    <p># of Lockers: 12</p>
                </td>
			</tr>
        </tbody>
    </table>
<body>
</html>
"""


def test_succeeds_after_retry(mocker):
    """BikeLockersToronto should retry (at least once) if fetching from City website fails"""
    mocker.patch("tenacity.nap.time", mocker.MagicMock())
    mock_success_response = mocker.MagicMock()
    mock_success_response.status_code = HTTPStatus.OK
    mock_success_response.text = mock_success_content
    mock_failure_response = mocker.MagicMock()
    mock_failure_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_requests = mocker.MagicMock(
        side_effect=[mock_failure_response, mock_success_response]
    )
    mocker.patch("requests.get", mock_requests)

    blt = BikeLockersToronto("test-dataset", "test-url")
    assert mock_requests.call_count == 2


def test_fails_after_retry(mocker):
    """BikeLockersToronto should retry (at least once) but fail once the retries are exhausted"""
    mocker.patch("tenacity.nap.time", mocker.MagicMock())
    mock_failure_response = mocker.MagicMock()
    mock_failure_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    mock_requests = mocker.MagicMock(side_effect=mock_failure_response)
    mocker.patch("requests.get", mock_requests)

    with raises(RetryError):
        blt = BikeLockersToronto("test-dataset", "test-url")
    assert mock_requests.call_count > 1


if __name__ == "__main__":
    init_live_url()
