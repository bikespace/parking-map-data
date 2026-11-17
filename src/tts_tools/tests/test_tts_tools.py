from ..src.tts_tools import read_crosstab


def test_read_crosstab():
    """Docstring TODO"""

    ct = read_crosstab(
        "src/tts_tools/tests/examples/ttsCross__comma__trip_2022__tts22_dest__mode_prime.txt",
        expansion_factor=True,
    )
    gdf = ct.gdf
    # TODO add validation


# TODO test that the error message line numbers are not off by one
