"""Helpers for fetching City of Toronto administrative boundary polygons (wards, neighbourhoods) from open.toronto.ca."""

from pathlib import Path

import geopandas as gpd

from bikespace_data.resources.toronto_open_data import request_tod_gdf
from bikespace_data.utilities import save_geo_output


def get_wards_gdf(
    source_save_path: Path | None = None,
    archive_name: str | None = None,
) -> gpd.GeoDataFrame:
    """Retrieves, simplifies, and saves data from the City Wards dataset from open.toronto.ca"""

    wards = request_tod_gdf(
        dataset_name="city-wards",
        resource_id="737b29e0-8329-4260-b6af-21555ab24f28",
    )

    # save original (and optionally archive) if requested
    if source_save_path is not None:
        save_geo_output(
            wards["gdf"],
            path=source_save_path,
            file_name="wards.geojson",
            archive_name=archive_name,
        )

    wards_formatted = (
        wards["gdf"][["AREA_SHORT_CODE", "AREA_NAME", "geometry"]]
        .assign(
            ward_full=[
                f"{x.AREA_NAME} ({x.AREA_SHORT_CODE})"
                for x in wards["gdf"].itertuples()
            ]
        )
        .rename(
            columns={
                "AREA_SHORT_CODE": "ward_code",
                "AREA_NAME": "ward_name",
            }
        )
    )
    return wards_formatted


def get_neighbourhoods_gdf(
    source_save_path: Path | None = None,
    archive_name: str | None = None,
) -> gpd.GeoDataFrame:
    "Retrieves and simplifies from https://open.toronto.ca/dataset/neighbourhoods/"
    response = request_tod_gdf(
        dataset_name="neighbourhoods",
        resource_id="0719053b-28b7-48ea-b863-068823a93aaa",
    )
    gdf = response["gdf"]

    # save original (and optionally archive) if requested
    if source_save_path is not None:
        save_geo_output(
            gdf,
            path=source_save_path,
            file_name="neighbourhoods.geojson",
            archive_name=archive_name,
        )

    gdf_formatted = gdf[
        [
            "AREA_SHORT_CODE",
            "AREA_NAME",
            "CLASSIFICATION",
            "CLASSIFICATION_CODE",
            "geometry",
        ]
    ].rename(
        columns={
            "AREA_SHORT_CODE": "neighbourhood_number",
            "AREA_NAME": "neighbourhood_name",
            "CLASSIFICATION": "neighbourhood_classification",
            "CLASSIFICATION_CODE": "neighbourhood_classification_code",
        }
    )
    return gdf_formatted
