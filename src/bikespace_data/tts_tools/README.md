## tts_tools: Data Utilities for the Transportation Tomorrow Survey

Purpose: simplify using exports from the Transportation Tomorrow Survey data portal.

The API should enable:

- Load an export txt file
- Provide a pandas dataframe of the data
- Provide a geopandas geodataframe of the data with the geometries automatically added
- Provide a metadata record

## Dev

```sh
# run pytest
uv run pytest src/bikespace_data/tts_tools --cov-reset --cov=src/bikespace_data/tts_tools
```

## Options Covered

Output Type:

- [x] Cross Tabulation
- [ ] Record Count
- [ ] Frequency Distribution

Metric:

- [ ] Household
- [ ] Person
- [x] Trip
- [ ] Transit

Year:

- [ ] 1986
- [ ] 1991
- [ ] 1996
- [ ] 2001
- [ ] 2006
- [ ] 2011
- [ ] 2016
- [x] 2022

Cross Tabulation Features

- [x] Row and Column Attributes
- [ ] Row, Column, AND Table Attributes
- [ ] Row, Column, and Table groupings
- [ ] Filters
- [x] Comma-defined table output
- [ ] Column format output
- [ ] Expansion factor on or off (this one is tricky)
