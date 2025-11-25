from datetime import datetime, timezone
from http import HTTPStatus

import geopandas as gpd
from pandera.pandas import DataFrameSchema
from pytest import mark

from bikespace_data.bicycle_network.update_cycling_network import (
    cycling_network_schema,
    cycling_network_schema_optional,
    update_cycling_network,
)
from bikespace_data.resources.toronto_open_data import TODResponseGDF
from bikespace_data.tests.testing_utilities import generate_gdf_from_schema


def generate_mock_tod_response(
    last_fresh: str, schema: DataFrameSchema
) -> TODResponseGDF:
    """last_fresh should be a datetime in ISO "YYYY-MM-DDTHH:MM:SS.SSSSSS" format either with our without the "+HH:MM" offset at the end"""
    return {
        "gdf": generate_gdf_from_schema(schema, size=10),
        "metadata": {
            "last_modified": last_fresh,
        },
    }


def generate_mock_status(last_fresh: str) -> str:
    """last_fresh should be a datetime in ISO "YYYY-MM-DDTHH:MM:SS.SSSSSS+HH:MM" format"""
    return "\n".join(
        [
            ",".join(
                [
                    "dataset_name",
                    "last_updated",
                    "num_features",
                    "last_checked",
                    "days_since_source_update",
                ]
            ),
            ",".join(
                [
                    "cycling-network",
                    last_fresh,
                    "123",
                    last_fresh,
                    "123",
                ]
            ),
        ]
    )


@mark.parametrize(
    "response_last_fresh,schema,archive",
    [
        ("2025-01-01T01:23:45.123000+00:00", cycling_network_schema_optional, True),
        ("2025-01-01T01:23:45.123000", cycling_network_schema, False),
    ],
)
def test_update_cycling_network(mocker, tmp_path, response_last_fresh, schema, archive):
    """Test that the script runs as expected under two sets of conditions:

    First (usual) condition:
    - response `last_modified` value is tz-aware
    - returned data has no schema warnings
    - archive output is generated (tests parquet file for validity)

    Second condition:
    - response `last_modified` value does not have a timezone offset
    - returned data has some schema warnings
    - archive output is not generated
    """

    # mock the data returned from the City of Toronto Open Data portal
    mocker.patch(
        "bikespace_data.bicycle_network.update_cycling_network.request_tod_gdf",
        return_value=generate_mock_tod_response(
            last_fresh=response_last_fresh, schema=schema
        ),
    )

    # mock the prior status info used by StatusManager
    mock_prior_status_response = mocker.MagicMock()
    mock_prior_status_response.status_code = HTTPStatus.OK
    mock_prior_status_response.text = generate_mock_status(
        last_fresh="2024-12-31T05:00:00.000000+00:00"
    )
    mocker.patch(
        "bikespace_data.utilities.utilities.requests.get",
        return_value=mock_prior_status_response,
    )

    update_cycling_network(
        status_path=tmp_path / "statuses/bicycle_network_status.csv",
        output_path=tmp_path / "cycling-network.geojson",
        archive=archive,
    )

    if archive:
        # confirm geoparquet is valid
        now = datetime.now(timezone.utc)
        gdf = gpd.read_parquet(
            tmp_path / "archive" / f"cycling-network_{now.date().isoformat()}.parquet"
        )
        assert len(gdf) > 0
        cycling_network_schema.validate(gdf)


def test_update_cycling_network_already_up_to_date(mocker, tmp_path):
    """Test that the script generates no files when the data is already up to date based on the last_updated value from StatusManager"""

    # mock the data returned from the City of Toronto Open Data portal
    last_fresh = "2025-01-01T00:00:00.000000+00:00"
    mocker.patch(
        "bikespace_data.bicycle_network.update_cycling_network.request_tod_gdf",
        return_value=generate_mock_tod_response(
            last_fresh=last_fresh,
            schema=cycling_network_schema_optional,
        ),
    )

    # mock the prior status info used by StatusManager
    mock_prior_status_response = mocker.MagicMock()
    mock_prior_status_response.status_code = HTTPStatus.OK
    mock_prior_status_response.text = generate_mock_status(last_fresh=last_fresh)
    mocker.patch(
        "bikespace_data.utilities.utilities.requests.get",
        return_value=mock_prior_status_response,
    )

    update_cycling_network(
        status_path=tmp_path / "statuses/bicycle_network_status.csv",
        output_path=tmp_path / "cycling-network.geojson",
    )

    assert not any(tmp_path.iterdir())  # no files created, directory empty
