"""Bicycle-theft rate analysis by City of Toronto neighbourhood.

Functions:
- load_thefts_gdf
- load_tts_zones
- detect_tts_weight_col
- assign_thefts_to_neighbourhoods
- filter_to_complete_years
- aggregate_theft_rates
- plot_theft_rates

Zones are the City's 158 official neighbourhoods (see
`bikespace_data.resources.toronto_boundaries.get_neighbourhoods_gdf`) rather than
computed Voronoi cells: neighbourhoods are already a disjoint, full-city partition
that a reader can recognize by name, so no clipping/sliver-removal/merging step is
needed to make the zones legible.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

AREA_CRS = "EPSG:3857"


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
    1. Compute bike_trips_est = TTS2022 * mode_bike (percent or proportion) if both columns exist
    2. Use one of: TTS2022, TTS, trips, bike_trips, TRIPS
    3. Return None if no usable column found (callers should treat every zone as equally weighted)
    """
    if "TTS2022" in tts.columns and "mode_bike" in tts.columns:
        mb = pd.to_numeric(tts["mode_bike"], errors="coerce").fillna(0)
        prop = mb / 100.0 if mb.max() > 1.5 else mb
        tts = tts.copy()
        tts["bike_trips_est"] = tts["TTS2022"] * prop
        return "bike_trips_est", tts

    for col in ("TTS2022", "TTS", "trips", "bike_trips", "TRIPS"):
        if col in tts.columns and pd.api.types.is_numeric_dtype(tts[col]):
            return col, tts

    return None, tts


def assign_thefts_to_neighbourhoods(
    thefts_gdf: gpd.GeoDataFrame, neighbourhoods_gdf: gpd.GeoDataFrame
) -> pd.Series:
    """Assign each theft point to the neighbourhood it falls within, with a nearest-neighbourhood
    fallback for points that miss every polygon (e.g. a point that lands just outside a boundary
    edge due to geocoding noise).

    Returns a Series indexed by neighbourhood_number containing theft counts.
    """
    if thefts_gdf.crs != neighbourhoods_gdf.crs:
        thefts_gdf = thefts_gdf.to_crs(neighbourhoods_gdf.crs)

    zones = neighbourhoods_gdf[["neighbourhood_number", "geometry"]]
    joined = gpd.sjoin(thefts_gdf, zones, predicate="within", how="left").drop(
        columns=["index_right"]
    )

    missing = joined[joined["neighbourhood_number"].isna()]
    if len(missing) > 0:
        missing_proj = missing.to_crs(AREA_CRS).drop(columns=["neighbourhood_number"])
        zones_proj = zones.to_crs(AREA_CRS)
        nearest = gpd.sjoin_nearest(missing_proj, zones_proj, how="left").drop(
            columns=["index_right"], errors="ignore"
        )
        joined.loc[nearest.index, "neighbourhood_number"] = nearest[
            "neighbourhood_number"
        ].values

    return joined.groupby("neighbourhood_number").size().rename("theft_count")


