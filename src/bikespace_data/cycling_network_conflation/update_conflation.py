import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import overpass
import pandas as pd
from shapely.ops import linemerge
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_chain, wait_fixed

from bikespace_data.cycling_network_conflation.region_config import (
    RegionConfig,
    TodMunicipalSource,
    UrlMunicipalSource,
    build_osm_cycling_query,
)
from bikespace_data.cycling_network_conflation.regions.toronto import toronto
from bikespace_data.cycling_network_conflation.spatial_match import match_cycling_network
from bikespace_data.resources.toronto_open_data import request_tod_gdf
from bikespace_data.utilities import StatusManager


_REGIONS: dict[str, RegionConfig] = {
    "toronto": toronto,
}


@retry(
    wait=wait_chain(wait_fixed(60), wait_fixed(120), wait_fixed(300)),
    stop=stop_after_attempt(3),
)
def _download_osm_gdf(config: RegionConfig) -> tuple[gpd.GeoDataFrame, datetime]:
    overpass_default = "https://overpass-api.de/api/interpreter"
    load_dotenv(override=False)
    api_url = os.environ.get("OVERPASS_API_URL", overpass_default)
    api_name = os.environ.get(
        "OVERPASS_API_NAME",
        "overpass-api.de" if api_url == overpass_default else "custom overpass server",
    )
    print(f"Requesting OSM data from {api_name}")

    api = overpass.API(
        endpoint=api_url,
        headers={
            "User-Agent": "bikespace-parking-map-data (https://github.com/bikespace/parking-map-data)"
        },
    )

    template_path = config.osm_cycling_query_template
    query = build_osm_cycling_query(config.osm_wikidata_id, template_path) if template_path else build_osm_cycling_query(config.osm_wikidata_id)

    response = api.get(query, responseformat="geojson", verbosity="geom")
    features = response.get("features", [])

    # The overpass library places OSM id/type in properties, not at the feature level
    ids = [f["properties"]["id"] for f in features]
    osm_gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    if ids:
        osm_gdf.index = ids

    last_updated = datetime.now(timezone.utc)
    return osm_gdf, last_updated


def _load_or_create_override_csv(config: RegionConfig) -> pd.DataFrame:
    override_path = config.override_csv
    mid_col = config.municipal_id_col

    if override_path is None or not override_path.exists():
        if override_path is not None:
            override_path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(columns=[mid_col, "osm_way_id", "action", "note"]).to_csv(
                override_path, index=False
            )
        return pd.DataFrame(columns=[mid_col, "osm_way_id", "action", "note"])

    df = pd.read_csv(override_path)

    if mid_col not in df.columns:
        raise ValueError(
            f"Override CSV at {override_path} is missing column '{mid_col}'. "
            f"Expected columns: [{mid_col}, osm_way_id, action, note]"
        )

    valid_actions = {"include", "exclude"}
    bad = df.loc[df["action"].notna() & ~df["action"].isin(valid_actions), "action"]
    if not bad.empty:
        raise ValueError(
            f"Override CSV column 'action' contains invalid values: {bad.tolist()}. "
            f"Must be 'include', 'exclude', or empty."
        )

    return df


def _build_conflation_props(
    feature_id,
    id_col: str,
    matches_df: pd.DataFrame,
    *,
    source_col: str,
    match_col: str,
) -> dict:
    """Return the three _conflation_* property values for one feature."""
    rows = matches_df[matches_df[id_col] == feature_id]

    algo_ids = rows.loc[
        (rows["match_type"] == "auto") & (rows["override_action"] != "exclude"),
        match_col,
    ].dropna().tolist()

    excluded_ids = rows.loc[
        rows["override_action"] == "exclude",
        match_col,
    ].dropna().tolist()

    included_ids = rows.loc[
        rows["match_type"] == "override",
        match_col,
    ].dropna().tolist()

    return {
        "_conflation_algo_matches": ";".join(str(x) for x in algo_ids),
        "_conflation_override_excluded": ";".join(str(x) for x in excluded_ids),
        "_conflation_override_included": ";".join(str(x) for x in included_ids),
    }


