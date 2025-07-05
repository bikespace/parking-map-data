# Filter and Transform maps for "bicycle-parking-bike-stations-indoor" dataset
# "meta_" attributes are included for the BikeSpace map but should not be uploaded to OpenStreetMap

import re
from typing import TypedDict, Required, Literal

_dataset_name = "bicycle-parking-bike-stations-indoor"


# WEBSITE INFO
# ------------

# Additional key details derived from the City of Toronto webpage, accessed 2023-11
_website_address = "https://www.toronto.ca/services-payments/streets-parking-transportation/cycling-in-toronto/bicycle-parking/bicycle-parking-stations/"

# TODO need to ground truth the situation at Union - are there actually two stations (per the API) or is one of them just older and now defunct?
# TODO discrepancies in capacity reported - website 168, api 160 for Union; website 170, api 300 (!) for City Hall - have implemented override to be more conservative for City Hall and slightly edited blurb for Union.
# TODO add in website info for Eglinton Crosstown station when it opens

# key values are 'ADDRESS_FULL'
_station_descriptions = {
    "25 York St": """MAY BE DEFUNCT - NEEDS CONFIRMATION""",  # Union Station - Old?
    "777 Victoria Park Ave": """Located at the main entrance to Victoria Park Subway Station, the bicycle station offers secure, 24-hour bicycle parking with 52 bicycle parking spaces available on two-tier racks.""",  # Victoria Park
    "97 Front St W": """The Bicycle Station is located on the east side of York Street, just south of Front Street. The facility features [approximately 160] bike racks, a washroom, a change room and  a shower with complimentary towels, and an office where staff can register new members and renew bike station parking plans. Tools and pumps are available for members to perform minor repairs.""",  # Union Station
    "100 Queen St W": """The Nathan Phillips Square Bicycle Station is located in the underground parking facility at Toronto City Hall, 100 Queen Street West. The facility opened May 6, 2019 and includes 170 bicycle parking spaces, washrooms and showers, and a staff office. To visit the bike station on foot, use the “Squirrel” stairs or elevator, located between the skate rental and the snacks concession, to get to the P1 level of the parking garage, then follow the signs. Once you have access as a Bicycle Station member, you can ride your bike down the vehicle entrance on the north side of Queen St., just east of York St.  You can also wheel your bike down the stair channel on the Pedestrian Southbound Concourse stairway, on the sidewalk near where the food vendor trucks park on Queen Street.""",  # City Hall / Nathan Phillips Square
    "3955 Keele St": """The new TTC station at Finch and Keele features a bicycle station with secure parking for 68 bicycles. The facility opened to the public in October of 2018.""",  # Finch West
}


# EXPECTED INPUT
# --------------

# TODO enforce typing?

InputProps = TypedDict(
    "InputProps",
    {
        "_id": int,
        "ADDRESS_POINT_ID": float,
        "ADDRESS_NUMBER": Required[str],
        "LINEAR_NAME_FULL": Required[str],
        "ADDRESS_FULL": Required[str],
        "POSTAL_CODE": Required[str],
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
        "CITY": Required[Literal["Toronto"]],
        "WARD_NAME": Required[str],
        "PLACE_NAME": Required[str],
        "GENERAL_USE_CODE": int,
        "CENTRELINE_ID": int,
        "LO_NUM": int,
        "LO_NUM_SUF": str,
        "HI_NUM": int,
        "HI_NUM_SUF": str,
        "LINEAR_NAME_ID": float,
        "MI_PRINX": int,
        "OBJECTID": Required[str],
        "ID": Required[int],
        "STATION_TYPE": Literal["Bicycle Station"],
        "TRANSIT_STATION": Required[str],
        "FLANKING": Required[str],
        "BIKE_CAPACITY": Required[int],
        "CHANGE_ROOM": Required[Literal["Yes", "No", ""]],
        "VENDING_MACHINE": Required[Literal["Yes", "No", ""]],
        "TOOLS_PUMP": Required[Literal["Yes", "No", ""]],
        "YR_INSTALL": Required[int],
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


# revises capacity of City Hall / Nathan Phillips Square to 170 from website blurb instead of 300 from API - see note in website section
def _override_capacity(input_val, address_full):
    return 170 if address_full == "100 Queen St W" else input_val


def _get_place_name(place_name, transit_station):
    if place_name == "None" or not (place_name):
        return "Bicycle Parking Station at " + transit_station
    else:
        return "Bicycle Parking Station at " + place_name


# TODO consider whether address should be included (proper implementation for OSM would likely be as a relation)
# TODO consider proper implementation for other amenities (separate POI with relation?)


def transform_properties(input_props: InputProps, global_props: dict):
    return (
        {
            "amenity": "bicycle_parking",
            "bicycle_parking": "building",
            "capacity": _override_capacity(
                input_props["BIKE_CAPACITY"], input_props["ADDRESS_FULL"]
            ),
            "operator": "City of Toronto",
            "covered": "yes",
            "access": "customers",
            "fee": "yes",
            "supervised": "no",  # per the website, staff may be present from time to time at certain stations but are not dedicated to supervision and are not present during all access hours.
            "opening_hours": "Mo-Su,PH 00:00-24:00",  # 24/7 including holidays
            "description": "\n\n".join(
                x.strip()
                for x in [
                    (
                        "Access from: " + input_props["FLANKING"]
                        if input_props["FLANKING"].strip()
                        else ""
                    ),
                    _station_descriptions[input_props["ADDRESS_FULL"]],
                ]
                if x.strip()
            ),
            "website": _website_address,
            "name": _get_place_name(
                input_props["PLACE_NAME"], input_props["TRANSIT_STATION"]
            ),
            "addr:housenumber": input_props["ADDRESS_NUMBER"],
            "addr:street": input_props["LINEAR_NAME_FULL"],
            "addr:city": input_props["CITY"],
            "addr:postcode": input_props["POSTAL_CODE"],
            "start_date": str(input_props["YR_INSTALL"]),
            f"ref:open.toronto.ca:{_dataset_name}:id": input_props["ID"],
            f"ref:open.toronto.ca:{_dataset_name}:objectid": input_props["OBJECTID"],
            "meta_borough": input_props["MUNICIPALITY"].title(),
            "meta_ward_name": None,  # placeholder
            "meta_ward_number": None,  # placeholder
            "meta_has_change_room": input_props["CHANGE_ROOM"],  # amenity=dressing_room
            "meta_has_tools_and_pump": input_props[
                "TOOLS_PUMP"
            ],  #  amenity=bicycle_repair_station
            "meta_has_vending_machine": input_props[
                "VENDING_MACHINE"
            ],  # amenity=vending_machine
        }
        | _convert_ward_name(input_props["WARD_NAME"])  # updates placeholders
        | global_props
    )
