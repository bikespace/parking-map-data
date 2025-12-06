import math
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict
from zoneinfo import ZoneInfo

import geopandas as gpd
import pandas as pd
import pandera.pandas as pa

from bikespace_data.apartments.geocode_missing import AddressCache, geocode_missing
from bikespace_data.resources.toronto_open_data import request_tod_df, request_tod_gdf
from bikespace_data.utilities import StatusManager, save_geo_output


def get_building_registrations(
    source_save_path: Path | None = None,
    archive_path: Path | None = None,
    status_manager: StatusManager | None = None,
):
    """
    Get the [building registration data](https://open.toronto.ca/dataset/apartment-building-registration/) from the City of Toronto Open Data portal, validate that it contains the expected columns, and extract the number of indoor and outdoor bicycle parking spots from the "BIKE_PARKING" column.

    Returns the registration data with added columns "bike_parking_indoor" and "bike_parking_outdoor".
    """
    response = request_tod_df(
        dataset_name="apartment-building-registration",
        resource_id="97b8b7a4-baca-49c7-915d-335322dbcf95",
    )
    df = response["df"]

    # save original if requested
    if source_save_path is not None:
        df.to_csv(source_save_path / "building_registrations.csv")

    # archive if requested
    if archive_path is not None:
        archive_path.mkdir(exist_ok=True, parents=True)
        df.to_parquet(archive_path / "building_registrations.parquet")

    # log in status manager if requested
    if status_manager is not None:
        last_updated = datetime.fromisoformat(response["metadata"]["last_modified"])
        status_manager.add(
            dataset_name="apartment-building-registration",
            last_updated=last_updated,
            num_features=len(df),
            last_checked=datetime.now(timezone.utc),
        )

    schema = pa.DataFrameSchema(
        {
            "BIKE_PARKING": pa.Column(str, required=True),
            "CONFIRMED_STOREYS": pa.Column(int),
            "CONFIRMED_UNITS": pa.Column(int),
            "PROP_MANAGEMENT_COMPANY_NAME": pa.Column(str, nullable=True),
            "PROPERTY_TYPE": pa.Column(
                str,
                nullable=True,
                checks=pa.Check.isin(["PRIVATE", "TCHC", "SOCIAL HOUSING"]),
            ),
            "RSN": pa.Column(int, required=True, unique=True),
            "SITE_ADDRESS": pa.Column(str, required=True),
            "WARD": pa.Column(int),
            "YEAR_BUILT": pa.Column(int, nullable=True),
            "YEAR_OF_REPLACEMENT": pa.Column(int, nullable=True),
            "YEAR_REGISTERED": pa.Column(int, nullable=True),
        },
        strict="filter",
    )
    vdf = schema.validate(df, lazy=True)

    BIKE_PARKING_PATTERN = r"(?P<bike_parking_indoor>\d+) indoor parking spots and (?P<bike_parking_outdoor>\d+) outdoor parking spots"
    bike_parking_matches = vdf["BIKE_PARKING"].str.extract(BIKE_PARKING_PATTERN)
    vdf = vdf.join(bike_parking_matches)
    vdf["bike_parking_indoor"] = pd.to_numeric(vdf["bike_parking_indoor"])
    vdf["bike_parking_outdoor"] = pd.to_numeric(vdf["bike_parking_outdoor"])

    return vdf


