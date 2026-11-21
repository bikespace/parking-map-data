from tts_tools.src.structure.structure_2022 import (
    code_to_props_direct_2022,
    description_to_code,
)


def test_description_to_code():
    """Docstring TODO"""

    assert description_to_code("mode_prime", "Transit excluding GO rail") == "B"


# def test_code_table():
#     breakpoint()
