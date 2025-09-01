import json

from bikespace_data.bicycle_parking.sources.load_sources import (
    SourceProperties,
    load_paths,
)

mock_open_toronto_ca: SourceProperties = {
    "url": "test",
    "datasets": [
        {
            "dataset_name": "open-toronto-ca-test-one",
            "resource_name": "test",
        },
        {
            "dataset_name": "open-toronto-ca-test-two",
            "resource_name": "test",
        },
    ],
}

mock_openstreetmap: SourceProperties = {
    "url": "test",
    "datasets": [
        {
            "dataset_name": "openstreetmap-one",
            "overpass_query": "test",
        }
    ],
}


def test_load_sources(tmp_path):
    """Should return a dict in the expected format."""

    open_toronto_ca_path = tmp_path / "open_toronto_ca.json"
    with open_toronto_ca_path.open("w") as f:
        json.dump(mock_open_toronto_ca, f)

    openstreetmap_path = tmp_path / "openstreetmap.json"
    with openstreetmap_path.open("w") as f:
        json.dump(mock_openstreetmap, f)

    sources = load_paths(
        {
            "open_toronto_ca": open_toronto_ca_path,
            "openstreetmap": openstreetmap_path,
        }
    )

    assert sources["open_toronto_ca"] == mock_open_toronto_ca
    assert sources["openstreetmap"] == mock_openstreetmap