def get_building_evaluations(
    source_save_path: Path | None = None,
    archive_path: Path | None = None,
):
    """
    Get the [building evaluations datasets](https://open.toronto.ca/dataset/apartment-building-evaluation/) from the City of Toronto Open Data portal,  validate that each dataset contains the expected columns, and combine the datasets.

    The function returns a Pandas Dataframe with the "RSN" id for each building along with latitude and longitude coordinates extracted from the evaluations data.

    Unlike the building registration data (which only includes street addresses), this data contains coordinates for each location in one or both of the following formats:

    - latitude / longitude (assumed to be EPSG:4326)
    - x / y (EPSG:7991 - MTM Zone 10 NAD27)

    If one or more latitude / longitude values are found for a building, the average of those values is returned. If there are no latitude / longitude values found, the average of any available x / y coordinates are converted into latitutde and longitude and returned instead. If no coordinates are found in either format, then the building is not included within the return dataset.

    There are two datasets for building evaluations:

    - evaluations conducted 2023 and later
    - evaluations conducted prior to 2023

    The coordinate information in both datasets is similar, though with slight variances in column naming.
    """
    response_2023_plus = request_tod_df(
        dataset_name="apartment-building-evaluation",
        resource_id="7fa98ab2-7412-43cd-9270-cb44dd75b573",
    )
    df_2023_plus = response_2023_plus["df"]

    # save original if requested
    if source_save_path is not None:
        df_2023_plus.to_csv(source_save_path / "building_evaluations_2023_plus.csv")

    # archive if requested
    if archive_path is not None:
        archive_path.mkdir(exist_ok=True, parents=True)
        df_2023_plus.to_parquet(archive_path / "building_evaluations_2023_plus.parquet")

    schema_2023_plus = pa.DataFrameSchema(
        {
            "RSN": pa.Column("int64", required=True),
            "SITE ADDRESS": pa.Column(str, required=True),
            "LATITUDE": pa.Column("float64", nullable=True),
            "LONGITUDE": pa.Column("float64", nullable=True),
            "X": pa.Column("float64", nullable=True),
            "Y": pa.Column("float64", nullable=True),
        },
        strict="filter",
        # Ensure that each entry has either a valid lat/long or x/y
        checks=[
            pa.Check(
                lambda df: ~(df["LONGITUDE"].isna() & df["X"].isna()),
                name="Has a valid long or x value",
            ),
            pa.Check(
                lambda df: ~(df["LATITUDE"].isna() & df["Y"].isna()),
                name="Has a valid lat or y value",
            ),
        ],
        # drop rows that fail validation
        drop_invalid_rows=True,
    )
    vdf_2023_plus = schema_2023_plus.validate(df_2023_plus, lazy=True).rename(
        columns={"SITE ADDRESS": "SITE_ADDRESS"}
    )

    response_prior = request_tod_df(
        dataset_name="apartment-building-evaluation",
        resource_id="979fb513-5186-41e9-bb23-7b5cc6b89915",
    )
    df_prior = response_prior["df"]

    # save original if requested
    if source_save_path is not None:
        df_prior.to_csv(source_save_path / "building_evaluations_prior_to_2023.csv")

    # archive if requested
    if archive_path is not None:
        df_prior.to_parquet(archive_path / "building_evaluations_prior_to_2023.parquet")

    schema_prior = pa.DataFrameSchema(
        {
            "RSN": pa.Column("int64", required=True),
            "SITE_ADDRESS": pa.Column(str, required=True),
            "LATITUDE": pa.Column("float64", nullable=True),
            "LONGITUDE": pa.Column("float64", nullable=True),
            "X": pa.Column("float64", nullable=True),
            "Y": pa.Column("float64", nullable=True),
        },
        strict="filter",
        # Ensure that each entry has either a valid lat/long or x/y
        checks=[
            pa.Check(
                lambda df: ~(df["LONGITUDE"].isna() & df["X"].isna()),
                name="Has a valid long or x value",
            ),
            pa.Check(
                lambda df: ~(df["LATITUDE"].isna() & df["Y"].isna()),
                name="Has a valid lat or y value",
            ),
        ],
        # drop rows that fail validation
        drop_invalid_rows=True,
    )
    vdf_prior = schema_prior.validate(df_prior, lazy=True)

    df_all = (
        pd.concat([vdf_2023_plus, vdf_prior])
        .groupby("RSN")
        .agg(
            {
                "SITE_ADDRESS": "first",
                "LATITUDE": "median",
                "LONGITUDE": "median",
                "X": "median",
                "Y": "median",
            }
        )
    )

    schema_all = pa.DataFrameSchema(
        # Ensure that each entry has either a valid lat/long or x/y
        checks=[
            pa.Check(
                lambda df: ~(df["LONGITUDE"].isna() & df["X"].isna()),
                name="Has a valid long or x value",
            ),
            pa.Check(
                lambda df: ~(df["LATITUDE"].isna() & df["Y"].isna()),
                name="Has a valid lat or y value",
            ),
        ],
        # drop rows that fail validation
        drop_invalid_rows=True,
    )
    vdf_all = schema_all.validate(df_all, lazy=True)

    xy_converted = gpd.GeoSeries.from_xy(
        x=vdf_all["X"],
        y=vdf_all["Y"],
        index=vdf_all.index,
        crs="EPSG:7991",  # MTM Zone 10 NAD27 EPSG:7991 - see https://www.toronto.ca/city-government/data-research-maps/maps/purchase-maps-data/mapping-glossary/
    ).to_crs("EPSG:4326")

    vdf_all["LONGITUDE"] = vdf_all["LONGITUDE"].fillna(xy_converted.x)
    vdf_all["LATITUDE"] = vdf_all["LATITUDE"].fillna(xy_converted.y)

    output = vdf_all.drop(columns=["X", "Y"])
    return output


