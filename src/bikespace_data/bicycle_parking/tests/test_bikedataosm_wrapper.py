import pandas as pd
from overpass import ServerLoadError
from pytest import raises, mark
from tenacity import RetryError

import bikespace_data.bicycle_parking.conversions as conversions
from bikespace_data.bicycle_parking.wrappers import BikeDataOSM

mock_overpass_response = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "type": "node",
                "id": 357049367,
                "tags": {
                    "amenity": "bicycle_parking",
                    "bicycle_parking": "stands",
                    "capacity": "4",
                },
            },
            "geometry": {"type": "Point", "coordinates": [-79.1334102, 43.7962425]},
        },
        {
            "type": "Feature",
            "properties": {
                "type": "node",
                "id": 357049370,
                "tags": {"amenity": "bicycle_parking"},
            },
            "geometry": {"type": "Point", "coordinates": [-79.1332816, 43.7962726]},
        },
        {
            "type": "Feature",
            "properties": {
                "type": "node",
                "id": 357049368,
                "tags": {
                    "amenity": "bicycle_parking",
                    "bicycle_parking": "stands",
                    "capacity": "large",
                },
            },
            "geometry": {"type": "Point", "coordinates": [-79.1334102, 43.7962425]},
        },
    ],
}

mock_overpass_meta = {
    "version": 0.6,
    "generator": "Overpass API 0.7.62.7 375dc00a",
    "osm3s": {
        "timestamp_osm_base": "2025-07-05T15:58:30Z",
        "timestamp_areas_base": "2025-07-05T09:13:45Z",
        "copyright": "The data included in this document is from www.openstreetmap.org. The data is made available under ODbL.",
    },
    "elements": [
        {
            "type": "node",
            "id": 357049367,
            "lat": 43.7962425,
            "lon": -79.1334102,
            "timestamp": "2009-03-08T05:31:52Z",
            "version": 1,
            "changeset": 123456,
            "user": "test_user",
            "uid": 1234,
            "tags": {
                "amenity": "bicycle_parking",
                "bicycle_parking": "stands",
                "capacity": "4",
            },
        },
        {
            "type": "node",
            "id": 357049370,
            "lat": 43.7962726,
            "lon": -79.1332816,
            "timestamp": "2009-03-08T05:31:53Z",
            "version": 1,
            "changeset": 123456,
            "user": "andrewpmk",
            "uid": 1679,
            "tags": {"amenity": "bicycle_parking"},
        },
        {
            "type": "node",
            "id": 357049368,
            "lat": 43.7962425,
            "lon": -79.1334102,
            "timestamp": "2009-03-08T05:31:52Z",
            "version": 1,
            "changeset": 123456,
            "user": "test_user",
            "uid": 1234,
            "tags": {
                "amenity": "bicycle_parking",
                "bicycle_parking": "stands",
                "capacity": "large",
            },
        },
    ],
}


def test_capacity_string_conversion(mocker):
    """BikeDataOSM object should convert non-numeric capacity values (e.g. 'large') to a new tag, capacity:description, so that all capacity values are either numeric or null."""
    dataset_name = "osm_bicycle_parking_city_of_toronto"

    overpass_mock = mocker.MagicMock(
        side_effect=[mock_overpass_response, mock_overpass_meta]
    )
    mocker.patch("overpass.API.get", overpass_mock)
    bdo = BikeDataOSM("test-osm", "test-query")
    gdf = bdo.normalize(
        conversions.get_filter(dataset_name),
        conversions.get_transform(dataset_name),
    )
    assert gdf["capacity"].equals(pd.Series([4, pd.NA, pd.NA], dtype="Int64"))
    assert gdf["capacity:description"].equals(
        pd.Series([pd.NA, pd.NA, "large"], dtype="string")
    )


def test_succeeds_after_retry(mocker):
    """BikeDataOSM should retry (at least once) if fetching from the Overpass API fails"""
    mocker.patch("tenacity.nap.time", mocker.MagicMock())
    overpass_mock = mocker.MagicMock(
        side_effect=[
            ServerLoadError(0),
            mock_overpass_response,
            mock_overpass_meta,
        ]
    )
    mocker.patch("overpass.API.get", overpass_mock)
    bdo = BikeDataOSM("test-osm", "test-query")
    assert overpass_mock.call_count == 3
    assert len(bdo._response) > 0
    assert len(bdo._metadata) > 0


def test_fails_after_retry(mocker):
    """BikeDataOSM should retry (at least once) but fail once the retries are exhausted"""
    mocker.patch("tenacity.nap.time", mocker.MagicMock())
    overpass_mock = mocker.MagicMock(side_effect=ServerLoadError(0))
    mocker.patch("overpass.API.get", overpass_mock)
    with raises(RetryError):
        bdo = BikeDataOSM("test-osm", "test-query")
    assert overpass_mock.call_count > 1


def test_default_overpass_server(mocker, monkeypatch, capsys):
    """BikeDataOSM should call the default overpass server if no OVERPASS_API_URL environment variable is set."""

    # simulate no environment variable
    monkeypatch.delenv("OVERPASS_API_URL", raising=False)
    monkeypatch.delenv("OVERPASS_API_NAME", raising=False)
    mocker.patch("bikespace_data.bicycle_parking.wrappers.load_dotenv")

    # mock overpass API constructor
    overpass_api_mock = mocker.MagicMock()
    mocker.patch("overpass.API", overpass_api_mock)

    bdo = BikeDataOSM("test-osm", "test-query")

    overpass_api_mock.assert_called_with(
        endpoint="https://overpass-api.de/api/interpreter",
        headers=mocker.ANY,
    )
    assert "User-Agent" in overpass_api_mock.call_args.kwargs["headers"]
    captured = capsys.readouterr()
    assert "overpass-api.de" in captured.out


@mark.parametrize(
    "test_overpass_server,test_overpass_name",
    [
        ("https://test-overpass.com/api/interpreter", None),
        ("https://test-overpass.com/api/interpreter", "Test Overpass"),
    ],
)
def test_set_overpass_server_from_environment(
    mocker, monkeypatch, capsys, test_overpass_server, test_overpass_name
):
    """BikeDataOSM should call the specified overpass server if set by OVERPASS_API_URL in the environment."""

    # simulate environment variables
    mocker.patch("bikespace_data.bicycle_parking.wrappers.load_dotenv")
    monkeypatch.setenv("OVERPASS_API_URL", test_overpass_server)
    if test_overpass_name:
        monkeypatch.setenv("OVERPASS_API_NAME", test_overpass_name)
    else:
        monkeypatch.delenv("OVERPASS_API_NAME", raising=False)

    # mock overpass API constructor
    overpass_api_mock = mocker.MagicMock()
    mocker.patch("overpass.API", overpass_api_mock)

    bdo = BikeDataOSM("test-osm", "test-query")

    overpass_api_mock.assert_called_with(
        endpoint=test_overpass_server,
        headers=mocker.ANY,
    )
    assert "User-Agent" in overpass_api_mock.call_args.kwargs["headers"]
    captured = capsys.readouterr()
    if test_overpass_name:
        assert test_overpass_name in captured.out
    else:
        assert "un-named" in captured.out
