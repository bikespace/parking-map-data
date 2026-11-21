import logging

import pytest

from tts_tools.src.tts_tools import read_crosstab


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


@pytest.mark.parametrize(
    "ct_fixture,ct_type",
    [
        ("trips_destination_by_mode_csv", "csv"),
        ("trips_destination_by_mode_col", "col"),
    ],
)
def test_read_crosstab(caplog, request, ct_fixture, ct_type):
    """Docstring TODO"""

    ct = request.getfixturevalue(ct_fixture)
    assert ct.metadata.crosstab_type == ct_type

    # confirm that missing geometries are logged
    with caplog.at_level(logging.INFO):
        gdf = ct.gdf
        assert "No matching geometry was found" in caplog.text
        assert "tts2022" in caplog.text

    # TODO add more validation


def test_read_crosstab_parity(
    trips_destination_by_mode_csv, trips_destination_by_mode_col
):
    """
    GIVEN two TTSCrossTabulation objects in csv and col format based on the same year, metric, row and column
    WHEN their underlying dataframes are compared
    THEN the dataframes should be identical
    """

    ct_csv = trips_destination_by_mode_csv
    ct_col = trips_destination_by_mode_col

    assert ct_csv.metadata.metric == ct_col.metadata.metric
    assert ct_csv.metadata.year == ct_col.metadata.year
    assert ct_csv.metadata.row_attribute == ct_col.metadata.row_attribute
    assert ct_csv.metadata.column_attribute == ct_col.metadata.column_attribute

    assert len(ct_csv.df) == len(ct_col.df)
    assert (ct_csv.df.columns == ct_col.df.columns).all()
    assert (ct_csv.df.index == ct_col.df.index).all()
    assert ct_csv.df.compare(ct_col.df).empty


# TODO test that the error message line numbers (for the source text file) are not off by one
