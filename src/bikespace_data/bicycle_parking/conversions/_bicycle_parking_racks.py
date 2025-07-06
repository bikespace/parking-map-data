# Filter and Transform maps for "bicycle-parking-racks" dataset
# "meta_" attributes are included for the BikeSpace map but should not be uploaded to OpenStreetMap

import re
from typing import TypedDict, Required, Literal

_dataset_name = "bicycle-parking-racks"


# EXPECTED INPUT
# --------------

# TODO enforce typing?
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
                "ETOBICOKE",
                "NORTH YORK",
                "SCARBOROUGH",
                "YORK",
                "EAST YORK",
                "former TORONTO",
            ]
        ],
        "CITY": Literal["Toronto"],
        "CENTRELINE_ID": int,
        "LO_NUM": int,
        "LO_NUM_SUF": str,
        "HI_NUM": int,
        "HI_NUM_SUF": str,
        "LINEAR_NAME_ID": float,
        "WARD_NAME": Required[str],
        "MI_PRINX": int,
        "OBJECTID": Required[int],
        "CAPACITY": Required[int],
        "MULTIMODAL": Literal["No", "Yes", " ", ""],
        "SEASONAL": Required[Literal["No", "Yes", " ", ""]],
        "SHELTERED": Required[Literal["No", "Yes", " ", ""]],
        "SURFACE": str,
        "STATUS": Required[
            str
        ],  # 'Delivered', 'Installed', 'Approved', 'Proposed', 'TBD'
        "LOCATION": Required[str],
        "NOTES": Required[str],
        "MAP_CLASS": Required[
            Literal[
                "Multi-Bike Rack",
                "Multi-Bike Rack (Angled)",
                "Bike Shelter",
                "Bike Corral",
            ]
        ],
    },
    total=False,
)


# FILTERS
# -------


def filter_properties(input_props: InputProps):
    return True if input_props["STATUS"] == "Installed" else False


# TRANSFORMS
# ----------


def _convert_ward_name(input_val):
    match = re.search(
        r"\s*?(?P<ward_name>.+?)\s*?\(\s*?(?P<ward_number>\d+?)\s*?\)", input_val
    )
    if match:
        return {
            "meta_ward_name": match.group("ward_name"),
            # ward number is sliced to last two digits since output is often repeated e.g. "1010" or "707"
            "meta_ward_number": match.group("ward_number")[-2:],
        }
    else:
        return {"meta_ward_name": None, "meta_ward_number": None}


def _convert_seasonal(input_val):
    if input_val == "Yes":
        return {
            "seasonal": "yes",
            "meta_about_seasonality": """Seasonality: "[seasonal parking is] typically removed before plowing season (starting December 1), and re-installed in the springtime" source: https://www.toronto.ca/services-payments/streets-parking-transportation/cycling-in-toronto/bicycle-parking/""",
        }
    elif input_val == "No":
        return {"seasonal": "no"}
    else:
        return {"seasonal": None}


def transform_properties(input_props: InputProps, global_props: dict):
    return (
        {
            "amenity": "bicycle_parking",
            "bicycle_parking": "rack",
            "capacity": input_props["CAPACITY"],
            "operator": "City of Toronto",
            "covered": input_props["SHELTERED"].strip().lower(),
            "access": "yes",
            "fee": "no",
            "description": "\n\n".join(
                x.strip()
                for x in [
                    (
                        "Address: " + input_props["ADDRESS_FULL"]
                        if input_props["ADDRESS_FULL"].strip()
                        else ""
                    ),
                    (
                        "Notes: " + input_props["NOTES"]
                        if input_props["NOTES"].strip()
                        else ""
                    ),
                    (
                        "Location: " + input_props["LOCATION"]
                        if input_props["LOCATION"].strip()
                        else ""
                    ),
                    _convert_seasonal(input_props["SEASONAL"]).get(
                        "meta_about_seasonality", ""
                    ),
                ]
                if x.strip()
            ),
            "seasonal": _convert_seasonal(input_props["SEASONAL"])["seasonal"],
            f"ref:open.toronto.ca:{_dataset_name}:objectid": input_props["OBJECTID"],
            "meta_borough": input_props["MUNICIPALITY"].title(),
            "meta_ward_name": None,  # placeholder
            "meta_ward_number": None,  # placeholder
            "meta_status": input_props["STATUS"],
        }
        | _convert_ward_name(input_props["WARD_NAME"])  # updates placeholders
        | global_props
    )
