from datetime import datetime, timezone
from http import HTTPStatus
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

status_manager_date_format = r"%Y-%m-%dT%H:%M:%S.%f%:z"


class StatusManager:
    """Interface for getting and updating database statuses"""

    def __init__(self, status_source: str, status_save: Path):
        self.status_save = status_save

        response = requests.get(status_source)

        if response.status_code == HTTPStatus.OK:
            st = (
                pd.read_csv(
                    StringIO(response.text),
                    parse_dates=["last_updated", "last_checked"],
                )
                .convert_dtypes()
                .astype(
                    {
                        "last_updated": "datetime64[ns, UTC]",
                        "last_checked": "datetime64[ns, UTC]",
                    }
                )
            )
            self._status_table = st.assign(
                last_updated=st["last_updated"].apply(lambda x: pd.Timestamp(x)),
                last_checked=st["last_checked"].apply(lambda x: pd.Timestamp(x)),
            )
        elif response.status_code == HTTPStatus.NOT_FOUND:
            self._status_table = pd.DataFrame(
                columns=[
                    "dataset_name",
                    "last_updated",
                    "num_features",
                    "last_checked",
                    "days_since_source_update",
                ]
            )
        else:
            raise Exception(
                f"Could not get status from source {status_source}. Resource returned status {response.status_code}"
            )

    def last_updated(self, dataset_name: str | None = None) -> datetime | None:
        if len(self._status_table) == 0:
            return None
        elif dataset_name is not None:
            filtered_status_table = self._status_table[
                self._status_table["dataset_name"] == dataset_name
            ]
            return filtered_status_table["last_updated"].max().to_pydatetime()
        elif len(self._status_table["dataset_name"].unique()) > 1:
            raise Exception(
                "There is more than one dataset in this status table. Please specify the dataset using the `dataset_name` parameter."
            )
        else:
            return self._status_table["last_updated"].max().to_pydatetime()

    def add(
        self,
        *,
        dataset_name: str,
        last_updated: datetime,
        num_features: int,
        last_checked: datetime,
    ):
        """Add an entry to the status table.

        Note: if either of the datetime arguments is provided in a timezone-naive format, it will assume the timezone is UTC"""

        # Note: ckan default is UTC for datetime: https://docs.ckan.org/en/latest/maintaining/configuration.html#ckan-display-timezone
        last_updated_ts = pd.Timestamp(
            last_updated.astimezone(timezone.utc)
            if last_updated.tzinfo is not None
            else last_updated.replace(tzinfo=timezone.utc),
        ).as_unit("ns")
        last_checked_ts = pd.Timestamp(
            last_checked.astimezone(timezone.utc)
            if last_checked.tzinfo is not None
            else last_checked.replace(tzinfo=timezone.utc),
        ).as_unit("ns")
        self._status_table = pd.concat(
            df.dropna(axis="columns", how="all")
            for df in [
                self._status_table,
                pd.DataFrame(
                    [
                        {
                            "dataset_name": dataset_name,
                            "last_updated": last_updated_ts,
                            "num_features": num_features,
                            "last_checked": last_checked_ts,
                            "days_since_source_update": (
                                last_checked_ts - last_updated_ts
                            ).days,
                        }
                    ]
                ),
            ]
        ).reset_index(drop=True)

    def save(self):
        self.status_save.parent.mkdir(exist_ok=True, parents=True)
        self._status_table.to_csv(
            self.status_save, index=False, date_format=status_manager_date_format
        )