def _build_combined_geojson(
    municipal_gdf: gpd.GeoDataFrame,
    osm_gdf: gpd.GeoDataFrame,
    matches_df: pd.DataFrame,
    config: RegionConfig,
) -> dict:
    mid_col = config.municipal_id_col

    muni_wgs84 = municipal_gdf.to_crs("EPSG:4326")
    osm_wgs84 = osm_gdf.to_crs("EPSG:4326") if osm_gdf.crs else osm_gdf

    features = []

    for _, row in muni_wgs84.iterrows():
        muni_id = row[mid_col]
        props = {k: v for k, v in row.items() if k != "geometry"}
        props["_source"] = "municipal"
        props.update(
            _build_conflation_props(
                muni_id,
                id_col=mid_col,
                matches_df=matches_df,
                source_col="municipal",
                match_col="osm_way_id",
            )
        )
        features.append(
            {
                "type": "Feature",
                "geometry": row.geometry.__geo_interface__,
                "properties": {k: (None if pd.isna(v) else v) for k, v in props.items()},
            }
        )

    for osm_id, row in osm_wgs84.iterrows():
        osm_way_id = f"way/{osm_id}"
        props = {k: v for k, v in row.items() if k != "geometry"}
        props["_source"] = "osm"
        props["osm_way_id"] = osm_way_id

        osm_rows = matches_df[matches_df["osm_way_id"] == osm_way_id]

        algo_muni_ids = osm_rows.loc[
            (osm_rows["match_type"] == "auto") & (osm_rows["override_action"] != "exclude"),
            mid_col,
        ].dropna().tolist()
        excluded_muni_ids = osm_rows.loc[
            osm_rows["override_action"] == "exclude", mid_col
        ].dropna().tolist()
        included_muni_ids = osm_rows.loc[
            osm_rows["match_type"] == "override", mid_col
        ].dropna().tolist()

        props["_conflation_algo_matches"] = ";".join(str(x) for x in algo_muni_ids)
        props["_conflation_override_excluded"] = ";".join(str(x) for x in excluded_muni_ids)
        props["_conflation_override_included"] = ";".join(str(x) for x in included_muni_ids)

        features.append(
            {
                "type": "Feature",
                "geometry": row.geometry.__geo_interface__ if row.geometry else None,
                "properties": {k: (None if (not isinstance(v, str) and pd.isna(v)) else v) for k, v in props.items()},
            }
        )

    return {
        "type": "FeatureCollection",
        "municipal_id_key": mid_col,
        "features": features,
    }


