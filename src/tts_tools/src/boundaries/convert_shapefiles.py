import warnings
from pathlib import Path

import geopandas as gpd

from tts_tools.src.boundaries.renaming_lookup import renamings
from tts_tools.src.types import TTSGeometryRenamingLookup

GEOJSON_CRS = "EPSG:4326"  # WGS84
OUTPUT_PATH = "src/tts_tools/src/boundaries/processed/"

# TODO add in missing "external" regions using geohub municipality boundaries


def convert_shp(
    input_dir: str,
    output_dir: str,
    renaming_lookup: dict[str, TTSGeometryRenamingLookup] | None = None,
) -> Path:
    """
    Takes a shapefile from `input_dir`, corrects invalid geometry, and outputs a GeoJSON file of the same name at `output_dir`. Returns the path of the saved GeoJSON file.

    If `renaming_lookup` is supplied, it will be used to rename the output file and its columns.
    """

    input_path = Path(input_dir)
    output_path = Path(output_dir)

    # Some of the source shapefiles have invalid winding orders
    # but these are auto-corrected by GeoPandas on load
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            category=RuntimeWarning,
            message=r".*invalid winding order.*",
        )
        gdf = gpd.read_file(input_path)

    gdf = gdf.to_crs(GEOJSON_CRS)

    # fix invalid geometry
    gdf["geometry"] = gdf.geometry.make_valid(
        method="structure",
        keep_collapsed=False,
    )

    # optionally rename output file and its columns
    if renaming_lookup and input_path.stem in renaming_lookup:
        lookup = renaming_lookup[input_path.stem]
        missing_column_names = set(gdf.columns.values).difference(
            set(lookup["columns"])
        )
        missing_column_names.remove("geometry")
        if missing_column_names:
            raise KeyError(
                f"Renamings not found for the following columns from {input_path.stem}: {missing_column_names}"
            )

        gdf = gdf.rename(columns=lookup["columns"])
        output_name = f"{lookup['output_name']}.geojson"
    else:
        output_name = f"{input_path.stem}.geojson"

    output_path.mkdir(parents=True, exist_ok=True)
    output_file = output_path / output_name
    gdf.to_file(output_file, driver="GeoJSON", RFC7946="YES")

    return output_file


def convert_source_folder(
    source_dir: str,
    output_path: str = OUTPUT_PATH,
    renamings: dict[str, TTSGeometryRenamingLookup] | None = renamings,
):
    """Convert all the shapefiles in the specified `source_dir` folder and save them in `output_path` as cleaned up GeoJSON using `convert_shp`."""

    source_path = Path(source_dir)
    source_files = source_path.glob("**/*.shp")

    for file in source_files:
        convert_shp(file.as_posix(), output_path, renamings)


if __name__ == "__main__":
    convert_source_folder("src/tts_tools/src/boundaries/source/")
