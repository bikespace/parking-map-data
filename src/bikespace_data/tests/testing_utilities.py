import random

import geopandas as gpd
import pandera.pandas as pa
from shapely import points

toronto_bbox = {
    "min_lon": -79.639283,
    "max_lon": -79.113219,
    "min_lat": 43.579608,
    "max_lat": 43.855442,
}


def generate_gdf_from_schema(schema: pa.DataFrameSchema, size: int) -> gpd.GeoDataFrame:
    """Generate a geodataframe using a pandera schema. Pandera's example method is used for the properties and the geometry column is populated with Point geometries (WGS 84 / EPSG:4326) within the bounding box of Toronto.

    This helper function is required because as of September 2025, pandera was not able to generate example values for "geometry" columns."""
    property_schema = schema.remove_columns(["geometry"])
    example_properties = property_schema.example(size=size)
    example_geometry = points(
        [
            [
                random.uniform(
                    toronto_bbox["min_lon"],
                    toronto_bbox["max_lon"],
                ),
                random.uniform(
                    toronto_bbox["min_lat"],
                    toronto_bbox["max_lat"],
                ),
            ]
            for _ in range(size)
        ]
    )
    example_gdf = gpd.GeoDataFrame(
        example_properties, geometry=example_geometry, crs="EPSG:4326"
    )
    return example_gdf
