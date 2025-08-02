# DATA PROCESSING SCRIPT - TORONTO BICYCLE PARKING LOCATIONS
# ==========================================================
#
# This script downloads, filters, and transforms data from two major sources: City of Toronto Open Data and OpenStreetMap. The goal of the script is to provide a clean and uniform data set that can be used to create a map that helps cyclists find bicycle parking in Toronto.


# IMPORTS
# -------

from argparse import ArgumentParser
from datetime import datetime, timezone
from itertools import chain
import json
import requests
from typing import Literal
from zoneinfo import ZoneInfo

import geojson
import geopandas
import pandas as pd
from pathlib import Path
from shapely import Polygon
import overpass

from bikespace_data.bicycle_parking.custom_types import GeoJSONFeatureCollection

import bikespace_data.bicycle_parking.conversions as conversions
from bikespace_data.bicycle_parking.wrappers import (
    BikeData,
    BikeDataToronto,
    BikeDataOSM,
    BikeLockersToronto,
)
from bikespace_data.bicycle_parking.downstream import (
    group_proximate_rings,
    group_proximate_racks,
    drop_mapped_city_lockers,
)
from bikespace_data.bicycle_parking.utilities import dt_cols_to_str, ref_cols_to_str

geopandas.options.io_engine = "pyogrio"


def save_output(
    output: GeoJSONFeatureCollection | geopandas.GeoDataFrame,
    *,
    path: Path,
    file_name: str,
    archive_name: str | None = None,
    na: Literal["null", "drop", "keep"] = "drop",
):
    """Save GeoJSON dict or GeoPandas Geodataframe to file. If archive_name is specified, the file will also be saved in an archive folder in the same path."""

    path.mkdir(exist_ok=True, parents=True)
    if archive_name:
        (path / archive_name).mkdir(exist_ok=True, parents=True)

    if isinstance(output, geopandas.GeoDataFrame):
        with open(path / file_name, "w") as f:
            f.write(dt_cols_to_str(output).to_json(na=na, drop_id=True, indent=2))
        if archive_name:
            output.to_parquet(
                (path / archive_name / file_name).with_suffix(".parquet"),
            )

    else:
        with open(path / file_name, "w") as f:
            geojson.dump(output, f, indent=2)
        if archive_name:
            gdf = geopandas.GeoDataFrame.from_features(
                output["features"]
            ).convert_dtypes()
            gdf.to_parquet((path / archive_name / file_name).with_suffix(".parquet"))


def get_city_exclusions(
    url: str = "https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/data/bicycle_parking/city_modifications/open_toronto_ca_exclusions.json",
):
    """Gets city exclusions from data branch. Implemented as a url request to prepare for later switch to hosting exclusions via API."""
    response = requests.get(url)

    if response.status_code != 200:
        raise Exception(
            f"Could not get city exclusions from resource url. Resource returned status {response.status_code}"
        )

    city_exclusions = response.json()
    return city_exclusions


# SCRIPT EXECUTION
# ----------------


