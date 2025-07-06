from pathlib import Path

import geopandas as gpd
from progress.bar import Bar

from data_pipeline import dt_cols_to_str


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
        Path("Source Files") / "archive",
        Path("Display Files") / "archive",
        Path("Output Files") / "archive",
    ]
    for path in archive_paths:
        convert_geojson_to_parquet(path)
        # convert_parquet_to_geojson(path)
