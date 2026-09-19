# Bike Theft Data

These scripts download, filter, and transform bicycle theft reports from the City of Toronto Open Data Portal. The goal is to provide a clean and uniform data set of reported bicycle thefts in Toronto.

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
* `stolen_bike_reports_raw.geojson`: filtered and transformed bicycle theft data used by the application
* `statuses`: status metadata for the update process
