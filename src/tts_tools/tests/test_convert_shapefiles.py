import geopandas as gpd

from tts_tools.src.boundaries.convert_shapefiles import convert_shp


def test_convert_shp(tmp_path):
    """
    GIVEN an input shapefile with known invalid geometry
    WHEN converted to GeoJSON using convert_shp, which fixes invalid geometry and rounds coordinate precision
    THEN the output GeoJSON will have valid geometry
    """

    input_file = "src/tts_tools/src/boundaries/source/tts2022_v1_1_shapefile/tts2022_v1_1_shapefile.shp"
    output_file = convert_shp(input_file, tmp_path)

    output_gdf = gpd.read_file(output_file)
    assert output_gdf.is_valid.all()


# TODO add test for renaming
