from pathlib import Path

import pandera.pandas as pa

from bikespace_data.cycling_network_conflation.region_config import (
    RegionConfig,
    UrlMunicipalSource,
)

_stub_schema = pa.DataFrameSchema(
    columns={
        "geometry": pa.Column("geometry"),
    }
)

ottawa = RegionConfig(
    name="ottawa",
    display_name="City of Ottawa",
    municipal_source=UrlMunicipalSource(url=""),  # TODO: populate URL
    municipal_schema=_stub_schema,
    municipal_id_col="",  # TODO
    municipal_infra_col="",  # TODO
    municipal_license="",  # TODO
    municipal_license_url="",  # TODO
    osm_wikidata_id="Q2145",
    crs="EPSG:32618",
)
