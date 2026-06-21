Parent issue: #34

## Overview

This issue tracks the implementation of Part One from #34: generating the initial conflation file that maps municipal cycling network feature IDs ↔ OSM way IDs, starting with the City of Toronto dataset and structured as a multi-municipality framework.

---

## New Module

`src/bikespace_data/cycling_network_conflation/` with the following layout:

```
cycling_network_conflation/
├── __init__.py
├── update_conflation.py       # CLI entry point; drives per-region pipeline
├── region_config.py           # RegionConfig dataclass + MunicipalSource types
├── spatial_match.py           # Core spatial matching algorithm
├── osm_cycling_query.overpass # Default OSM query template (uses $wikidata_id placeholder)
├── regions/
│   ├── __init__.py
│   ├── toronto.py             # Toronto config + Pandera schema (fully implemented)
│   ├── brampton.py            # Brampton stub (config only, schema TBD)
│   └── ottawa.py              # Ottawa stub (config only, schema TBD)
├── overrides/
│   └── toronto_overrides.csv  # Empty initially; user-edited manual overrides
└── tests/
    └── test_spatial_match.py
```

---

## Data Output Structure (committed to `data` branch)

```
cycling_network_conflation/{region}/
├── source_files/
│   ├── municipal.geojson              # Raw municipal download
│   └── osm.geojson                    # Raw OSM download
├── output_files/
│   ├── matches.csv                    # Full match table for development/debugging
│   └── combined_with_matches.geojson  # Municipal + OSM features with match metadata (primary QA file)
├── display_files/
│   ├── matches.csv                    # Clean match table for downstream consumption
│   ├── municipal_with_matches.json    # Lookup: municipal_id → [osm_ids]
│   └── osm_with_matches.json          # Lookup: osm compound key → [municipal_ids]
└── statuses/
    └── conflation_status.csv
```

---

## `region_config.py` — Data Classes and Query Helper

```python
@dataclass
class TodMunicipalSource:       # City of Toronto Open Data (CKAN)
    dataset_name: str
    resource_id: str

@dataclass
class UrlMunicipalSource:       # Direct URL (Brampton, Ottawa)
    url: str

@dataclass
class RegionConfig:
    name: str                           # e.g. "toronto"
    display_name: str                   # e.g. "City of Toronto"

    # Municipal open data
    municipal_source: TodMunicipalSource | UrlMunicipalSource
    municipal_schema: pa.DataFrameSchema
    municipal_id_col: str               # e.g. "SEGMENT_ID"
    municipal_infra_col: str            # e.g. "INFRA_HIGHORDER"
    municipal_license: str
    municipal_license_url: str

    # OSM data
    osm_wikidata_id: str               # e.g. "Q172" for Toronto
    # Query is built at runtime via build_osm_cycling_query(osm_wikidata_id).
    # Pass osm_cycling_query_template to override the default osm_cycling_query.overpass file.
    osm_cycling_query_template: Path | None = None

    # Spatial matching parameters
    crs: str                           # Local UTM CRS, e.g. "EPSG:32617"
    buffer_m: float = 15.0
    orthogonality_threshold_deg: float = 45.0
    endpoint_trim_m: float = 10.0      # Trim from each end before making core buffer

    # Paths
    override_csv: Path | None = None
```

