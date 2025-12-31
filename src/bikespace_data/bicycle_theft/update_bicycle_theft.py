"""
DATA PROCESSING SCRIPT - TORONTO BICYCLE THEFTS
================================================

Downloads the City of Toronto "bicycle-thefts" dataset from open.toronto.ca and saves source, normalized, and display files.

Behavior summary:
- Prefers GeoJSON resource, falls back to CSV, then the first available resource.
- For CSV inputs, attempts to infer coordinates from common columns (longitude/lon/LONGITUDE/LON/X and latitude/lat/LATITUDE/LAT/Y).
- If no coordinates can be inferred, produces normalized output without geometry and a geometry-only display file when needed.
- Missing or malformed metadata['last_modified'] will raise an error when parsing dates.
"""

from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import pandas as pd
import requests

from bikespace_data.resources.toronto_open_data import (
    PACKAGE_URL,
    request_tod_df,
    request_tod_gdf,
)
from bikespace_data.utilities import StatusManager, save_geo_output


def _pick_resource_id(dataset_name: str, prefer_geojson: bool = True) -> str:
    """Query the package metadata and choose a resource id.

    Preference order: GeoJSON -> CSV -> first resource. Raises RuntimeError if no resources are found.
    """
    resp = requests.get(PACKAGE_URL, params={"id": dataset_name})
    resp.raise_for_status()
    meta = resp.json()["result"]
    resources = meta.get("resources", [])

    if not resources:
        raise RuntimeError(f"No resources found for dataset {dataset_name}")

    if prefer_geojson:
        for rs in resources:
            if rs.get("format", "").lower() == "geojson":
                return rs["id"]
    # prefer CSV if no geojson found
    for rs in resources:
        if rs.get("format", "").lower() == "csv":
            return rs["id"]
    # fallback
    return resources[0]["id"]


