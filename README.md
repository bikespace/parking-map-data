# BikeSpace Project Data for Toronto Bicycle Parking and Other Sources

This repository holds and runs scripts to provide data used by the BikeSpace project, including a clean and up to date dataset of bicycle parking locations in Toronto and the city bicycle network.

## [View the Data](https://github.com/bikespace/parking-map-data/tree/data)

The output data for this repository can be [viewed in the data branch](https://github.com/bikespace/parking-map-data/tree/data).

## Bicycle Parking Data

The scripts in `src/../bicycle_parking` download, filter, and transform data from two major sources: City of Toronto Open Data and OpenStreetMap. The goal of the script is to provide a clean and uniform data set of bicycle parking locations in Toronto.

### [BikeSpace Parking Map](https://bikespace.ca/parking-map)

The data is used for the BikeSpace parking map available at [bikespace.ca/parking-map](https://bikespace.ca/parking-map).

### Prototype Maps

Proof of concept maps that also use this data:

#### [Map Demo](https://demo-map-app.new-parking-map.pages.dev/)

Link: https://demo-map-app.new-parking-map.pages.dev/

- Displays bicycle parking from both City and OpenStreetMap sources with some simple de-duplication.
- You can click on the features to see more details.
- If you click on the heading at the top it will provide some more information and has a button to optionally show a bike theft heatmap. (source: https://open.toronto.ca/dataset/bicycle-thefts/)
- The City of Toronto bike network is shown for context (source: https://open.toronto.ca/dataset/cycling-network/)
- This is a prototype used to help design the bicycle parking map now available on bikespace.ca

#### [Quest Map](https://quest-map.new-parking-map.pages.dev/)

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
- To remove City bike parking that no longer exists, add an entry in `bicycle_parking/city_modifications/open_toronto_ca_exclusions.json` in the [data branch](https://github.com/bikespace/parking-map-data/tree/data).
  - There is a template in the `bicycle_parking/city_modifications` folder to help you.
  - These entries will be removed from the "display" dataset.

#### [Current Map](https://demo-map-app.new-parking-map.pages.dev/CurrentMap/)

Link: https://demo-map-app.new-parking-map.pages.dev/CurrentMap/

- This shows the old data layer previously used for https://bikespace.ca/ParkingMap (in red) along with the current up-to-date data from the City open datasets (in black) and OpenStreetMap (in blue). 
- There are some bicycle parking points in the old data layer that are not currently available in any City open data set or OpenStreetMap that should be added to OpenStreetMap.
- For the dataset, see [datasets/old_parking_data in the bikespace repo](https://github.com/bikespace/bikespace/tree/main/datasets/old_parking_data)


### Development

You will need [uv installed](https://docs.astral.sh/uv/getting-started/installation/) to run the scripts.


