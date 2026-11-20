import logging

import pytest

from ..src.tts_tools import read_crosstab


@pytest.fixture
def trips_destination_by_mode_csv():
    ct = read_crosstab(
        "src/tts_tools/tests/examples/ttsCross__csv__trip_2022__tts22_dest__mode_prime.txt",
        expansion_factor=True,
    )
    return ct


@pytest.fixture
def trips_destination_by_mode_col():
    ct = read_crosstab(
        "src/tts_tools/tests/examples/ttsCross__col__trip_2022__tts22_dest__mode_prime.txt",
        expansion_factor=True,
    )
    return ct


def test_read_crosstab_csv(caplog, trips_destination_by_mode_csv):
    """Docstring TODO"""

    ct = trips_destination_by_mode_csv

    assert ct.metadata.crosstab_type == "csv"

    # confirm that missing geometries are logged
    with caplog.at_level(logging.INFO):
        gdf = ct.gdf
        assert "No matching geometry was found" in caplog.text
        assert "tts2022" in caplog.text

    # TODO add more validation


def test_read_crosstab_col(caplog, trips_destination_by_mode_col):
    """Docstring TODO"""

    ct = trips_destination_by_mode_col

    assert ct.metadata.crosstab_type == "col"


def test_read_crosstab_parity(
    trips_destination_by_mode_csv, trips_destination_by_mode_col
):
    """Docstring TODO"""

    ct_csv = trips_destination_by_mode_csv
    ct_col = trips_destination_by_mode_col

    assert len(ct_csv.df) == len(ct_col.df)
    # assert ct_csv.df.columns == ct_col.df.columns
    # assert ct_csv.df.index == ct_col.df.index


# TODO test that the error message line numbers (for the source text file) are not off by one
