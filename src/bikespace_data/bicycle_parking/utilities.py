from pathlib import Path
import shutil

from pandas.api.types import is_datetime64_any_dtype

import geopandas as gpd
from progress.bar import Bar


def ref_cols_to_str(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Convert dtype for ref columns to string"""
    ref_cols = gdf.filter(like="ref:open.toronto.ca", axis=1)
    for name, values in ref_cols.items():
        gdf[name] = values.astype("str")
    return gdf


def dt_cols_to_str(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Convert dtype for datetime columns to string"""
    json_not_supported_cols = gdf.columns[
        [is_datetime64_any_dtype(gdf[c]) for c in gdf.columns]
    ].union(gdf.columns[gdf.dtypes == "object"])
    if len(json_not_supported_cols) > 0:
        gdf = gdf.astype({c: "string" for c in json_not_supported_cols})
    return gdf


def copy_production_files():
    source_destination_paths = [
        (Path("bicycle_parking/display_files"), Path("Display Files")),
        (Path("bicycle_parking/output_files"), Path("Output Files")),
    ]
    for source_path, destination_path in source_destination_paths:
        source_files = source_path.glob("*.geojson")
        for source_file in source_files:
            shutil.copy(source_file, destination_path / source_file.name)


def convert_geojson_to_parquet(path: Path):
    print(f"Converting geojson files in {path} to parquet")
    to_convert = list(path.rglob("*.geojson"))
    bar = Bar("Converting files", max=len(to_convert))

    for original_file in to_convert:
        gdf = gpd.read_file(original_file).convert_dtypes()
        gdf.to_parquet(original_file.with_suffix(".parquet"))
        original_file.unlink()
        bar.next()
    bar.finish()


def convert_parquet_to_geojson(path: Path):
    print(f"Converting parquet files in {path} to geojson")
    to_convert = list(path.rglob("*.parquet"))
    bar = Bar("Converting files", max=len(to_convert))

    for original_file in to_convert:
        gdf = gpd.read_parquet(original_file).convert_dtypes()
        with open(original_file.with_suffix(".geojson"), "w") as f:
            f.write(
                dt_cols_to_str(gdf).to_json(
                    na="drop",
                    drop_id=True,
                    indent=2,
                )
            )
        original_file.unlink()
        bar.next()
    bar.finish()


if __name__ == "__main__":
    archive_paths = [
        Path("bicycle_parking/source_files") / "archive",
        Path("bicycle_parking/display_files") / "archive",
        Path("bicycle_parking/output_files") / "archive",
    ]
    for path in archive_paths:
        convert_geojson_to_parquet(path)
        # convert_parquet_to_geojson(path)
