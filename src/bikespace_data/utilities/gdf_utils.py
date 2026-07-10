from pathlib import Path
from typing import Literal

import geojson
import geopandas as gpd
from pandas.api.types import is_datetime64_any_dtype, is_object_dtype, is_string_dtype

from bikespace_data.bicycle_parking.custom_types import GeoJSONFeatureCollection


def dt_cols_to_str(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Convert dtype for datetime columns to string"""
    json_not_supported_cols = gdf.columns[
        [is_datetime64_any_dtype(gdf[c]) for c in gdf.columns]
    ].union(
        gdf.columns[
            [is_object_dtype(gdf[c]) or is_string_dtype(gdf[c]) for c in gdf.columns]
        ]
    )
    if len(json_not_supported_cols) > 0:
        gdf = gdf.astype({c: "string" for c in json_not_supported_cols})
    return gdf


def save_geo_output(
    output: GeoJSONFeatureCollection | gpd.GeoDataFrame,
    *,
    path: Path,
    file_name: str,
    archive_name: str | None = None,
    na: Literal["null", "drop", "keep"] = "drop",
):
    """Save GeoJSON dict or GeoPandas Geodataframe to file. If archive_name is specified, the file will also be saved in an archive folder in the same path."""

    path.mkdir(exist_ok=True, parents=True)
    if archive_name:
        (path / archive_name).mkdir(exist_ok=True, parents=True)

    if isinstance(output, gpd.GeoDataFrame):
        with open(path / file_name, "w") as f:
            f.write(dt_cols_to_str(output).to_json(na=na, drop_id=True, indent=2))
        if archive_name:
            output.to_parquet(
                (path / archive_name / file_name).with_suffix(".parquet"),
            )

    else:
        with open(path / file_name, "w") as f:
            geojson.dump(output, f, indent=2)
        if archive_name:
            gdf = gpd.GeoDataFrame.from_features(output["features"]).convert_dtypes()
            gdf.to_parquet((path / archive_name / file_name).with_suffix(".parquet"))
