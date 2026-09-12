"""
Bicycle-theft rate by neighbourhood
====================================

Joins Toronto bicycle-theft locations to the City's 158 official neighbourhoods, joins
TTS bike-usage zone data, computes theft rates per 1000 bike trips, and saves output
and display GeoJSON files (plus a diagnostic PNG heat-map) alongside the rest of the
bicycle_theft dataset outputs, so the results are picked up by the `data` branch the
same way as every other dataset in this repo.

Usage (from project root):
    python -m bikespace_data.bicycle_theft.run_theft_rate_zones [options]

    # or update thefts first, then run
    python -m bikespace_data.bicycle_theft.run_theft_rate_zones --update-thefts

Options:
    --thefts PATH         Path to the normalized thefts GeoJSON
                          (default: bicycle_theft/output_files/bicycle-thefts-normalized.geojson)
    --tts-source URL|PATH GeoJSON or CSV source for TTS zones
                          (default: School-of-Cities GitHub tts2022zones_data.geojson)
    --output-dir DIR      Directory for the full output GeoJSON + PNG (default: bicycle_theft/output_files)
    --display-dir DIR     Directory for the slim display GeoJSON (default: bicycle_theft/display_files)
    --min-bike-trips N    Neighbourhoods with fewer estimated bike trips than this are masked
                          on the plot as too noisy to rate (default 10)
    --update-thefts       Run update_bicycle_thefts() before the analysis
    --no-archive          Disable parquet archives when --update-thefts is used
"""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd

from bikespace_data.bicycle_theft.theft_rate_zones import (
    aggregate_theft_rates,
    detect_tts_weight_col,
    load_thefts_gdf,
    load_tts_zones,
    plot_theft_rates,
)
from bikespace_data.resources.toronto_boundaries import get_neighbourhoods_gdf
from bikespace_data.utilities import save_geo_output

TTS_DEFAULT_SOURCE = (
    "https://raw.githubusercontent.com/schoolofcities/"
    "transportation-tomorrow-survey/main/data/tts2022zones_data.geojson"
)
THEFTS_DEFAULT = Path("bicycle_theft/output_files/bicycle-thefts-normalized.geojson")
OUTPUT_DEFAULT = Path("bicycle_theft/output_files")
DISPLAY_DEFAULT = Path("bicycle_theft/display_files")
MIN_BIKE_TRIPS_DEFAULT = 10

OUTPUT_FILE_NAME = "theft-rate-by-neighbourhood.geojson"
DISPLAY_FILE_NAME = "theft-rate-by-neighbourhood-display.geojson"
PLOT_FILE_NAME = "theft-rate-by-neighbourhood.png"

DISPLAY_COLUMNS = [
    "neighbourhood_number",
    "neighbourhood_name",
    "theft_count",
    "theft_years_of_data",
    "daily_theft_estimate",
    "bike_trips",
    "theft_per_1000_trips",
    "geometry",
]


