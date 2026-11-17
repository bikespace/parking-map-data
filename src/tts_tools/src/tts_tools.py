import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import geopandas as gpd
import pandas as pd

from .structure.structure_2022 import geometry_match
from .types import TTSMetric, TTSYear


@dataclass
class TTSCrossTabulationMetadata:
    """Docstring TODO"""

    run_datetime: str  # TODO update this later once you add parsing logic
    run_duration: str  # usually returns milliseconds
    metric: TTSMetric
    year: TTSYear
    row_attribute: str  # TODO update this to be stricter for autocomplete
    column_attribute: str  # TODO update this to be stricter for autocomplete
    table_attribute: str | None  # TODO update this to be stricter for autocomplete
    expansion_factor: bool | None


class TTSCrossTabulation:
    """Docstring TODO"""

    def __init__(self, df: pd.DataFrame, metadata: TTSCrossTabulationMetadata):
        self._df = df
        self._metadata = metadata

    # TODO add __repr__

    @property
    def metadata(self) -> TTSCrossTabulationMetadata:
        return self._metadata

    @property
    def df(self) -> pd.DataFrame:
        return self._df

    @property
    def gdf(self) -> gpd.GeoDataFrame:
        # TODO add additional years to the gdf matching, not just 2022

        geometry = geometry_match.get(self.metadata.row_attribute, None)
        if geometry:
            match_key = str(geometry["key"])
            geometry_gdf = gpd.read_file(geometry["file"]).set_index(match_key)
            data = self._df.copy()
            data[match_key] = data[self.metadata.row_attribute]
            data = data.set_index(match_key)

            # TODO add checks to warn if there are un-matched rows
            # TODO need to handle difference between formats - csv-like uses string name for row/col values, whereas tabular uses the internal code. E.g. pd in csv-like: "PD 1 of Toronto", in tabular: 1
            # Therefore, for parsing csv-like, it needs a name to value lookup for each row/col value
            # The difference for tts zone is very subtle since only the 99998 and 99999 values get names that appear string-like.
            # convert the df and gdf properties to get functions and add a param for friendly row/column names or not

            output_gdf = gpd.GeoDataFrame(
                data.join(geometry_gdf), crs=geometry_gdf.crs, geometry="geometry"
            )
            breakpoint()
        else:
            raise ValueError(
                f"No geometry found to match row attribute {self.metadata.row_attribute}"
            )

        return output_gdf


def read_crosstab(filepath: str, *, expansion_factor: bool | None = None):
    """Docstring TODO"""

    # read file into a list of lines
    source = Path(filepath)
    text = source.read_text().splitlines()

    # TODO add in logic to determine filetype also: csv-like if ',' line found, otherwise table-format if 'ROW :' found

    # find the index of key lines
    for index, line in enumerate(text):
        if len(line) == 0:
            continue
        if line[0:27] == "Cross Tabulation Query Form":
            year_and_metric_index = index
        elif line[0:4] == "Row:":
            row_index = index
        elif line[0:7] == "Column:":
            column_index = index
        elif line[0] == ",":
            header_index = index
            break

    # extract run datetime and duration
    RUN_TIME_PATTERN = r"^(?P<run_datetime>.+) \((?P<timezone_name>.+)\) - Run Time: (?P<run_duration>\d+\w+)"
    run_time_match = re.search(RUN_TIME_PATTERN, text[0])
    if run_time_match:
        run_datetime = run_time_match.group("run_datetime")
        run_duration = run_time_match.group("run_duration")
    else:
        raise ValueError(
            f"Unable to parse cross-tab run datetime or duration from line 1 of {source.name}."
        )

    # extract year and metric
    YEAR_AND_METRIC_PATTERN = r"Cross Tabulation Query Form - (?P<metric>Household|Person|Trip|Transit) - (?P<year>\d{4})"
    year_and_metric_match = re.search(
        YEAR_AND_METRIC_PATTERN, text[year_and_metric_index]
    )
    if year_and_metric_match:
        metric = cast(TTSMetric, str(year_and_metric_match.group("metric")).lower())
        year = cast(TTSYear, int(year_and_metric_match.group("year")))
    else:
        raise ValueError(
            f"Unable to parse survey year and output metric from line {year_and_metric_index + 1} of {source.name}."
        )

    # extract row and column names
    HEADING_PATTERN = (
        r"(Row|Column): (?P<attribute_description>.+) - (?P<attribute_code>.+)"
    )
    row_heading_match = re.search(HEADING_PATTERN, text[row_index])
    if row_heading_match:
        row_heading = row_heading_match.group("attribute_code")
    else:
        raise ValueError(
            f"Unable to parse row heading from line {row_index + 1} of {source.name}."
        )
    column_heading_match = re.search(HEADING_PATTERN, text[column_index])
    if column_heading_match:
        column_heading = column_heading_match.group("attribute_code")
    else:
        raise ValueError(
            f"Unable to parse column heading from line {column_index + 1} of {source.name}."
        )

    metadata = TTSCrossTabulationMetadata(
        run_datetime=run_datetime,
        run_duration=run_duration,
        metric=metric,
        year=year,
        row_attribute=row_heading,
        column_attribute=column_heading,
        table_attribute=None,  # TODO, not yet implemented
        expansion_factor=expansion_factor,
    )

    # extract csv segment
    csv_segment = "\n".join(text[header_index:])
    data = pd.read_csv(io.StringIO(row_heading + csv_segment))

    return TTSCrossTabulation(data, metadata)
