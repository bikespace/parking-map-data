# Filter and Transform maps for "street-furniture-bicycle-parking" dataset
# "meta_" attributes are included for the BikeSpace map but should not be uploaded to OpenStreetMap

import re
from typing import TypedDict, Required, Literal, Any

_dataset_name = "street-furniture-bicycle-parking"


# EXPECTED INPUT
# --------------

# TODO enforce typing?

# examples of typing: int, str, float, Literal["Yes", "No"]
InputProps = TypedDict(
    "InputProps",
    {
        "_id": int,
        "OBJECTID": int,  # not a primary key - inconsistent between updates
        "ID": Required[str],  # primary key
        "ADDRESSNUMBERTEXT": str,
        "ADDRESSSTREET": str,
        "FRONTINGSTREET": str,
        "SIDE": str,
        "FROMSTREET": str,
        "DIRECTION": str,
        "SITEID": str,  # no idea what this means
        "WARD": Required[str],  # string of numerical id, e.g. "01" or "12"
        "BIA": Required[
            str
        ],  # unclear whether this denotes responsibility or proximity
        "ASSETTYPE": Required[
            Literal["Ring", "Rack", "Art Stand", "Shelter", "Other", ""]
        ],
        "STATUS": Required[Literal["Existing", "Temporarily Removed"]],
        "SDE_STATE_ID": float,
        "CLUSTER_ID": Any,  # all null in source data
    },
    total=False,
)


# SUPPLEMENTARY DATA
# ------------------

_toronto_ward_names = {
    "01": "Etobicoke North",
    "02": "Etobicoke Centre",
    "03": "Etobicoke-Lakeshore",
    "04": "Parkdale-High Park",
    "05": "York South-Weston",
    "06": "York Centre",
    "07": "Humber River-Black Creek",
    "08": "Eglinton-Lawrence",
    "09": "Davenport",
    "10": "Spadina-Fort York",
    "11": "University-Rosedale",
    "12": "Toronto-St. Paul’s",
    "13": "Toronto Centre",
    "14": "Toronto-Danforth",
    "15": "Don Valley West",
    "16": "Don Valley East",
    "17": "Don Valley North",
    "18": "Willowdale",
    "19": "Beaches-East York",
    "20": "Scarborough Southwest",
    "21": "Scarborough Centre",
    "22": "Scarborough-Agincourt",
    "23": "Scarborough North",
    "24": "Scarborough-Guildwood",
    "25": "Scarborough-Rouge Park",
}


# FILTERS
# -------


def filter_properties(input_props: InputProps):
    return True if input_props["STATUS"] == "Existing" else False


# TRANSFORMS
# ----------


def _get_bicycle_parking_type(assettype):
    parking_type = {
        "Ring": "bollard",
        "Rack": "rack",
        "Art Stand": "bollard",  # three entries as of 2023-11 marked as "temporarily removed", appear to be bollards per Google Street View History
        "Shelter": "rack",  # covered rack
        "Other": "stands",  # two entries as of 2023-11, checked on Google Street View
    }
    return parking_type.get(assettype, None)


def _get_bicycle_parking_capacity(assettype):
    parking_capacity = {
        "Ring": 2,
        "Rack": None,  # likely 6-8 in most cases, but unknown and may vary
        "Art Stand": 2,  # three entries as of 2023-11 marked as "temporarily removed", appear to be bollards per Google Street View History
        "Shelter": None,  # covered rack - appears to vary
        "Other": 2,  # two entries as of 2023-11, checked on Google Street View
    }
    return parking_capacity.get(assettype, None)


def transform_properties(input_props: InputProps, global_props: dict):
    return {
        "amenity": "bicycle_parking",
        "bicycle_parking": _get_bicycle_parking_type(input_props["ASSETTYPE"]),
        "capacity": _get_bicycle_parking_capacity(input_props["ASSETTYPE"]),
        "operator": "City of Toronto",
        "covered": "yes" if input_props["ASSETTYPE"] == "Shelter" else "no",
        "access": "yes",
        "fee": "no",
        f"ref:open.toronto.ca:{_dataset_name}:id": input_props["ID"],
        "meta_status": input_props["STATUS"],
        "meta_business_improvement_area": input_props["BIA"],
        "meta_ward_name": _toronto_ward_names.get(input_props["WARD"], None),
        "meta_ward_number": input_props["WARD"],
    } | global_props
