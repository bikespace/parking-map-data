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

## `region_config.py` — Data Classes

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
    osm_cycling_query: str             # Overpass query body

    # Spatial matching parameters
    crs: str                           # Local UTM CRS, e.g. "EPSG:32617"
    buffer_m: float = 15.0
    orthogonality_threshold_deg: float = 45.0
    endpoint_trim_m: float = 10.0      # Trim from each end before making core buffer

    # Paths
    override_csv: Path | None = None
```

---

## Toronto Region Config (`regions/toronto.py`)

- **Municipal source**: `TodMunicipalSource(dataset_name="cycling-network", resource_id="023da9a2-8848-4e10-9cad-e7f9119cd874")`
- **Pandera schema**: Extends existing schema from `update_cycling_network.py` — `SEGMENT_ID`, `INFRA_HIGHORDER`, `INFRA_LOWORDER`, `geometry`
- **Municipal ID col**: `SEGMENT_ID`
- **OSM Wikidata**: `Q172`
- **CRS**: `EPSG:32617`
- **OSM query** (cycling-specific, crossings excluded):

```
area["wikidata"="Q172"]->.searchArea;
(
  way["highway"="cycleway"](area.searchArea);
  way["cycleway"~"lane|track|shared_lane|opposite_lane|opposite_track|shared_use|sidepath|opposite"](area.searchArea);
  way["bicycle"="designated"]["highway"~"path|footway|pedestrian"](area.searchArea);
  way["bicycle_road"="yes"](area.searchArea);
);
out geom;
```

---

## `spatial_match.py` — Algorithm

**Inputs**: `municipal_gdf`, `osm_gdf`, `config: RegionConfig`, `overrides_df: pd.DataFrame`

**Steps**:

1. **Project** both GDFs to `config.crs` (UTM) for metre-accurate distance calculations
2. **Buffer** each municipal linestring by `config.buffer_m` → `municipal_buffers`
3. **Core buffer** (endpoint exclusion): trim `config.endpoint_trim_m` from each end of each municipal linestring using Shapely's `substring`, then buffer → `municipal_core_buffers`
4. **Spatial join** OSM ways against `municipal_buffers` to get candidate pairs (`sjoin`)
5. **Angle filter**: for each candidate pair, compute bearing of each linestring (start→end, `atan2(dy, dx)`), compute acute angle between them; exclude pairs where acute angle > `config.orthogonality_threshold_deg`
6. **Endpoint flag**: for each surviving pair, compute fraction of OSM way's length inside `municipal_core_buffer`; if < 10%, flag as `endpoint_only`
7. **Apply overrides**: `action=exclude` removes pair; `action=include` adds pair with `match_type=override`
8. **Return** DataFrame: `municipal_id, osm_way_id, match_type, flags`

**Key functions**:
```python
def compute_linestring_bearing(geom: LineString) -> float
def acute_angle_between(b1: float, b2: float) -> float
def core_buffer(geom: LineString, trim_m: float, buffer_m: float) -> Polygon
def match_cycling_network(
    municipal_gdf, osm_gdf, config, overrides_df
) -> pd.DataFrame
```

---

## `update_conflation.py` — Entry Point

```python
def run_region(config: RegionConfig, output_root: Path, archive: bool = False):
    # 1. Download + validate municipal data  → save to source_files/municipal.geojson
    # 2. Download OSM data via overpass      → save to source_files/osm.geojson
    # 3. Load override CSV (or empty df)
    # 4. Call match_cycling_network(...)
    # 5. Build output_files/matches.csv (full debug table, includes unmatched municipal rows)
    # 6. Build output_files/combined_with_matches.geojson (single FeatureCollection; source + 3 conflation properties)
    # 7. Build display_files/matches.csv (clean table: municipal_id + osm_way_id; overrides applied)
    # 8. Build display_files/municipal_with_matches.json (lookup dict)
    # 9. Build display_files/osm_with_matches.json (lookup dict)
    # 10. Save outputs, update StatusManager

if __name__ == "__main__":
    # argparse: --region toronto|brampton|ottawa  (default: all)
```

**StatusManager**: uses existing `StatusManager` from `bikespace_data.utilities` — tracks last download time per region to avoid redundant re-runs.

---

## Output File Details

### `output_files/matches.csv`
Full many-to-many table for development and debugging. Includes every row produced or considered by the algorithm, plus one row per unmatched municipal feature (blank OSM columns).

| Column                                    | Description                                        |
| ----------------------------------------- | -------------------------------------------------- |
| `{municipal_id_col}` (e.g. `SEGMENT_ID`) | Municipal feature ID                               |
| `osm_way_id`                              | OSM way ID; blank for unmatched municipal features |
| `match_type`                              | `auto`, `override`, or blank for unmatched         |
| `override_action`                         | `include` / `exclude` / null                       |
| `flags`                                   | Comma-separated: `endpoint_only`                   |

### `output_files/combined_with_matches.geojson`
Single FeatureCollection merging all municipal and OSM features. Includes a top-level `municipal_id_key` field (e.g. `"SEGMENT_ID"`) alongside the standard `type` and `features` keys. Each feature retains all original properties from its source dataset plus:

| Property                       | Description                                                                           |
| ------------------------------ | ------------------------------------------------------------------------------------- |
| `_source`                      | `municipal` or `osm`                                                                  |
| `_conflation_algo_matches`     | Semicolon-separated IDs from the other dataset matched by the algorithm (pre-override)|
| `_conflation_override_excluded`| Semicolon-separated IDs that were auto-matched but removed by a manual override       |
| `_conflation_override_included`| Semicolon-separated IDs added by a manual override                                    |

IDs in these properties are always from the opposite dataset (OSM IDs for municipal features, municipal IDs for OSM features).

### `display_files/matches.csv`
Clean many-to-many table for downstream consumption. Excludes matches removed by manual override; includes unmatched municipal features (blank `osm_way_id`) and matches added via manual override.

The municipal column is named after the actual ID field rather than a generic name — e.g. `SEGMENT_ID` for Toronto. This makes the column self-documenting without repeating metadata in every row.

| Column                          | Description                                          |
| ------------------------------- | ---------------------------------------------------- |
| `{municipal_id_col}` (e.g. `SEGMENT_ID`) | Municipal feature ID                      |
| `osm_way_id`                    | OSM way ID; blank for unmatched municipal features   |

### `display_files/municipal_with_matches.json`
Lookup object mapping each municipal feature ID to a list of matching OSM feature IDs (empty list if no matches). No geometry or other properties. Includes a top-level `municipal_id_key` field naming the column used as the ID.

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
Lookup object mapping each OSM feature (compound `type/id` key, e.g. `way/123456789`) to a list of matching municipal IDs (empty list if no matches). No geometry or other properties. Includes a top-level `municipal_id_key` field for consistency with the municipal lookup file.

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

(Initially empty — user adds rows to force-include or force-exclude specific pairs.)

---

## Reusing Existing Code

- `bikespace_data.utilities.StatusManager` — track per-region last-updated timestamps
- `bikespace_data.resources.toronto_open_data.request_tod_gdf` — download Toronto municipal data
- `overpass.API` setup pattern from `bicycle_parking/wrappers.py:165-197` — replicate (don't import) to support `OVERPASS_API_URL` env var and correct User-Agent header
- `cycling_network_schema` and `bike_lane_types` from `bicycle_network/update_cycling_network.py` — import and extend

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