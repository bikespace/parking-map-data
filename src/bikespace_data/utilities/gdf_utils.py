from pathlib import Path
from typing import Literal

import geojson
import geopandas as gpd
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype

from bikespace_data.bicycle_parking.custom_types import GeoJSONFeatureCollection


def _make_json_serializable(val):
    """Convert non-JSON-serializable values to strings."""
    if val is None or (pd.api.types.is_scalar(val) and pd.isna(val)):
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, (pd.Timestamp,)):
        return str(val)
    if hasattr(val, "__dataframe__") or isinstance(val, pd.DataFrame):
        return str(val)
    try:
        import datetime
        if isinstance(val, datetime.datetime):
            return val.isoformat()
        if isinstance(val, datetime.date):
            return val.isoformat()
    except ImportError:
        pass
    return str(val)


def dt_cols_to_str(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Convert non-JSON-serializable columns to string"""
    datetime_cols = gdf.columns[[is_datetime64_any_dtype(gdf[c]) for c in gdf.columns]]
    object_cols = gdf.columns[gdf.dtypes == "object"]
    json_not_supported_cols = datetime_cols.union(object_cols)

    if len(json_not_supported_cols) > 0:
        gdf = gdf.copy()
        # datetime64 columns already convert cleanly via astype below; only
        # object columns need per-value handling for non-serializable values.
        for c in object_cols:
            gdf[c] = gdf[c].apply(_make_json_serializable)
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
        (path / archive_name).mkdir(parents=True, exist_ok=True)

    is_gdf = isinstance(output, gpd.GeoDataFrame)
    if not is_gdf and hasattr(output, "__class__") and output.__class__.__name__ == "GeoDataFrame":
        import geopandas as gpd_check
        is_gdf = isinstance(output, gpd_check.GeoDataFrame)

    if is_gdf:
        gdf = dt_cols_to_str(output)
        try:
            gdf_json = gdf.to_json(na=na, drop_id=True, indent=2)
        except TypeError as e:
            for col in gdf.columns:
                sample = gdf[col].iloc[0] if len(gdf) > 0 else None
                if sample is not None:
                    try:
                        import json
                        json.dumps(sample)
                    except TypeError:
                        raise TypeError(f"Column '{col}' has non-serializable type {type(sample)}: {e}")
            raise
        with open(path / file_name, "w") as f:
            f.write(gdf_json)
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
