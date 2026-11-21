from pathlib import Path

import pandas as pd

from tts_tools.src.types import (
    CodeLookup,
    TTSAttribute,
    TTSBaseAttribute,
    TTSGeometry,
    TTSYear,
)

from .code_table_2022 import code_table_direct, code_table_range

SURVEY_YEAR: TTSYear = 2022

# generate lookup dicts to get properties by code or description
code_to_props_direct_2022 = {
    k: {p["code"]: p for p in props_list} for k, props_list in code_table_direct.items()
}
description_to_props_direct_2022 = {
    k: {p["description"]: p for p in props_list}
    for k, props_list in code_table_direct.items()
}
code_to_props_range_2022 = {
    k: {(p["code_min"], p["code_max"]): p for p in props_list}
    for k, props_list in code_table_range.items()
}
description_to_props_range_direct_2022 = {
    k: {p["description"]: p for p in props_list if p["type"] == "range_direct"}
    for k, props_list in code_table_range.items()
}


_geometry_types = ["accs", "dest", "egrs", "emp", "hhld", "orig", "sch"]


def get_geometry(key: TTSAttribute) -> TTSGeometry | None:
    """
    Returns a link to a GeoJSON file and the column name in that file that matches to `key`.

    e.g. "tts22_dest" ->

    ```python
    {
        "key": "tts22",
        "file": <<path_to_geojson_file>>
    }
    ```
    """
    if key in [f"gta06_{type}" for type in _geometry_types]:
        # TODO check that this implementation is actually correct
        return {
            "file": Path("src/tts_tools/src/boundaries/processed/2022_tts2006.geojson"),
            "key": "tts2006",
        }
    elif key in [f"mun_{type}" for type in _geometry_types]:
        # TODO - extract from 2022_tts2022
        raise ValueError("mun geometry not yet implemented")
    elif key in [f"pd_{type}" for type in _geometry_types]:
        return {
            "file": Path("src/tts_tools/src/boundaries/processed/2022_pd.geojson"),
            "key": "pd_no",
        }
    elif key in [f"region_{type}" for type in _geometry_types]:
        # TODO - extract from 2022_pd
        raise ValueError("region geometry not yet implemented")
    elif key in [f"tts22_{type}" for type in _geometry_types]:
        return {
            "file": Path("src/tts_tools/src/boundaries/processed/2022_tts2022.geojson"),
            "key": "tts2022",
        }


# TODO figure out handling for ward - this is not an available query output


def description_to_code(
    column: TTSBaseAttribute | TTSAttribute,
    description: str,
    *,
    survey_year: TTSYear = SURVEY_YEAR,
) -> int | str:
    """
    Converts the description text for the specified column and outputs the matching code value.

    E.g.:

    - description "Transit excluding GO rail" -> code "B" (column "mode_prime")
    - description "1002" -> code 1002 (column "tts22")
    - description "Unknown" -> code 99999 (column "tts22")
    """

    if not isinstance(description, str):
        raise TypeError(
            f"Unable to find code to description conversion for {column}: {description}. {description} must be either an int or a str."
        )

    def check_year_validity(props: CodeLookup):
        """Raises an exception if the `CodeLookup` properties are not valid for the current year."""
        if survey_year not in props.get("years_valid", [survey_year]):
            raise ValueError(f"{column}: {description} is not valid in {survey_year}")

    # handle column name variants
    if column in [f"gta06_{type}" for type in _geometry_types]:
        column = "gta06"
    elif column in [f"mun_{type}" for type in _geometry_types]:
        column = "mun"
    elif column in [f"pd_{type}" for type in _geometry_types]:
        column = "pd"
    elif column in [f"region_{type}" for type in _geometry_types]:
        column = "region"
    elif column in [f"tts22_{type}" for type in _geometry_types]:
        column = "tts22"

    # convert description to matching code value
    if column in code_table_direct:
        lookup = description_to_props_direct_2022[column]
        props = lookup.get(description)
        if props:
            check_year_validity(props)
            return props["code"]
        else:
            raise ValueError(
                f"Unable to find description to code conversion for {column}: {description}"
            )
    elif column in code_table_range:
        # return descriptions that can be converted to integers if they are in the known ranges
        try:
            code = int(description)
            lookup = code_to_props_range_2022[column]
            for key in lookup:
                min, max = key
                if min <= code <= max:
                    props = lookup[key]
                    check_year_validity(props)
                    return code
        # check string descriptions for direct lookup matches
        except ValueError, TypeError:
            lookup = description_to_props_range_direct_2022[column]
            props = lookup.get(description)
            if props:
                check_year_validity(props)
                return props["code"]
            else:
                raise ValueError(
                    f"Unable to find description to code conversion for {column}: {description}"
                )
        # handle descriptions that can be converted to integers that are not within the known ranges
        else:
            raise ValueError(
                f"Unable to find description to code conversion for {column}: {description}. {description} not in known range for {column} values."
            )
    else:
        raise ValueError(
            f"Description to code conversion for {column} is not yet implemented"
        )


def code_to_description(
    column: TTSBaseAttribute | TTSAttribute,
    code: int | str,
    *,
    survey_year: TTSYear = SURVEY_YEAR,
) -> str:
    """
    Converts the code value for the specified column and outputs the matching description.

    E.g.:

    - code "B" -> description "Transit excluding GO rail" (column "mode_prime")
    - code 1002 -> description "1002"(column "tts22")
    - code 99999 -> description "Unknown" (column "tts22")
    """

    if not (isinstance(code, (str, int))):
        raise TypeError(
            f"Unable to find code to description conversion for {column}: {code}. {code} must be either an int or a str."
        )

    def check_year_validity(props: CodeLookup):
        """Raises an exception if the `CodeLookup` properties are not valid for the current year."""
        if survey_year not in props.get("years_valid", [survey_year]):
            raise ValueError(f"{column}: {code} is not valid in {survey_year}")

    # handle column name variants
    if column in [f"gta06_{type}" for type in _geometry_types]:
        column = "gta06"
    elif column in [f"mun_{type}" for type in _geometry_types]:
        column = "mun"
    elif column in [f"pd_{type}" for type in _geometry_types]:
        column = "pd"
    elif column in [f"region_{type}" for type in _geometry_types]:
        column = "region"
    elif column in [f"tts22_{type}" for type in _geometry_types]:
        column = "tts22"

    if column in code_table_direct:
        lookup = code_to_props_direct_2022[column]
        props = lookup.get(code)
        if props:
            check_year_validity(props)
            return props["description"]
        else:
            raise ValueError(
                f"Unable to find code to description conversion for {column}: {code}"
            )
    elif column in code_table_range and isinstance(code, int):
        lookup = code_to_props_range_2022[column]
        for key in lookup:
            min, max = key
            if min <= code <= max:
                props = lookup[key]
                check_year_validity(props)
                return props.get("description", str(code))
        raise ValueError(
            f"Unable to find code to description conversion for {column}: {code}. {code} not in known range for {column} values."
        )
    else:
        raise ValueError(
            f"Code to description conversion for {column} is not yet implemented"
        )
