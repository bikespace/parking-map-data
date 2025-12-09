# Bicycle Parking in Apartments

Cleaned dataset of apartment buildings in the City of Toronto and the amount of bicycle parking available at each building as self-reported via the RentSafeTO program. 

The script also calculates the amount of bicycle parking that would be required under the current zoning by-law and how the actual amount of bicycle parking compares.

See [documentation in the `data` branch](https://github.com/bikespace/parking-map-data/blob/data/apartments/README.md) for additional details and a data dictionary.


## How to run

This project uses [uv](https://github.com/astral-sh/uv) to run the python script and keep dependencies organized.

```bash
# main script to update data
$ uv run src/bikespace_data/apartments/update_apartments.py

# global run tests
uv run pytest

# run tests and calculate coverage for apartments folder only
uv run pytest src/bikespace_data/apartments --cov-reset --cov=src/bikespace_data/apartments

# run specific test file
$ uv run pytest PATH_TO_TEST_FILE
```


Output folders are as follows:

* `source_files`: data received from the original source before any filtering or transformation
* `output_files`: full data after filtering and transformation
* `display_files`: data used for BikeSpace web app (only contains necessary columns)
* `address_cache`: store of addresses previously looked up to determine their location