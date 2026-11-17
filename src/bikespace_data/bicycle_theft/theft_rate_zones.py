"""Bicycle-theft rate analysis by zone.

Functions:
- load_thefts_gdf
- load_tts_zones
- detect_tts_weight_col
- assign_thefts_to_zones
- filter_to_complete_years
- aggregate_theft_rates
- load_lake_ontario
- clip_zones_outside_lake
- plot_theft_rates

Works on any set of disjoint zone polygons with a `zone_id` column; the runner uses the
trip-balanced Manhattan zones from `bikespace_data.bicycle_theft.manhattan_zones`.
"""
from __future__ import annotations

import time
from http import HTTPStatus
from pathlib import Path
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import shapely
from shapely.geometry import LineString, Point, Polygon

AREA_CRS = "EPSG:3857"
SHORELINE_CRS = "EPSG:32617"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_USER_AGENT = (
    "bikespace-parking-map-data (https://github.com/bikespace/parking-map-data)"
)
# The Toronto shore and islands are the outer and inner rings of this relation.
LAKE_ONTARIO_RELATION_ID = 1206310


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
    swap_mask = (gdf["y"].abs() < 0.5) | ((gdf["x"] > 0) & (gdf["y"] > 0)) | (gdf["y"] < -20)
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


def detect_tts_weight_col(tts: gpd.GeoDataFrame) -> tuple[Optional[str], gpd.GeoDataFrame]:
    """Return (weight_col, possibly_augmented_tts).

    Tries the following in order:
    1. Estimate daily bike trips made by each zone's residents:
       population * trips_5up_per_person * bike mode share (percent or proportion)
    2. Use one of: trips, bike_trips, TRIPS
    3. Return None if no usable column found (callers should treat every zone as equally weighted)

    Note `TTS2022` in the School of Cities data is the zone ID, not a trip count, so it must never
    be used as a weight. The estimate in (1) is residence-based: it undercounts places people
    cycle to (e.g. downtown) and overcounts places they cycle from.
    """
    if {"population", "trips_5up_per_person", "mode_bike"}.issubset(tts.columns):
        population = pd.to_numeric(tts["population"], errors="coerce").fillna(0)
        trips_per_person = pd.to_numeric(tts["trips_5up_per_person"], errors="coerce").fillna(0)
        mb = pd.to_numeric(tts["mode_bike"], errors="coerce").fillna(0)
        share = mb / 100.0 if mb.max() > 1.5 else mb
        tts = tts.copy()
        tts["bike_trips_est"] = population * trips_per_person * share
        return "bike_trips_est", tts

    for col in ("trips", "bike_trips", "TRIPS"):
        if col in tts.columns and pd.api.types.is_numeric_dtype(tts[col]):
            return col, tts

    return None, tts


def assign_thefts_to_zones(
    thefts_gdf: gpd.GeoDataFrame, zones_gdf: gpd.GeoDataFrame
) -> pd.Series:
    """Assign each theft point to the zone it falls within, with a nearest-zone fallback for
    points that miss every polygon (e.g. a point that lands just outside a boundary edge due to
    geocoding noise).

    Returns a Series indexed by zone_id containing theft counts.
    """
    if thefts_gdf.crs != zones_gdf.crs:
        thefts_gdf = thefts_gdf.to_crs(zones_gdf.crs)

    zones = zones_gdf[["zone_id", "geometry"]]
    joined = gpd.sjoin(thefts_gdf, zones, predicate="within", how="left").drop(
        columns=["index_right"]
    )

    missing = joined[joined["zone_id"].isna()]
    if len(missing) > 0:
        missing_proj = missing.to_crs(AREA_CRS).drop(columns=["zone_id"])
        zones_proj = zones.to_crs(AREA_CRS)
        nearest = gpd.sjoin_nearest(missing_proj, zones_proj, how="left").drop(
            columns=["index_right"], errors="ignore"
        )
        joined.loc[nearest.index, "zone_id"] = nearest[
            "zone_id"
        ].values

    return joined.groupby("zone_id").size().rename("theft_count")


