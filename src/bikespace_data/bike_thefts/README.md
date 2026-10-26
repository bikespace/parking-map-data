# Bike Theft Data

These scripts download, filter, and transform bicycle theft reports from the [Toronto Police ArcGIS service](https://services.arcgis.com/S9th0jAJ7bqgIRjw/arcgis/rest/services/Bicycle_Thefts_Open_Data/FeatureServer/0). The goal is to provide a clean and uniform data set of reported bicycle thefts in Toronto.

See [documentation in the `data` branch](https://github.com/bikespace/parking-map-data/blob/data/bike_thefts/README.md) for additional details.

## How to Run

This project uses [uv](https://github.com/astral-sh/uv) to run the Python script and keep dependencies organized.

```bash
# main script to update data
$ uv run python -m bikespace_data.bike_thefts.update_bike_thefts

# run all tests
$ uv run pytest

# run tests and calculate coverage for the bike_thefts folder only
$ uv run pytest src/bikespace_data/bike_thefts --cov-reset --cov=src/bikespace_data/bike_thefts

# run a specific test file
$ uv run pytest PATH_TO_TEST_FILE
```

Output folders are as follows:

* `source_files`: data received from the original source before filtering or transformation
* `stolen_bike_reports.geojson`: filtered and transformed bicycle theft data used by the application
* `statuses`: status metadata for the update process

The fetch uses `LAYER_URL` for metadata and its `/query` path for paginated GeoJSON downloads of all reports. ArcGIS object IDs and millisecond dates are normalized to the existing output schema, geometry is requested in EPSG:4326, and the layer’s last edit timestamp is used to skip unchanged data.
