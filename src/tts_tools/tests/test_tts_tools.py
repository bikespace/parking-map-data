import logging

import pytest

from tts_tools.src.tts_tools import TTSCrossTabulation, read_crosstab


@pytest.fixture
def trips_destination_by_mode_csv(caplog) -> TTSCrossTabulation:
    with caplog.at_level(logging.INFO):
        ct = read_crosstab(
            "src/tts_tools/tests/examples/ttsCross__csv__trip_2022__tts22_dest__mode_prime.txt",
            expansion_factor=True,
        )
        assert "No matching geometry was found" in caplog.text
        assert "tts2022" in caplog.text
    return ct


@pytest.fixture
def trips_destination_by_mode_col(caplog) -> TTSCrossTabulation:
    with caplog.at_level(logging.INFO):
        ct = read_crosstab(
            "src/tts_tools/tests/examples/ttsCross__col__trip_2022__tts22_dest__mode_prime.txt",
            expansion_factor=True,
        )
        assert "No matching geometry was found" in caplog.text
        assert "tts2022" in caplog.text
    return ct


@pytest.mark.parametrize(
    "ct_fixture,ct_type",
    [
        ("trips_destination_by_mode_csv", "csv"),
        ("trips_destination_by_mode_col", "col"),
    ],
)
def test_read_crosstab(caplog, request, ct_fixture, ct_type):
    """
    GIVEN a TTS CrossTab "csv" or "col" type query output
    WHEN a `TTSCrossTabulation` is initiated using the `read_crosstab` function
    THEN the file read is successful with the correct metadata and data table properties
    """

    ct: TTSCrossTabulation = request.getfixturevalue(ct_fixture)
    assert ct.metadata.crosstab_type == ct_type

    df = ct.get_df()
    gdf = ct.get_gdf()

    assert len(df) == len(gdf)

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

    assert len(ct_csv.get_df()) == len(ct_col.get_df())
    assert (ct_csv.get_df().columns == ct_col.get_df().columns).all()
    assert (ct_csv.get_df().index == ct_col.get_df().index).all()
    assert ct_csv.get_df().compare(ct_col.get_df()).empty


# TODO test that the error message line numbers (for the source text file) are not off by one