def _apportion_by_area(
    source_gdf: gpd.GeoDataFrame,
    weight_col: str,
    zones_gdf: gpd.GeoDataFrame,
    min_covered_fraction: float = 0.5,
) -> pd.Series:
    """Split each source_gdf row's weight_col value across the zones it overlaps,
    in proportion to the share of that row's area falling in each zone.

    This avoids double-counting a value into every zone a source polygon merely
    touches (which a plain `intersects()` sum would do).

    Lakeshore source zones extend out over open water, where nobody lives or rides. When at
    least `min_covered_fraction` of a source polygon lies inside the zones, its whole
    weight is spread over that covered (land) part rather than losing the over-water share. A
    polygon mostly outside the zones (i.e. in a neighbouring municipality) keeps the
    plain area share, so only its sliver inside the city is counted.
    """
    src_proj = source_gdf.to_crs(AREA_CRS).reset_index(drop=True)
    src_proj["_source_id"] = src_proj.index
    src_proj["_source_area"] = src_proj.geometry.area
    src_proj = src_proj[src_proj["_source_area"] > 0]

    zones_proj = zones_gdf[["zone_id", "geometry"]].to_crs(AREA_CRS)

    overlay = gpd.overlay(
        src_proj[["_source_id", "_source_area", weight_col, "geometry"]],
        zones_proj,
        how="intersection",
        keep_geom_type=False,
    )
    if len(overlay) == 0:
        return pd.Series(dtype=float, name="bike_trips")

    overlay["_piece_area"] = overlay.geometry.area
    covered_area = overlay.groupby("_source_id")["_piece_area"].transform("sum")
    mostly_covered = covered_area / overlay["_source_area"] >= min_covered_fraction
    share_denominator = overlay["_source_area"].where(~mostly_covered, covered_area)
    overlay["_weight_share"] = overlay[weight_col] * (overlay["_piece_area"] / share_denominator)
    return overlay.groupby("zone_id")["_weight_share"].sum().rename("bike_trips")


def filter_to_complete_years(
    thefts_gdf: gpd.GeoDataFrame,
    year_col: str = "OCC_YEAR",
    min_year_fraction: float = 0.5,
) -> tuple[gpd.GeoDataFrame, int]:
    """Keep only theft records from years with enough reports to be considered a complete
    reporting year.

    The raw Toronto Police theft dataset has a handful of stray historical records (occurrence
    dates decades before the dataset's real reporting era) and an in-progress current year with
    a partial count — both would distort a simple "total thefts / number of years" average. A
    year qualifies here if its record count is at least `min_year_fraction` of the median count
    across all years that have any records at all, which excludes both kinds of outliers without
    hardcoding specific years.

    Returns (filtered_gdf, num_complete_years). If `year_col` isn't present, returns the input
    unchanged with num_complete_years=0 so callers know annualizing isn't possible.
    """
    if year_col not in thefts_gdf.columns:
        return thefts_gdf, 0

    year_counts = thefts_gdf[year_col].value_counts()
    if len(year_counts) == 0:
        return thefts_gdf, 0

    threshold = year_counts.median() * min_year_fraction
    complete_years = year_counts[year_counts >= threshold].index
    return thefts_gdf[thefts_gdf[year_col].isin(complete_years)], len(complete_years)


def aggregate_theft_rates(
    zones_gdf: gpd.GeoDataFrame,
    thefts_gdf: gpd.GeoDataFrame,
    tts_zones_gdf: gpd.GeoDataFrame,
    tts_weight_col: Optional[str] = None,
    year_col: str = "OCC_YEAR",
) -> gpd.GeoDataFrame:
    """Aggregate theft counts and TTS bike-trip estimates by zone and compute a theft
    rate per 1000 bike trips.

    `bike_trips` is a TTS estimate for a single typical day, but `thefts_gdf` is normally a
    cumulative, multi-year record — comparing those directly would be off by orders of
    magnitude. When `year_col` is available, thefts are first annualized using only "complete"
    years (see `filter_to_complete_years`) and converted to a per-day estimate before computing
    the rate, so both sides of the ratio are on the same time scale. If `year_col` isn't usable,
    falls back to the raw theft count (the resulting rate should then be treated as a rough,
    same-scale comparison across zones rather than a literal daily rate).

    `zones_gdf` must have a `zone_id` column. If `tts_zones_gdf` has no usable weight column, every zone is
    counted as weight 1 (i.e. `bike_trips` becomes a proxy for TTS zone coverage rather than an
    actual trip estimate).
    """
    th_counts = assign_thefts_to_zones(thefts_gdf, zones_gdf)

    complete_thefts, num_years = filter_to_complete_years(thefts_gdf, year_col=year_col)
    if num_years > 0:
        annual_thefts = assign_thefts_to_zones(complete_thefts, zones_gdf) / num_years
        daily_thefts = (annual_thefts / 365).rename("daily_theft_estimate")
    else:
        daily_thefts = th_counts.astype(float).rename("daily_theft_estimate")

    if isinstance(tts_zones_gdf, gpd.GeoDataFrame) and not tts_zones_gdf.empty:
        tts = tts_zones_gdf.copy()
        if not tts_weight_col or tts_weight_col not in tts.columns:
            tts_weight_col = "_zone_weight"
            tts[tts_weight_col] = 1.0
        usage = _apportion_by_area(tts, tts_weight_col, zones_gdf)
    else:
        usage = pd.Series(dtype=float, name="bike_trips")

    result = zones_gdf.merge(
        th_counts, left_on="zone_id", right_index=True, how="left"
    )
    result = result.merge(
        daily_thefts, left_on="zone_id", right_index=True, how="left"
    )
    result = result.merge(usage, left_on="zone_id", right_index=True, how="left")
    result["theft_count"] = result["theft_count"].fillna(0).astype(int)
    result["daily_theft_estimate"] = result["daily_theft_estimate"].fillna(0)
    result["bike_trips"] = result["bike_trips"].fillna(0)
    result["theft_years_of_data"] = num_years
    # `.where` keeps the column float (NaN where there are no trips); replacing 0 with pd.NA
    # would turn it into an object column that gets written to GeoJSON as strings
    result["theft_per_1000_trips"] = (
        result["daily_theft_estimate"] / result["bike_trips"].where(result["bike_trips"] > 0)
    ) * 1000
    return result


