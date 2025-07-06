# Filter and Transform maps for "bicycle-parking-high-capacity-outdoor" dataset
# "meta_" attributes are included for the BikeSpace map but should not be uploaded to OpenStreetMap

import re
from typing import TypedDict, Required, Literal

_dataset_name = "bicycle-parking-high-capacity-outdoor"


# EXPECTED INPUT
# --------------

# TODO enforce typing?
# examples of typing: int, str, float, Literal["Yes", "No"]
InputProps = TypedDict(
    "InputProps",
    {
        "_id": int,
        "ADDRESS_POINT_ID": int,
        "ADDRESS_NUMBER": str,
        "LINEAR_NAME_FULL": str,
        "ADDRESS_FULL": Required[str],
        "POSTAL_CODE": str,
        "MUNICIPALITY": Required[
            Literal[
                "Etobicoke",
                "North York",
                "Scarborough",
                "York",
                "East York",
                "former Toronto",
            ]
        ],
        "CITY": Literal["Toronto"],
        "WARD": Required[str],
        "PLACE_NAME": Required[str],
        "GENERAL_USE_CODE": int,
        "CENTRELINE_ID": int,
        "LO_NUM": int,
        "LO_NUM_SUF": str,
        "HI_NUM": int,
        "HI_NUM_SUF": str,
        "LINEAR_NAME_ID": int,
        "ID": Required[int],
        "PARKING_TYPE": Required[
            Literal["Bike Rack", "Angled Bike Rack", "Bike Corral", "Bike Shelter"]
        ],
        "FLANKING": Required[str],
        "BICYCLE_CAPACITY": Required[int],
        "SIZE_M": Required[str],
        "YEAR_INSTALLED": Required[int],
        "BY_LAW": Literal["N/A", "NO", "Y", ""],
        "DETAILS": Required[str],  # blank throughout dataset
        "OBJECTID": Required[int],
    },
    total=False,
)


# FILTERS
# -------


# no filters applied
def filter_properties(input_props: InputProps):
    return True


# TRANSFORMS
# ----------

# TODO ground truth meaning of flanking field
# TODO check if leaving blank install date years as zero causes problems


def _convert_ward(input_val):
    match = re.search(
        r"\s*?(?P<ward_name>.+?)\s*?\(\s*?(?P<ward_number>\d+?)\s*?\)", input_val
    )
    if match:
        return {
            "meta_ward_name": match.group("ward_name"),
            "meta_ward_number": match.group("ward_number"),
        }
    else:
        return {"meta_ward_name": None, "meta_ward_number": None}


# TODO need to ground truth classification
def _convert_parking_type(input_val):
    value = {
        "Bike Rack": "rack",
        "Angled Bike Rack": "rack",
        "Bike Corral": "rack",
        "Bike Shelter": "rack",
    }.get(input_val, None)  # return null if a new type is added
    return value


def _is_covered(input_val):
    value = {
        "Bike Rack": "no",
        "Angled Bike Rack": "no",
        "Bike Corral": "no",
        "Bike Shelter": "yes",
    }.get(input_val, None)  # return null if a new type is added
    return value


def transform_properties(input_props: InputProps, global_props: dict):
    return (
        {
            "amenity": "bicycle_parking",
            "bicycle_parking": _convert_parking_type(input_props["PARKING_TYPE"]),
            "capacity": input_props["BICYCLE_CAPACITY"],
            "operator": "City of Toronto",
            "covered": _is_covered(input_props["PARKING_TYPE"]),
            "access": "yes",
            "fee": "no",
            "start_date": str(input_props["YEAR_INSTALLED"]),
            "length": str(input_props["SIZE_M"]),
            "description": "\n\n".join(
                x.strip()
                for x in [
                    (
                        "Address: " + input_props["ADDRESS_FULL"]
                        if input_props["ADDRESS_FULL"].strip()
                        else ""
                    ),
                    (
                        "Placement Street: " + input_props["FLANKING"]
                        if input_props["FLANKING"].strip()
                        else ""
                    ),
                    (
                        "Place Name: " + input_props["PLACE_NAME"]
                        if input_props["PLACE_NAME"].strip()
                        else ""
                    ),
                    (
                        "Details: " + input_props["DETAILS"]
                        if input_props["DETAILS"].strip()
                        else ""
                    ),
                ]
                if x.strip()
            ),
            f"ref:open.toronto.ca:{_dataset_name}:id": input_props["ID"],
            "meta_borough": input_props["MUNICIPALITY"].title(),
            "meta_ward_name": None,  # placeholder
            "meta_ward_number": None,  # placeholder
        }
        | _convert_ward(input_props["WARD"])  # updates placeholders
        | global_props
    )
