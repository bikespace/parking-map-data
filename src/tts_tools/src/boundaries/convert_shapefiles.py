from pathlib import Path

import geopandas as gpd

from tts_tools.src.boundaries.renaming_lookup import renamings

GEOJSON_CRS = "EPSG:4326"  # WGS84

FILE_PATH = "src/tts_tools/src/boundaries/source/tts2022_v1_1_shapefile/tts2022_v1_1_shapefile.shp"
OUTPUT_PATH = "src/tts_tools/src/boundaries/processed/"

# TODO add a proper typed dict type for the renamings


def convert_shp(
    input_path: str,
    output_path: str,
    renaming_lookup: dict | None = None,
):
    """
    Takes a shapefile from `input_path`, corrects invalid geometry, and outputs a GeoJSON file of the same name at `output_path`.

    If `renaming_lookup` is supplied, it will be used to rename the output file and its columns.
    """

    input_dir = Path(input_path)
    output_dir = Path(output_path)

    gdf = gpd.read_file(input_dir)
    gdf = gdf.to_crs(GEOJSON_CRS)

    # fix invalid geometry
    gdf["geometry"] = gdf.geometry.make_valid(
        method="structure",
        keep_collapsed=False,
    )

    # optionally rename output file and its columns
    # TODO add handling for no match found
    if renaming_lookup:
        lookup = renaming_lookup[input_dir.stem]
        gdf = gdf.rename(columns=lookup["columns"])
        output_name = f"{lookup['output_name']}.geojson"
    else:
        output_name = f"{input_dir.stem}.geojson"

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / output_name
    gdf.to_file(output_file, driver="GeoJSON", RFC7946="YES")

    return output_file


if __name__ == "__main__":
    convert_shp(FILE_PATH, OUTPUT_PATH, renamings)
