# Bicycle Parking Data

Output folders are as follows:

* `source_files`: data received from the original source before any upstream filtering or transformation
* `output_files`: data after upstream filtering and transformation
* `display_files`: final data after downstream filtering and transformation

## Data Sources:

The OpenStreetMap data includes all elements with the tag "amenity=bicycle_parking" within the City of Toronto relation (id=324211) as well as those with [lifecycle prefixes](https://wiki.openstreetmap.org/wiki/Lifecycle_prefix) like "construction:amenity=bicycle_parking".

The City of Toronto Open Data portal has four current datasets for bicycle parking:
- "bicycle-parking-high-capacity-outdoor"
- "bicycle-parking-racks"
- "bicycle-parking-bike-stations-indoor"
- "street-furniture-bicycle-parking"

More information about these datasets can be found on open.toronto.ca

In addition, data on bicycle lockers is taken from the [Toronto bicycle lockers locations web page](https://www.toronto.ca/services-payments/streets-parking-transportation/cycling-in-toronto/bicycle-parking/bicycle-lockers/locker-locations/).

## Upstream Filtering

Upstream filtering removes irrelevant features (e.g. features in City data that have been "temporarily removed" or not yet marked as installed). 

## Upstream Transformation

The primary goal of upstream data transformations is to ensure a consistent output format. The output format is based on the OpenStreetMap tagging schema, with the addition of fields with the "meta_" prefix for information that may be useful but does not fit with a logical OpenStreetMap tag. (In many cases, in OpenStreetMap this meta information would be inferred from the edit history, the geography, or added as a relation).

## Downstream Filtering and Transformation

Downstream filtering and transformation is applied to clean and organize the data in more complex ways, and requires analyzing features and datasets in relation to each other. Examples include:

Handling of overlapping entries between City data and OpenStreetMap. Features are currently retained or excluded as follows (and see diagram at the end of the README):

OpenStreetMap:

* Retain: OpenStreetMap features that have a ref tag linking the feature to a City dataset (e.g. `ref:open.toronto.ca:street-furniture-bicycle-parking:id`, `ref:toronto.ca:lockers:title`)
* This also means that OpenStreetMap features that have any value for "ref:open.toronto.ca" or "ref:toronto.ca" are retained (intended to allow for "ref:open.toronto.ca"="no" for City of Toronto features not included in any City dataset).
* Exclude: Any feature likely to be a City ring and post (e.g. `bicycle_parking=bollard/stands` or no `bicycle_parking` tag) that is within 5m of a retained City feature that is also likely to be a ring and post (i.e. not `bicycle_parking=rack`)
* Exclude: Any other feature with operator like "City of Toronto" unless there are no retained City features within 30m

City of Toronto:

* Exclude: features where the ID matches a retained feature from OpenStreetMap
* Exclude: features included in `bicycle_parking/city_modifications/open_toronto_ca_exclusions.json` in the [data branch](https://github.com/bikespace/parking-map-data/tree/data) (intended to allow for City of Toronto features which have been removed, but have not yet been updated in the City dataset).

Clustering of city ring and posts (i.e. `"bicycle_parking"="bollard"`) to reduce clutter --- ring and post features within 5m of each other are combined into a single point.

De-duplication of bicycle racks across multiple City datasets --- in many cases, racks from different City datasets within 30m of each other are duplicates. Since there may be cases where they are not duplicates, the processing combines the features into a single point that retains the properties of all of them. In order to prevent racks from being combined, they should be surveyed to verify their number, capacity, and locations, and added to OpenStreetMap.

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
    A(["OSM Query<br>(bicycle parking features in Toronto)"]) --> B["Extract city ref tags from OSM features"] & n5@{ label: "Tag OSM features with operator like 'City of Toronto' to be dropped unless they have a ref tag or are not within 30m of a retained City feature" }
    B --> n2["Tag city features with matching ref tags from OSM to be dropped"]
    n1(["City Data<br>(Open Data Portal and Webpage)"]) --> n2
    n2 --> n4["Tag city features matching exclusion file to be dropped"]
    n3(["City Exclusions"]) --> n4
    n4 --> n5
    n5 --> n10["Tag OSM features that are likely to be a city ring and post and that are within 5m of a retained city feature to be dropped"]
    n6["Cluster city racks (possible conflation)"] --> n7["Cluster city ring &amp; posts (simplification)"]
    n10 --> n11["Drop features tagged for removal"] & n12(["save tagged data to all_normalized_tagged output file for debugging"])
    n11 --> n6
    n7 --> n9(["Display Data"])
    
    B@{ shape: rect}
    n2@{ shape: rect}
    n5@{ shape: rect}
    n6@{ shape: rounded}
    n7@{ shape: rounded}
    n11@{ shape: rect}

    classDef cityData fill:#BBDEFB
    class n1,n2,n4,n6,n7 cityData
    classDef OSMData fill:#FFF9C4
    class A,B,n5,n10 OSMData
    classDef mixedData fill:#E1BEE7
    class n9,n11 mixedData
```