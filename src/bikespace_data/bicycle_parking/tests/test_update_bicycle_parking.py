from pathlib import Path
from pprint import pformat
from typing import TypedDict, cast

from pytest import mark

from bikespace_data.bicycle_parking.tests.benchmarks.bicycle_parking_outputs import (
    bicycle_parking_outputs,
)
from bikespace_data.bicycle_parking.update_bicycle_parking import update_bicycle_parking


def generate_expected_files(
    path: Path,
    benchmark_output: Path = Path(
        "src/bikespace_data/bicycle_parking/tests/benchmarks/bicycle_parking_outputs.py"
    ),
):
    """Utility function to help prepare a list of expected files and benchmark sizes."""
    files = [
        *path.rglob("*.csv", case_sensitive=False),
        *path.rglob("*.geojson", case_sensitive=False),
        *path.rglob("*.parquet", case_sensitive=False),
    ]
    results = [
        {
            "path": str(file.relative_to(path)),
            "benchmark_size": file.stat().st_size,
        }
        for file in files
    ]
    with benchmark_output.open("w") as f:
        f.write(
            f"bicycle_parking_outputs = \\\n{pformat(results, indent=4, underscore_numbers=True)}"
        )


class ExpectedOutput(TypedDict):
    path: str
    benchmark_size: int


@mark.long
@mark.uses_external_resources
def test_update_bicycle_parking(
    tmp_path, file_size_var: float = 0.2, update_benchmarks: bool = False
):
    """
    Optional test to run update_bicycle_parking with no mocks. **This test takes a long time and calls external APIs.**

    Puts the output files into tmp_path and checks that they are within a margin of error for their expected size.
    """
    update_bicycle_parking(
        output_dir=tmp_path,
        status_path=tmp_path / "bicycle_parking/statuses/bicycle_parking_statuses.csv",
    )

    if update_benchmarks:
        generate_expected_files(tmp_path)

    expected_outputs = cast(list[ExpectedOutput], bicycle_parking_outputs)
    for output in expected_outputs:
        assert (tmp_path / output["path"]).exists()
        assert file_size_var >= abs(
            (tmp_path / output["path"]).stat().st_size / output["benchmark_size"] - 1
        )