class ZoningRequirements(TypedDict):
    short_term_min: int | pd.api.typing.NAType
    short_term_max: int | pd.api.typing.NAType
    long_term_min: int | pd.api.typing.NAType
    long_term_max: int | pd.api.typing.NAType
    long_term_oversized_min: int | pd.api.typing.NAType
    long_term_oversized_max: int | pd.api.typing.NAType


def calculate_zoning_requirement(row) -> ZoningRequirements:
    """
    Calculate the required number of bicycle parking spaces under the current zoning by-law using the BICYCLE_ZONE and CONFIRMED_UNITS columns.

    Assumes that all buildings are in the "Apartment or Mixed Use with Dwelling Units" category and not "Residential Care Home, Retirement Home, Nursing Home" or "Student Residence" (for which there are lower rates).
    """
    # guard in case required fields are null or improper
    if pd.isna(row["BICYCLE_ZONE"]) or pd.isna(row["CONFIRMED_UNITS"]):
        return {
            "short_term_min": pd.NA,
            "short_term_max": pd.NA,
            "long_term_min": pd.NA,
            "long_term_max": pd.NA,
            "long_term_oversized_min": pd.NA,
            "long_term_oversized_max": pd.NA,
        }
    if row["BICYCLE_ZONE"] not in [1, 2]:
        raise TypeError(
            f"{row['BICYCLE_ZONE']} is not an expected bicycle zone (supported values are int 1 or 2)"
        )
    if not pd.api.types.is_integer(row["CONFIRMED_UNITS"]):
        raise TypeError(
            f"{row['CONFIRMED_UNITS']} is not an expected integer (whole number)"
        )

    # set multiplier by bicycle zone
    unit_multipliers: dict = {}
    if row["BICYCLE_ZONE"] == 1:
        unit_multipliers["short_term"] = 0.2
        unit_multipliers["long_term"] = 0.9
    elif row["BICYCLE_ZONE"] == 2:
        unit_multipliers["short_term"] = 0.07
        unit_multipliers["long_term"] = 0.68

    # requirement is rounded up to nearest whole number
    short_term_max = math.ceil(unit_multipliers["short_term"] * row["CONFIRMED_UNITS"])
    long_term_max = math.ceil(unit_multipliers["long_term"] * row["CONFIRMED_UNITS"])

    # payment in lieu allows for 50% reduction in short term; reduction amount is rounded down (i.e. total is rounded up after dividing by two)
    short_term_min = math.ceil(short_term_max * 0.5)
    long_term_min = math.ceil(long_term_max * 0.5)

    # number of oversized bike parking spaces is based on 5% of the long-term spaces times (including any payment in lieu adjustments), rounded down
    long_term_oversized_min = math.floor(long_term_min * 0.05)
    long_term_oversized_max = math.floor(long_term_max * 0.05)

    return {
        "short_term_min": short_term_min,
        "short_term_max": short_term_max,
        "long_term_min": long_term_min,
        "long_term_max": long_term_max,
        "long_term_oversized_min": long_term_oversized_min,
        "long_term_oversized_max": long_term_oversized_max,
    }


def get_wards_gdf(
    source_save_path: Path | None = None,
    archive_name: str | None = None,
) -> gpd.GeoDataFrame:
    """Retrieves, simplifies, and saves data from the City Wards dataset from open.toronto.ca"""

    wards = request_tod_gdf(
        dataset_name="city-wards",
        resource_id="737b29e0-8329-4260-b6af-21555ab24f28",
    )

    # save original (and optionally archive) if requested
    if source_save_path is not None:
        save_geo_output(
            wards["gdf"],
            path=source_save_path,
            file_name="wards.geojson",
            archive_name=archive_name,
        )

    wards_formatted = (
        wards["gdf"][["AREA_SHORT_CODE", "AREA_NAME", "geometry"]]
        .assign(
            ward_full=[
                f"{x.AREA_NAME} ({x.AREA_SHORT_CODE})"
                for x in wards["gdf"].itertuples()
            ]
        )
        .rename(
            columns={
                "AREA_SHORT_CODE": "ward_code",
                "AREA_NAME": "ward_name",
            }
        )
    )
    return wards_formatted


