from pathlib import Path

from bikespace_data.bicycle_network.update_cycling_network import (
    cycling_network_schema_optional,
)
from bikespace_data.cycling_network_conflation.region_config import (
    RegionConfig,
    TodMunicipalSource,
)

toronto = RegionConfig(
    name="toronto",
    display_name="City of Toronto",
    municipal_source=TodMunicipalSource(
        dataset_name="cycling-network",
        resource_id="023da9a2-8848-4e10-9cad-e7f9119cd874",
    ),
    municipal_schema=cycling_network_schema_optional,
    municipal_id_col="SEGMENT_ID",
    municipal_infra_col="INFRA_HIGHORDER",
    municipal_license="Open Government Licence – Toronto",
    municipal_license_url="https://open.toronto.ca/open-data-license/",
    osm_wikidata_id="Q172",
    crs="EPSG:32617",
    override_csv=Path(__file__).parent.parent / "overrides" / "toronto_overrides.csv",
)
