from pathlib import Path

import geopandas as gpd

from tts_tools.src.boundaries.renaming_lookup import renamings

GEOJSON_CRS = "EPSG:4326"  # WGS84

FILE_PATH = "src/tts_tools/src/boundaries/source/tts2022_v1_1_shapefile/tts2022_v1_1_shapefile.shp"
OUTPUT_PATH = "src/tts_tools/src/boundaries/processed/"

# TODO add a proper typed dict type for the renamings


def convert_shp(
    input_dir: str,
    output_dir: str,
    renaming_lookup: dict | None = None,
):
    """
    Takes a shapefile from `input_dir`, corrects invalid geometry, and outputs a GeoJSON file of the same name at `output_dir`.

    If `renaming_lookup` is supplied, it will be used to rename the output file and its columns.
    """

    input_path = Path(input_dir)
    output_path = Path(output_dir)

    # TODO - suppress winding order warning
    gdf = gpd.read_file(input_path)
    gdf = gdf.to_crs(GEOJSON_CRS)

    # fix invalid geometry
    gdf["geometry"] = gdf.geometry.make_valid(
        method="structure",
        keep_collapsed=False,
    )

    # optionally rename output file and its columns
    # TODO add handling for no match found
    if renaming_lookup and input_path.stem in renaming_lookup:
        lookup = renaming_lookup[input_path.stem]
        gdf = gdf.rename(columns=lookup["columns"])
        output_name = f"{lookup['output_name']}.geojson"
    else:
        output_name = f"{input_path.stem}.geojson"

    output_path.mkdir(parents=True, exist_ok=True)
    output_file = output_path / output_name
    gdf.to_file(output_file, driver="GeoJSON", RFC7946="YES")

    return output_file


def convert_source_folder(source_dir: str):
    """Docstring TODO"""

    source_path = Path(source_dir)
    source_files = source_path.glob("**/*.shp")

    for file in source_files:
        convert_shp(file.as_posix(), OUTPUT_PATH, renamings)


if __name__ == "__main__":
    convert_source_folder("src/tts_tools/src/boundaries/source/")