def get_neighbourhoods_gdf(
    source_save_path: Path | None = None,
    archive_name: str | None = None,
) -> gpd.GeoDataFrame:
    "Retrieves and simplifies from https://open.toronto.ca/dataset/neighbourhoods/"
    response = request_tod_gdf(
        dataset_name="neighbourhoods",
        resource_id="0719053b-28b7-48ea-b863-068823a93aaa",
    )
    gdf = response["gdf"]

    # save original (and optionally archive) if requested
    if source_save_path is not None:
        save_geo_output(
            gdf,
            path=source_save_path,
            file_name="neighbourhoods.geojson",
            archive_name=archive_name,
        )

    gdf_formatted = gdf[
        [
            "AREA_SHORT_CODE",
            "AREA_NAME",
            "CLASSIFICATION",
            "CLASSIFICATION_CODE",
            "geometry",
        ]
    ].rename(
        columns={
            "AREA_SHORT_CODE": "neighbourhood_number",
            "AREA_NAME": "neighbourhood_name",
            "CLASSIFICATION": "neighbourhood_classification",
            "CLASSIFICATION_CODE": "neighbourhood_classification_code",
        }
    )
    return gdf_formatted


def get_bike_parking_info(
    status_path: Path = Path("apartments/statuses/apartments_status.csv"),
    output_path: Path = Path("apartments"),
    address_cache_path: Path = Path("apartments/address_cache/address_cache.json"),
    bicycle_policy_zones_path: Path = Path(
        "src/bikespace_data/apartments/Toronto_Bicycle_Policy_Zones.geojson"
    ),
    archive=False,
):
    """
    Get data on bicycle parking for apartments from a variety of RentSafeTO datasets from the Open Data Portal and calculate the amount of bicycle parking that would be required for each building if it were built under current zoning rules.

    For any apartments where the geolocation cannot be determined from the evaluations data, the location is reverse geocoded using nominatim.
    """
    today_toronto_isodate = datetime.now(ZoneInfo("America/Toronto")).strftime(
        "%Y-%m-%d"
    )

    sm = StatusManager(
        status_source=f"https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/data/{str(status_path)}",
        status_save=status_path,
    )
    (output_path / "source_files").mkdir(exist_ok=True, parents=True)
    (output_path / "output_files").mkdir(exist_ok=True, parents=True)
    (output_path / "display_files").mkdir(exist_ok=True, parents=True)

    # contains statistics on building bicycle parking
    building_registrations = get_building_registrations(
        source_save_path=output_path / "source_files",
        archive_path=output_path / "source_files" / f"archive/{today_toronto_isodate}"
        if archive
        else None,
        status_manager=sm,
    )

    # contains geolocation for most buildings
    building_evaluations = get_building_evaluations(
        source_save_path=output_path / "source_files",
        archive_path=output_path / "source_files" / f"archive/{today_toronto_isodate}"
        if archive
        else None,
    )
    joined = building_registrations.merge(building_evaluations, how="left", on="RSN")

    # add missing geolocations
    address_cache = AddressCache(
        source_path=f"https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/data/{str(address_cache_path)}",
        save_path=address_cache_path,
    )
    geocode_result = geocode_missing(
        joined, "LATITUDE", "LONGITUDE", "SITE_ADDRESS_x", address_cache.cache
    )
    joined_geocoded = geocode_result["df"]
    updated_cache = geocode_result["address_cache"]

    address_cache.cache = updated_cache
    address_cache.save_cache()

    schema_joined_geocoded = pa.DataFrameSchema(
        # Ensure that each entry has a valid lat/long
        checks=[
            pa.Check(
                lambda df: ~df["LONGITUDE"].isna(),
                name="Has a valid longitude value",
                raise_warning=True,
            ),
            pa.Check(
                lambda df: ~df["LATITUDE"].isna(),
                name="Has a valid latitude value",
                raise_warning=True,
            ),
        ],
    )
    joined_validated = schema_joined_geocoded.validate(joined_geocoded, lazy=True)

    gdf = gpd.GeoDataFrame(
        joined_validated,
        geometry=gpd.GeoSeries.from_xy(
            x=joined_validated["LONGITUDE"],
            y=joined_validated["LATITUDE"],
            crs="EPSG:4326",
        ),
    )

    # add city wards
    wards = get_wards_gdf(
        source_save_path=output_path / "source_files",
        archive_name=f"archive/{today_toronto_isodate}" if archive else None,
    )
    gdf_with_wards = gdf.sjoin(wards, how="left").drop(columns=["index_right"])

    # add city neighbourhoods
    neighbourhoods = get_neighbourhoods_gdf(
        source_save_path=output_path / "source_files",
        archive_name=f"archive/{today_toronto_isodate}" if archive else None,
    )
    gdf_with_neighbourhoods = gdf_with_wards.sjoin(neighbourhoods, how="left").drop(
        columns=["index_right"]
    )

    # add city bicycle parking zoning policy areas
    bicycle_parking_zones = gpd.GeoDataFrame.from_file(bicycle_policy_zones_path)
    gdf_with_zones = gdf_with_neighbourhoods.sjoin(
        bicycle_parking_zones, how="left"
    ).drop(columns=["index_right"])

    gdf_with_zoning_reqs = gdf_with_zones.assign(
        zoning_reqs=gdf_with_zones[["BICYCLE_ZONE", "CONFIRMED_UNITS"]].apply(
            calculate_zoning_requirement, axis=1
        )  # type: ignore
    )
    gdf_split_zoning_reqs = gpd.GeoDataFrame(
        pd.concat(
            [
                gdf_with_zoning_reqs,
                pd.json_normalize(gdf_with_zoning_reqs["zoning_reqs"]),  # type: ignore
            ],
            axis=1,
        ).drop(columns=["zoning_reqs"])
    )

    gdf_unmet_need = gdf_split_zoning_reqs.assign(
        short_term_min_unmet=gdf_split_zoning_reqs["short_term_min"]
        - gdf_split_zoning_reqs["bike_parking_outdoor"].fillna(0),
        short_term_max_unmet=gdf_split_zoning_reqs["short_term_max"]
        - gdf_split_zoning_reqs["bike_parking_outdoor"].fillna(0),
        long_term_min_unmet=gdf_split_zoning_reqs["long_term_min"]
        - gdf_split_zoning_reqs["bike_parking_indoor"].fillna(0),
        long_term_max_unmet=gdf_split_zoning_reqs["long_term_max"]
        - gdf_split_zoning_reqs["bike_parking_indoor"].fillna(0),
    ).convert_dtypes()

    gdf_unmet_need["total_unmet_min"] = (
        gdf_unmet_need["short_term_min_unmet"] + gdf_unmet_need["long_term_min_unmet"]
    )
    gdf_unmet_need["total_req_min"] = (
        gdf_unmet_need["short_term_min"] + gdf_unmet_need["long_term_min"]
    )
    gdf_unmet_need["pc_unmet"] = round(
        gdf_unmet_need["total_unmet_min"] / gdf_unmet_need["total_req_min"],
        2,
    )

    # output
    save_geo_output(
        gdf_unmet_need,
        path=output_path / "output_files",
        file_name="apartments.geojson",
        archive_name=f"archive/{today_toronto_isodate}" if archive else None,
    )
    gdf_unmet_need.to_csv(output_path / "output_files" / "apartments.csv")

    # filtered output for mapping
    save_geo_output(
        gdf_unmet_need[
            [
                "CONFIRMED_UNITS",
                "bike_parking_indoor",
                "long_term_min",
                "long_term_max",
                "bike_parking_outdoor",
                "short_term_min",
                "short_term_max",
                "total_req_min",
                "total_unmet_min",
                "pc_unmet",
                "long_term_oversized_min",
                "long_term_oversized_max",
                "geometry",
            ]
        ],
        path=output_path / "display_files",
        file_name="apartments_bicycle_parking_display.geojson",
        archive_name=f"archive/{today_toronto_isodate}" if archive else None,
    )


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

    get_bike_parking_info(archive=args.archive)
