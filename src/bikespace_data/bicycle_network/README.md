# City of Toronto Bicycle Network

Simplified version of the [City of Toronto bicycle network dataset](https://open.toronto.ca/dataset/cycling-network/), keeping only the columns relevant for use on bikespace.ca.

See [documentation in the data branch](https://github.com/bikespace/parking-map-data/blob/data/bicycle_network/README.md) for additional details.

The main output file used by the BikeSpace bicycle parking map is `cycling-network-display.geojson`.


## How to run

This project uses [uv](https://github.com/astral-sh/uv) to run the python script and keep dependencies organized.

```bash
# main script to update data
$ uv run src/bikespace_data/apartments/update_cycling_network.py

# global run tests
uv run pytest

# run tests and calculate coverage for apartments folder only
uv run pytest src/bikespace_data/bicycle_network --cov-reset --cov=src/bikespace_data/bicycle_network

# run specific test file
$ uv run pytest PATH_TO_TEST_FILE
```