from tts_tools.src.structure.structure_2022 import description_to_code


def test_description_to_code():
    """Docstring TODO"""

    assert description_to_code("mode_prime", "Transit excluding GO rail") == "B"
