"""
Bicycle-theft rate by zone
==========================

Splits Toronto into trip-balanced zones (Voronoi cells in Manhattan distance on the street grid,
see manhattan_zones.py), joins bicycle-theft locations and TTS bike-usage zone data to them,
computes theft rates per 1000 bike trips, and saves output
and display GeoJSON files (plus a diagnostic PNG heat-map) alongside the rest of the
bicycle_theft dataset outputs, so the results are picked up by the `data` branch the
same way as every other dataset in this repo.

Usage (from project root):
    python -m bikespace_data.bicycle_theft.run_theft_rate_zones [options]

Options:
    --thefts URL|PATH     Toronto Police bicycle-theft GeoJSON with an OCC_YEAR column
                          (default: the raw download that the bike_thefts update job publishes
                          on the `data` branch, so the data is only downloaded once)
    --tts-source URL|PATH GeoJSON or CSV source for TTS zones
                          (default: School-of-Cities GitHub tts2022zones_data.geojson)
    --output-dir DIR      Directory for the full output GeoJSON + PNG (default: bicycle_theft/output_files)
    --display-dir DIR     Directory for the slim display GeoJSON (default: bicycle_theft/display_files)
    --n-zones N           Number of zones to split the city into (default 400)
    --min-bike-trips N    Zones with fewer estimated bike trips than this are masked
                          on the plot as too noisy to rate (default 100)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd

from bikespace_data.bicycle_theft.manhattan_zones import (
    DEFAULT_N_ZONES,
    build_manhattan_zones,
)
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
THEFTS_DEFAULT = (
    "https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/"
    "data/bike_thefts/source_files/bicycle-thefts_raw.geojson"
)
OUTPUT_DEFAULT = Path("bicycle_theft/output_files")
DISPLAY_DEFAULT = Path("bicycle_theft/display_files")
MIN_BIKE_TRIPS_DEFAULT = 100

OUTPUT_FILE_NAME = "theft-rate-zones.geojson"
DISPLAY_FILE_NAME = "theft-rate-zones-display.geojson"
PLOT_FILE_NAME = "theft-rate-zones.png"

DISPLAY_COLUMNS = [
    "zone_id",
    "theft_count",
    "theft_years_of_data",
    "daily_theft_estimate",
    "bike_trips",
    "theft_per_1000_trips",
    "geometry",
]


def generate_theft_rate_zones(
    thefts_path: Path | str = THEFTS_DEFAULT,
    tts_source: str = TTS_DEFAULT_SOURCE,
    output_dir: Path = OUTPUT_DEFAULT,
    display_dir: Path = DISPLAY_DEFAULT,
    min_bike_trips: int = MIN_BIKE_TRIPS_DEFAULT,
    n_zones: int = DEFAULT_N_ZONES,
) -> gpd.GeoDataFrame:
    """Run the full theft-rate-by-zone analysis and return the aggregated GeoDataFrame."""

    print(f"\nLoading thefts from {thefts_path} …")
    th_gdf = load_thefts_gdf(thefts_path)
    print(f"  {len(th_gdf)} theft points after cleaning")
    if len(th_gdf) == 0:
        raise RuntimeError("No theft points loaded — check the thefts path and file contents.")

    print("\nLoading Toronto city outline …")
    city = get_neighbourhoods_gdf()

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

    print(f"\nBuilding {n_zones} trip-balanced Manhattan zones …")
    zones = build_manhattan_zones(city, tts, tts_weight_col, n_zones=n_zones)
    print(f"  {len(zones)} zones")

    print("\nAggregating theft counts and TTS bike trips by zone …")
    rates = aggregate_theft_rates(zones, th_gdf, tts, tts_weight_col=tts_weight_col)
    nonzero_theft = (rates["theft_count"] > 0).sum()
    nonzero_trips = (rates["bike_trips"] > 0).sum()
    years_of_data = rates["theft_years_of_data"].iloc[0] if len(rates) > 0 else 0
    print(
        f"  Zones with theft_count > 0: {nonzero_theft}, "
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
        description="Bicycle-theft rate by trip-balanced zone",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--thefts",
        default=str(THEFTS_DEFAULT),
        help="URL or path to the bicycle-theft GeoJSON (default: the bike_thefts raw download on the data branch)",
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
        help=f"Mask zones with fewer estimated bike trips than this (default {MIN_BIKE_TRIPS_DEFAULT})",
    )
    parser.add_argument(
        "--n-zones",
        type=int,
        default=DEFAULT_N_ZONES,
        help=f"Number of zones to split the city into (default {DEFAULT_N_ZONES})",
    )
    args = parser.parse_args()

    generate_theft_rate_zones(
        thefts_path=args.thefts,
        tts_source=args.tts_source,
        output_dir=Path(args.output_dir),
        display_dir=Path(args.display_dir),
        min_bike_trips=args.min_bike_trips,
        n_zones=args.n_zones,
    )


if __name__ == "__main__":
    main()
