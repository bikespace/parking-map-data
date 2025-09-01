"""
DATA PROCESSING SCRIPT - TORONTO BICYCLE PARKING LOCATIONS
==========================================================

This script downloads, filters, and transforms data from City of Toronto Open Data, the City of Toronto Website, and OpenStreetMap. The goal of the script is to provide a clean and uniform data set that can be used to create a map that helps cyclists find bicycle parking in Toronto.
"""


# IMPORTS
# -------

from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, TypedDict, cast
from zoneinfo import ZoneInfo

import geojson
import geopandas
import pandas as pd

import bikespace_data.bicycle_parking.conversions as conversions
from bikespace_data.bicycle_parking.custom_types import GeoJSONFeatureCollection
from bikespace_data.bicycle_parking.downstream import (
    extract_ref_tags,
    group_proximate_racks,
    group_proximate_rings,
)
from bikespace_data.bicycle_parking.sources.city_exclusions import (
    city_exclusions_getids,
    get_city_exclusions,
)
from bikespace_data.bicycle_parking.sources.load_sources import (
    SourceDatasetOpenStreetMap,
    SourceDatasetTorontoOpenData,
    SourceDatasetTorontoWeb,
    load_paths,
)
from bikespace_data.bicycle_parking.utilities import dt_cols_to_str, ref_cols_to_str
from bikespace_data.bicycle_parking.wrappers import (
    BikeData,
    BikeDataOSM,
    BikeDataToronto,
    BikeLockersToronto,
)
from bikespace_data.utilities import StatusManager

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


class StatusDict(TypedDict):
    dataset_name: str
    last_updated: datetime
    num_features: int
    last_checked: datetime


def run_update(
    bike_data: BikeData,
    *,
    status_manager: StatusManager,
    sfp: Path,
    ofp: Path,
    archive_name: str | None,
) -> StatusDict:
    """Download a dataset using its BikeData class wrapper and update the status for that dataset.

    Returns
    -------
        Returns a status dict with the following values:
        - dataset_name
        - last_updated: datetime the source dataset was last updated
        - num_features: number of features in filtered/transformed output
        - last_checked: datetime the source was last queried

    As a side effect, will update the status file managed by `status_manager` and save or update the following files:
    - Data received from the source: /source_files/{bike_data.dataset_name}.geojson
    - Normalized (filtered and transformed) data: /source_files/{bike_data.dataset_name}-normalized.geojson

    """

    # check if data has been updated (NOT CURRENTLY USED)
    rec_last_updated = status_manager.last_updated(dataset_name=bike_data.dataset_name)

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

    dataset_status: StatusDict = {
        "dataset_name": bike_data.dataset_name,
        "last_updated": bike_data.last_updated,
        "num_features": len(normalized_gdf),
        "last_checked": datetime.now(timezone.utc),
    }
    status_manager.add(**dataset_status)
    status_manager.save()

    return dataset_status


# SCRIPT EXECUTION
# ----------------


