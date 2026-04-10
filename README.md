# BikeSpace Project Data for Toronto Bicycle Parking and Other Sources

This repository holds and runs scripts to provide data used by the BikeSpace project, including a clean and up to date dataset of bicycle parking locations in Toronto and the city bicycle network. The data is used for the BikeSpace parking map available at [bikespace.ca/parking-map](https://bikespace.ca/parking-map).

## [View the Data](https://github.com/bikespace/parking-map-data/tree/data)

The output data files and data documentation for this repository can be [viewed in the data branch](https://github.com/bikespace/parking-map-data/tree/data).

## Bicycle Parking Data

The scripts in `src/../bicycle_parking` download, filter, and transform data from two major sources: City of Toronto Open Data and OpenStreetMap. The goal of the script is to provide a clean and uniform data set of bicycle parking locations in Toronto.

See the [bicycle parking data README](https://github.com/bikespace/parking-map-data/blob/data/bicycle_parking/README.md) for more details.


### Development

You will need [uv installed](https://docs.astral.sh/uv/getting-started/installation/) to run the scripts.

Each dataset has a folder of scripts in `src/bikespace_data/` and a main script usually named `update_DATASET_NAME.py`. Dataset-specific tests are kept within each dataset folder, and tests for shared code are kept in `src/bikespace_data/tests/`.

Other `src/bikespace_data/` folders are as follows:

- `resources/` for helper code to fetch data from external services (e.g. City of Toronto Open Data Portal)
- `utilities` for other tools used by multiple datasets, e.g. StatusManager and helper functions for working with GeoDataFrames.

The scripts are run on a schedule using the workflows in `.github/workflows`. The general flow is that the scripts will generate updated data files and then commit them to the `data` branch. This keeps a clear separation between production code (`main`) and the data outputs (`data`).

How to run tests (options are pre-configured in pyproject.toml):
```bash
# run all tests
$ uv run pytest

# show print output
$ uv run pytest -s

# run long-running tests
$ uv run pytest -m long -s
```

Contributions to the `main` branch should be made via pull request and squash merged into `main` once an approving review has been given.
