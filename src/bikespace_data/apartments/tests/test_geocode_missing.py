import json
from http import HTTPStatus

import pandas as pd
from geopy import Location, Point

from bikespace_data.apartments.geocode_missing import (
    AddressCache,
    AddressCacheDict,
    geocode_missing,
)

test_df = pd.DataFrame(
    [
        {
            "description": "existing lat long",
            "address": "36 SPENCER AVE",
            "latitude": 43.634955198449894,
            "longitude": -79.429994303185111,
        },
        {
            "description": "lat long cached",
            "address": "9 STAG HILL DR",
            "latitude": None,
            "longitude": None,
        },
        {
            "description": "lat long geocoded",
            "address": "39 NIAGARA ST",
            "latitude": None,
            "longitude": None,
        },
    ]
)
CACHED_ADDRESS = "9 STAG HILL DR"
test_cache: AddressCacheDict = {
    CACHED_ADDRESS: {
        "latitude": 43,  # fake lat
        "longitude": -79,  # fake long
    },
}


def test_geocode_missing(mocker):
    """Confirm that the geocode_missing function correctly adds location points for a dataframe where some latitude and longitude values are missing."""
    # mock geocoder
    mock_nominatim = mocker.patch("bikespace_data.apartments.geocode_missing.Nominatim")
    mock_nominatim_instance = mock_nominatim.return_value
    mock_geocode = mock_nominatim_instance.geocode
    mock_geocode.return_value = Location(
        address="doesn't matter",
        point=Point(latitude=43.70, longitude=-79.40),
        raw=mocker.MagicMock(),
    )

    geocoded_df = geocode_missing(
        test_df,
        "latitude",
        "longitude",
        "address",
        test_cache,
    )["df"]

    assert len(test_df) == len(geocoded_df)

    assert not (geocoded_df["latitude"].hasnans or geocoded_df["longitude"].hasnans)

    cached_row = geocoded_df[geocoded_df["address"] == CACHED_ADDRESS].iloc[0].to_dict()
    assert cached_row["latitude"] == test_cache[CACHED_ADDRESS]["latitude"]
    assert cached_row["longitude"] == test_cache[CACHED_ADDRESS]["longitude"]


def test_address_cache(mocker, tmp_path):
    """Confirm that AddressCache correctly loads from a remote URL, can be updated, and correctly saves the updated cache to file."""
    # mock existing address cache returned from url
    ex1 = {
        "address": "123 Fake St",
        "latitude": 43.70,
        "longitude": -79.40,
    }
    ex2 = {
        "address": "456 Rue Faux",
        "latitude": 43.60,
        "longitude": -79.30,
    }
    mock_remote_cache: AddressCacheDict = {
        ex1["address"]: {
            "latitude": ex1["latitude"],
            "longitude": ex1["longitude"],
        }
    }
    new_cache_entry: AddressCacheDict = {
        ex2["address"]: {
            "latitude": ex2["latitude"],
            "longitude": ex2["longitude"],
        }
    }

    mock_response = mocker.MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json = mocker.MagicMock(return_value=mock_remote_cache)
    mocker.patch("requests.get", return_value=mock_response)

    # add a new cache entry
    test_cache = AddressCache(
        source_path="https://mocked.com/fake.json",
        save_path=tmp_path / "address_cache.json",
    )
    test_cache.cache.update(new_cache_entry)

    # save the cache to file
    test_cache.save_cache()

    # saved cache should contain the existing and added values
    with (tmp_path / "address_cache.json").open("r") as f:
        saved_cache: AddressCacheDict = json.load(f)
    assert saved_cache[ex1["address"]]["latitude"] == ex1["latitude"]
    assert saved_cache[ex1["address"]]["longitude"] == ex1["longitude"]
    assert saved_cache[ex2["address"]]["latitude"] == ex2["latitude"]
    assert saved_cache[ex2["address"]]["longitude"] == ex2["longitude"]


def test_address_cache_noremote(mocker, tmp_path):
    """Confirm that AddressCache correctly handles the case where the remote URL fails or does not exist"""

    mock_response = mocker.MagicMock()
    mock_response.status_code = HTTPStatus.NOT_FOUND
    mocker.patch("requests.get", return_value=mock_response)

    test_cache = AddressCache(
        source_path="https://mocked.com/fake.json",
        save_path=tmp_path / "address_cache.json",
    )

    assert test_cache.cache == {}
