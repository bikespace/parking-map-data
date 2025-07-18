from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd

from bikespace_data.bicycle_network.utilities import StatusManager
from bikespace_data.resources.toronto_open_data import TODResponse, request_tod_gdf


def update_cycling_network(
    status_path: Path = Path("bicycle_network/statuses/bicycle_network_status.csv"),
    output_path: Path = Path("bicycle_network/cycling-network.geojson"),
):
    """Check https://open.toronto.ca/dataset/cycling-network/ and re-download the file if it has changed"""

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
    if sm.last_updated is None or last_updated > sm.last_updated:
        cycling_network = cycling_network_data["gdf"]

        output_path.parent.mkdir(exist_ok=True, parents=True)
        cycling_network.to_file(
            output_path,
            driver="GeoJSON",
            index=False,
        )

        sm.add(
            dataset_name="cycling-network",
            last_updated=last_updated,
            num_features=len(cycling_network),
            last_checked=datetime.now(timezone.utc),
        )
        sm.save()
