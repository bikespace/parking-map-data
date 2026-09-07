from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from bikespace_data.resources.toronto_open_data import request_tod_gdf
from bikespace_data.utilities import StatusManager, save_geo_output

# This script fetches bike stolen report then process ETL to generate a GeoJSON file for the BikeSpace app.
# The data is sourced from the Toronto Open Data Portal.
# Run command: python -m bikespace_data.bike_thefts.update_bike_thefts

# Database and resource name
DATASET_NAME = "bicycle-thefts"
RESOURCE_ID = "e7fe6133-17d8-4a39-88af-352440dec684"

# File Paths for output and source files
OUTPUT_DIR = Path("bikespace_data/bike_thefts")
OUTPUT_FILE = "stolen_bike_reports.geojson"
OUTPUT_SOURCE_FILE = "source_files/bicycle-thefts_raw.geojson"

# Status file path and source URL
STATUS_PATH = OUTPUT_DIR / "statuses" / "bike_thefts_status.csv"
STATUS_SOURCE = (
    "https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/"
    "data/bike_thefts/statuses/bike_thefts_status.csv"
)

BIKE_TYPE_MAP = {
    "RC": "Road bike",
    "RG": "Regular bike",
    "MT": "Mountain bike",
    "BM": "BMX",
    "EL": "Electric bike",
    "FO": "Folding bike",
    "SC": "Scooter",
    "TO": "Touring bike",
    "TR": "Tricycle",
    "UN": "Unicycle",
    "OT": "Other",
}
COLOR_MAP = {
    "BLK": "Black",
    "WHI": "White",
    "RED": "Red",
    "BLU": "Blue",
    "GRN": "Green",
    "YEL": "Yellow",
    "ONG": "Orange",
    "PUR": "Purple",
    "GRY": "Grey",
    "SIL": "Silver",
    "GLD": "Gold",
    "BRN": "Brown",
    "BGE": "Beige",
    "PNK": "Pink",
    "MRN": "Maroon",
    "TAN": "Tan",
    "SILRED": "Silver/Red",
    "BLKRED": "Black/Red",
    "BLKWHI": "Black/White",
    "BLUBLU": "Blue",
}
STATUS_MAP = {
    "STOLEN": "stolen",
    "RECOVERED": "recovered",
    "UNKNOWN": "unknown",
}
LOCATION_TYPE_MAP = {
    "OUTSIDE": "Outside",
    "OTHER": "Other",
    "HOUSE": "House",
    "TRANSIT": "Transit",
    "EDUCATIONAL": "Educational",
}

EXCLUDED_PREMISES = {"APARTMENT", "COMMERCIAL"}

# Function to map bike colors
def normalize_color(raw_color) -> str:
    # Return "Unknown" if the color is None, NaN, or "none"
    if pd.isna(raw_color) or str(raw_color).strip().lower() == "none":
        return "Unknown"
    upper = str(raw_color).strip().upper()
    return COLOR_MAP.get(upper, str(raw_color).strip().title())

# Function to map stolen location
def normalize_location(raw_location) -> str:
    if raw_location is None or pd.isna(raw_location) or str(raw_location).strip().lower() == "none":
        return "Unknown location"
    return LOCATION_TYPE_MAP.get(str(raw_location).strip().upper(), str(raw_location).strip().title())



def normalize_bike_type(raw_type) -> str:
    if raw_type is None or pd.isna(raw_type) or str(raw_type).strip().lower() == "none":
        return "Unknown"
    return BIKE_TYPE_MAP.get(str(raw_type).strip().upper(), str(raw_type).strip().title())

# Note: Passing file paths for flexibility in testing evi.
# Main function to fetch, process, and save bike theft data
def main(
    output_dir: Path = OUTPUT_DIR,
    output_file: str = OUTPUT_FILE,
    output_source_file: str = OUTPUT_SOURCE_FILE,
    status_path: Path = STATUS_PATH,
    status_source: str = STATUS_SOURCE,
) -> None:
    
    # Display information about the data fetching process
    print("Starting the bike theft data update process...")
    print(f"Dataset: {DATASET_NAME}, Resource ID: {RESOURCE_ID}")
    print(f"Output directory: {output_dir}, Output file: {output_file}")
    print(f"Source file: {output_source_file}, Status path: {status_path}")
    print("Fetching bike theft data from Toronto Open Data Portal...")

    # Update the status manager with the source and save paths
    status_manager = StatusManager(
        status_source=status_source,
        status_save=status_path,
    )
        
    result = request_tod_gdf(DATASET_NAME, RESOURCE_ID)
    
    # Check if the data has been updated since the last fetch
    portal_last_modified = datetime.fromisoformat(
        result["metadata"]["last_modified"]
    ).replace(tzinfo=timezone.utc)
    
    # Get last update 
    status_last_modified = status_manager.last_updated(
        dataset_name="bike-thefts"
    )
    print(f"Portal last modified: {portal_last_modified}")
    print(f"Status last modified: {status_last_modified}")
    print(f"Status path: {status_path}")
    if (
        status_last_modified is not None
        and portal_last_modified <= status_last_modified
    ):
        print("Bike theft data has not been updated; exiting.")
        return

    gdf = result["gdf"]
    
    # Save a raw dataset in the sources_file for reference
    save_geo_output(gdf, path=output_dir, file_name=output_source_file)

    # Filter out excluded premises
    gdf = gdf[~gdf["PREMISES_TYPE"].str.upper().isin(EXCLUDED_PREMISES)].copy()

    # Normalize columns
    gdf["location"] = gdf["PREMISES_TYPE"].apply(normalize_location)
    gdf["bikeType"] = gdf["BIKE_TYPE"].apply(normalize_bike_type)
    gdf["color"] = gdf["BIKE_COLOUR"].apply(normalize_color)
    gdf["status"] = gdf["STATUS"].apply(
        lambda x: STATUS_MAP.get(str(x).strip().upper(), "unknown")
    )
    gdf["date"] = gdf["OCC_DATE"].astype(str).str[:10]
    
    # Save only normalized columns to the final output
    output_gdf = gdf[["location", "bikeType", "color", "status", "date", "geometry"]].copy()
    
    # Save in GeoJSON format after normalization
    save_geo_output(output_gdf, path=output_dir, file_name=output_file)
    
    # Update status manager with last updated timestamp and number of features
    status_manager.add(
        dataset_name="bike-thefts",
        last_updated=portal_last_modified,
        num_features=len(gdf),
        last_checked=datetime.now(timezone.utc),
    )
    # Save the status manager to persist the status information
    status_manager.save()
    print(f"Saved {len(gdf)} records → {output_dir / output_file}")


if __name__ == "__main__":
    main()