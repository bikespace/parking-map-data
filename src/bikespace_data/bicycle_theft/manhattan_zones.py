"""Trip-balanced "Manhattan" zones for the bicycle-theft rate map.

Zones are Voronoi cells measured in Manhattan (L1) distance on Toronto's street grid, so a cell
is "the part of the city closest to this site by riding along the streets" rather than as the
crow flies. Sites are placed so each zone holds a similar number of estimated bike trips: dense
areas like downtown get many small zones and quiet suburbs get a few large ones, which keeps
every zone's rate backed by enough trips to be meaningful.

Functions:
- build_manhattan_zones
"""
from __future__ import annotations

from typing import Optional

import geopandas as gpd
import numpy as np
import shapely
from scipy.spatial import cKDTree
from shapely import affinity

from bikespace_data.bicycle_theft.theft_rate_zones import _apportion_by_area

METRIC_CRS = "EPSG:32617"  # UTM 17N, metres
# Toronto's street grid runs about 17.5 degrees counter-clockwise from east (the peak of the
# neighbourhood boundary edge bearings, which follow the streets)
GRID_ANGLE_DEG = 17.5
DEFAULT_N_ZONES = 400
DEFAULT_CELL_M = 100.0
SIMPLIFY_M = 40.0


def _balanced_sites(xy: np.ndarray, weights: np.ndarray, n_sites: int) -> np.ndarray:
    """Split the weighted points into `n_sites` groups of roughly equal total weight by
    repeatedly cutting the longer side at the weighted median (a k-d split), and return each
    group's weighted centre."""
    sites: list[np.ndarray] = []

    def split(idx: np.ndarray, k: int) -> None:
        if k == 1 or len(idx) <= 1:
            w = weights[idx]
            sites.append(np.average(xy[idx], axis=0, weights=w if w.sum() > 0 else None))
            return
        axis = int(np.argmax(np.ptp(xy[idx], axis=0)))
        order = idx[np.argsort(xy[idx, axis], kind="stable")]
        cum = np.cumsum(weights[order])
        if cum[-1] > 0:
            cut = int(np.searchsorted(cum, cum[-1] * (k // 2) / k)) + 1
        else:
            cut = len(order) // 2
        cut = min(max(cut, 1), len(order) - 1)
        split(order[:cut], k // 2)
        split(order[cut:], k - k // 2)

    split(np.arange(len(xy)), n_sites)
    return np.array(sites)


def build_manhattan_zones(
    city_gdf: gpd.GeoDataFrame,
    tts_zones_gdf: gpd.GeoDataFrame,
    tts_weight_col: Optional[str] = None,
    n_zones: int = DEFAULT_N_ZONES,
    cell_m: float = DEFAULT_CELL_M,
) -> gpd.GeoDataFrame:
    """Build `n_zones` trip-balanced Manhattan-distance zones covering `city_gdf`.

    `city_gdf` supplies the city outline (its shapes are merged, so the neighbourhoods work
    directly) and is what keeps the zones off the lake. `tts_weight_col` in `tts_zones_gdf`
    says how many bike trips each survey zone holds; without it, zones are balanced by area.

    Returns a GeoDataFrame (EPSG:4326) with a `zone_id` column (1..n_zones) and polygon geometry.
    """
    city = shapely.make_valid(city_gdf.to_crs(METRIC_CRS).union_all())
    origin = city.centroid
    origin_xy = (origin.x, origin.y)
    to_grid = lambda geom: affinity.rotate(geom, -GRID_ANGLE_DEG, origin=origin_xy)  # noqa: E731
    from_grid = lambda geom: affinity.rotate(geom, GRID_ANGLE_DEG, origin=origin_xy)  # noqa: E731
    city_grid = to_grid(city)

    # square cells aligned with the street grid, keeping those that touch the city
    minx, miny, maxx, maxy = city_grid.bounds
    xs = np.arange(minx, maxx, cell_m)
    ys = np.arange(miny, maxy, cell_m)
    gx, gy = np.meshgrid(xs, ys)
    x0, y0 = gx.ravel(), gy.ravel()
    boxes = shapely.box(x0, y0, x0 + cell_m, y0 + cell_m)
    shapely.prepare(city_grid)
    touches = shapely.intersects(boxes, city_grid)
    boxes, centres = boxes[touches], np.column_stack([x0[touches], y0[touches]]) + cell_m / 2

    # how many bike trips sit in each cell's land, to place the sites
    if tts_weight_col and tts_weight_col in tts_zones_gdf.columns and len(tts_zones_gdf) > 0:
        land = shapely.intersection(boxes, city_grid)
        land_cells = gpd.GeoDataFrame(
            {"zone_id": np.arange(len(boxes))},
            geometry=[from_grid(g) for g in land],
            crs=METRIC_CRS,
        )
        trips = _apportion_by_area(tts_zones_gdf, tts_weight_col, land_cells)
        weights = trips.reindex(np.arange(len(boxes))).fillna(0).to_numpy()
    else:
        weights = shapely.area(boxes)

    sites = _balanced_sites(centres, weights, n_zones)
    _, label = cKDTree(sites).query(centres, p=1)

    # merge each site's cells into one zone; the shared cell edges line up exactly, so
    # coverage_simplify can smooth the staircase between zones without opening gaps
    zones = [shapely.union_all(boxes[label == i]) for i in range(len(sites))]
    keep = [i for i, z in enumerate(zones) if not z.is_empty]
    zones = shapely.coverage_simplify(np.array([zones[i] for i in keep], dtype=object), SIMPLIFY_M)
    clipped = [from_grid(shapely.intersection(z, city_grid)) for z in zones]

    out = gpd.GeoDataFrame(
        {"zone_id": np.arange(1, len(clipped) + 1)}, geometry=clipped, crs=METRIC_CRS
    )
    out = out[~out.geometry.is_empty].reset_index(drop=True)
    return out.to_crs(epsg=4326)
