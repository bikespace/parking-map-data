from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from bikespace_data.bicycle_network.utilities import StatusManager

sm_schema = pa.DataFrameSchema(
    columns={
        "dataset_name": pa.Column(str),
        "last_updated": pa.Column(pd.DatetimeTZDtype(tz=timezone.utc)),
        "num_features": pa.Column(int),
        "last_checked": pa.Column(pd.DatetimeTZDtype(tz=timezone.utc)),
        "days_since_source_update": pa.Column(int),
    },
    index=pa.Index(int),
    strict=True,
)


def test_status_manager(mocker, tmp_path):
    mock_csv = "\n".join(
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
                    "test_name",
                    "2025-01-01T05:00:00.000+00:00",
                    "123",
                    "2025-01-07T05:00:00.000+00:00",
                    "10",
                ]
            ),
        ]
    )

    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.text = mock_csv
    mocker.patch("requests.get", return_value=mock_response)

    # load the status table from source file
    sm = StatusManager(
        status_source="https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/data/bicycle_network/statuses/bicycle_network_status.csv",
        status_save=Path(tmp_path / "bicycle_network_status.csv"),
    )
    sm_schema.validate(sm._status_table)

    # add an update with timezone-naive datetimes
    sm.add(
        dataset_name="test",
        last_updated=datetime(2025, 7, 1),
        num_features=150,
        last_checked=datetime.now(),
    )
    sm_schema.validate(sm._status_table)

    # add an update with timezone-aware datetimes
    sm.add(
        dataset_name="test",
        last_updated=datetime(2025, 7, 1, tzinfo=timezone.utc),
        num_features=150,
        last_checked=datetime.now(timezone.utc),
    )
    sm_schema.validate(sm._status_table)

    # save the status table (twice)
    sm.save()
    sm.save()
