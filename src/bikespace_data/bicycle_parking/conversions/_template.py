# Filter and Transform maps for "INSERT NAME" dataset
# "meta_" attributes are included for the BikeSpace map but should not be uploaded to OpenStreetMap
# make sure to add lookup to "_get_map" in __init__.py and to add module to imports

import re
from typing import TypedDict, Required, Literal

_dataset_name = "INSERT NAME"  # e.g. bicycle-parking-high-capacity-outdoor


# EXPECTED INPUT
# --------------

# TODO enforce typing?
# Documents expected input values
# `total=False` makes all fields optional unless enclosed in `Required[...]`
# examples of typing: int, str, float, Literal["Yes", "No"]
InputProps = TypedDict(
    "InputProps",
    {
        "EXAMPLE_KEY": Required[int],
        "REGEX_EXAMPLE": Required[str],
        "IGNORED_KEY": str,
    },
    total=False,
)


# FILTERS
# -------

# use `return True` if there are no filters applied
# Function should take a dict of properties and return True/False.


def filter_properties(input_props: InputProps):
    return True if input_props["EXAMPLE_KEY"] > 0 else False


# TRANSFORMS
# ----------

# At least one source attribute should be transformed


# Function example
# valx = "Regex Name (10)" -->
#   {"meta_regex_name": "Regex Name", "meta_regex_number": "10"}
def _convert_regex_example(input_val):
    match = re.search(r"\s*?(?P<name>.+?)\s*?\(\s*?(?P<number>\d+?)\s*?\)", input_val)
    if match:
        return {
            "meta_regex_name": match.group("name"),
            "meta_regex_number": match.group("number"),
        }
    else:
        return {"meta_regex_name": "", "meta_regex_number": ""}


# Function should take a dict of properties and an optional dict of global_properties and return a new dict with the transformed keys and values.
# To just rename the key, do `"newkey": input_props['OLD_KEY']`
# Other values may be more complex and require some processing (e.g. or a function
# For functions that return a dict of multiple values, you can set a placeholder for the attribute order with `"newkey": None` and then merge in the dict at the end
# Global Props are used to indicate values common to all features e.g. data source, date source was last updated


def transform_properties(input_props: InputProps, global_props: dict):
    return (
        {
            "amenity": "bicycle_parking",
            "bicycle_parking": None,
            "capacity": None,
            "operator": None,
            "covered": None,
            "access": None,
            "fee": None,
            "colour": None,  # optional
            "description": None,  # optional
            "image": None,  # optional
            "meta_regex_name": None,  # example placeholder
            "meta_regex_number": None,  # example placeholder
        }
        | _convert_regex_example(input_props["REGEX_EXAMPLE"])  # example merge
        | global_props
    )
