from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests


class StatusManager:
    """Interface for getting and updating database statuses"""

    def __init__(self, status_source: str, status_save: Path):
        self.status_save = status_save

        response = requests.get(status_source)

        if response.status_code == 200:
            st = pd.read_csv(
                StringIO(response.text), parse_dates=["last_updated", "last_checked"]
            ).convert_dtypes()
            self._status_table = st.assign(
                last_updated=st["last_updated"].apply(lambda x: pd.Timestamp(x)),
                last_checked=st["last_checked"].apply(lambda x: pd.Timestamp(x)),
            )
        elif response.status_code == 404:
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

    @property
    def last_updated(self):
        if len(self._status_table) == 0:
            return None
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
        last_updated_ts = pd.Timestamp(
            last_updated
            if last_updated.tzinfo is not None
            else last_updated.astimezone(timezone.utc),
        )
        last_checked_ts = pd.Timestamp(
            last_checked
            if last_checked.tzinfo is not None
            else last_checked.astimezone(timezone.utc),
        )
        self._status_table = pd.concat(
            [
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
        self._status_table.to_csv(self.status_save, index=False)
