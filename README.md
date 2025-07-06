# Toronto Bicycle Parking Map Data

This script downloads, filters, and transforms data from two major sources: City of Toronto Open Data and OpenStreetMap. The goal of the script is to provide a clean and uniform data set of bicycle parking locations in Toronto.

## [BikeSpace Parking Map](https://bikespace.ca/parking-map)

The data is used for the BikeSpace parking map available at [bikespace.ca/parking-map](https://bikespace.ca/parking-map).

## Prototype Maps

Proof of concept maps that also use this data:

### [Map Demo](https://demo-map-app.new-parking-map.pages.dev/)

Link: https://demo-map-app.new-parking-map.pages.dev/

- Displays bicycle parking from both City and OpenStreetMap sources with some simple de-duplication.
- You can click on the features to see more details.
- If you click on the heading at the top it will provide some more information and has a button to optionally show a bike theft heatmap. (source: https://open.toronto.ca/dataset/bicycle-thefts/)
- The City of Toronto bike network is shown for context (source: https://open.toronto.ca/dataset/cycling-network/)
- This is a prototype used to help design the bicycle parking map now available on bikespace.ca

### [Quest Map](https://quest-map.new-parking-map.pages.dev/)

Link: https://quest-map.new-parking-map.pages.dev/

- Displays bicycle parking from the City that needs to be surveyed to fill in some gaps in the data.
- There is also a toggle on this map to show individual ring and posts in case that's useful (e.g. for issue reporting)
- [Bike Stations](https://open.toronto.ca/dataset/bicycle-parking-bike-stations-indoor/) data set is address geolocated and could be improved with more precise locations.
- [Bicycle Parking - High Capacity (Outdoor)](https://open.toronto.ca/dataset/bicycle-parking-high-capacity-outdoor/) and [Bicycle Parking Racks](https://open.toronto.ca/dataset/bicycle-parking-racks/) are also address geolocated and could be improved with more precise locations. These two datasets also overlap significantly (and need to be de-duplicated) and have many racks that are out of date, e.g. have been removed or relocated.
- [Street Furniture - Bicycle Parking](https://open.toronto.ca/dataset/street-furniture-bicycle-parking/) is very high quality but is missing the capacity number for bike racks. It also has some racks that are duplicates of racks in the High Capacity or Racks datasets.

How to fix:

- Survey the location
- To add/edit details, add or link to a bike parking node in OpenStreetMap.
  - You can link the OpenStreetMap entry to any of the City datasets using the appropriate [ref tag](https://www.openstreetmap.org/user/tallcoleman).
  - The correct ref tag value should be pre-generated for you if you click on the details in the quest map.
  - The script uses the ref tags to de-duplicate entries for the "display" dataset.
- To remove City bike parking that no longer exists, add an entry in `Data Pipeline/city_modifications/open_toronto_ca_exclusions.json`.
  - There is a template in the `Data Pipeline/city_modifications` folder to help you.
  - These entries will be removed from the "display" dataset.

### [Current Map](https://demo-map-app.new-parking-map.pages.dev/CurrentMap/)

Link: https://demo-map-app.new-parking-map.pages.dev/CurrentMap/

- This shows the old data layer previously used for https://bikespace.ca/ParkingMap (in red) along with the current up-to-date data from the City open datasets (in black) and OpenStreetMap (in blue). 
- There are some bicycle parking points in the old data layer that are not currently available in any City open data set or OpenStreetMap that should be added to OpenStreetMap.
- For the dataset, see [datasets/old_parking_data in the bikespace repo](https://github.com/bikespace/bikespace/tree/main/datasets/old_parking_data)


## Development

Folder content is as follows:

* Source Files: data received from the original source before any upstream filtering or transformation
* Output Files: data after upstream filtering and transformation
* Display Files: final data after downstream filtering and transformation

### Data Processing Script - Toronto Bicycle Parking Locations

Main script is `src/bikespace_data/bicycle_parking/data_pipeline.py`

You will need [uv installed](https://docs.astral.sh/uv/getting-started/installation/) to run the script.

Run with:
```bash
$ uv run src/bikespace_data/bicycle_parking/data_pipeline.py
```

### Data Sources:

The OpenStreetMap data includes all elements with the tag "amenity=bicycle_parking" within the City of Toronto relation (id=324211).
The City of Toronto Open Data portal has four current datasets:
- "bicycle-parking-high-capacity-outdoor"
- "bicycle-parking-racks"
- "bicycle-parking-bike-stations-indoor"
- "street-furniture-bicycle-parking"

More information about these datasets can be found on open.toronto.ca

### Upstream Filtering

Upstream filtering removes irrelevant features (e.g. features in City data that have been "temporarily removed" or not yet marked as installed). 

### Upstream Transformation

The primary goal of upstream data transformations is to ensure a consistent output format. The output format is based on the OpenStreetMap tagging schema, with the addition of fields with the "meta_" prefix for information that may be useful but does not fit with a logical OpenStreetMap tag. (In many cases, in OpenStreetMap this meta information would be inferred from the edit history, the geography, or added as a relation).

### Downstream Filtering and Transformation

Downstream filtering and transformation is applied to clean and organize the data in more complex ways, and requires analyzing features and datasets in relation to each other. Examples include:

Handling of overlapping entries between City data and OpenStreetMap. Features are currently retained or excluded as follows:

OpenStreetMap:
* Retain: OpenStreetMap features that have a ref tag linking the feature to a City dataset (e.g. `ref:open.toronto.ca:street-furniture-bicycle-parking:id`)
* Retain: OpenStreetMap features that have any value for "ref:open.toronto.ca" (intended to allow for "ref:open.toronto.ca"="no" for City of Toronto features not included in any City dataset).
* Exclude: Any other feature with operator like "City of Toronto".

City of Toronto:
* Exclude: features where the ID matches a retained feature from OpenStreetMap
* Exclude: features included in `Data Pipeline/city_modifications/open_toronto_ca_exclusions.json` (intended to allow for City of Toronto features which have been removed, but have not yet been updated in the City dataset).

Clustering of city ring and posts (i.e. `"bicycle_parking"="bollard"`) to reduce clutter - ring and post features within 5m of each other are combined into a single point.

De-duplication of bicycle racks across multiple City datasets - in many cases, racks from different City datasets within 30m of each other are duplicates. Since there may be cases where they are not duplicates, the processing combines the features into a single point that retains the properties of all of them. In order to prevent racks from being combined, they should be surveyed to verify their number, capacity, and locations, and added to OpenStreetMap.

## City Exclusions - Instructions

1. Copy template from `Data Pipeline/city_modifications/exclusion_template.json`
2. Add to `Data Pipeline/city_modifications/open_toronto_ca_exclusions.json`
3. Add IDs, reason, and notes. If there is more than one ID with the same key, do not use the semicolon separator, add a separate line for each instance of the key-value pair.

Reasons:

- `removed`: Not found via survey, but there is a probable cause for removal (e.g. construction, CafeTO installation).
- `missing`: Not found via survey.
- `area_survey`: Used for cases where address-geolocated points are insufficiently distinguishable in order to map data to found features 1:1. Should survey comprehensively, add all found features to OpenStreetMap, and then add the relevant data points to the exclusion list with this reason tag.
