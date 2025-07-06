# Filter and Transform maps for "toronto_lockers" dataset
# "meta_" attributes are included for the BikeSpace map but should not be uploaded to OpenStreetMap

import re
import geopandas as gpd
import pandas as pd
import pandera as pa


_dataset_name = "toronto_lockers"


# EXPECTED INPUT
# --------------

response_schema_toronto_lockers = pa.DataFrameSchema(
    {
        "location": pa.Column(str, required=True),
        "location_description": pa.Column(str, required=True),
        "quantity": pa.Column(str, required=True),
        "geometry": pa.Column("geometry"),
    }
)


# FILTERS
# -------


def filter_properties(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    filtered_gdf = response_schema_toronto_lockers.validate(gdf, lazy=True)
    return filtered_gdf


# TRANSFORMS
# ----------


def transform_properties(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    original_cols = gdf.columns.drop("geometry")

    CAPACITY_PATTERN = r"# of lockers:? (?P<capacity>\d+)"

    transformed_gdf = gdf.assign(
        **{
            "amenity": "bicycle_parking",
            "bicycle_parking": "lockers",
            "capacity": pd.to_numeric(
                gdf["quantity"].str.extract(
                    CAPACITY_PATTERN, expand=False, flags=re.IGNORECASE
                )
            ),
            "covered": "yes",
            "fee": "yes",
            "operator": "City of Toronto",
            "operator:type": "government",
            "access": "customers",
            "website": "https://www.toronto.ca/services-payments/streets-parking-transportation/cycling-in-toronto/bicycle-parking/bicycle-lockers/",
            "description": gdf["location"] + ": " + gdf["location_description"],
        }
    ).drop(original_cols, axis=1)

    return transformed_gdf
