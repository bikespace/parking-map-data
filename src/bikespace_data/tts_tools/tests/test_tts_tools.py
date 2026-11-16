from ..src.tts_tools import read_crosstab


def test_read_crosstab():
    """Docstring TODO"""

    ct = read_crosstab(
        "src/bikespace_data/tts_tools/tests/examples/ttsCross__comma__trip_2022__tts22_dest__mode_prime.txt"
    )
    # TODO add validation
