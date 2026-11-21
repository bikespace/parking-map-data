import pytest

from tts_tools.src.structure.structure_2022 import (
    code_to_description,
    description_to_code,
)


@pytest.mark.parametrize(
    "column,code,description",
    [
        ("mode_prime", "B", "Transit excluding GO rail"),
        ("pd", 1, "PD 1 of Toronto"),
        ("tts22", 1002, "1002"),
        ("tts22", 99999, "Unknown"),
    ],
)
def test_description_to_from_code_roundtrips(column, code, description):
    """
    GIVEN a column, code, and description documented in code_table_2022
    WHEN code is converted to description and vice versa
    THEN the correct value is returned and round trips are idempotent
    """

    converted_code = description_to_code(column, description)
    converted_description = code_to_description(column, code)

    assert converted_code == code
    assert converted_description == description
    assert description_to_code(column, converted_description) == code
    assert code_to_description(column, converted_code) == description


@pytest.mark.parametrize(
    "column,code,description",
    [
        ("pd", 47, "Durham Fringe"),
    ],
)
def test_description_to_from_code_invalid_years(column, code, description):
    """
    GIVEN a column, code, and description documented in code_table_2022 and marked as NOT being valid in 2022
    WHEN code is converted to description and vice versa
    THEN the correct error is shown
    """

    with pytest.raises(ValueError, match=r".*not valid in 2022.*"):
        code_to_description(column, code)

    with pytest.raises(ValueError, match=r".*not valid in 2022.*"):
        description_to_code(column, description)
