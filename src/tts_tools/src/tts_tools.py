import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import geopandas as gpd
import pandas as pd

from .structure.structure_2022 import description_to_code, get_geometry
from .types import CrossTabType, TTSAttribute, TTSMetric, TTSYear

# set up logging
logger = logging.getLogger(__name__)


@dataclass
class TTSCrossTabulationMetadata:
    """Dataclass for metadata returned by TTS CrossTab queries"""

    crosstab_type: CrossTabType
    run_datetime: str  # TODO update this later once you add parsing logic
    run_duration: str  # usually returns milliseconds
    metric: TTSMetric
    year: TTSYear
    row_attribute: TTSAttribute
    column_attribute: TTSAttribute
    table_attribute: TTSAttribute | None
    filters: str | None
    expansion_factor: bool | None


class TTSCrossTabulation:
    """
    Results of a TTS CrossTab query

    TODO describe key methods and attributes
    """

    # TODO add a param for friendly row/column names or not in df/gdf functions

    def __init__(self, df: pd.DataFrame, metadata: TTSCrossTabulationMetadata):
        self._df = df
        self._metadata = metadata

        # check if there is matching geometry for the row_attribute and populate self._gdf if there is
        geometry = get_geometry(self._metadata.row_attribute)
        if geometry:
            match_key = str(geometry["key"])
            geometry_gdf = gpd.read_file(geometry["file"]).set_index(match_key)

            # convert row index to a column and rename row to match_key
            data = self._df.copy()
            data[data.index.name] = data.index
            data.index.name = match_key

            output_gdf = gpd.GeoDataFrame(
                data.join(geometry_gdf), crs=geometry_gdf.crs, geometry="geometry"
            )

            if output_gdf.geometry.hasnans:
                logger.info(
                    f"No matching geometry was found for {output_gdf.geometry.isna().sum()} of {len(output_gdf)} fields in {output_gdf.index.name}."
                )

            self._gdf = output_gdf

        else:
            self._gdf = None

    def __repr__(self) -> str:
        if self._metadata.expansion_factor is None:
            expansion_description = "not specified"
        elif self._metadata.expansion_factor:
            expansion_description = "on"
        else:
            expansion_description = "off"
        return f"<TTSCrossTabulation {self._metadata.year}: {self._metadata.row_attribute} x {self._metadata.column_attribute} (Expansion factor: {expansion_description})>"

    @property
    def metadata(self) -> TTSCrossTabulationMetadata:
        return self._metadata

    def get_df(self) -> pd.DataFrame:
        return self._df

    def get_gdf(self) -> gpd.GeoDataFrame:
        if self._gdf is not None:
            return self._gdf
        else:
            raise ValueError(
                f"No geometry found to match row attribute {self._metadata.row_attribute}"
            )

    # TODO add a geojson save file option that adds the metadata


def read_crosstab(
    filepath: str, *, expansion_factor: bool | None = None
) -> TTSCrossTabulation:
    """Read a TTS CrossTab query output file, parse the values and metadata, and normalize the representation of the resulting dataframe to use code values for row and column headings."""

    # read file into a list of lines
    source = Path(filepath)
    text = source.read_text().splitlines()

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
        elif line[0:8] == "Filters:":
            filters_index = index
        elif line[0] == ",":
            header_index = index
            crosstab_type: CrossTabType = "csv"
            break
        elif line[0:8] == "COLUMN :":
            header_index = index + 1
            crosstab_type: CrossTabType = "col"
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
        row_heading = cast(TTSAttribute, row_heading_match.group("attribute_code"))
    else:
        raise ValueError(
            f"Unable to parse row heading from line {row_index + 1} of {source.name}."
        )
    column_heading_match = re.search(HEADING_PATTERN, text[column_index])
    if column_heading_match:
        column_heading = cast(
            TTSAttribute, column_heading_match.group("attribute_code")
        )
    else:
        raise ValueError(
            f"Unable to parse column heading from line {column_index + 1} of {source.name}."
        )

    metadata = TTSCrossTabulationMetadata(
        crosstab_type=crosstab_type,
        run_datetime=run_datetime,
        run_duration=run_duration,
        metric=metric,
        year=year,
        row_attribute=row_heading,
        column_attribute=column_heading,
        table_attribute=None,  # TODO, not yet implemented
        filters=None,  # TODO, not yet implemented
        expansion_factor=expansion_factor,
    )

    # extract data into a pandas dataframe
    if crosstab_type == "csv":
        csv_segment = "\n".join(text[header_index:])
        # append the otherwise-blank row heading
        segment_io = io.StringIO(row_heading + csv_segment)
        data = pd.read_csv(segment_io)
        data.columns.name = column_heading
        data = data.set_index(row_heading)

        # convert description-based row and column headings to codes
        column_names = {
            k: description_to_code(column_heading, k) for k in data.columns.values
        }
        row_names = {k: description_to_code(row_heading, k) for k in data.index.values}
        data = data.rename(columns=column_names, index=row_names)

    elif crosstab_type == "col":
        table_segment = "\n".join(text[header_index:])
        segment_io = io.StringIO(table_segment)
        records = pd.read_fwf(segment_io)
        data = records.pivot(
            index=row_heading,
            columns=column_heading,
            values="total",
        ).fillna(0)
    else:
        raise ValueError(
            f"Unable to determine if crosstab {source.name} is in csv or columnar format."
        )

    return TTSCrossTabulation(data, metadata)