def _apportion_by_area(
    source_gdf: gpd.GeoDataFrame,
    weight_col: str,
    neighbourhoods_gdf: gpd.GeoDataFrame,
) -> pd.Series:
    """Split each source_gdf row's weight_col value across the neighbourhoods it overlaps,
    in proportion to the share of that row's area falling in each neighbourhood.

    This avoids double-counting a value into every neighbourhood a source polygon merely
    touches (which a plain `intersects()` sum would do).
    """
    src_proj = source_gdf.to_crs(AREA_CRS).reset_index(drop=True)
    src_proj["_source_id"] = src_proj.index
    src_proj["_source_area"] = src_proj.geometry.area
    src_proj = src_proj[src_proj["_source_area"] > 0]

    zones_proj = neighbourhoods_gdf[["neighbourhood_number", "geometry"]].to_crs(AREA_CRS)

    overlay = gpd.overlay(
        src_proj[["_source_id", "_source_area", weight_col, "geometry"]],
        zones_proj,
        how="intersection",
        keep_geom_type=False,
    )
    if len(overlay) == 0:
        return pd.Series(dtype=float, name="bike_trips")

    overlay["_piece_area"] = overlay.geometry.area
    overlay["_weight_share"] = overlay[weight_col] * (
        overlay["_piece_area"] / overlay["_source_area"]
    )
    return overlay.groupby("neighbourhood_number")["_weight_share"].sum().rename("bike_trips")


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
    neighbourhoods_gdf: gpd.GeoDataFrame,
    thefts_gdf: gpd.GeoDataFrame,
    tts_zones_gdf: gpd.GeoDataFrame,
    tts_weight_col: Optional[str] = None,
    year_col: str = "OCC_YEAR",
) -> gpd.GeoDataFrame:
    """Aggregate theft counts and TTS bike-trip estimates by neighbourhood and compute a theft
    rate per 1000 bike trips.

    `bike_trips` is a TTS estimate for a single typical day, but `thefts_gdf` is normally a
    cumulative, multi-year record — comparing those directly would be off by orders of
    magnitude. When `year_col` is available, thefts are first annualized using only "complete"
    years (see `filter_to_complete_years`) and converted to a per-day estimate before computing
    the rate, so both sides of the ratio are on the same time scale. If `year_col` isn't usable,
    falls back to the raw theft count (the resulting rate should then be treated as a rough,
    same-scale comparison across neighbourhoods rather than a literal daily rate).

    `neighbourhoods_gdf` must have a `neighbourhood_number` column (see
    `get_neighbourhoods_gdf`). If `tts_zones_gdf` has no usable weight column, every zone is
    counted as weight 1 (i.e. `bike_trips` becomes a proxy for TTS zone coverage rather than an
    actual trip estimate).
    """
    th_counts = assign_thefts_to_neighbourhoods(thefts_gdf, neighbourhoods_gdf)

    complete_thefts, num_years = filter_to_complete_years(thefts_gdf, year_col=year_col)
    if num_years > 0:
        annual_thefts = assign_thefts_to_neighbourhoods(complete_thefts, neighbourhoods_gdf) / num_years
        daily_thefts = (annual_thefts / 365).rename("daily_theft_estimate")
    else:
        daily_thefts = th_counts.astype(float).rename("daily_theft_estimate")

    if isinstance(tts_zones_gdf, gpd.GeoDataFrame) and not tts_zones_gdf.empty:
        tts = tts_zones_gdf.copy()
        if not tts_weight_col or tts_weight_col not in tts.columns:
            tts_weight_col = "_zone_weight"
            tts[tts_weight_col] = 1.0
        usage = _apportion_by_area(tts, tts_weight_col, neighbourhoods_gdf)
    else:
        usage = pd.Series(dtype=float, name="bike_trips")

    result = neighbourhoods_gdf.merge(
        th_counts, left_on="neighbourhood_number", right_index=True, how="left"
    )
    result = result.merge(
        daily_thefts, left_on="neighbourhood_number", right_index=True, how="left"
    )
    result = result.merge(usage, left_on="neighbourhood_number", right_index=True, how="left")
    result["theft_count"] = result["theft_count"].fillna(0).astype(int)
    result["daily_theft_estimate"] = result["daily_theft_estimate"].fillna(0)
    result["bike_trips"] = result["bike_trips"].fillna(0)
    result["theft_years_of_data"] = num_years
    result["theft_per_1000_trips"] = (
        result["daily_theft_estimate"] / result["bike_trips"].replace({0: pd.NA})
    ) * 1000
    return result


def plot_theft_rates(
    rates_gdf: gpd.GeoDataFrame,
    out_path: Path,
    min_bike_trips: int = 10,
    n_quantiles: int = 5,
    top_n_labels: int = 5,
) -> None:
    """Plot a quantile-colored choropleth of theft_per_1000_trips by neighbourhood and save as PNG.

    Neighbourhoods with fewer than `min_bike_trips` estimated bike trips are greyed out (the rate
    is too noisy to be meaningful), and the `top_n_labels` highest-rate neighbourhoods are labeled
    by name so a reader can immediately see which places are worst, not just how dark they are.
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

    import matplotlib.patheffects as path_effects

    top_zones = main.dropna(subset=["plot_rate_num"]).nlargest(top_n_labels, "plot_rate_num")
    for _, row in top_zones.iterrows():
        centroid = row.geometry.centroid
        ax.annotate(
            row["neighbourhood_name"],
            xy=(centroid.x, centroid.y),
            fontsize=7,
            fontweight="bold",
            ha="center",
            color="white",
            path_effects=[path_effects.withStroke(linewidth=2.5, foreground="black")],
        )

    plt.title("Estimated bicycle theft rate per 1000 bike trips by neighbourhood")
    plt.axis("off")
    plt.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
