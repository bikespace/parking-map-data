# Filter and Transform maps for "osm_bicycle_parking_city_of_toronto" dataset
# "meta_" attributes are included for the BikeSpace map but should not be uploaded to OpenStreetMap

import re
from typing import TypedDict, Required, Literal

_dataset_name = "osm_bicycle_parking_city_of_toronto"


# EXPECTED INPUT
# --------------

# TODO enforce typing?

# FILTERS
# -------


# no filter applied
def filter_properties(gdf):
    """Takes a geodataframe of features and returns a filtered geodataframe"""
    return gdf


# TRANSFORMS
# ----------


def transform_properties(gdf, global_props: dict):
    pass


# https://www.openstreetmap.org/node/{id}
