# Bicycle Parking Data

Main script is `src/bikespace_data/bicycle_parking/update_bicycle_parking.py`

Run with:
```bash
$ uv run src/bikespace_data/bicycle_parking/update_bicycle_parking.py
```

Output folders are as follows:

* `source_files`: data received from the original source before any upstream filtering or transformation
* `output_files`: data after upstream filtering and transformation
* `display_files`: final data after downstream filtering and transformation

## Data Sources:

The OpenStreetMap data includes all elements with the tag "amenity=bicycle_parking" within the City of Toronto relation (id=324211).
The City of Toronto Open Data portal has four current datasets:
- "bicycle-parking-high-capacity-outdoor"
- "bicycle-parking-racks"
- "bicycle-parking-bike-stations-indoor"
- "street-furniture-bicycle-parking"

More information about these datasets can be found on open.toronto.ca

## Upstream Filtering

Upstream filtering removes irrelevant features (e.g. features in City data that have been "temporarily removed" or not yet marked as installed). 

## Upstream Transformation

The primary goal of upstream data transformations is to ensure a consistent output format. The output format is based on the OpenStreetMap tagging schema, with the addition of fields with the "meta_" prefix for information that may be useful but does not fit with a logical OpenStreetMap tag. (In many cases, in OpenStreetMap this meta information would be inferred from the edit history, the geography, or added as a relation).

## Downstream Filtering and Transformation

Downstream filtering and transformation is applied to clean and organize the data in more complex ways, and requires analyzing features and datasets in relation to each other. Examples include:

Handling of overlapping entries between City data and OpenStreetMap. Features are currently retained or excluded as follows:

OpenStreetMap:

* Retain: OpenStreetMap features that have a ref tag linking the feature to a City dataset (e.g. `ref:open.toronto.ca:street-furniture-bicycle-parking:id`)
* Retain: OpenStreetMap features that have any value for "ref:open.toronto.ca" (intended to allow for "ref:open.toronto.ca"="no" for City of Toronto features not included in any City dataset).
* Retain: OpenStreetMap features that are `bicycle_parking=lockers`
* Exclude: Any other feature with operator like "City of Toronto".

City of Toronto:

* Exclude: features where the ID matches a retained feature from OpenStreetMap
* Exclude: features included in `bicycle_parking/city_modifications/open_toronto_ca_exclusions.json` in the [data branch](https://github.com/bikespace/parking-map-data/tree/data) (intended to allow for City of Toronto features which have been removed, but have not yet been updated in the City dataset).
* Exclude: city lockers within a buffer radius (200m) of any `bicycle_parking=lockers` from OpenStreetMap with an operator like "City of Toronto" (The locations on some City lockers data is very inaccurate, so if the locker has been mapped in OSM, it is likely more precise)

Clustering of city ring and posts (i.e. `"bicycle_parking"="bollard"`) to reduce clutter - ring and post features within 5m of each other are combined into a single point.

De-duplication of bicycle racks across multiple City datasets - in many cases, racks from different City datasets within 30m of each other are duplicates. Since there may be cases where they are not duplicates, the processing combines the features into a single point that retains the properties of all of them. In order to prevent racks from being combined, they should be surveyed to verify their number, capacity, and locations, and added to OpenStreetMap.

### City Exclusions - Instructions

1. Copy template from `bicycle_parking/city_modifications/exclusion_template.json`
2. Add to `bicycle_parking/city_modifications/open_toronto_ca_exclusions.json`
3. Add IDs, reason, and notes. If there is more than one ID with the same key, do not use the semicolon separator, add a separate line for each instance of the key-value pair.

Reasons:

- `removed`: Not found via survey, but there is a probable cause for removal (e.g. construction, CafeTO installation).
- `missing`: Not found via survey.
- `area_survey`: Used for cases where address-geolocated points are insufficiently distinguishable in order to map data to found features 1:1. Should survey comprehensively, add all found features to OpenStreetMap, and then add the relevant data points to the exclusion list with this reason tag.

## Downstream Processing Diagram

```mermaid
---
config:
  theme: redux
---

flowchart TD
    A(["OSM Query"]) --> B["Extract ref tags"] & n5@{ label: "Tag features with operator like 'City of Toronto' to be dropped unless they have a ref tag or are not within 30m of a retained City feature" }
    B --> n2["Tag features with matching ref tags to be dropped"]
    n1(["City Data<br>(Open Data Portal and Webpage)"]) --> n2
    n2 --> n4["Tag features matching exclusion file to be dropped"]
    n3(["City Exclusions"]) --> n4
    n4 --> n5 & n6["Tag city racks to be clustered (possible conflation)"]
    n5 --> n7["Tag posts/stands to be clustered (simplification)"]
    n6 --> n7
    n7 --> n8["Drop features tagged for removal and combine features tagged for clustering"]
    n8 --> n9(["Display Data"])

    B@{ shape: rect}
    n5@{ shape: rect}
    n2@{ shape: rect}
    n6@{ shape: rounded}
    n7@{ shape: rounded}
    n8@{ shape: rounded}
    
    classDef cityData fill:#BBDEFB
    class A,B,n5 OSMData
    classDef OSMData fill:#FFF9C4
    class n1,n2,n4,n6 cityData
    classDef mixedData fill:#E1BEE7
    class n7,n8,n9 mixedData
```