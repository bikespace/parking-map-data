from pathlib import Path

import geopandas as gpd

FILE_PATH = "src/tts_tools/src/boundaries/source/tts2022_v1_1_shapefile/tts2022_v1_1_shapefile.shp"
OUTPUT_PATH = "src/tts_tools/src/boundaries/processed/"


def convert_shp(input_path: str, output_path):
    """Docstring TODO"""

    input_dir = Path(input_path)
    output_dir = Path(output_path)

    gdf = gpd.read_file(input_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_dir / f"{input_dir.stem}.geojson", driver="GeoJSON")

    # TODO debug - output is not rendering correctly


if __name__ == "__main__":
    convert_shp(FILE_PATH, OUTPUT_PATH)
