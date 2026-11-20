import logging

from ..src.tts_tools import read_crosstab


def test_read_crosstab(caplog):
    """Docstring TODO"""

    ct = read_crosstab(
        "src/tts_tools/tests/examples/ttsCross__comma__trip_2022__tts22_dest__mode_prime.txt",
        expansion_factor=True,
    )

    # confirm that missing geometries are logged
    with caplog.at_level(logging.INFO):
        gdf = ct.gdf
        assert "No matching geometry was found" in caplog.text
        assert "tts2022" in caplog.text

    # TODO add more validation


# TODO test that the error message line numbers (for the source text file) are not off by one
