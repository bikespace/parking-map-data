from datetime import datetime, timezone
from pathlib import Path

import pandera.pandas as pa
from pandera.errors import SchemaErrors

from bikespace_data.bicycle_network.utilities import StatusManager
from bikespace_data.resources.toronto_open_data import TODResponse, request_tod_gdf

cycling_network_schema = pa.DataFrameSchema(
    columns={
        "SEGMENT_ID": pa.Column(int, coerce=True),
        "INFRA_HIGHORDER": pa.Column(str, nullable=True),
        "INFRA_LOWORDER": pa.Column(str, nullable=True),
        "geometry": pa.Column("geometry"),
    },
)

bike_lane_types = [
    # protected bike route
    "Cycle Track",
    "Cycle Track - Contraflow",
    "Bi-Directional Cycle Track",
    # painted bike route
    "Bike Lane",
    "Bike Lane - Buffered",
    "Bike Lane - Contraflow",
    "Contra-Flow Bike Lane",
    "Contraflow",
    # multi-use trails
    "Multi-Use Trail",
    "Multi-Use Trail - Boulevard",
    "Multi-Use Trail - Connector",
    "Multi-Use Trail - Entrance",
    "Multi-Use Trail - Existing Connector",
    "Park Road",
    # unprotected connectors
    "Sharrows",
    "Sharrows - Arterial",
    "Sharrows - Arterial - Connector",
    "Sharrows - Wayfinding",
    "Signed Route (No Pavement Markings)",
    # nulls
    " ",
    "<Null>",
    "--",
    "---",
    "N/A",
]

cycling_network_schema_optional = pa.DataFrameSchema(
    columns={
        **cycling_network_schema.columns,
        "INFRA_HIGHORDER": pa.Column(
            str,
            nullable=True,
            checks=pa.Check.isin(bike_lane_types, ignore_na=True),
        ),
        "INFRA_LOWORDER": pa.Column(
            str,
            nullable=True,
            checks=pa.Check.isin(bike_lane_types, ignore_na=True),
        ),
    }
)


def update_cycling_network(
    status_path: Path = Path("bicycle_network/statuses/bicycle_network_status.csv"),
    output_path: Path = Path("bicycle_network/cycling-network.geojson"),
    archive=True,
):
    """Check https://open.toronto.ca/dataset/cycling-network/ and re-download the file if it has changed"""
    print("Checking open.toronto.ca to see if cycling-network dataset has been updated")

    sm = StatusManager(
        status_source=f"https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/data/{str(status_path)}",
        status_save=status_path,
    )

    cycling_network_data: TODResponse = request_tod_gdf(
        dataset_name="cycling-network",
        resource_id="023da9a2-8848-4e10-9cad-e7f9119cd874",
    )

    # Save cycling network file if the data has been updated
    last_updated = datetime.fromisoformat(
        cycling_network_data["metadata"]["last_modified"]
    )
    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)

    if sm.last_updated is None or last_updated > sm.last_updated:
        print("Changes posted, updating cycling-network dataset")

        # sort values to reduce differences in diff
        cycling_network = cycling_network_data["gdf"].sort_values(by="SEGMENT_ID")
        now = datetime.now(timezone.utc)

        # validate data meets requirements and log optional variances
        cycling_network_schema.validate(cycling_network, lazy=True)
        try:
            cycling_network_schema_optional.validate(cycling_network, lazy=True)
        except SchemaErrors as e:
            print(f"Non-breaking Schema Error with cycling-network: {e}")

        # save full file received
        output_path.parent.mkdir(exist_ok=True, parents=True)
        with open(output_path, "w") as f:
            f.write(cycling_network.to_json(na="drop", drop_id=True, indent=2))

        # save display version with needed columns only
        cycling_network_display = cycling_network[
            ["SEGMENT_ID", "INFRA_HIGHORDER", "INFRA_LOWORDER", "geometry"]
        ]
        display_path = (
            output_path.parent / f"{output_path.stem}-display{output_path.suffix}"
        )
        with open(display_path, "w") as f:
            f.write(cycling_network_display.to_json(na="drop", drop_id=True))

        if archive:
            archive_path = (
                output_path.parent
                / "archive"
                / f"{output_path.stem}_{now.date().isoformat()}.parquet"
            )
            archive_path.parent.mkdir(exist_ok=True, parents=True)
            cycling_network.to_parquet(archive_path)

        sm.add(
            dataset_name="cycling-network",
            last_updated=last_updated,
            num_features=len(cycling_network),
            last_checked=now,
        )
        sm.save()

    else:
        print("No changes detected")


if __name__ == "__main__":
    update_cycling_network()
