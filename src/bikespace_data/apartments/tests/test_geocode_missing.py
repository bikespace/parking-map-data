import pandas as pd

from bikespace_data.apartments.geocode_missing import (
    geocode_missing,
    AddressCacheDict,
    AddressCache,
)
from geopy import Location, Point

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
