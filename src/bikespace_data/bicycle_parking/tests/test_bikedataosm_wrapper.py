import pandas as pd

from wrappers import BikeDataOSM
import conversions

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
