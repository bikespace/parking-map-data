import math

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge, substring

from bikespace_data.cycling_network_conflation.region_config import RegionConfig


def compute_linestring_bearing(geom: LineString) -> float:
    coords = list(geom.coords)
    x0, y0 = coords[0][0], coords[0][1]
    x1, y1 = coords[-1][0], coords[-1][1]
    return math.atan2(y1 - y0, x1 - x0)


def acute_angle_between(b1: float, b2: float) -> float:
    diff = abs(b1 - b2) % math.pi
    return min(diff, math.pi - diff)


def core_buffer(geom, trim_m: float, buffer_m: float):
    if isinstance(geom, MultiLineString):
        geom = linemerge(geom)
        if isinstance(geom, MultiLineString):
            return None
    if geom.length < 2 * trim_m:
        return None
    trimmed = substring(geom, trim_m, geom.length - trim_m)
    return trimmed.buffer(buffer_m)


def _local_tangent(geom: LineString, t: float) -> float:
    t0 = max(0.0, t - 0.01)
    t1 = min(1.0, t + 0.01)
    p0 = geom.interpolate(t0, normalized=True)
    p1 = geom.interpolate(t1, normalized=True)
    return math.atan2(p1.y - p0.y, p1.x - p0.x)


def _longest_linestring(geom) -> LineString | None:
    if isinstance(geom, LineString):
        return geom
    if isinstance(geom, MultiLineString):
        return max(geom.geoms, key=lambda g: g.length)
    return None


def match_cycling_network(
    municipal_gdf: gpd.GeoDataFrame,
    osm_gdf: gpd.GeoDataFrame,
    config: RegionConfig,
    overrides_df: pd.DataFrame,
) -> pd.DataFrame:
    mid_col = config.municipal_id_col

    muni = municipal_gdf.to_crs(config.crs).copy()
    osm = osm_gdf.to_crs(config.crs).copy()

    if "_related_highway" in osm.columns:
        osm = osm[~osm["_related_highway"].fillna(False)]

    muni["_buffer"] = muni.geometry.buffer(config.buffer_m)
    muni["_core_buffer"] = muni.geometry.apply(
        lambda g: core_buffer(g, config.endpoint_trim_m, config.buffer_m)
    )

    muni_buffers = muni.set_geometry("_buffer")

    osm["_osm_way_id"] = "way/" + osm.index.astype(str)

    candidates = gpd.sjoin(
        osm.set_geometry("geometry"),
        muni_buffers[[mid_col, "_buffer", "_core_buffer", "geometry"]].rename(
            columns={"geometry": "_muni_geom"}
        ).set_geometry("_buffer"),
        how="inner",
        predicate="intersects",
    )

    matched_pairs = []

    threshold_rad = math.radians(config.orthogonality_threshold_deg)

    for _, row in candidates.iterrows():
        osm_way_id = row["_osm_way_id"]
        muni_id = row[mid_col]

        osm_geom = row.geometry
        muni_geom = muni.loc[muni[mid_col] == muni_id, "geometry"].iloc[0]
        muni_buffer = muni.loc[muni[mid_col] == muni_id, "_buffer"].iloc[0]
        muni_core_buf = muni.loc[muni[mid_col] == muni_id, "_core_buffer"].iloc[0]

        clipped_raw = osm_geom.intersection(muni_buffer)
        clipped = _longest_linestring(clipped_raw)

        if clipped is None or clipped.is_empty:
            continue

        buffer_overlap = clipped.length

        if buffer_overlap >= 2.0 and not isinstance(muni_geom, MultiLineString):  # safety: skip unmerged disconnected segments
            midpoint = clipped.interpolate(0.5, normalized=True)
            t = muni_geom.project(midpoint, normalized=True)
            muni_bearing = _local_tangent(muni_geom, t)
            osm_bearing = compute_linestring_bearing(clipped)
            angle = acute_angle_between(muni_bearing, osm_bearing)
            if math.degrees(angle) > config.orthogonality_threshold_deg:
                continue

        if muni_core_buf is None:
            endpoint_only = True
            core_overlap = 0.0
        else:
            core_clipped = osm_geom.intersection(muni_core_buf)
            core_ls = _longest_linestring(core_clipped)
            core_overlap = core_ls.length if (core_ls and not core_ls.is_empty) else 0.0
            endpoint_only = buffer_overlap > 0 and (core_overlap / buffer_overlap) < 0.10

        flags = "endpoint_only" if endpoint_only else ""
        matched_pairs.append(
            {
                mid_col: muni_id,
                "osm_way_id": osm_way_id,
                "match_type": "auto",
                "override_action": None,
                "flags": flags,
            }
        )

    result_df = pd.DataFrame(
        matched_pairs,
        columns=[mid_col, "osm_way_id", "match_type", "override_action", "flags"],
    )

    if not overrides_df.empty:
        exclude_mask = overrides_df["action"] == "exclude"
        excludes = overrides_df.loc[exclude_mask, [mid_col, "osm_way_id"]]

        for _, exc in excludes.iterrows():
            mask = (result_df[mid_col] == exc[mid_col]) & (
                result_df["osm_way_id"] == exc["osm_way_id"]
            )
            result_df.loc[mask, "override_action"] = "exclude"

        include_mask = overrides_df["action"] == "include"
        includes = overrides_df.loc[include_mask, [mid_col, "osm_way_id"]]
        already = set(zip(result_df[mid_col], result_df["osm_way_id"]))
        new_rows = []
        for _, inc in includes.iterrows():
            if (inc[mid_col], inc["osm_way_id"]) not in already:
                new_rows.append(
                    {
                        mid_col: inc[mid_col],
                        "osm_way_id": inc["osm_way_id"],
                        "match_type": "override",
                        "override_action": "include",
                        "flags": "",
                    }
                )
        if new_rows:
            result_df = pd.concat(
                [result_df, pd.DataFrame(new_rows)], ignore_index=True
            )

    all_muni_ids = muni[mid_col].unique()
    matched_muni_ids = set(result_df[mid_col].unique())
    unmatched = pd.DataFrame(
        [
            {
                mid_col: mid,
                "osm_way_id": None,
                "match_type": None,
                "override_action": None,
                "flags": "",
            }
            for mid in all_muni_ids
            if mid not in matched_muni_ids
        ]
    )
    if not unmatched.empty:
        result_df = pd.concat([result_df, unmatched], ignore_index=True)

    return result_df
