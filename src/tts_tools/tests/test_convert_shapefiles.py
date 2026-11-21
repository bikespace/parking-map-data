import geopandas as gpd
import pytest

from tts_tools.src.boundaries.convert_shapefiles import convert_shp
from tts_tools.src.boundaries.renaming_lookup import renamings


@pytest.mark.parametrize("renaming_lookup", [renamings, None])
def test_convert_shp(tmp_path, renaming_lookup):
    """
    GIVEN an input shapefile with known invalid geometry
    WHEN converted to GeoJSON using convert_shp, which fixes invalid geometry and rounds coordinate precision
    THEN the output GeoJSON will have valid geometry
    """

    input_file = "src/tts_tools/src/boundaries/source/tts2022_v1_1_shapefile/tts2022_v1_1_shapefile.shp"
    output_file = convert_shp(input_file, tmp_path, renaming_lookup)

    output_gdf = gpd.read_file(output_file)
    assert output_gdf.is_valid.all()


def test_convert_shp_with_missing_renaming_col(tmp_path):
    """
    GIVEN an input shapefile with known invalid geometry and a renaming lookup with a missing column mapping
    WHEN converted to GeoJSON using convert_shp
    THEN a KeyError will be raised for the missing column mapping
    """

    input_file = "src/tts_tools/src/boundaries/source/tts2022_v1_1_shapefile/tts2022_v1_1_shapefile.shp"
    renamings_with_missing_col_values = renamings.copy()
    renamings_with_missing_col_values["tts2022_v1_1_shapefile"]["columns"].pop("PD_no")

    with pytest.raises(KeyError, match=r".*PD_no.*"):
        convert_shp(input_file, tmp_path, renamings_with_missing_col_values)
