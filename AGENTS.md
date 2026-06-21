# CLAUDE.md

This file provides guidance to AI agents when working with code in this repository.

## Project Overview

This repo generates data for the [BikeSpace](https://bikespace.ca/parking-map) parking map — a map of bicycle parking in Toronto. Scripts download, filter, and transform data from City of Toronto Open Data and OpenStreetMap, then commit results to the `data` branch of [bikespace/parking-map-data](https://github.com/bikespace/parking-map-data).

## Commands

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
# Run all tests (excludes long-running tests by default)
uv run pytest

# Show print output
uv run pytest -s

# Run a single test file
uv run pytest src/bikespace_data/bicycle_parking/tests/test_downstream.py

# Run long-running tests
uv run pytest -m long -s

# Run the bicycle parking pipeline
uv run src/bikespace_data/bicycle_parking/update_bicycle_parking.py

# Run the bicycle parking pipeline with archive output
uv run src/bikespace_data/bicycle_parking/update_bicycle_parking.py --archive

# Run the cycling network data update
uv run src/bikespace_data/bicycle_network/update_cycling_network.py

# Run the cycling network conflation
uv run src/bikespace_data/cycling_network_conflation/update_conflation.py [--region toronto|all] [--archive]
```

## Architecture

All source code lives in `src/bikespace_data/`. Each dataset has its own folder with an `update_*.py` entry-point script. Tests are co-located in `tests/` subdirectories within each dataset folder. Shared code is in `resources/` and `utilities/`.

### Datasets

**`bicycle_parking/`** — Main dataset. Downloads from three source types, normalizes each, de-duplicates City vs OSM features, clusters ring-and-post bollards, and saves display files.
- `wrappers.py`: Abstract `BikeData` base class; concrete `BikeDataToronto`, `BikeDataOSM`, `BikeLockersToronto` handle fetching + normalizing each source
- `conversions/`: One file per dataset with `filter_properties` and `transform_properties` functions; `__init__.py` exposes `get_filter(name)` / `get_transform(name)`
- `sources/`: JSON files listing dataset names/resource IDs/overpass queries; `load_sources.py` reads them; `city_exclusions.py` manages the manual exclusion list
- `downstream.py`: Post-processing — `extract_ref_tags`, `group_proximate_rings` (bollard clustering), `group_proximate_racks`

**`bicycle_network/`** — Downloads City of Toronto cycling-network GeoJSON from open.toronto.ca; skips if unchanged.

**`cycling_network_conflation/`** — Matches City of Toronto cycling-network segments to OSM ways spatially.
- `region_config.py`: `RegionConfig` dataclass defines all region parameters (CRS, buffer, thresholds, override CSV path, etc.); `build_osm_cycling_query` builds Overpass query from a Wikidata ID
- `regions/`: One file per city (currently only `toronto.py`); imports schema from `bicycle_network/`
- `spatial_match.py`: `match_cycling_network` — buffer-based spatial join + angle filter to find municipal↔OSM pairs; returns a DataFrame with `match_type` (`auto`/`override`) and `override_action` columns
- Override CSVs (`overrides/toronto_overrides.csv`) allow manual include/exclude corrections
- Outputs: `matches.csv` (full debug), `combined_with_matches.geojson`, `display_files/matches.csv`, `municipal_with_matches.json`, `osm_with_matches.json`

**`apartments/`** — Geocodes apartment building locations (separate smaller pipeline).

### Shared utilities

- `utilities/status_manager.py`: `StatusManager` — reads last-run status from the `data` branch on GitHub and saves updated status CSV locally
- `utilities/gdf_utils.py`: `save_geo_output` (writes GeoJSON with optional archive copy), `dt_cols_to_str`
- `resources/toronto_open_data.py`: `request_tod_gdf` — fetches a dataset from the City of Toronto CKAN API

### Data flow

Scripts run daily via `.github/workflows/run-update-sensor.yml`. After running, output files are committed to the `data` branch (not `main`) via cherry-pick. Monday runs include `--archive` for date-stamped backups.

### CRS conventions

- Data is stored/loaded in **EPSG:4326** (WGS 84)
- Spatial operations (buffering, distances) are done in **EPSG:32617** (UTM Zone 17N, appropriate for Toronto)

### Key properties schema

Normalized bicycle parking features use `meta_source`, `meta_source_dataset`, `meta_source_url`, `meta_source_license`, `meta_source_last_updated` for provenance. Conflation outputs use `_source` (`municipal`/`osm`), `_conflation_algo_matches`, `_conflation_override_excluded`, `_conflation_override_included` (semicolon-separated IDs).

### Environment variables

- `OVERPASS_API_URL` — optional custom Overpass endpoint (defaults to `https://overpass-api.de/api/interpreter`)
- `OVERPASS_API_NAME` — display name for the custom endpoint
- Both can be set via `.env` file (loaded with `python-dotenv`)

### Adding a new conflation region

1. Create `regions/<name>.py` defining a `RegionConfig` instance
2. Add it to `_REGIONS` dict in `update_conflation.py`
3. Add a pandera schema for the municipal data (see `bicycle_network/update_cycling_network.py` for the Toronto example)
