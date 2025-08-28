import csv
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pandera.pandas as pa

from bikespace_data.utilities import StatusManager, status_manager_date_format

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
    """Confirm that status manager can run its main functions without error, save over its own output file, and output datetimes consistently."""
    mock_header = [
        "dataset_name",
        "last_updated",
        "num_features",
        "last_checked",
        "days_since_source_update",
    ]
    mock_line_one = [
        "test_existing",
        "2025-01-01T05:00:00.000000+00:00",
        "123",
        "2025-01-07T05:00:00.000000+00:00",
        "10",
    ]
    mock_line_two = [
        "test_existing",
        "2025-01-01T05:00:00+00:00",
        "123",
        "2025-01-07T05:00:00+00:00",
        "10",
    ]
    mock_line_three = [
        "test_existing",
        "2025-01-01T01:00:00-04:00",
        "123",
        "2025-01-07T01:00:00-04:00",
        "10",
    ]
    mock_csv = "\n".join(
        [
            ",".join(mock_header),
            ",".join(mock_line_one),
            ",".join(mock_line_two),
            ",".join(mock_line_three),
        ]
    )

    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.text = mock_csv
    mocker.patch("requests.get", return_value=mock_response)

    # load the status table from source file
    status_save_path = Path(tmp_path / "bicycle_network_status.csv")
    sm = StatusManager(
        status_source="https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/data/bicycle_network/statuses/bicycle_network_status.csv",
        status_save=status_save_path,
    )
    sm_schema.validate(sm._status_table)

    # add an update with timezone-naive datetimes
    tz_naive_last_checked = datetime.now()
    sm.add(
        dataset_name="test tz-naive",
        last_updated=datetime(2025, 7, 1),
        num_features=150,
        last_checked=tz_naive_last_checked,
    )
    sm_schema.validate(sm._status_table)

    # add an update with timezone-aware datetimes
    tz_aware_last_checked = datetime.now(timezone.utc)
    sm.add(
        dataset_name="test tz-aware",
        last_updated=datetime(2025, 7, 1, tzinfo=timezone.utc),
        num_features=150,
        last_checked=tz_aware_last_checked,
    )
    sm_schema.validate(sm._status_table)

    # add an update with a non-utc timezone
    tz_not_utc_last_checked = datetime.now(ZoneInfo("America/Toronto"))
    sm.add(
        dataset_name="test tz-not-utc",
        last_updated=datetime(2025, 7, 1, tzinfo=timezone.utc),
        num_features=150,
        last_checked=tz_not_utc_last_checked,
    )

    # save the status table (twice)
    sm.save()
    sm.save()

    with status_save_path.open("r") as f:
        lines = [x for x in csv.reader(f)]

    assert lines == [
        mock_header,
        mock_line_one,
        # dates in mock_line_two and mock_line_three should be coerced to mock_line_one format:
        mock_line_one,
        mock_line_one,
        [
            "test tz-naive",
            "2025-07-01T00:00:00.000000+00:00",
            "150",
            tz_naive_last_checked.strftime(status_manager_date_format) + "+00:00",
            "58",
        ],
        [
            "test tz-aware",
            "2025-07-01T00:00:00.000000+00:00",
            "150",
            tz_aware_last_checked.strftime(status_manager_date_format),
            "58",
        ],
        [
            "test tz-not-utc",
            "2025-07-01T00:00:00.000000+00:00",
            "150",
            tz_not_utc_last_checked.astimezone(timezone.utc).strftime(
                status_manager_date_format
            ),
            "58",
        ],
    ]


def test_status_manager_tznaive_date_handling(mocker):
    """Confirm that status manager correctly handles timezone-naive datetimes"""
    mock_response = mocker.MagicMock()
    mock_response.status_code = 404
    mocker.patch("requests.get", return_value=mock_response)

    # load the status table (no valid source file)
    sm = StatusManager(
        status_source="mocked",
        status_save=Path("bicycle_network_status.csv"),
    )

    # add a tz-naive datetime
    sm.add(
        dataset_name="test",
        last_updated=datetime.fromisoformat("2025-06-30T23:00:00.000000"),
        num_features=1,
        last_checked=datetime.now(timezone.utc),
    )
    assert sm.last_updated() == datetime(2025, 6, 30, 23, 0, 0, 0, tzinfo=timezone.utc)