def generate_theft_rate_zones(
    thefts_path: Path = THEFTS_DEFAULT,
    tts_source: str = TTS_DEFAULT_SOURCE,
    output_dir: Path = OUTPUT_DEFAULT,
    display_dir: Path = DISPLAY_DEFAULT,
    min_bike_trips: int = MIN_BIKE_TRIPS_DEFAULT,
    update_thefts: bool = False,
    no_archive: bool = False,
) -> gpd.GeoDataFrame:
    """Run the full neighbourhood theft-rate analysis and return the aggregated GeoDataFrame."""

    if update_thefts:
        from bikespace_data.bicycle_theft.update_bicycle_theft import update_bicycle_thefts

        update_bicycle_thefts(archive=not no_archive)

    print(f"\nLoading thefts from {thefts_path} …")
    th_gdf = load_thefts_gdf(thefts_path)
    print(f"  {len(th_gdf)} theft points after cleaning")
    if len(th_gdf) == 0:
        raise RuntimeError("No theft points loaded — check the thefts path and file contents.")

    print("\nLoading Toronto neighbourhoods …")
    neighbourhoods = get_neighbourhoods_gdf()
    print(f"  {len(neighbourhoods)} neighbourhoods")

    print(f"\nLoading TTS zones from {tts_source} …")
    try:
        tts = load_tts_zones(tts_source)
        print(f"  {len(tts)} TTS zones, CRS={tts.crs}")
    except Exception as e:
        print(f"  Warning: could not load TTS source: {e}")
        tts = gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:4326")

    tts_weight_col = None
    if len(tts) > 0:
        tts_weight_col, tts = detect_tts_weight_col(tts)
        if tts_weight_col:
            print(f"  Using TTS weight column: {tts_weight_col}")
        else:
            print("  No numeric weight column found in TTS zones; counting zone coverage instead")

    print("\nAggregating theft counts and TTS bike trips by neighbourhood …")
    rates = aggregate_theft_rates(neighbourhoods, th_gdf, tts, tts_weight_col=tts_weight_col)
    nonzero_theft = (rates["theft_count"] > 0).sum()
    nonzero_trips = (rates["bike_trips"] > 0).sum()
    years_of_data = rates["theft_years_of_data"].iloc[0] if len(rates) > 0 else 0
    print(
        f"  Neighbourhoods with theft_count > 0: {nonzero_theft}, "
        f"with bike_trips > 0: {nonzero_trips}"
    )
    if years_of_data > 0:
        print(
            f"  Annualized thefts using {years_of_data} complete year(s) of data, "
            f"then converted to a per-day estimate to match bike_trips' typical-day scale"
        )
    else:
        print(
            "  Warning: could not determine complete years of theft data — theft_per_1000_trips "
            "is a raw, unscaled comparison and may not reflect a real daily rate"
        )
    print(
        f"  Total thefts (all-time): {int(rates['theft_count'].sum())}, "
        f"total bike_trips (typical day): {rates['bike_trips'].sum():,.0f}"
    )

    print(f"\nSaving outputs to {output_dir} and {display_dir} …")
    save_geo_output(rates, path=output_dir, file_name=OUTPUT_FILE_NAME, na="null")
    save_geo_output(
        rates[DISPLAY_COLUMNS], path=display_dir, file_name=DISPLAY_FILE_NAME, na="null"
    )
    plot_theft_rates(rates, output_dir / PLOT_FILE_NAME, min_bike_trips=min_bike_trips)
    print("Done.")

    return rates


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bicycle-theft rate by Toronto neighbourhood",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--thefts",
        default=str(THEFTS_DEFAULT),
        help=f"Path to normalized thefts GeoJSON (default: {THEFTS_DEFAULT})",
    )
    parser.add_argument(
        "--tts-source",
        default=TTS_DEFAULT_SOURCE,
        help="URL or path to TTS zones GeoJSON/CSV",
    )
    parser.add_argument(
        "--output-dir",
        default=str(OUTPUT_DEFAULT),
        help=f"Directory to write the full output GeoJSON + PNG (default: {OUTPUT_DEFAULT})",
    )
    parser.add_argument(
        "--display-dir",
        default=str(DISPLAY_DEFAULT),
        help=f"Directory to write the slim display GeoJSON (default: {DISPLAY_DEFAULT})",
    )
    parser.add_argument(
        "--min-bike-trips",
        type=int,
        default=MIN_BIKE_TRIPS_DEFAULT,
        help=f"Mask neighbourhoods with fewer estimated bike trips than this (default {MIN_BIKE_TRIPS_DEFAULT})",
    )
    parser.add_argument(
        "--update-thefts",
        action="store_true",
        help="Run update_bicycle_thefts() to refresh the source data before analysis",
    )
    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Disable parquet archives when --update-thefts is used",
    )
    args = parser.parse_args()

    generate_theft_rate_zones(
        thefts_path=Path(args.thefts),
        tts_source=args.tts_source,
        output_dir=Path(args.output_dir),
        display_dir=Path(args.display_dir),
        min_bike_trips=args.min_bike_trips,
        update_thefts=args.update_thefts,
        no_archive=args.no_archive,
    )


if __name__ == "__main__":
    main()