def _lake_query() -> str:
    return (
        "[out:json][timeout:180];\n"
        f"relation({LAKE_ONTARIO_RELATION_ID});\n"
        "out geom;"
    )


def _overpass_json(query: str) -> dict:
    """POST a query to Overpass, retrying when the public server is at capacity."""
    retryable = {429, HTTPStatus.BAD_GATEWAY, HTTPStatus.SERVICE_UNAVAILABLE, HTTPStatus.GATEWAY_TIMEOUT}
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.post(
                OVERPASS_URL,
                data={"data": query},
                headers={"User-Agent": OVERPASS_USER_AGENT},
                timeout=180,
            )
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
            continue
        if response.status_code in retryable:
            last_error = RuntimeError(f"status {response.status_code}")
            time.sleep(2 * (attempt + 1))
            continue
        if response.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f"Could not download Lake Ontario (status {response.status_code})."
            )
        payload = response.json()
        if isinstance(payload, dict) and "elements" in payload:
            return payload
        raise RuntimeError("Lake Ontario response did not contain a relation.")
    raise RuntimeError(f"Could not download Lake Ontario ({last_error}).")


def _member_line(member: dict) -> LineString | None:
    coords = [
        (point["lon"], point["lat"])
        for point in member.get("geometry") or []
        if "lon" in point and "lat" in point
    ]
    if len(coords) < 2:
        return None
    return LineString(coords)


def _endpoint(coord: tuple[float, float]) -> tuple[float, float]:
    return (round(coord[0], 6), round(coord[1], 6))


def _chain_ways(ways: list[LineString]) -> list[LineString]:
    """Join way pieces that share an endpoint, reversing a piece when needed."""
    unused = [list(way.coords) for way in ways]
    chains: list[list[tuple[float, float]]] = []
    while unused:
        chain = unused.pop()
        extended = True
        while extended:
            extended = False
            start, end = _endpoint(chain[0]), _endpoint(chain[-1])
            for index, coords in enumerate(unused):
                other_start, other_end = _endpoint(coords[0]), _endpoint(coords[-1])
                if other_start == end:
                    chain.extend(coords[1:])
                elif other_end == end:
                    chain.extend(list(reversed(coords[:-1])))
                elif other_end == start:
                    chain = coords[:-1] + chain
                elif other_start == start:
                    chain = list(reversed(coords[1:])) + chain
                else:
                    continue
                unused.pop(index)
                extended = True
                break
        if _endpoint(chain[0]) == _endpoint(chain[-1]) and chain[0] != chain[-1]:
            chain.append(chain[0])
        if len(chain) >= 2:
            chains.append(chain)
    return [LineString(chain) for chain in chains]


def _closed_rings(ways: list[LineString]) -> list[LineString]:
    rings = []
    for line in _chain_ways(ways):
        if len(line.coords) >= 4 and _endpoint(line.coords[0]) == _endpoint(line.coords[-1]):
            rings.append(line)
    return rings


def _as_polygons(geom):
    """Keep polygonal pieces and drop lines left behind by a difference."""
    if geom is None or geom.is_empty:
        return None
    geom = shapely.make_valid(geom)
    if geom.geom_type == "GeometryCollection":
        pieces = [part for part in geom.geoms if part.geom_type in ("Polygon", "MultiPolygon")]
        geom = shapely.union_all(pieces) if pieces else None
    if geom is None or geom.is_empty or geom.geom_type not in ("Polygon", "MultiPolygon"):
        return None
    return geom


