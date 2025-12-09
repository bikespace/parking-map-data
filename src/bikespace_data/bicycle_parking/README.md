# Bicycle Parking Data

These scripts download, filter, and transform data from two major sources: City of Toronto Open Data and OpenStreetMap. The goal of the script is to provide a clean and uniform data set of bicycle parking locations in Toronto.

See [documentation in the `data` branch](https://github.com/bikespace/parking-map-data/blob/data/bicycle_parking/README.md) for additional details.


## How to Run

This project uses [uv](https://github.com/astral-sh/uv) to run the python script and keep dependencies organized.

```bash
# main script to update data
$ uv run src/bikespace_data/bicycle_parking/update_bicycle_parking.py

# global run tests
uv run pytest

# run tests and calculate coverage for bicycle_parking folder only
uv run pytest src/bikespace_data/bicycle_parking --cov-reset --cov=src/bikespace_data/bicycle_parking

# run specific test file
$ uv run pytest PATH_TO_TEST_FILE
```

Output folders are as follows:

* `source_files`: data received from the original source before any upstream filtering or transformation
* `output_files`: data after upstream filtering and transformation
* `display_files`: final data after downstream filtering and transformation
