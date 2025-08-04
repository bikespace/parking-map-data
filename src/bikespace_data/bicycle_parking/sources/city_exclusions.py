from itertools import chain
from typing import TypedDict, Literal, Required

import requests


class CityExclusion(TypedDict, total=False):
    survey_date: str  # iso YYYY-MM-DD format
    ids: Required[list[dict[str, str]]]
    reason: Literal["removed", "missing", "area_survey"]


def get_city_exclusions(
    url: str = "https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/data/bicycle_parking/city_modifications/open_toronto_ca_exclusions.json",
) -> list[CityExclusion]:
    """Gets city exclusions from data branch. Implemented as a url request to prepare for later switch to hosting exclusions via API."""
    response = requests.get(url)

    if response.status_code != 200:
        raise Exception(
            f"Could not get city exclusions from resource url. Resource returned status {response.status_code}"
        )

    city_exclusions = response.json()
    return city_exclusions


def city_exclusions_getids(
    city_exclusions: list[CityExclusion],
) -> dict[str, list[str]]:
    """Convert city exclusions source format into a dict for pandas .isin checks, e.g.

    from: `[{ids: {"key": "value1"}}, {ids: {"key": "value2"}}]`

    to: `{"key": ["value1", "value2"]}`
    """
    city_exclusions_ids = list(chain.from_iterable([x["ids"] for x in city_exclusions]))

    city_exclusions_dict = {}
    for id in city_exclusions_ids:
        [[k, v]] = id.items()
        city_exclusions_dict.setdefault(k, [])
        city_exclusions_dict[k].append(v)

    return city_exclusions_dict
