"""Voronoi utilities for bicycle-theft analysis.

Functions:
- load_thefts_gdf
- load_tts_zones
- build_voronoi
- create_disjoint_partition
- assign_parts_to_voronoi
- remove_small_slivers
- clip_and_merge_fragments
- assign_missing_thefts
- aggregate_to_voronoi
- plot_and_save_voronoi

This module is a cleaned-up extraction from notebooks/voronoi_theft_tts.ipynb.
"""
from __future__ import annotations

from pathlib import Path
import warnings
from typing import Iterable, Optional

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import MultiPoint, Point, Polygon
from shapely.ops import polygonize

# SciPy fallback flag is used for KDTree assignment and optional Voronoi
try:
    from scipy.spatial import Voronoi, cKDTree
    SCIPY_AVAILABLE = True
except Exception:
    SCIPY_AVAILABLE = False


def load_thefts_gdf(path: Path | str) -> gpd.GeoDataFrame:
    """Load thefts GeoJSON and ensure a proper CRS (EPSG:4326).

    Returns a cleaned GeoDataFrame with Point geometries.
    """
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    else:
        gdf = gdf.to_crs(epsg=4326)

    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()
    # convert non-points to centroids
    non_pts = ~gdf.geometry.geom_type.eq("Point")
    if non_pts.any():
        gdf.loc[non_pts, "geometry"] = gdf.loc[non_pts, "geometry"].centroid

    # simple heuristic for swapped coords (same as notebook)
    gdf["x"] = gdf.geometry.x
    gdf["y"] = gdf.geometry.y
    swap_mask = ((gdf["y"].abs() < 0.5) | ((gdf["x"] > 0) & (gdf["y"] > 0)) | (gdf["y"] < -20))
    if swap_mask.any():
        gdf.loc[swap_mask, ["x", "y"]] = gdf.loc[swap_mask, ["y", "x"]].values
        gdf["geometry"] = gdf.apply(lambda r: Point(r["x"], r["y"]), axis=1)
    # keep only broad NA extents
    na_mask = (gdf["x"] >= -130) & (gdf["x"] <= -50) & (gdf["y"] >= 5) & (gdf["y"] <= 70)
    gdf = gdf.loc[na_mask].copy()
    gdf = gdf.drop(columns=["x", "y"]).reset_index(drop=True)
    return gdf


def load_tts_zones(source: str | Path) -> gpd.GeoDataFrame:
    """Load TTS zones/GeoJSON and ensure EPSG:4326."""
    gdf = gpd.read_file(source)
    gdf = gdf.to_crs(epsg=4326)
    return gdf


def build_voronoi(points_gdf: gpd.GeoDataFrame, clipping_mask: Optional[Polygon] = None) -> gpd.GeoDataFrame:
    """Build Voronoi polygons from point geometries and clip to clipping_mask (EPSG:4326).

    Uses SciPy fallback if available; returns polygons in EPSG:4326.
    """
    pts = [pt for pt in points_gdf.geometry if pt is not None]
    if len(pts) == 0:
        return gpd.GeoDataFrame(columns=["geometry"])
    mp = MultiPoint(pts)
    if clipping_mask is None:
        clipping_mask = mp.convex_hull.buffer(0.01)

    # prefer SciPy Voronoi for robustness with many points, but SciPy needs at least 4 pts
    coords = np.array([[p.x, p.y] for p in pts])
    if SCIPY_AVAILABLE and coords.shape[0] >= 4:
        vor = Voronoi(coords)
        polys = []
        for pt_idx, region_idx in enumerate(vor.point_region):
            vertices = vor.regions[region_idx]
            if -1 in vertices or len(vertices) == 0:
                poly = Point(coords[pt_idx]).buffer(0.05)
            else:
                poly = Polygon(vor.vertices[vertices])
            poly = poly.intersection(clipping_mask)
            polys.append(poly)
        vor_gdf = gpd.GeoDataFrame(geometry=polys, crs="EPSG:4326")
        return vor_gdf
    # otherwise fall back to shapely implementation (works well for small sets)

    # fallback to shapely's voronoi_diagram
    from shapely.ops import voronoi_diagram
    try:
        vor_geom = voronoi_diagram(mp, envelope=clipping_mask)
    except Exception as e:
        raise RuntimeError("shapely.voronoi_diagram failed") from e
    polys = [g for g in vor_geom.geoms] if hasattr(vor_geom, "geoms") else [vor_geom]
    vor_gdf = gpd.GeoDataFrame(geometry=polys, crs="EPSG:4326")
    vor_gdf = gpd.overlay(vor_gdf, gpd.GeoDataFrame(geometry=[clipping_mask], crs="EPSG:4326"), how="intersection")
    return vor_gdf


