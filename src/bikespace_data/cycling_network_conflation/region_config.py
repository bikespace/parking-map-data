from dataclasses import dataclass, field
from pathlib import Path
from string import Template

import pandera as pa

_DEFAULT_QUERY_TEMPLATE = Path(__file__).parent / "osm_cycling_query.overpass"


@dataclass
class TodMunicipalSource:
    dataset_name: str
    resource_id: str


@dataclass
class UrlMunicipalSource:
    url: str


@dataclass
class RegionConfig:
    name: str
    display_name: str

    municipal_source: TodMunicipalSource | UrlMunicipalSource
    municipal_schema: pa.DataFrameSchema
    municipal_id_col: str
    municipal_infra_col: str
    municipal_license: str
    municipal_license_url: str

    osm_wikidata_id: str

    crs: str

    osm_cycling_query_template: Path | None = None
    buffer_m: float = 15.0
    orthogonality_threshold_deg: float = 45.0
    endpoint_trim_m: float = 10.0

    override_csv: Path | None = None


def build_osm_cycling_query(
    wikidata_id: str,
    template_path: Path = _DEFAULT_QUERY_TEMPLATE,
) -> str:
    return Template(template_path.read_text()).substitute(wikidata_id=wikidata_id)
