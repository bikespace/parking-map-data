import io
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .types import TTSMetric, TTSYear

HEADING_PATTERN = (
    r"(Row|Column): (?P<attribute_description>.+) - (?P<attribute_code>.+)"
)


@dataclass
class TTSCrossTabulationMetadata:
    """Docstring TODO"""

    run_datetime: str  # TODO update this later once you add parsing logic
    run_duration: int  # milliseconds
    metric: TTSMetric
    year: TTSYear
    row_attribute: str  # TODO update this to be stricter for autocomplete
    column_attribute: str  # TODO update this to be stricter for autocomplete
    table_attribute: str | None  # TODO update this to be stricter for autocomplete


class TTSCrossTabulation:
    """Docstring TODO"""

    # TODO add metadata: TTSCrossTabulationMetadata
    def __init__(self, df: pd.DataFrame, metadata: TTSCrossTabulationMetadata):
        self.df = df
        self.metadata = metadata

    # TODO add __repr__


def read_crosstab(filepath: str):
    """Docstring TODO"""

    # read file into a list of lines
    source = Path(filepath)
    text = source.read_text().splitlines()

    # TODO add in logic to determine filetype also: csv-like if ',' line found, otherwise table-format if 'ROW :' found

    # find the index of key lines
    for index, line in enumerate(text):
        if len(line) == 0:
            continue
        print(line[0:10])  # TODO remove debug
        if line[0:4] == "Row:":
            row_index = index
        elif line[0:7] == "Column:":
            column_index = index
        elif line[0] == ",":
            header_index = index
            break

    # extract row and column names
    row_heading_search = re.search(HEADING_PATTERN, text[row_index])
    row_heading = (
        row_heading_search.group("attribute_code")
        if row_heading_search
        else "unknown row attribute"  # TODO should this throw an error instead?
    )
    column_heading_search = re.search(HEADING_PATTERN, text[column_index])
    column_heading = (
        column_heading_search.group("attribute_code")
        if column_heading_search
        else "unknown column attribute"  # TODO should this throw an error instead?
    )

    metadata = TTSCrossTabulationMetadata(
        run_datetime="todo",
        run_duration=1,  # TODO
        metric="trip",  # TODO
        year=2022,  # TODO
        row_attribute=row_heading,
        column_attribute=column_heading,
        table_attribute=None,
    )

    # extract csv segment
    csv_segment = "\n".join(text[header_index:])
    data = pd.read_csv(io.StringIO(row_heading + csv_segment))

    return TTSCrossTabulation(data, metadata)