def run_region(
    config: RegionConfig,
    output_root: Path = Path("cycling_network_conflation"),
    archive: bool = False,
):
    region_root = output_root / config.name
    source_dir = region_root / "source_files"
    output_dir = region_root / "output_files"
    display_dir = region_root / "display_files"
    status_path = region_root / "statuses" / "conflation_status.csv"

    for d in [source_dir, output_dir, display_dir]:
        d.mkdir(parents=True, exist_ok=True)

    sm = StatusManager(
        status_source=f"https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/data/{status_path}",
        status_save=status_path,
    )

    # 1. Download + validate municipal data
    print(f"[{config.name}] Downloading municipal cycling network data...")
    if isinstance(config.municipal_source, TodMunicipalSource):
        tod_response = request_tod_gdf(
            dataset_name=config.municipal_source.dataset_name,
            resource_id=config.municipal_source.resource_id,
        )
        municipal_gdf = tod_response["gdf"]
        municipal_last_updated = datetime.fromisoformat(
            tod_response["metadata"]["last_modified"]
        )
        if municipal_last_updated.tzinfo is None:
            municipal_last_updated = municipal_last_updated.replace(tzinfo=timezone.utc)
    elif isinstance(config.municipal_source, UrlMunicipalSource):
        municipal_gdf = gpd.read_file(config.municipal_source.url)
        municipal_last_updated = datetime.now(timezone.utc)
    else:
        raise ValueError(f"Unknown municipal source type: {type(config.municipal_source)}")

    config.municipal_schema.validate(municipal_gdf, lazy=True)

    municipal_gdf = municipal_gdf.copy()
    municipal_gdf["geometry"] = municipal_gdf.geometry.apply(linemerge)

    with open(source_dir / "municipal.geojson", "w") as f:
        f.write(municipal_gdf.to_json(na="drop", drop_id=True, indent=2))

    # 2. Download OSM data
    print(f"[{config.name}] Downloading OSM cycling network data...")
    osm_gdf, osm_last_updated = _download_osm_gdf(config)

    with open(source_dir / "osm.geojson", "w") as f:
        f.write(osm_gdf.to_json(na="drop", drop_id=True, indent=2))

    # 3. Load override CSV
    overrides_df = _load_or_create_override_csv(config)

    # 4. Run spatial matching
    print(f"[{config.name}] Running spatial matching...")
    matches_df = match_cycling_network(municipal_gdf, osm_gdf, config, overrides_df)

    now = datetime.now(timezone.utc)

    # 5. Full debug matches table
    matches_df.to_csv(output_dir / "matches.csv", index=False)

    # 6. Combined GeoJSON (municipal + OSM features with conflation metadata)
    combined = _build_combined_geojson(municipal_gdf, osm_gdf, matches_df, config)
    with open(output_dir / "combined_with_matches.geojson", "w") as f:
        json.dump(combined, f, indent=2, default=str)

    # 7. Display matches CSV (drop internal columns; exclude overridden-out rows)
    display_matches = matches_df.copy()
    display_matches = display_matches[display_matches["override_action"] != "exclude"]
    display_matches = display_matches[[config.municipal_id_col, "osm_way_id"]]
    display_matches.to_csv(display_dir / "matches.csv", index=False)

    # 8. municipal_with_matches.json
    mid_col = config.municipal_id_col
    all_muni_ids = municipal_gdf[mid_col].unique().tolist()
    muni_lookup: dict[str, list] = {str(mid): [] for mid in all_muni_ids}
    for _, row in display_matches.iterrows():
        if pd.notna(row["osm_way_id"]) and row["osm_way_id"]:
            muni_lookup.setdefault(str(row[mid_col]), []).append(row["osm_way_id"])
    with open(display_dir / "municipal_with_matches.json", "w") as f:
        json.dump({"municipal_id_key": mid_col, "matches": muni_lookup}, f, indent=2)

    # 9. osm_with_matches.json (all downloaded OSM ways, not just matched)
    all_osm_ids = [f"way/{i}" for i in osm_gdf.index.tolist()]
    osm_lookup: dict[str, list] = {osm_id: [] for osm_id in all_osm_ids}
    for _, row in display_matches.iterrows():
        if pd.notna(row["osm_way_id"]) and pd.notna(row[mid_col]):
            osm_lookup.setdefault(row["osm_way_id"], []).append(str(row[mid_col]))
    with open(display_dir / "osm_with_matches.json", "w") as f:
        json.dump({"municipal_id_key": mid_col, "matches": osm_lookup}, f, indent=2)

    # 10. StatusManager
    matched_count = display_matches[display_matches["osm_way_id"].notna()].shape[0]
    sm.add(
        dataset_name=f"cycling_network_conflation_{config.name}",
        last_updated=municipal_last_updated,
        num_features=matched_count,
        last_checked=now,
    )
    sm.save()

    # 11. Archive
    if archive:
        archive_dir = output_dir / "archive" / now.strftime("%Y%m%d_%H%M%S")
        archive_dir.mkdir(parents=True, exist_ok=True)
        matches_df.to_parquet(archive_dir / "matches.parquet")

        archive_display = display_dir / "archive" / now.strftime("%Y%m%d_%H%M%S")
        archive_display.mkdir(parents=True, exist_ok=True)
        display_matches.to_parquet(archive_display / "matches.parquet")

    print(f"[{config.name}] Done. Matched {matched_count} municipal-OSM pairs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate cycling network conflation files"
    )
    parser.add_argument(
        "--region",
        choices=list(_REGIONS.keys()) + ["all"],
        default="all",
        help="Region to process (default: all)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("cycling_network_conflation"),
        help="Root directory for output files",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Archive outputs with timestamp",
    )
    args = parser.parse_args()

    regions = list(_REGIONS.values()) if args.region == "all" else [_REGIONS[args.region]]
    for region_config in regions:
        run_region(region_config, output_root=args.output_root, archive=args.archive)