def create_disjoint_partition(voronoi_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Convert overlapping Voronoi polygons into a disjoint partition and return pieces (with no vor_id assigned)."""
    merged = polygonize(voronoi_gdf.boundary.unary_union)
    parts = list(merged)
    parts_gdf = gpd.GeoDataFrame(geometry=parts, crs=voronoi_gdf.crs)
    return parts_gdf


def assign_parts_to_voronoi(parts_gdf: gpd.GeoDataFrame, voronoi_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Assign partition pieces to voronoi original ids by largest intersection area and dissolve to disjoint polygons.

    Returns a GeoDataFrame with columns: vor_id, geometry (disjoint polygons).
    """
    if 'vor_id' not in voronoi_gdf.columns:
        voronoi_gdf = voronoi_gdf.reset_index(drop=True).copy()
        voronoi_gdf['vor_id'] = range(len(voronoi_gdf))

    # project for accurate areas
    vor_proj = voronoi_gdf.to_crs(epsg=3857).copy()
    parts_proj = parts_gdf.to_crs(epsg=3857).copy()
    parts_proj['vor_id'] = -1
    for i, part in parts_proj.geometry.items():
        try:
            part_clean = part.buffer(0)
        except Exception:
            part_clean = part
        candidates = vor_proj[vor_proj.intersects(part_clean)]
        if len(candidates) == 0:
            continue
        candidates = candidates.copy()
        candidates['geometry'] = candidates.geometry.buffer(0)
        try:
            inter_areas = candidates.geometry.intersection(part_clean).area
        except Exception:
            inter_areas = []
            for idx2, geom2 in candidates.geometry.items():
                try:
                    inter_areas.append(geom2.intersection(part_clean).area)
                except Exception:
                    inter_areas.append(0.0)
            inter_areas = pd.Series(inter_areas, index=candidates.index)
        max_idx = inter_areas.idxmax()
        parts_proj.at[i, 'vor_id'] = int(vor_proj.loc[max_idx, 'vor_id'])

    parts_assigned = parts_proj[parts_proj['vor_id'] != -1].copy()
    # dissolve
    groups = []
    for vid, grp in parts_assigned.groupby('vor_id'):
        geoms = [g.buffer(0) for g in grp.geometry if g is not None and not g.is_empty]
        try:
            from shapely.ops import unary_union as shapely_unary_union
            merged = shapely_unary_union(geoms)
        except Exception:
            merged = grp.geometry.unary_union
        groups.append({'vor_id': int(vid), 'geometry': merged})
    vor_disjoint = gpd.GeoDataFrame(groups, crs=parts_proj.crs).to_crs(epsg=4326)
    return vor_disjoint[['vor_id', 'geometry']]


def remove_small_slivers(partition_parts: gpd.GeoDataFrame, min_area_m2: float = 1000) -> gpd.GeoDataFrame:
    """Merge partition pieces smaller than min_area_m2 into neighboring large polygons.

    Input expected in projected CRS (EPSG:3857) or will be projected internally.
    Returns cleaned disjoint polygons (voronoi_clean) in EPSG:4326.
    """
    parts_proj = partition_parts.to_crs(epsg=3857).copy()
    parts_proj['area_m2'] = parts_proj.geometry.area
    small_mask = parts_proj['area_m2'] < min_area_m2
    if small_mask.sum() == 0:
        # dissolve by vor_id if present
        if 'vor_id' in parts_proj.columns:
            return parts_proj.dissolve(by='vor_id').reset_index()[['vor_id','geometry']].to_crs(epsg=4326)
        else:
            return parts_proj.to_crs(epsg=4326)

    large = parts_proj[~small_mask].copy()
    small = parts_proj[small_mask].copy()
    large_sindex = large.sindex

    assign_map = {}
    for idx, row in small.iterrows():
        geom = row.geometry
        cand_pos = list(large_sindex.intersection(geom.bounds))
        if len(cand_pos) > 0:
            try:
                candidates = large.iloc[cand_pos].copy()
            except Exception:
                candidates = large.copy()
        else:
            candidates = large.iloc[[]].copy()
        candidates['geometry'] = candidates.geometry.buffer(0)
        try:
            part_clean = geom.buffer(0)
        except Exception:
            part_clean = geom
        candidates = candidates[candidates.intersects(part_clean)]
        if len(candidates) == 0:
            dists = large.geometry.distance(part_clean.centroid)
            nearest_idx = dists.idxmin()
            assign = int(large.loc[nearest_idx, 'vor_id'])
        else:
            try:
                shared_lengths = candidates.geometry.intersection(part_clean).length
                if shared_lengths.sum() == 0:
                    shared_areas = candidates.geometry.intersection(part_clean).area
                    max_idx = shared_areas.idxmax()
                    assign = int(candidates.loc[max_idx, 'vor_id'])
                else:
                    max_idx = shared_lengths.idxmax()
                    assign = int(candidates.loc[max_idx, 'vor_id'])
            except Exception:
                dists = candidates.geometry.distance(part_clean.centroid)
                nearest_idx = dists.idxmin()
                assign = int(candidates.loc[nearest_idx, 'vor_id'])
        assign_map[int(row['vor_id'])] = assign

    parts_proj['vor_id'] = parts_proj['vor_id'].apply(lambda v: assign_map[v] if int(v) in assign_map else int(v))
    groups = []
    from shapely.ops import unary_union as shapely_unary_union
    for vid, grp in parts_proj.groupby('vor_id'):
        geoms = [g.buffer(0) for g in grp.geometry if g is not None and not g.is_empty]
        try:
            merged = shapely_unary_union(geoms)
        except Exception:
            merged = grp.geometry.unary_union
        groups.append({'vor_id': int(vid), 'geometry': merged})
    vor_clean = gpd.GeoDataFrame(groups, crs=parts_proj.crs).to_crs(epsg=4326)
    return vor_clean[['vor_id','geometry']]


def clip_and_merge_fragments(voronoi_clean: gpd.GeoDataFrame, clipping_mask: Polygon, buffer_neg_m: float = 3, min_fragment_m2: float = 2000) -> gpd.GeoDataFrame:
    """Apply an inward buffer to clipping_mask, clip voronoi_clean to it, drop tiny fragments and merge them into nearest large piece.

    Returns voronoi_final in EPSG:4326 with columns (vor_id, geometry).
    """
    mask_gdf = gpd.GeoDataFrame(geometry=[clipping_mask], crs='EPSG:4326')
    mask_proj = mask_gdf.to_crs(epsg=3857)
    try:
        mask_shrunk = mask_proj.geometry.buffer(-buffer_neg_m).unary_union
        if mask_shrunk.is_empty:
            mask_shrunk = mask_proj.unary_union
    except Exception:
        mask_shrunk = mask_proj.unary_union

    vor_proj = voronoi_clean.to_crs(epsg=3857).copy()
    vor_proj['geometry'] = vor_proj.geometry.intersection(mask_shrunk)
    vor_proj = vor_proj.loc[~vor_proj.geometry.is_empty & vor_proj.geometry.notna()].reset_index(drop=True)
    vor_proj['area_m2'] = vor_proj.geometry.area
    small_frags = vor_proj[vor_proj['area_m2'] < min_fragment_m2].copy()
    large_pieces = vor_proj[vor_proj['area_m2'] >= min_fragment_m2].copy()

    from shapely.ops import unary_union as shapely_unary_union
    if len(small_frags) > 0 and len(large_pieces) > 0:
        small_pts = gpd.GeoDataFrame(geometry=small_frags.geometry.centroid, crs=vor_proj.crs)
        large_index = large_pieces[['vor_id','geometry']].copy()
        nearest = gpd.sjoin_nearest(small_pts, large_index, how='left', distance_col='dist')
        vor_col = next((c for c in nearest.columns if 'vor_id' in c), None)
        if vor_col is None:
            raise RuntimeError('sjoin_nearest did not return vor_id column')
        assign_map = dict(zip(small_frags.index, nearest[vor_col].values))
        small_assigned = small_frags.copy()
        small_assigned['vor_id'] = small_assigned.index.map(lambda i: assign_map.get(i, None))
        small_assigned = small_assigned.dropna(subset=['vor_id']).copy()

        combined = pd.concat([large_pieces[['vor_id','geometry']], small_assigned[['vor_id','geometry']]], ignore_index=True)
        groups = []
        for vid, grp in combined.groupby('vor_id'):
            geoms = [g.buffer(0) for g in grp.geometry if g is not None and not g.is_empty]
            try:
                merged = shapely_unary_union(geoms)
            except Exception:
                merged = grp.geometry.unary_union
            groups.append({'vor_id': int(vid), 'geometry': merged})
        vor_final_proj = gpd.GeoDataFrame(groups, crs=vor_proj.crs)
    else:
        vor_final_proj = vor_proj[['vor_id','geometry']].copy()

    vor_final = vor_final_proj[['vor_id','geometry']].to_crs(epsg=4326).reset_index(drop=True)
    return vor_final


def assign_missing_thefts(thefts_gdf: gpd.GeoDataFrame, vor_final: gpd.GeoDataFrame) -> pd.Series:
    """Assign any thefts that do not fall within vor_final polygons to the nearest polygon.

    Returns a Series indexed by vor_id containing theft counts.
    """
    joined = gpd.sjoin(thefts_gdf, vor_final[['vor_id','geometry']], predicate='within', how='left')
    missing = joined[joined['vor_id'].isna()].copy()
    if len(missing) > 0:
        missing_proj = missing.to_crs(epsg=3857)
        vor_proj = vor_final.to_crs(epsg=3857)[['vor_id','geometry']].copy()
        for col in ['index_right','index_left','level_0']:
            if col in missing_proj.columns:
                missing_proj = missing_proj.drop(columns=[col])
            if col in vor_proj.columns:
                vor_proj = vor_proj.drop(columns=[col])
        nearest = gpd.sjoin_nearest(missing_proj, vor_proj, how='left', distance_col='dist')
        vor_col = next((c for c in nearest.columns if 'vor_id' in c), None)
        if vor_col is None:
            raise RuntimeError('sjoin_nearest did not return vor_id')
        joined.loc[nearest.index, 'vor_id'] = nearest[vor_col].values
        # extra fallback using KDTree if still missing
        still_missing = joined[joined['vor_id'].isna()].copy()
        if len(still_missing) > 0:
            if not SCIPY_AVAILABLE:
                raise RuntimeError('scipy required for KDTree fallback')
            vor_centroids = vor_final.to_crs(epsg=3857).geometry.centroid.reset_index(drop=True)
            cent_coords = np.array([[p.x, p.y] for p in vor_centroids])
            tree = cKDTree(cent_coords)
            sm_proj = still_missing.to_crs(epsg=3857)
            pts = np.array([[p.x, p.y] for p in sm_proj.geometry])
            dists, idxs = tree.query(pts, k=1)
            vor_ids_ordered = vor_final.to_crs(epsg=3857).reset_index(drop=True)['vor_id'].tolist()
            assigned_vids = [int(vor_ids_ordered[i]) for i in idxs]
            joined.loc[still_missing.index, 'vor_id'] = assigned_vids
    thft = joined.groupby('vor_id').size().rename('theft_count')
    return thft


def aggregate_to_voronoi(voronoi_gdf: gpd.GeoDataFrame, thefts_gdf: gpd.GeoDataFrame, tts_zones_gdf: gpd.GeoDataFrame, tts_weight_col: Optional[str] = None) -> gpd.GeoDataFrame:
    """Aggregate theft counts and TTS usage counts to voronoi_gdf (voronoi_gdf must have 'vor_id')."""
    if voronoi_gdf.crs != thefts_gdf.crs:
        thefts_gdf = thefts_gdf.to_crs(voronoi_gdf.crs)
    if isinstance(tts_zones_gdf, gpd.GeoDataFrame) and not tts_zones_gdf.empty and tts_zones_gdf.crs != voronoi_gdf.crs:
        tts_zones_gdf = tts_zones_gdf.to_crs(voronoi_gdf.crs)

    th_counts = gpd.sjoin(thefts_gdf, voronoi_gdf, predicate='within', how='left').groupby('vor_id').size().rename('theft_count')
    if isinstance(tts_zones_gdf, gpd.GeoDataFrame) and not tts_zones_gdf.empty:
        if tts_weight_col and tts_weight_col in tts_zones_gdf.columns:
            usage = gpd.sjoin(tts_zones_gdf, voronoi_gdf, predicate='intersects', how='left').groupby('vor_id')[tts_weight_col].sum().rename('bike_trips')
        else:
            usage = gpd.sjoin(tts_zones_gdf, voronoi_gdf, predicate='intersects', how='left').groupby('vor_id').size().rename('bike_trips')
    else:
        usage = pd.Series(dtype=float, name='bike_trips')

    result = voronoi_gdf.merge(th_counts, left_on='vor_id', right_index=True, how='left')
    result = result.merge(usage, left_on='vor_id', right_index=True, how='left')
    result['theft_count'] = result['theft_count'].fillna(0).astype(int)
    result['bike_trips'] = result['bike_trips'].fillna(0)
    result['theft_per_1000_trips'] = (result['theft_count'] / result['bike_trips'].replace({0: pd.NA})) * 1000
    return result


def plot_and_save_voronoi(voronoi_rates_gdf: gpd.GeoDataFrame, out_dir: Path, fname_stem: str = 'voronoi_theft_rates', min_bike_trips: int = 10, n_quantiles: int = 5) -> None:
    """Plot quantile-colored map and save GeoJSON + PNG."""
    OUT_DIR = Path(out_dir)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gdf = voronoi_rates_gdf.copy()
    gdf['plot_rate'] = gdf['theft_per_1000_trips']
    gdf['masked'] = gdf['bike_trips'] < min_bike_trips
    proj = gdf.to_crs(epsg=3857)
    low = proj[proj['masked']].copy()
    main = proj[~proj['masked']].copy()
    main.loc[:, 'plot_rate_num'] = pd.to_numeric(main['plot_rate'], errors='coerce')
    vals = main['plot_rate_num'].dropna()

    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm
    cmap = plt.cm.Reds
    if len(vals) > 0 and vals.max() > 0:
        breaks = np.nanpercentile(vals, np.linspace(0, 100, n_quantiles + 1))
        breaks = np.unique(breaks).astype(float)
        if len(breaks) > 1:
            norm = BoundaryNorm(breaks, ncolors=cmap.N, clip=True)
        else:
            norm = plt.Normalize(vmin=vals.min(), vmax=vals.max())
    else:
        norm = None

    fig, ax = plt.subplots(figsize=(10,10))
    if len(low) > 0:
        low.plot(ax=ax, color="#efefef", edgecolor='#cccccc', linewidth=0.2, alpha=0.7)
    if len(main) > 0:
        if norm is not None:
            main.plot(column='plot_rate_num', ax=ax, cmap=cmap, norm=norm, linewidth=0.2, edgecolor='white')
        else:
            main.plot(column='plot_rate_num', ax=ax, cmap=cmap, linewidth=0.2, edgecolor='white')

    if norm is not None:
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax, fraction=0.036, pad=0.04)
        cbar.set_label('Thefts per 1000 bike trips (quantiles)')

    try:
        import contextily as ctx
        provider = ctx.providers.CartoDB.Positron
        ctx.add_basemap(ax, source=provider)
    except Exception:
        pass

    plt.title(f"Theft rate per 1000 bike trips ({fname_stem})")
    plt.axis('off')
    plt.tight_layout()

    geojson_path = OUT_DIR / f"{fname_stem}.geojson"
    png_path = OUT_DIR / f"{fname_stem}.png"
    voronoi_rates_gdf.to_file(geojson_path, driver='GeoJSON')
    fig.savefig(png_path, dpi=150)
    return
