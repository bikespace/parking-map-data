from datetime import datetime, timezone

import geopandas as gpd

from bikespace_data.bicycle_network.update_cycling_network import (
    update_cycling_network,
    cycling_network_schema,
)


def test_update_cycling_network(mocker, tmp_path):
    update_cycling_network(
        status_path=tmp_path / "statuses/bicycle_network_status.csv",
        output_path=tmp_path / "cycling-network.geojson",
    )

    # confirm geoparquet is valid
    now = datetime.now(timezone.utc)
    gdf = gpd.read_parquet(
        tmp_path / "archive" / f"cycling-network_{now.date().isoformat()}.parquet"
    )
    assert len(gdf) > 0
    cycling_network_schema.validate(gdf)
