from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from bikespace_data.resources.toronto_open_data import request_tod_gdf
from bikespace_data.utilities import StatusManager, save_geo_output

# This script fetches bike stolen report then process ETL to generate a GeoJSON file for the BikeSpace app.
# The data is sourced from the Toronto Open Data Portal.
# Run command: python -m bikespace_data.bike_thefts.update_bike_thefts


DATASET_NAME = "c7d34d9b-23d2-44fe-8b3b-cd82c8b38978"
RESOURCE_ID = "e7fe6133-17d8-4a39-88af-352440dec684"

OUTPUT_DIR = Path(__file__).parent
OUTPUT_FILE = "stolen_bike_reports.geojson"
STATUS_PATH = OUTPUT_DIR / "statuses" / "bike_thefts_status.csv"
STATUS_SOURCE = (
    "https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/data/"
    "src/bikespace_data/bike_thefts/statuses/bike_thefts_status.csv"
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
    if raw_color is None or pd.isna(raw_color) or str(raw_color).strip().lower() == "none":
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

def main() -> None:
    print("Fetching bike theft data from Toronto Open Data Portal...")
    status_manager = StatusManager(
        status_source=STATUS_SOURCE,
        status_save=STATUS_PATH,
    )
    result = request_tod_gdf(DATASET_NAME, RESOURCE_ID)
    gdf = result["gdf"]

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

    # Save in GeoJSON format
    save_geo_output(gdf, path=OUTPUT_DIR, file_name=OUTPUT_FILE)
    
    # Update status manager with last updated timestamp and number of features
    last_updated = datetime.fromisoformat(result["metadata"]["last_modified"])
    status_manager.add(
        dataset_name="bike-thefts",
        last_updated=last_updated,
        num_features=len(gdf),
        last_checked=datetime.now(timezone.utc),
    )
    # Save the status manager to persist the status information
    status_manager.save()
    print(f"Saved {len(gdf)} records → {OUTPUT_DIR / OUTPUT_FILE}")


if __name__ == "__main__":
    main()