Also in `region_config.py`, a helper that builds the Overpass query from the template file using `string.Template` substitution (modelled on the [LTS-OSM pattern](https://github.com/bikespace/LTS-OSM)):

```python
from string import Template
from pathlib import Path

_DEFAULT_QUERY_TEMPLATE = Path(__file__).parent / "osm_cycling_query.overpass"

def build_osm_cycling_query(
    wikidata_id: str,
    template_path: Path = _DEFAULT_QUERY_TEMPLATE,
) -> str:
    return Template(template_path.read_text()).substitute(wikidata_id=wikidata_id)
```

The default `osm_cycling_query.overpass` template (cycling-specific, crossings excluded):

```
area["wikidata"="$wikidata_id"]->.searchArea;
(
  way["highway"="cycleway"](area.searchArea);
  way["cycleway"~"lane|track|shared_lane|opposite_lane|opposite_track|shared_use|sidepath|opposite"](area.searchArea);
  way["bicycle"="designated"]["highway"~"path|footway|pedestrian"](area.searchArea);
  way["bicycle_road"="yes"](area.searchArea);
);
out geom;
```

---

## Toronto Region Config (`regions/toronto.py`)

- **Municipal source**: `TodMunicipalSource(dataset_name="cycling-network", resource_id="023da9a2-8848-4e10-9cad-e7f9119cd874")`
- **Pandera schema**: Extends existing schema from `update_cycling_network.py` — `SEGMENT_ID`, `INFRA_HIGHORDER`, `INFRA_LOWORDER`, `geometry`
- **Municipal ID col**: `SEGMENT_ID`
- **OSM Wikidata**: `Q172`
- **CRS**: `EPSG:32617`
- **OSM query**: built via `build_osm_cycling_query("Q172")` using the default `osm_cycling_query.overpass` template (no override needed)

---

## `spatial_match.py` — Algorithm

**Inputs**: `municipal_gdf`, `osm_gdf`, `config: RegionConfig`, `overrides_df: pd.DataFrame`

**Steps**:

1. **Project** both GDFs to `config.crs` (UTM) for metre-accurate distance calculations
2. **Buffer** each municipal linestring by `config.buffer_m` → `municipal_buffers`
3. **Core buffer** (endpoint exclusion): trim `config.endpoint_trim_m` from each end of each municipal linestring using Shapely's `substring`, then buffer → `municipal_core_buffers`. If a linestring is shorter than `2 * endpoint_trim_m`, skip the core buffer for that segment (set `municipal_core_buffer = None`); any OSM overlap with such a segment will be flagged `endpoint_only` in step 6.
4. **Spatial join** OSM ways against `municipal_buffers` to get candidate pairs (`sjoin`)
5. **Angle filter**: for each candidate pair:
   1. Clip the OSM way to the municipal buffer: `clipped = osm_geom.intersection(municipal_buffer)`. If the result is a `MultiLineString`, use the longest sub-geometry. If `clipped.length < 2m`, skip angle filtering — treat as an endpoint contact and let the `endpoint_only` flag handle it.
   2. Find the midpoint of the clipped segment and project it onto the municipal linestring to get normalized parameter `t = municipal_geom.project(midpoint, normalized=True)`.
   3. Compute the **local municipal tangent** at `t`: sample `municipal_geom.interpolate(t ± 0.01, normalized=True)`, clamped to [0, 1], and compute `atan2(dy, dx)`.
   4. Compute the bearing of the clipped OSM segment (`atan2(dy, dx)` from its start→end).
   5. Compute the acute angle between these two bearings; exclude pairs where it exceeds `config.orthogonality_threshold_deg`.

   This approach correctly handles Z-shaped or curved municipal linestrings (by comparing against the local tangent rather than the overall start→end bearing) and short OSM segments split at intersections (by comparing only the portion of the OSM way that overlaps the buffer, not the full way).

   > **Fallback if needed**: If the algorithm underperforms on curved OSM segments after manual review, step 5.4 can be replaced with a PCA/least-squares orientation of the clipped segment's coordinate array (first principal component of the point set). This is more robust than start→end bearing for curved clipped geometries but adds a numpy dependency and complexity; try it only if the simpler bearing is insufficient.
6. **Endpoint flag**: for each surviving pair, flag as `endpoint_only` if `core_overlap / buffer_overlap < 10%`, where:
   - `buffer_overlap` = length of OSM way clipped to `municipal_buffer` (the `clipped` segment already computed in step 5)
   - `core_overlap` = length of OSM way clipped to `municipal_core_buffer`

   Using `buffer_overlap` as the denominator (not the full OSM way length) ensures the flag correctly answers "of the portion of this OSM way that overlaps the municipal feature at all, is most of it confined to the endpoint zone?" A long OSM way that genuinely parallels a short municipal segment will have a high core/buffer ratio and will not be incorrectly flagged.
7. **Apply overrides**: for `action=exclude`, mark the pair with `override_action=exclude` (do not remove it); for `action=include`, add the pair with `match_type=override` and `override_action=include`
8. **Return** DataFrame: `municipal_id, osm_way_id, match_type, override_action, flags` — includes all pairs (auto-matched, override-excluded, and override-included). The caller (`run_region`) filters for display output.

**Key functions**:
```python
def compute_linestring_bearing(geom: LineString) -> float  # pass the clipped segment, not the full OSM way
def acute_angle_between(b1: float, b2: float) -> float
def core_buffer(geom: LineString, trim_m: float, buffer_m: float) -> Polygon
def match_cycling_network(
    municipal_gdf, osm_gdf, config, overrides_df
) -> pd.DataFrame
# Returns columns: municipal_id, osm_way_id (compound key e.g. "way/123456789"),
# match_type ("auto" | "override" | null), override_action ("include" | "exclude" | null), flags
```

---

## `update_conflation.py` — Entry Point

```python
def run_region(config: RegionConfig, output_root: Path, archive: bool = False):
    # 1. Download + validate municipal data  → save to source_files/municipal.geojson
    # 2. Download OSM data via overpass      → save to source_files/osm.geojson
    #    (Build query via build_osm_cycling_query(config.osm_wikidata_id, config.osm_cycling_query_template))
    # 3. Load override CSV from overrides/{region}_overrides.csv.
    #    If the file does not exist, generate a blank version with columns
    #    ({municipal_id_col}, osm_way_id, action, note) and save it.
    #    Validate: "action" column must contain only "include", "exclude", or null.
    #    The municipal ID column must match config.municipal_id_col; raise an informative
    #    ValueError if the column is missing or misnamed.
    # 4. Call match_cycling_network(...)
    # 5. Build output_files/matches.csv (full debug table; all pairs including override-excluded;
    #    includes unmatched municipal rows with blank OSM columns)
    # 6. Build output_files/combined_with_matches.geojson (single FeatureCollection;
    #    _source + 3 conflation properties; reproject to EPSG:4326 before writing)
    # 7. Derive display_files/matches.csv from output_files/matches.csv:
    #    drop match_type, override_action, flags; exclude rows where override_action == "exclude"
    # 8. Derive display_files/municipal_with_matches.json from display_files/matches.csv
    # 9. Derive display_files/osm_with_matches.json from display_files/matches.csv
    # 10. Save outputs, update StatusManager
    #     (See bicycle_network/update_cycling_network.py for StatusManager initialization pattern)
    # 11. If archive=True: copy all output files to a date-stamped subdirectory
    #     (e.g. output_files/archive/YYYYMMDD_HHMMSS/); use parquet for tabular data.
    #     (See existing modules for archive patterns)

if __name__ == "__main__":
    # argparse: --region toronto|brampton|ottawa  (default: all)
```

**StatusManager**: uses existing `StatusManager` from `bikespace_data.utilities` — tracks last download time per region to avoid redundant re-runs.

---

## Output File Details

### `output_files/matches.csv`
Full many-to-many table for development and debugging. Includes every row produced or considered by the algorithm, plus one row per unmatched municipal feature (blank OSM columns).

| Column                                    | Description                                                           |
| ----------------------------------------- | --------------------------------------------------------------------- |
| `{municipal_id_col}` (e.g. `SEGMENT_ID`) | Municipal feature ID                                                  |
| `osm_way_id`                              | OSM compound key (e.g. `way/123456789`); blank for unmatched rows     |
| `match_type`                              | `auto`, `override`, or blank for unmatched                            |
| `override_action`                         | `include` / `exclude` / null                                          |
| `flags`                                   | Comma-separated: `endpoint_only`                                      |

### `output_files/combined_with_matches.geojson`
Single FeatureCollection merging all municipal and OSM features, written in **EPSG:4326** (WGS84, per RFC 7946). Reproject from `config.crs` before writing. Includes a top-level `municipal_id_key` field (e.g. `"SEGMENT_ID"`) alongside the standard `type` and `features` keys. Each feature retains all original properties from its source dataset plus:

| Property                       | Description                                                                           |
| ------------------------------ | ------------------------------------------------------------------------------------- |
| `_source`                      | `municipal` or `osm`                                                                  |
| `_conflation_algo_matches`     | Semicolon-separated IDs from the other dataset matched by the algorithm (pre-override)|
| `_conflation_override_excluded`| Semicolon-separated IDs that were auto-matched but removed by a manual override       |
| `_conflation_override_included`| Semicolon-separated IDs added by a manual override                                    |

IDs in these properties are always from the opposite dataset (OSM IDs for municipal features, municipal IDs for OSM features).

### `display_files/matches.csv`
Clean many-to-many table for downstream consumption. Derived from `output_files/matches.csv` by dropping `match_type`, `override_action`, and `flags`, and excluding rows where `override_action == "exclude"`. Includes unmatched municipal features (blank `osm_way_id`) and matches added via manual override.

The municipal column is named after the actual ID field rather than a generic name — e.g. `SEGMENT_ID` for Toronto. This makes the column self-documenting without repeating metadata in every row.

| Column                          | Description                                                        |
| ------------------------------- | ------------------------------------------------------------------ |
| `{municipal_id_col}` (e.g. `SEGMENT_ID`) | Municipal feature ID                                   |
| `osm_way_id`                    | OSM compound key (e.g. `way/123456789`); blank for unmatched rows |

### `display_files/municipal_with_matches.json`
Lookup object mapping each municipal feature ID to a list of matching OSM compound keys (empty list if no matches). No geometry or other properties. Includes a top-level `municipal_id_key` field naming the column used as the ID. Derived from `display_files/matches.csv`.

```json
{
  "municipal_id_key": "SEGMENT_ID",
  "matches": {
    "SEGMENT_ID_1": ["way/123456789", "way/987654321"],
    "SEGMENT_ID_2": []
  }
}
```

### `display_files/osm_with_matches.json`
Lookup object mapping each OSM compound key (e.g. `way/123456789`) to a list of matching municipal IDs. Covers all OSM features downloaded during the analysis run — features that were considered but not matched have an empty list. Features absent from the download (e.g. ways created after the run) simply won't appear; this distinguishes "considered and unmatched" from "not yet in scope." Includes a top-level `municipal_id_key` field for consistency. Derived from `display_files/matches.csv` (all OSM IDs from the OSM source file, not just those that appear in matches).

**Note:** Evaluate file size after the first Toronto run. If the file is too large for downstream use, it is acceptable to cull keys with empty match lists; document this decision in a top-level `"culled_empty_matches": true` field.

```json
{
  "municipal_id_key": "SEGMENT_ID",
  "matches": {
    "way/123456789": ["SEGMENT_ID_1"],
    "way/111111111": []
  }
}
```

### `overrides/toronto_overrides.csv`
```csv
{municipal_id_col},osm_way_id,action,note
```
e.g. for Toronto: `SEGMENT_ID,osm_way_id,action,note`

`osm_way_id` values are compound keys (e.g. `way/123456789`). `action` must be `include` or `exclude`.

If the file does not exist, it is auto-generated as a blank CSV with the correct column headers (using `config.municipal_id_col` for the municipal ID column). Initially empty — user adds rows to force-include or force-exclude specific pairs.

---

## Reusing Existing Code

- `bikespace_data.utilities.StatusManager` — track per-region last-updated timestamps. See `bicycle_network/update_cycling_network.py` for the initialization pattern (status_source URL, dataset_name conventions).
- `bikespace_data.resources.toronto_open_data.request_tod_gdf` — download Toronto municipal data
- `overpass.API` setup pattern from `bicycle_parking/wrappers.py:165-197` — replicate (don't import) to support `OVERPASS_API_URL` env var and correct User-Agent header
- `cycling_network_schema` and `bike_lane_types` from `bicycle_network/update_cycling_network.py` — import and extend
- Archive pattern — see existing modules for how `archive=True` is implemented (date-stamped subdirectory, parquet for tabular data)

---

## Tests

Unit tests in `tests/test_spatial_match.py` using synthetic GeoDataFrames (no network calls):

- Parallel linestrings within buffer → match found
- Perpendicular linestrings → excluded by angle filter
- OSM way entirely in endpoint zone → flagged `endpoint_only`
- Override `include` rescues a pair excluded by angle filter
- Override `exclude` removes a pair that would auto-match
- Empty override CSV → same result as no override

Integration test (marked `@pytest.mark.uses_external_resources`): full Toronto pipeline run end-to-end.

---

## Verification

1. `uv run pytest src/bikespace_data/cycling_network_conflation/tests/ -v` — all unit tests pass
2. `uv run src/bikespace_data/cycling_network_conflation/update_conflation.py --region toronto` — produces all output files without error
3. Open `output_files/combined_with_matches.geojson` in QGIS; confirm matched pairs are spatially plausible; verify `_conflation_algo_matches`, `_conflation_override_excluded`, `_conflation_override_included` properties are populated correctly
4. Add a test override row to `overrides/toronto_overrides.csv`, re-run, confirm the excluded pair appears in `output_files/matches.csv` with `override_action=exclude` but is absent from `display_files/matches.csv`