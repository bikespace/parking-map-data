from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import geopandas as gpd
import pandas as pd
import requests
from bikespace_data.utilities import StatusManager, save_geo_output

# This script fetches bike stolen report then process ETL to generate a GeoJSON file for the BikeSpace app.
# The data is sourced from the Toronto Police ArcGIS service.
# Run command: python -m bikespace_data.bike_thefts.update_bike_thefts

# Toronto Police bicycle theft layer
LAYER_URL = (
    "https://services.arcgis.com/S9th0jAJ7bqgIRjw/arcgis/rest/services/"
    "Bicycle_Thefts_Open_Data/FeatureServer/0"
)
# File Paths for output and source files
OUTPUT_DIR = "bike_thefts"
OUTPUT_FILE = "stolen_bike_reports.geojson"
OUTPUT_SOURCE_FILE = "source_files/bicycle-thefts_raw.geojson"

# Status file path and source URL
STATUS_PATH = Path(OUTPUT_DIR) / "statuses" / "bike_thefts_status.csv"
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

def request_arcgis_json(url: str, params: dict) -> dict:
    response = requests.get(url, params=params, timeout=120)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"ArcGIS request failed: {payload['error']}")
    return payload


def fetch_thefts(metadata: dict) -> gpd.GeoDataFrame:
    """Download every layer query page and normalize the source fields."""
    features = []
    page_size = metadata["maxRecordCount"]
    while True:
        page = request_arcgis_json(f"{LAYER_URL}/query", {
            "where": "1=1",
            "outFields": "*",
            "f": "geojson",
            "outSR": 4326,
            "orderByFields": metadata["objectIdField"],
            "resultOffset": len(features),
            "resultRecordCount": page_size,
        })
        batch = page["features"]
        exceeded = page.get("properties", {}).get("exceededTransferLimit", False)
        if not batch:
            if exceeded:
                raise RuntimeError("ArcGIS returned an empty page with more results pending")
            break
        features.extend(batch)
        if not exceeded and len(batch) < page_size:
            break

    if not features:
        raise RuntimeError("ArcGIS returned no bicycle theft reports")
    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    gdf["_id"] = gdf[metadata["objectIdField"]]
    for column in ("OCC_DATE", "REPORT_DATE"):
        gdf[column] = pd.to_datetime(gdf[column], unit="ms", utc=True).dt.strftime(
            "%Y-%m-%dT%H:%M:%S%z"
        )
    return gdf.replace("None", pd.NA).convert_dtypes()


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


def build_location_label(props: Mapping) -> str:
    """Build the user-facing location label from a source record."""
    return normalize_location(props.get("PREMISES_TYPE"))

# Function to build a description of the bike theft without exposing source column names
def build_description(props: Mapping) -> str:
    """Compose a human-readable description from available fields."""
    def present(value) -> bool:
        return (
            value is not None
            and not pd.isna(value)
            and str(value).strip().lower() not in {"", "none", "nan", "<na>"}
        )

    parts = []
    make = props.get("BIKE_MAKE")
    model = props.get("BIKE_MODEL")

    if present(make):
        parts.append(str(make).title())
    if present(model):
        parts.append(str(model).title())

    cost = props.get("BIKE_COST")
    if present(cost):
        try:
            parts.append(f"valued at ${(cost):,.0f}")
        except (TypeError, ValueError):
            parts.append(f"valued at ${cost}")

    speed = props.get("BIKE_SPEED")
    if present(speed) and str(speed).strip() != "0":
        parts.append(f"{speed}-speed")

    location_type = props.get("LOCATION_TYPE")
    if present(location_type):
        parts.append(f"stolen from {str(location_type).lower()}")

    return ", ".join(parts) if parts else "No description available"


# Note: Passing file paths for flexibility in testing evi.
# Main function to fetch, process, and save bike theft data
def main(
    output_dir: str | Path = OUTPUT_DIR,
    output_file: str = OUTPUT_FILE,
    output_source_file: str = OUTPUT_SOURCE_FILE,
    status_path: Path = STATUS_PATH,
    status_source: str = STATUS_SOURCE,
) -> None:
    output_dir = Path(output_dir)
    status_path = Path(status_path)

    # Display information about the data fetching process
    print("Starting the bike theft data update process...")
    print(f"Source: {LAYER_URL}")
    print(f"Output directory: {output_dir}, Output file: {output_file}")
    print(f"Source file: {output_source_file}, Status path: {status_path}")
    print("Fetching bike theft data from Toronto Police ArcGIS...")

    # Update the status manager with the source and save paths
    status_manager = StatusManager(
        status_source=status_source,
        status_save=status_path,
    )
        
    metadata = request_arcgis_json(LAYER_URL, {"f": "json"})
    
    # Check if the data has been updated since the last fetch
    portal_last_modified = datetime.fromtimestamp(
        metadata["editingInfo"]["lastEditDate"] / 1000, tz=timezone.utc
    )
    
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

    # Explode the GeoDataFrame to ensure each geometry is a single feature
    gdf = fetch_thefts(metadata)
    
    # Save a raw dataset in the sources_file for reference
    (output_dir / output_source_file).parent.mkdir(parents=True, exist_ok=True)
    save_geo_output(gdf, path=output_dir, file_name=output_source_file)  
    
    # Save a raw dataset in CSV format for easier analysis and debugging
    csv_path = (output_dir / output_source_file).with_suffix(".csv")
    gdf.drop(columns=["geometry"]).to_csv(csv_path, index=False)
      
    
    # Get only last 5 years thefts data
    dates = pd.to_datetime(gdf["OCC_DATE"], utc=True, errors="coerce")
    today = pd.Timestamp.now(tz="UTC").normalize()
    cutoff = today - pd.DateOffset(years=5)

    gdf = gdf[dates.between(cutoff, today + pd.Timedelta(days=1), inclusive="left")].copy()
    
    
    # Filter out excluded premises
    gdf = gdf[~gdf["PREMISES_TYPE"].str.upper().isin(EXCLUDED_PREMISES)].copy()

    # Normalize columns and create the complete application-facing schema.
    gdf["id"] = gdf["_id"].apply(
        lambda value: "" if pd.isna(value) else str(value)
    )
    gdf["date"] = gdf["OCC_DATE"].astype(str).str[:10]
    gdf["location"] = gdf.apply(build_location_label, axis=1)
    gdf["bikeType"] = gdf["BIKE_TYPE"].apply(normalize_bike_type)
    gdf["color"] = gdf["BIKE_COLOUR"].apply(normalize_color)
    gdf["description"] = gdf.apply(build_description, axis=1)
    gdf["status"] = gdf["STATUS"].apply(
        lambda value: STATUS_MAP.get(str(value).strip().upper(), "unknown")
    )
    gdf["latitude"] = pd.to_numeric(gdf["LAT_WGS84"], errors="coerce")
    gdf["longitude"] = pd.to_numeric(gdf["LONG_WGS84"], errors="coerce")

    output_columns = [
        "id",
        "date",
        "location",
        "bikeType",
        "color",
        "description",
        "status",
        "latitude",
        "longitude",
        "geometry",
    ]
    output_gdf = gdf[output_columns].copy()

    # Save in GeoJSON format after normalization
    save_geo_output(output_gdf, path=output_dir, file_name=output_file)
    
    # Save in CSV format for easier analysis and debugging
    output_csv_file = output_file.replace(".geojson", ".csv")
    output_gdf.to_csv(output_dir / output_csv_file, index=False)

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