def update_bicycle_parking(
    *,
    archive=False,
    output_dir: Path = Path(""),
    status_path: Path = Path("bicycle_parking/statuses/bicycle_parking_statuses.csv"),
):
    """Main function to update the bicycle parking data."""

    # get today's date and use to set output folders
    # unlike other dates in this script, uses Toronto time not UTC
    today_toronto_isodate = datetime.now(ZoneInfo("America/Toronto")).strftime(
        "%Y-%m-%d"
    )
    archive_name = f"archive/{today_toronto_isodate}/" if archive else None
    if archive:
        print("Archive folder option enabled")

    sfp = output_dir / "bicycle_parking/source_files/"
    ofp = output_dir / "bicycle_parking/output_files/"
    dfp = output_dir / "bicycle_parking/display_files/"

    for path in [sfp, ofp, dfp]:
        path.mkdir(exist_ok=True, parents=True)

    # load in details and status
    print("Loading sources and statuses...")

    sm = StatusManager(
        status_source=f"https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/data/{str(status_path)}",
        status_save=status_path,
    )

    # load paths to .json files specifying details of data sources
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
    sources = load_paths(source_paths)

    # City of Toronto Data
    print("Checking and updating City of Toronto data...")

    # check status and update output file if needed
    for dataset in sources["city"]["datasets"]:
        dataset = cast(SourceDatasetTorontoOpenData, dataset)
        bdt = BikeDataToronto(dataset["dataset_name"], dataset["resource_name"])
        # check source and save output files if there are new changes
        updated_status = run_update(
            bdt,
            status_manager=sm,
            sfp=sfp,
            ofp=ofp,
            archive_name=archive_name,
        )

    # get output files, do further processing and combine
    city_data = {}
    for dataset in sources["city"]["datasets"]:
        dataset = cast(SourceDatasetTorontoOpenData, dataset)
        gdf = geopandas.read_file(
            ofp / f"{dataset['dataset_name']}-normalized.geojson"
        ).convert_dtypes()
        gdf = gdf.astype({"meta_source_last_updated": "str", "capacity": "Int64"})
        gdf = ref_cols_to_str(gdf)
        gdf = gdf.explode(index_parts=False)
        city_data[dataset["dataset_name"]] = gdf

    # OpenStreetMap Data
    print("Checking and updating OpenStreetMap data...")

    # check status and update output file if needed
    for dataset in sources["osm"]["datasets"]:
        dataset = cast(SourceDatasetOpenStreetMap, dataset)
        bdo = BikeDataOSM(dataset["dataset_name"], dataset["overpass_query"])
        # check source and save output files if there are new changes
        updated_status = run_update(
            bdo,
            status_manager=sm,
            sfp=sfp,
            ofp=ofp,
            archive_name=archive_name,
        )

    # get output files, do further processing and combine
    osm_data_list = []
    for dataset in sources["osm"]["datasets"]:
        dataset = cast(SourceDatasetOpenStreetMap, dataset)
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

    osm_combined = geopandas.GeoDataFrame(pd.concat(osm_data_list))

    # City Lockers
    print("Checking and updating City of Toronto bike lockers...")

    # check status and update output file if needed
    for dataset in sources["lockers"]["datasets"]:
        dataset = cast(SourceDatasetTorontoWeb, dataset)
        blt = BikeLockersToronto(dataset["dataset_name"], dataset["url"])
        # check source and save output files if there are new changes
        updated_status = run_update(
            blt,
            status_manager=sm,
            sfp=sfp,
            ofp=ofp,
            archive_name=archive_name,
        )

    # get output files, do further processing and combine
    lockers_data_list = []
    for dataset in sources["lockers"]["datasets"]:
        dataset = cast(SourceDatasetTorontoWeb, dataset)
        gdf = geopandas.read_file(ofp / f"{dataset['dataset_name']}-normalized.geojson")
        gdf = gdf.convert_dtypes().astype(
            {"meta_source_last_updated": "str", "capacity": "Int64"}
        )
        lockers_data_list.append(gdf)

    lockers: geopandas.GeoDataFrame = geopandas.GeoDataFrame(
        pd.concat(lockers_data_list)
    )

    # save full normalized data without any deduplication or clustering
    all_normalized = geopandas.GeoDataFrame(
        pd.concat(
            [
                df.dropna(axis="columns", how="all")
                for df in [
                    *city_data.values(),
                    osm_combined,
                    lockers,
                ]
            ],
            ignore_index=True,
        )
    ).convert_dtypes()

    save_output(
        all_normalized,
        path=ofp,
        file_name="all_normalized_unprocessed.geojson",
        archive_name=archive_name,
        na="drop",
    )

    # Downstream: City and OSM data de-duplication
    # -------------------------------
    print("Applying downstream processing: City and OSM data de-duplication...")

    # convert to projected crs for spatial analysis
    all_normalized_utm17N = all_normalized.to_crs("EPSG:32617")

    # get all instances of osm city ref tags and split out if needed
    id_lists = extract_ref_tags(osm_combined, r"ref:(open\.)?toronto\.ca")

    # get city data points from the manual exclusion file
    city_exclusions = get_city_exclusions()
    city_exclusions_ids = city_exclusions_getids(city_exclusions)

    # add property-based attributes used for data selection
    add_attr = all_normalized_utm17N.assign(
        _city_drop_ref_match=lambda df: (
            (df["meta_source"].eq("City of Toronto", fill_value=False))
            & (df.isin(id_lists).any(axis=1))
        ),
        _city_drop_exclusions=lambda df: (
            (df["meta_source"].eq("City of Toronto", fill_value=False))
            & (df.isin(city_exclusions_ids).any(axis=1))
        ),
        _osm_operator_city=lambda df: (
            (df["meta_source"].eq("OpenStreetMap", fill_value=False))
            & (
                df["operator"].str.contains(
                    r"city\s*?of\s*?toronto",
                    case=False,
                    regex=True,
                    na=False,
                )
            )
        ),
        _osm_has_ref=lambda df: (
            (df["meta_source"].eq("OpenStreetMap", fill_value=False))
            & (
                df.filter(
                    regex=r"ref:(open\.)?toronto\.ca",
                    axis=1,
                )
                .notna()
                .any(axis=1)
            )
        ),
    )

    # add spatial-based attributes used for data selection
    osm_attr = add_attr[add_attr["meta_source"].eq("OpenStreetMap")]
    city_attr_retained = add_attr[
        add_attr["meta_source"].eq("City of Toronto")
        & ~add_attr["_city_drop_ref_match"]
        & ~add_attr["_city_drop_exclusions"]
    ][["bicycle_parking", "geometry"]]

    osm_city_5m_join = osm_attr.sjoin_nearest(
        city_attr_retained[
            ~city_attr_retained["bicycle_parking"].eq("rack", fill_value=False)
        ],
        how="left",
        max_distance=5,
        distance_col="distance",
    )
    osm_city_30m_join = osm_attr.sjoin_nearest(
        city_attr_retained,
        how="left",
        max_distance=30,
        distance_col="distance",
    )

    osm_drop_5m_match = osm_city_5m_join[
        ~osm_city_5m_join.index.duplicated()
        # spatial match within 5m radius only
        & ~osm_city_5m_join["distance"].isna()
        # do not drop OSM features with city ref
        & ~osm_city_5m_join["_osm_has_ref"]
        # only drop OSM features that are likely to be a ring and post
        & (
            osm_city_5m_join["bicycle_parking_left"].isin(["bollard", "stands"])
            | osm_city_5m_join["bicycle_parking_left"].isna()
        )
    ]
    osm_drop_operator_city = osm_city_30m_join[
        ~osm_city_30m_join.index.duplicated()
        # drop OSM features where operator is like "City of Toronto"
        & osm_city_30m_join["_osm_operator_city"]
        # but keep if they have a ref tag
        & ~osm_city_30m_join["_osm_has_ref"]
        # and keep if they are more than 30m from a retained City feature
        & ~osm_city_30m_join["distance"].isna()
    ]

    add_spatial = add_attr.assign(
        _osm_drop_5m_match=lambda df: df.index.isin(osm_drop_5m_match.index),
        _osm_drop_operator_city=lambda df: df.index.isin(osm_drop_operator_city.index),
    )

    final_selection = add_spatial.assign(
        _retained=lambda df: ~(
            # drop City data points if they have matching ref tags from OSM data
            (df["_city_drop_ref_match"])
            # drop City data points in the manual exclusion file
            | (df["_city_drop_exclusions"])
            # drop all OSM with operator like "City of Toronto" unless they have ref tag or are more than 30m from a retained City feature
            # this also retains osm points with ANY value for "ref:open.toronto.ca", including "ref.open.toronto.ca"="no"
            | (df["_osm_drop_operator_city"])
            # drop any OSM that are likely to be a ring and post and within 5m of a retained City feature
            | (df["_osm_drop_5m_match"])
        )
    )

    save_output(
        final_selection.to_crs("EPSG:32617")
        .set_geometry(final_selection.to_crs("EPSG:32617").geometry.centroid)
        .to_crs("EPSG:4326"),
        path=ofp,
        file_name="all_normalized_tagged.geojson",
        archive_name=archive_name,
        na="drop",
    )

    all_filtered = final_selection[final_selection["_retained"]].drop(
        # drop all columns with prefix "_"
        columns=final_selection.filter(regex=r"^_", axis=1).columns
    )
    all_centroid_utm17N = all_filtered.set_geometry(all_filtered.geometry.centroid)

    # Downstream: Ring and Post Clustering
    # ------------------------------------
    print("Applying downstream processing: Ring and Post Clustering...")

    # special handling for ring and post features from "street-furniture-bicycle-parking"
    furniture_bollards_test = (
        all_centroid_utm17N["meta_source_dataset"].eq(
            "street-furniture-bicycle-parking", fill_value=False
        )
    ) & (all_centroid_utm17N["bicycle_parking"].eq("bollard", fill_value=False))

    furniture_bollards = all_centroid_utm17N[furniture_bollards_test]
    furniture_not_bollards = all_centroid_utm17N[~furniture_bollards_test]
    assert len(furniture_bollards) + len(furniture_not_bollards) == len(
        all_centroid_utm17N
    )

    agg_bollards = group_proximate_rings(furniture_bollards)
    rings_clustered_utm17N = geopandas.GeoDataFrame(
        pd.concat([furniture_not_bollards, agg_bollards], ignore_index=True)
    ).convert_dtypes()

    # Downstream: Rack Deduplication
    # ------------------------------
    print("Applying downstream processing: Rack Deduplication...")

    city_racks_test = (
        rings_clustered_utm17N["meta_source"].eq("City of Toronto", fill_value=False)
    ) & (rings_clustered_utm17N["bicycle_parking"].eq("rack", fill_value=False))
    city_racks = rings_clustered_utm17N[city_racks_test]
    not_city_racks = rings_clustered_utm17N[~city_racks_test]
    assert len(city_racks) + len(not_city_racks) == len(rings_clustered_utm17N)

    # run rack clustering
    agg_racks = group_proximate_racks(city_racks)
    racks_clustered_utm17N = geopandas.GeoDataFrame(
        pd.concat([not_city_racks, agg_racks], ignore_index=True)
    ).convert_dtypes()

    # convert back to WGS 84
    all_sources = racks_clustered_utm17N.to_crs("EPSG:4326")

    # Save display files
    # ------------------
    print("Saving display files...")

    save_output(
        all_sources[all_sources["meta_source"].eq("City of Toronto", fill_value=False)],
        path=dfp,
        file_name="open_toronto_ca.geojson",
        archive_name=archive_name,
        na="drop",
    )
    save_output(
        all_centroid_utm17N[
            all_centroid_utm17N["meta_source"].eq("City of Toronto", fill_value=False)
        ].to_crs("EPSG:4326"),
        path=dfp,
        file_name="open_toronto_ca_unclustered.geojson",
        archive_name=archive_name,
        na="drop",
    )
    save_output(
        all_sources[all_sources["meta_source"].eq("OpenStreetMap", fill_value=False)],
        path=dfp,
        file_name="openstreetmap.geojson",
        archive_name=archive_name,
        na="drop",
    )
    save_output(  # unmapped lockers
        all_sources[
            all_sources["meta_source_dataset"].eq(
                "City of Toronto Bicycle Locker webpage", fill_value=False
            )
        ],
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

    update_bicycle_parking(archive=args.archive)