def run_pipeline(*, archive=False):
    """Main function to run the data processing pipeline."""

    # get today's date and use to set output folders
    # unlike other dates in this script, uses Toronto time not UTC
    today_toronto_isodate = datetime.now(ZoneInfo("America/Toronto")).strftime(
        "%Y-%m-%d"
    )
    archive_name = f"archive/{today_toronto_isodate}/" if archive else None
    if archive:
        print("Archive folder option enabled")

    sfp = Path("bicycle_parking/source_files/")
    ofp = Path("bicycle_parking/output_files/")
    dfp = Path("bicycle_parking/display_files/")

    for path in [sfp, ofp, dfp]:
        path.mkdir(exist_ok=True, parents=True)

    # load in details and status
    print("Loading sources and statuses...")

    def load_paths(paths: dict) -> dict:
        data = {}
        for label, path in paths.items():
            item_data = None
            if path.exists():
                with path.open() as f:
                    item_data = json.load(f)
            else:
                item_data = {}

            data = data | {label: item_data}

        return data

    # load paths to .json files specifying details and status of data sources
    source_paths = {
        "city": Path(
            "src/bikespace_data/bicycle_parking/sources/open_toronto_ca_sources.json"
        ),
        "osm": Path(
            "src/bikespace_data/bicycle_parking/sources/openstreetmap_sources.json"
        ),
        "lockers": Path(
            "src/bikespace_data/bicycle_parking/sources/toronto_lockers_sources.json"
        ),
    }
    status_paths = {
        "city": Path("bicycle_parking/statuses/open_toronto_ca_statuses.json"),
        "osm": Path("bicycle_parking/statuses/openstreetmap_statuses.json"),
        "lockers": Path("bicycle_parking/statuses/toronto_lockers_statuses.json"),
    }
    sources = load_paths(source_paths)
    statuses = load_paths(status_paths)

    # update function

    def run_update(bike_data: type[BikeData], dataset_status: dict) -> dict:
        """Function to check whether specified dataset is up to date and download new data if required.

        Parameters
        ----------
        bike_data: type[BikeData]
        dataset_status: dict
          - Optional

        Returns
        -------
          Returns a status dict with the following values:
          - last_updated: datetime the source dataset was last updated
          - num_normalized_features: number of features in filtered/transformed output
          - last_checked: datetime the source was last queried
          - days_since_source_update: calculated number of days between last_checked and last_updated to indicate source data freshness

        As a side effect, will save or update the following files:
        - Data received from the source: /source_files/{bike_data.dataset_name}.geojson
        - Normalized (filtered and transformed) data: /source_files/{bike_data.dataset_name}-normalized.geojson

        """

        # check if data has been updated
        rec_last_updated_str = dataset_status.setdefault("last_updated", None)
        rec_last_updated = (
            datetime.fromisoformat(rec_last_updated_str)
            if rec_last_updated_str
            # None not allowed in date comparsion; this is like datetime.min but tz aware
            else datetime(1, 1, 1, tzinfo=timezone.utc)
        )

        # save source file
        save_output(
            bike_data.response_geojson,
            path=sfp,
            file_name=f"{bike_data.dataset_name}.geojson",
            archive_name=archive_name,
        )

        # get normalized output
        filter_properties = conversions.get_filter(bike_data.dataset_name)
        transform_properties = conversions.get_transform(bike_data.dataset_name)
        normalized_gdf = bike_data.normalize(filter_properties, transform_properties)

        # save normalized output
        na_option = "drop" if isinstance(bike_data, BikeDataOSM) else "null"
        save_output(
            normalized_gdf,
            path=ofp,
            file_name=f"{bike_data.dataset_name}-normalized.geojson",
            archive_name=archive_name,
            na=na_option,
        )

        num_normalized_features = len(normalized_gdf)

        # update status from metadata
        dataset_status["last_updated"] = bike_data.last_updated.isoformat()
        dataset_status["num_normalized_features"] = num_normalized_features

        # update check datetime
        last_checked = datetime.now(timezone.utc)
        dataset_status["last_checked"] = last_checked.isoformat()
        dataset_status["days_since_source_update"] = (
            last_checked - datetime.fromisoformat(dataset_status["last_updated"])
        ).days
        return dataset_status

    # City of Toronto Data
    print("Checking and updating City of Toronto data...")

    # check status and update output file if needed
    for dataset in sources["city"]["datasets"]:
        bdt = BikeDataToronto(dataset["dataset_name"], dataset["resource_name"])
        dataset_status = statuses["city"].setdefault(bdt.dataset_name, {})
        # check source and save output files if there are new changes
        updated_status = run_update(bdt, dataset_status)
        statuses["city"][bdt.dataset_name] = (
            statuses["city"][bdt.dataset_name] | updated_status
        )

    # update status JSON
    status_fp = Path("bicycle_parking/statuses/")
    status_fp.mkdir(exist_ok=True, parents=True)

    with status_paths["city"].open("w") as f:
        json.dump(statuses["city"], f, indent=2)

    # get output files, do further processing and combine
    city_data = {}
    for dataset in sources["city"]["datasets"]:
        gdf = geopandas.read_file(
            ofp / f"{dataset['dataset_name']}-normalized.geojson"
        ).convert_dtypes()
        gdf = gdf.astype({"meta_source_last_updated": "str", "capacity": "Int64"})
        gdf = ref_cols_to_str(gdf)
        gdf = gdf.explode(index_parts=False)
        gdf.insert(0, "source", dataset["dataset_name"])
        city_data[dataset["dataset_name"]] = gdf

    # OpenStreetMap Data
    print("Checking and updating OpenStreetMap data...")

    # check status and update output file if needed
    for dataset in sources["osm"]["datasets"]:
        bdo = BikeDataOSM(dataset["dataset_name"], dataset["overpass_query"])
        dataset_status = statuses["osm"].setdefault(bdo.dataset_name, {})
        # check source and save output files if there are new changes
        updated_status = run_update(bdo, dataset_status)
        statuses["osm"][bdo.dataset_name] = (
            statuses["osm"][bdo.dataset_name] | updated_status
        )

    # update status JSON
    with status_paths["osm"].open("w") as f:
        json.dump(statuses["osm"], f, indent=2)

    # get output files, do further processing and combine
    osm_data_list = []
    for dataset in sources["osm"]["datasets"]:
        gdf = geopandas.read_file(
            ofp / f"{dataset['dataset_name']}-normalized.geojson"
        ).convert_dtypes()
        gdf = gdf.astype(
            {
                "meta_source_last_updated": "str",
                "meta_feature_last_updated": "str",
            }
        )
        osm_data_list.append(gdf)

    osm_combined = pd.concat(osm_data_list)

    # City Lockers
    print("Checking and updating City of Toronto bike lockers...")

    # check status and update output file if needed
    for dataset in sources["lockers"]["datasets"]:
        blt = BikeLockersToronto(dataset["dataset_name"], dataset["url"])
        dataset_status = statuses["lockers"].setdefault(blt.dataset_name, {})
        # check source and save output files if there are new changes
        updated_status = run_update(blt, dataset_status)
        statuses["lockers"][blt.dataset_name] = (
            statuses["lockers"][blt.dataset_name] | updated_status
        )

    # update status JSON
    with status_paths["lockers"].open("w") as f:
        json.dump(statuses["lockers"], f, indent=2)

    # get output files, do further processing and combine
    lockers_data_list = []
    for dataset in sources["lockers"]["datasets"]:
        gdf = geopandas.read_file(ofp / f"{dataset['dataset_name']}-normalized.geojson")
        gdf = gdf.convert_dtypes().astype(
            {"meta_source_last_updated": "str", "capacity": "Int64"}
        )
        lockers_data_list.append(gdf)

    lockers: geopandas.GeoDataFrame = pd.concat(lockers_data_list)

    # save full normalized data without any deduplication or clustering
    all_normalized_unprocessed = pd.concat(
        df.dropna(axis="columns", how="all")
        for df in [
            *city_data.values(),
            osm_combined,
            lockers,
        ]
    ).convert_dtypes()

    save_output(
        all_normalized_unprocessed,
        path=ofp,
        file_name="all_normalized_unprocessed.geojson",
        archive_name=archive_name,
        na="drop",
    )

    # Downstream: City Data Selection
    # -------------------------------
    print("Applying downstream processing: City Data Selection...")

    # get osm with ref tags
    open_toronto_ca_test = (
        osm_combined.filter(like="ref:open.toronto.ca", axis=1).notna().any(axis=1)
    )
    city_verified_osm = osm_combined[open_toronto_ca_test]

    # get all instances of osm city ref tags and split out if needed
    id_lists = {}
    id_cols = city_verified_osm.filter(like="ref:open.toronto.ca", axis=1)
    for ref_type, tags in id_cols.items():
        id_list = []
        for tag_str in tags:
            tags = str(tag_str).split(";")
            id_list.extend([tag.strip() for tag in tags])

        id_lists.setdefault(ref_type, [])
        id_lists[ref_type].extend(id_list)

    # drop city data points if they have matching tags from osm data
    for dataset_name, dataset in city_data.items():
        city_data[dataset_name] = dataset[~dataset.isin(id_lists).any(axis=1)]

    # drop all osm with operator="City of Toronto" (case/space-insensitive) unless they have ref tag or unless they are a locker (for which no ref match can currently be made).
    # this also retains osm points with ANY value for "ref:open.toronto.ca", including "ref.open.toronto.ca"="no"
    operator_not_city_and_no_ref_test = (
        (
            ~osm_combined["operator"].str.contains(
                r"city\s*?of\s*?toronto", case=False, regex=True
            )
            | osm_combined["operator"].isna()
        )
        | (osm_combined["bicycle_parking"] == "lockers")
    ) & (~open_toronto_ca_test)
    osm_filtered = (
        pd.concat([city_verified_osm, osm_combined[operator_not_city_and_no_ref_test]])
        .to_crs(32617)  # change to UTM 17 N for centroid calculation
        .convert_dtypes()
    )
    osm_centroid = osm_filtered.set_geometry(osm_filtered.geometry.centroid).to_crs(
        4326
    )

    # drop city data points in the manual exclusion file
    city_exclusions = get_city_exclusions()

    city_exclusions_ids = list(chain.from_iterable([x["ids"] for x in city_exclusions]))

    city_exclusions_dict = {}
    for id in city_exclusions_ids:
        [[k, v]] = id.items()
        city_exclusions_dict.setdefault(k, [])
        city_exclusions_dict[k].append(v)

    for dataset_name, dataset in city_data.items():
        city_data[dataset_name] = dataset[
            ~dataset.isin(city_exclusions_dict).any(axis=1)
        ]
    city_unclustered = city_data.copy()
    city_unclustered_combined = pd.concat(
        [
            dataset.dropna(axis="columns", how="all")
            for name, dataset in city_unclustered.items()
        ]
    ).convert_dtypes()

    # drop city lockers already in OpenStreetMap
    lockers_unmapped = drop_mapped_city_lockers(lockers, osm_combined)

    # Downstream: Ring and Post Clustering
    # ------------------------------------
    print("Applying downstream processing: Ring and Post Clustering...")

    # special handling for ring and post features from "street-furniture-bicycle-parking"
    furniture = city_data["street-furniture-bicycle-parking"]
    furniture_bollards = furniture[furniture["bicycle_parking"] == "bollard"]
    furniture_not_bollards = furniture[
        (furniture["bicycle_parking"] != "bollard")
        | (furniture["bicycle_parking"].isna())
    ]

    agg_bollards = group_proximate_rings(furniture_bollards)
    city_data["street-furniture-bicycle-parking"] = pd.concat(
        [furniture_not_bollards, agg_bollards]
    )

    # Downstream: Rack Deduplication
    # ------------------------------
    print("Applying downstream processing: Rack Deduplication...")

    # get boundary for Toronto Metropolitan University
    api = overpass.API()
    response = api.get("way(id:23250594)", responseformat="geojson", verbosity="geom")
    tmupoly = Polygon(response["features"][0]["geometry"]["coordinates"])
    tmugs = geopandas.GeoSeries(tmupoly, crs=4326).to_crs(32617).buffer(20).to_crs(4326)

    # combine city datasets (bicycle stations excluded)
    city_combined = pd.concat(
        [
            df.dropna(axis="columns", how="all")
            for df in [
                city_data["bicycle-parking-high-capacity-outdoor"],
                city_data["bicycle-parking-racks"],
                city_data["street-furniture-bicycle-parking"],
            ]
        ]
    )
    city_racks = city_combined[city_combined["bicycle_parking"] == "rack"]
    city_not_racks = city_combined[
        (city_combined["bicycle_parking"] != "rack")
        | (city_combined["bicycle_parking"].isna())
    ]

    # no duplicates at TMU apparently
    city_racks = city_racks.assign(
        tmu=city_racks["geometry"].apply(lambda p: tmugs.intersects(p, align=False))
    )

    # run clustering (excluding TMU)
    city_racks_clustered = group_proximate_racks(city_racks[city_racks["tmu"] == False])  # noqa: E712
    city_full = pd.concat(
        [
            city_racks_clustered,
            city_racks[city_racks["tmu"] == True],  # noqa: E712
            city_not_racks,
            city_data["bicycle-parking-bike-stations-indoor"],
        ]
    ).convert_dtypes()
    city_full = city_full.drop("tmu", axis=1)

    # make combined set from all sources
    all_sources = pd.concat(
        [city_full, osm_centroid, lockers_unmapped]
    ).convert_dtypes()

    # Save display files
    # ------------------
    print("Saving display files...")

    save_output(
        city_full,
        path=dfp,
        file_name="open_toronto_ca.geojson",
        archive_name=archive_name,
        na="drop",
    )
    save_output(
        city_unclustered_combined,
        path=dfp,
        file_name="open_toronto_ca_unclustered.geojson",
        archive_name=archive_name,
        na="drop",
    )
    save_output(
        osm_centroid,
        path=dfp,
        file_name="openstreetmap.geojson",
        archive_name=archive_name,
        na="drop",
    )
    save_output(
        lockers_unmapped,
        path=dfp,
        file_name="toronto_lockers.geojson",
        archive_name=archive_name,
        na="drop",
    )
    save_output(
        all_sources,
        path=dfp,
        file_name="all_sources.geojson",
        archive_name=archive_name,
        na="drop",
    )


# Script Execution
# ----------------

# run from command line `uv run src/bikespace_data/bicycle_parking/update_bicycle_parking.py`
if __name__ == "__main__":
    # parse script arguments from command line
    parser = ArgumentParser(
        description="""A copy of outputs can optionally be put in a date-stamped archive folder using --archive"""
    )
    parser.add_argument(
        "-a",
        "--archive",
        action="store_true",
        help="Create a date-stamped archive folder alongside outputs",
    )
    args = parser.parse_args()

    run_pipeline(archive=args.archive)
