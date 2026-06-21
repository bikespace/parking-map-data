# Cycling Network Conflation

This module matches municipal cycling network segments to their corresponding OpenStreetMap (OSM) ways. The output supports cross-referencing official cycling network data against OSM for validation and display.

## How it works

For each configured region, the script:

1. Downloads the municipal cycling network from the configured source
2. Downloads OSM ways within the municipality via the Overpass API — both dedicated cycling ways and general road ways that may or may not carry cycling infrastructure
3. Spatially matches municipal segments to OSM ways using a buffer + angle filter
4. Applies manual overrides from a CSV file
5. Writes output files to `cycling_network_conflation/<region>/`

### Matching algorithm

Each municipal segment is buffered by `buffer_m` (default 15 m). OSM ways that intersect that buffer are candidates. Candidates are then filtered by angle: if the acute angle between the OSM way's bearing and the municipal segment's local tangent exceeds `orthogonality_threshold_deg` (default 45°), the pair is rejected. This removes perpendicular roads (e.g. cross-streets) that happen to pass through the buffer.

A match is flagged `endpoint_only` when all of the OSM overlap falls within `endpoint_trim_m` (default 10 m) of the municipal segment's ends, indicating a shared junction point rather than a shared corridor.

OSM ways tagged `cycleway=separate` or `cycleway:both=separate` are excluded from matching — these roads have their cycling infrastructure mapped as a parallel way, so the road itself should not match municipal cycling segments.

## Running

```bash
# Run all regions
uv run src/bikespace_data/cycling_network_conflation/update_conflation.py

# Run a specific region
uv run src/bikespace_data/cycling_network_conflation/update_conflation.py --region toronto

# Archive outputs with a timestamp
uv run src/bikespace_data/cycling_network_conflation/update_conflation.py --archive
```

Output is written to `cycling_network_conflation/<region>/`:

| File                                         | Description                                                           |
| -------------------------------------------- | --------------------------------------------------------------------- |
| `source_files/municipal.geojson`             | Raw municipal data as downloaded                                      |
| `source_files/osm.geojson`                   | Raw OSM ways as downloaded                                            |
| `output_files/matches.csv`                   | Full match table including override-excluded pairs (for debugging)    |
| `output_files/combined_with_matches.geojson` | All features (municipal + OSM) with conflation metadata as properties |
| `display_files/matches.csv`                  | Matches with override-excluded pairs removed                          |
| `display_files/municipal_with_matches.json`  | Lookup from municipal ID → list of matched OSM way IDs                |
| `display_files/osm_with_matches.json`        | Lookup from OSM way ID → list of matched municipal IDs                |

## Tests

```bash
uv run pytest src/bikespace_data/cycling_network_conflation --cov-reset --cov=src/bikespace_data/cycling_network_conflation
```

Tests use synthetic GeoDataFrames in projected CRS (EPSG:32617) with simple LineString geometries — no external data or network access is needed.

## Manual overrides

Each region can have an override CSV at `overrides/<region>_overrides.csv`. The file is created automatically (empty) if it doesn't exist when the script runs.

| Column               | Values                        | Description                                                                             |
| -------------------- | ----------------------------- | --------------------------------------------------------------------------------------- |
| `<municipal_id_col>` | e.g. `SEGMENT_ID` for Toronto | Municipal feature ID                                                                    |
| `osm_way_id`         | e.g. `way/123456`             | OSM way ID (with `way/` prefix)                                                         |
| `action`             | `include` or `exclude`        | `exclude` suppresses an auto-matched pair; `include` forces a pair the algorithm missed |
| `note`               | free text                     | Reason for the override                                                                 |

## Adding a new region

1. Create `regions/<name>.py` defining a `RegionConfig` instance. See `regions/toronto.py` for a City Open Data (CKAN) source or `regions/brampton.py` for a URL-based source.
2. Define a [pandera](https://pandera.readthedocs.io/) schema validating the municipal data's required columns (at minimum `geometry` and the ID column).
3. Add the region to `_REGIONS` in `update_conflation.py`.
4. Optionally create `overrides/<name>_overrides.csv` in advance, or let the script create it on first run.

### `RegionConfig` reference

| Parameter                     | Default                       | Description                                                                                                     |
| ----------------------------- | ----------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `municipal_id_col`            | —                             | Column name for the unique segment ID in the municipal dataset (e.g. `SEGMENT_ID`)                              |
| `municipal_infra_col`         | —                             | Column name for the infrastructure type (used for display, not matching)                                        |
| `osm_wikidata_id`             | —                             | Wikidata ID for the municipality, used to scope the Overpass query (e.g. `Q172` for Toronto)                    |
| `crs`                         | —                             | Projected CRS for spatial operations, should be appropriate for the region (e.g. `EPSG:32617` for UTM Zone 17N) |
| `buffer_m`                    | `15.0`                        | Match buffer radius in metres                                                                                   |
| `orthogonality_threshold_deg` | `45.0`                        | Maximum angle between ways to accept a match                                                                    |
| `endpoint_trim_m`             | `10.0`                        | Metres trimmed from each end of a segment when computing the core buffer                                        |
| `osm_query_template`          | `osm_lts_road_query.overpass` | Path to a custom Overpass query template                                                                        |
| `override_csv`                | `None`                        | Path to the manual overrides CSV                                                                                |