def _to_gdf_from_df(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Attempt to construct a GeoDataFrame from common latitude/longitude or x/y columns.

    Supported lon columns: longitude, lon, LONGITUDE, LON, X
    Supported lat columns: latitude, lat, LATITUDE, LAT, Y

    If matching columns are found, returns a GeoDataFrame with EPSG:4326 geometry.
    If not, returns a GeoDataFrame converted from the DataFrame (may not have a geometry column).
    """
    # Common possible coordinate column names
    lon_cols: Iterable[str] = ["longitude", "lon", "LONGITUDE", "LON", "X"]
    lat_cols: Iterable[str] = ["latitude", "lat", "LATITUDE", "LAT", "Y"]

    df_cols = set(df.columns)

    lon = next((c for c in lon_cols if c in df_cols), None)
    lat = next((c for c in lat_cols if c in df_cols), None)

    if lon and lat:
        # coerce to numeric and drop rows missing coords
        df = df.copy()
        df[lon] = pd.to_numeric(df[lon], errors="coerce")
        df[lat] = pd.to_numeric(df[lat], errors="coerce")
        df = df.dropna(subset=[lon, lat])
        gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon], df[lat]))
        gdf.set_crs(epsg=4326, inplace=True)
        return gdf

    # If we can't find coordinates, return empty gdf with no geometry
    return gpd.GeoDataFrame(df)


def update_bicycle_thefts(
    status_path: Path = Path("bicycle_theft/statuses/bicycle_theft_statuses.csv"),
    output_dir: Path = Path("bicycle_theft"),
    archive: bool = True,
):
    """Fetch the bicycle-thefts dataset and save source, normalized, and display files when updated.

    - Uses StatusManager to skip unchanged data.
    - `archive=True` enables parquet archives for source and normalized outputs.
    - Parsing `metadata['last_modified']` expects an ISO timestamp and will raise `KeyError`/`ValueError` if missing or invalid.
    """
    print("Checking open.toronto.ca for bicycle-thefts dataset")

    sm = StatusManager(
        status_source=f"https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/data/{str(status_path)}",
        status_save=status_path,
    )

    dataset_name = "bicycle-thefts"

    # choose resource id (prefer geojson if available)
    resource_id = _pick_resource_id(dataset_name)

    # depending on resource format, request appropriate type
    # We'll attempt gdf first; request_tod_gdf will raise if resource is not geojson but that's fine
    try:
        response = request_tod_gdf(dataset_name=dataset_name, resource_id=resource_id)
        gdf = response["gdf"]
        metadata = response["metadata"]
        used_format = "geojson"
    except Exception:
        # fallback to csv resource
        response = request_tod_df(dataset_name=dataset_name, resource_id=resource_id)
        df = response["df"]
        metadata = response["metadata"]
        gdf = _to_gdf_from_df(df)
        used_format = "csv"

    # determine last_updated
    last_updated = datetime.fromisoformat(metadata["last_modified"])
    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)

    last_updated_from_status = sm.last_updated(dataset_name=dataset_name)

    now = datetime.now(timezone.utc)

    if last_updated_from_status is None or last_updated > last_updated_from_status:
        print("Changes posted, updating bicycle-thefts dataset")

        # sort to make diffs easier if there's an id-like column
        if "id" in gdf.columns:
            try:
                gdf = gdf.sort_values(by="id")
            except Exception:
                pass

        # save full source file under source_files
        sfp = output_dir / "source_files"
        ofp = output_dir / "output_files"
        dfp = output_dir / "display_files"
        for p in [sfp, ofp, dfp]:
            p.mkdir(exist_ok=True, parents=True)

        # if original source was geojson we already have geometry; save original
        source_file_name = f"{dataset_name}.{ 'geojson' if used_format == 'geojson' else 'csv' }"
        if used_format == "geojson":
            save_geo_output(gdf, path=sfp, file_name=source_file_name, archive_name=f"archive/{now.date().isoformat()}/" if archive else None)
        else:
            # we have original df in response only when CSV was used
            # write csv file for source
            response["df"].to_csv(sfp / source_file_name, index=False)
            if archive:
                (sfp / f"archive/{now.date().isoformat()}").mkdir(parents=True, exist_ok=True)
                response["df"].to_parquet(sfp / f"archive/{now.date().isoformat()}" / source_file_name.replace('.csv', '.parquet'))

        # save normalized (geojson) output
        # ensure we have a GeoDataFrame
        if not isinstance(gdf, gpd.GeoDataFrame):
            gdf = gpd.GeoDataFrame(gdf)

        # convert dtypes for stability
        gdf = gdf.convert_dtypes()

        output_file_name = f"{dataset_name}-normalized.geojson"
        save_geo_output(
            gdf,
            path=ofp,
            file_name=output_file_name,
            archive_name=f"archive/{now.date().isoformat()}/" if archive else None,
            na="null",
        )

        # produce a lightweight display file with a subset of columns
        candidate_cols = [
            "OCCURRENCE_DATE",
            "OCCURRENCE_TIME",
            "DATE",
            "TIME",
            "OFFENCE_TYPE",
            "THEFT_DESCRIPTION",
            "LOCATION",
            "NEIGHBOURHOOD",
            "WARD",
        ]
        display_cols = [c for c in candidate_cols if c in gdf.columns]
        # always include geometry
        display_gdf = gdf[display_cols + (["geometry"] if "geometry" in gdf.columns else [])]
        if len(display_gdf.columns) == 0:
            # fallback to first 5 columns + geometry if available
            cols = list(gdf.columns[:5])
            if "geometry" in gdf.columns:
                cols.append("geometry")
            display_gdf = gdf[cols]

        save_geo_output(display_gdf, path=dfp, file_name=f"{dataset_name}-display.geojson")

        # update status
        sm.add(
            dataset_name=dataset_name,
            last_updated=last_updated,
            num_features=len(gdf),
            last_checked=now,
        )
        sm.save()

    else:
        print("No changes detected for bicycle-thefts")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--no-archive", action="store_true", help="Disable writing parquet archives")
    args = parser.parse_args()
    update_bicycle_thefts(archive=not args.no_archive)
