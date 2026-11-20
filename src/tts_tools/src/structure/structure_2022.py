from pathlib import Path
from typing import cast

from tts_tools.src.types import CodeLookupDirect

from .code_table_2022 import code_table

attributes = {
    "tts22_dest": "2022 TTS zone of destination",
    "mode_prime": "Primary travel mode of trip",
}


_geometry_types = ["accs", "dest", "egrs", "emp", "hhld", "orig", "sch"]


# TODO convert this to a function instead?
geometry_match = {
    # gta06
    **{
        k: {
            "file": Path("src/tts_tools/src/boundaries/processed/2022_tts2006.geojson"),
            "key": "tts2006",
        }
        for k in [f"gta06_{type}" for type in _geometry_types]
    },
    # mun_ TODO - extract from 2022_tts2022
    # pd
    **{
        k: {
            "file": Path("src/tts_tools/src/boundaries/processed/2022_pd.geojson"),
            "key": "pd_no",
        }
        for k in [f"pd_{type}" for type in _geometry_types]
    },
    # region_ TODO - extract from 2022_pd
    # tts
    **{
        k: {
            "file": Path("src/tts_tools/src/boundaries/processed/2022_tts2022.geojson"),
            "key": "tts2022",
        }
        for k in [f"tts22_{type}" for type in _geometry_types]
    },
    # ward_ TODO - extract from PDF
}


# ward - this is not an available query output


# TODO should this return a closure?
def description_to_code(column, description):
    """Docstring TODO"""

    if column in [f"gta06_{type}" for type in _geometry_types]:
        raise ValueError("gta06 is not yet implemented")

    elif column in [f"mun_{type}" for type in _geometry_types]:
        raise ValueError("mun is not yet implemented")

    elif column in [f"pd_{type}" for type in _geometry_types]:
        # direct lookup
        raise ValueError("pd is not yet implemented")

    elif column in [f"region_{type}" for type in _geometry_types]:
        raise ValueError("region is not yet implemented")

    elif column in [f"tts22_{type}" for type in _geometry_types]:
        try:
            code = int(description)
            return code
        except ValueError, TypeError:
            if description == "External Undefined":
                return 99998
            elif description == "Unknown":
                return 99999
            else:
                raise ValueError(
                    f"Unable to convert {description} to a tts 2022 zone number"
                )

    elif column == "mode_prime":
        lookup = code_table.get(column)
        if lookup:
            lookup_results = [l for l in lookup if l["description"] == description]
            if not lookup_results:
                raise ValueError(
                    f"Unable to find description to code conversion for mode_prime: {description}"
                )
            if len(lookup_results) > 1:
                raise ValueError(
                    f"Found multiple description to code conversions for mode_prime: {description}"
                )
            lookup_result = cast(CodeLookupDirect, lookup_results[0])
            return lookup_result["code"]
        else:
            raise ValueError(
                f"Unable to find description to code conversion lookup table for {column}."
            )


def code_to_description(column, code):
    """Docstring TODO"""

    pass