def _ways_by_role(payload: dict) -> tuple[list[LineString], list[LineString]]:
    outers: list[LineString] = []
    inners: list[LineString] = []
    for element in payload.get("elements") or []:
        if element.get("type") != "relation":
            continue
        for member in element.get("members") or []:
            if member.get("type") != "way":
                continue
            line = _member_line(member)
            if line is None:
                continue
            if (member.get("role") or "outer") == "inner":
                inners.append(line)
            else:
                outers.append(line)
    return outers, inners


def _lake_geometry(payload: dict):
    """Build the lake polygon. Inner rings are islands, so they become holes."""
    outers, inners = _ways_by_role(payload)
    outer_rings = _closed_rings(outers)
    if not outer_rings:
        raise RuntimeError("Lake Ontario download did not contain a closed shoreline.")
    water = shapely.union_all([Polygon(ring) for ring in outer_rings])
    inner_rings = _closed_rings(inners)
    if inner_rings:
        islands = shapely.union_all([Polygon(ring) for ring in inner_rings])
        water = water.difference(islands)
    water = _as_polygons(water)
    if water is None:
        raise RuntimeError("Lake Ontario download did not contain a polygon.")
    return water


def load_lake_ontario() -> gpd.GeoDataFrame:
    """Download Lake Ontario as one polygon, with islands kept as holes.

    OpenStreetMap relation 1206310 is the lake multipolygon. The outer ring is
    water. Each inner ring is an island, so it is cut out of the water and a
    later difference leaves that land in place.
    """
    return gpd.GeoDataFrame(geometry=[_lake_geometry(_overpass_json(_lake_query()))], crs="EPSG:4326")


def clip_zones_outside_lake(
    zones_gdf: gpd.GeoDataFrame, lake_gdf: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Drop the part of each zone that falls inside the lake.

    Land outside the lake stays, including islands that are holes in the lake
    polygon. Attributes stay on the zone. A zone that was only water is removed.
    """
    if zones_gdf.empty:
        return zones_gdf
    if lake_gdf.empty or lake_gdf.geometry.isna().all():
        raise RuntimeError("Lake Ontario has no polygon to clip against.")

    zones_m = zones_gdf.to_crs(SHORELINE_CRS).copy()
    water = _as_polygons(lake_gdf.to_crs(SHORELINE_CRS).union_all())
    if water is None:
        raise RuntimeError("Lake Ontario has no polygon to clip against.")
    zones_m["geometry"] = zones_m.geometry.difference(water).map(_as_polygons)
    zones_m = zones_m[zones_m.geometry.notna()].reset_index(drop=True)
    return zones_m.to_crs(epsg=4326)


def plot_theft_rates(
    rates_gdf: gpd.GeoDataFrame,
    out_path: Path,
    min_bike_trips: int = 100,
    n_quantiles: int = 5,
) -> None:
    """Plot a quantile-colored choropleth of theft_per_1000_trips by zone and save as PNG.

    Zones with fewer than `min_bike_trips` estimated bike trips are greyed out (the rate is too
    noisy to be meaningful).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    gdf = rates_gdf.copy()
    gdf["masked"] = gdf["bike_trips"] < min_bike_trips
    proj = gdf.to_crs(epsg=3857)
    low = proj[proj["masked"]].copy()
    main = proj[~proj["masked"]].copy()
    main["plot_rate_num"] = pd.to_numeric(main["theft_per_1000_trips"], errors="coerce")
    vals = main["plot_rate_num"].dropna()

    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm

    cmap = plt.cm.Reds
    if len(vals) > 0 and vals.max() > 0:
        breaks = np.unique(np.nanpercentile(vals, np.linspace(0, 100, n_quantiles + 1)))
        norm = (
            BoundaryNorm(breaks, ncolors=cmap.N, clip=True)
            if len(breaks) > 1
            else plt.Normalize(vmin=vals.min(), vmax=vals.max())
        )
    else:
        norm = None

    fig, ax = plt.subplots(figsize=(10, 10))
    if len(low) > 0:
        low.plot(ax=ax, color="#efefef", edgecolor="#cccccc", linewidth=0.2, alpha=0.7)
    if len(main) > 0:
        plot_kwargs = {"norm": norm} if norm is not None else {}
        main.plot(
            column="plot_rate_num", ax=ax, cmap=cmap, linewidth=0.3, edgecolor="white",
            **plot_kwargs,
        )

    if norm is not None:
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax, fraction=0.036, pad=0.04)
        cbar.set_label("Est. thefts per 1000 bike trips, typical day (quantiles)")

    plt.title("Estimated bicycle theft rate per 1000 bike trips")
    plt.axis("off")
    plt.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
