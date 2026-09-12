import json
from datetime import date, datetime, timezone

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from bikespace_data.bicycle_parking.custom_types import GeoJSONFeatureCollection
from bikespace_data.utilities.gdf_utils import dt_cols_to_str, save_geo_output


def test_dt_cols_to_str_datetime_columns():
    """
    Test that datetime columns are converted to string dtype and retain their string representation.
    """
    # Use fixed timezone for consistent testing
    fixed_tz = timezone.utc

    data = {
        "col1": [1, 2],
        "col_dt_tz_aware": [
            datetime(2023, 1, 1, 10, 0, 0, tzinfo=fixed_tz),
            datetime(2023, 1, 2, 11, 0, 0, tzinfo=fixed_tz),
        ],
        "col_dt_tz_naive": [
            datetime(2023, 1, 1, 10, 0, 0),
            datetime(2023, 1, 2, 11, 0, 0),
        ],
        "col_date": [date(2023, 1, 1), date(2023, 1, 2)],
        "geometry": [Point(1, 1), Point(2, 2)],
    }
    gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")

    modified_gdf = dt_cols_to_str(gdf)

    assert modified_gdf["col_dt_tz_aware"].dtype == "string"
    assert modified_gdf["col_dt_tz_naive"].dtype == "string"
    assert modified_gdf["col_date"].dtype == "string"
    assert modified_gdf["col1"].dtype == "int64"  # Should remain unchanged
    assert modified_gdf["geometry"].dtype == "geometry"  # Should remain unchanged

    # Assert specific string representations
    pd.testing.assert_series_equal(
        modified_gdf["col_dt_tz_aware"],
        pd.Series(
            [
                datetime(
                    2023, 1, 1, 10, 0, 0, tzinfo=fixed_tz
                ).__str__(),  # Use __str__ for pandas default
                datetime(2023, 1, 2, 11, 0, 0, tzinfo=fixed_tz).__str__(),
            ],
            dtype="string",
            name="col_dt_tz_aware",
        ),
    )
    pd.testing.assert_series_equal(
        modified_gdf["col_dt_tz_naive"],
        pd.Series(
            [
                "2023-01-01 10:00:00",
                "2023-01-02 11:00:00",
            ],
            dtype="string",
            name="col_dt_tz_naive",
        ),
    )
    pd.testing.assert_series_equal(
        modified_gdf["col_date"],
        pd.Series(["2023-01-01", "2023-01-02"], dtype="string", name="col_date"),
    )


def test_dt_cols_to_str_object_columns():
    """
    Test that object columns (e.g., mixed types or inferred strings) are converted to string dtype.
    """
    data = {
        "col1": [1, 2],
        "col_obj_str": ["hello", "world"],
        "col_obj_mixed": ["apple", 123],  # object dtype will be inferred
        "geometry": [Point(1, 1), Point(2, 2)],
    }
    gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")

    modified_gdf = dt_cols_to_str(gdf)

    assert modified_gdf["col_obj_str"].dtype == "string"
    assert modified_gdf["col_obj_mixed"].dtype == "string"
    assert modified_gdf["col1"].dtype == "int64"
    assert modified_gdf["geometry"].dtype == "geometry"

    pd.testing.assert_series_equal(
        modified_gdf["col_obj_str"],
        pd.Series(["hello", "world"], dtype="string", name="col_obj_str"),
        check_dtype=False,
    )
    pd.testing.assert_series_equal(
        modified_gdf["col_obj_mixed"],
        pd.Series(["apple", "123"], dtype="string", name="col_obj_mixed"),
    )


def test_dt_cols_to_str_no_datetime_or_object_columns():
    """
    Test that a GeoDataFrame with no datetime or object columns remains unchanged.
    """
    data = {
        "col1": [1, 2],
        "col2": [3.0, 4.0],
        "geometry": [Point(1, 1), Point(2, 2)],
    }
    gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")
    original_dtypes = gdf.dtypes.copy()

    modified_gdf = dt_cols_to_str(gdf)

    pd.testing.assert_series_equal(modified_gdf.dtypes, original_dtypes)


def test_dt_cols_to_str_empty_dataframe():
    """
    Test with an empty GeoDataFrame.
    """
    gdf = gpd.GeoDataFrame(geometry=[])
    modified_gdf = dt_cols_to_str(gdf)
    assert modified_gdf.empty
    # An empty GeoDataFrame still has a 'geometry' column, but it's empty of rows.


def test_dt_cols_to_str_dataframe_with_none_values():
    """
    Test with a GeoDataFrame containing None values in datetime/object columns.
    """
    data = {
        "col1": [1, 2],
        "col_dt": [datetime(2023, 1, 1), None],
        "col_obj": ["text", None],
        "geometry": [Point(1, 1), Point(2, 2)],
    }
    gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")

    modified_gdf = dt_cols_to_str(gdf)

    assert modified_gdf["col_dt"].dtype == "string"
    assert modified_gdf["col_obj"].dtype == "string"
    assert modified_gdf["col1"].dtype == "int64"
    assert modified_gdf["geometry"].dtype == "geometry"

    # When converting datetime.datetime(YYYY, M, D) (00:00:00 time) in an object column to string dtype,
    # pandas seems to represent it as 'YYYY-MM-DD' instead of 'YYYY-MM-DD 00:00:00'.
    # None values become pd.NA in pandas' 'string' dtype.
    pd.testing.assert_series_equal(
        modified_gdf["col_dt"],
        pd.Series(["2023-01-01", pd.NA], dtype="string", name="col_dt"),
    )
    pd.testing.assert_series_equal(
        modified_gdf["col_obj"],
        pd.Series(["text", pd.NA], dtype="string", name="col_obj"),
        check_dtype=False,
    )


# --- Tests for save_geo_output ---


@pytest.fixture
def sample_gdf():
    data = {
        "col1": ["a", "b"],
        "col2": [1.0, 2.0],
        "geometry": [Point(0, 0), Point(1, 1)],
    }
    return gpd.GeoDataFrame(data, crs="EPSG:4326")


@pytest.fixture
def sample_geojson_dict() -> GeoJSONFeatureCollection:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {"col1": "a", "col2": 1.0},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1, 1]},
                "properties": {"col1": "b", "col2": 2.0},
            },
        ],
    }  # type: ignore


@pytest.mark.parametrize("archive", [True, False])
def test_save_geo_output_gdf(archive, sample_gdf, tmp_path):
    """
    Test saving a GeoDataFrame to GeoJSON, with and without archiving.
    """
    file_name = "output.geojson"
    archive_name = "archive_folder" if archive else None

    save_geo_output(
        sample_gdf,
        path=tmp_path,
        file_name=file_name,
        archive_name=archive_name,
    )

    # Check if GeoJSON file was created and is valid
    output_path = tmp_path / file_name
    assert output_path.exists()
    with open(output_path, "r") as f:
        data = json.load(f)
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 2
        assert data["features"][0]["properties"]["col1"] == "a"

    # Check archive
    archive_path = tmp_path / archive_name if archive else None
    if archive_path is not None:
        assert archive_path.is_dir()
        parquet_path = (archive_path / file_name).with_suffix(".parquet")
        assert parquet_path.exists()
        # Read back and compare
        archived_gdf = gpd.read_parquet(parquet_path)
        pd.testing.assert_frame_equal(
            sample_gdf.drop(columns="geometry"), archived_gdf.drop(columns="geometry")
        )
    else:
        assert not (tmp_path / "archive_folder").exists()


def test_save_geo_output_gdf_with_datetime(tmp_path):
    """
    Test that datetime columns in a GeoDataFrame are correctly converted to strings.
    """
    data = {
        "col1": [datetime(2023, 1, 1, 10, 0)],
        "geometry": [Point(0, 0)],
    }
    gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")
    file_name = "dt_output.geojson"

    save_geo_output(gdf, path=tmp_path, file_name=file_name)

    output_path = tmp_path / file_name
    assert output_path.exists()
    with open(output_path, "r") as f:
        data = json.load(f)
        # Check that the datetime was converted to a string
        assert isinstance(data["features"][0]["properties"]["col1"], str)
        assert data["features"][0]["properties"]["col1"] == "2023-01-01 10:00:00"


@pytest.mark.parametrize("archive", [True, False])
def test_save_geo_output_dict(archive, sample_geojson_dict, tmp_path):
    """
    Test saving a GeoJSON dictionary, with and without archiving.
    """
    file_name = "output_dict.geojson"
    archive_name = "archive_folder" if archive else None

    save_geo_output(
        sample_geojson_dict,
        path=tmp_path,
        file_name=file_name,
        archive_name=archive_name,
    )

    # Check if GeoJSON file was created and is valid
    output_path = tmp_path / file_name
    assert output_path.exists()
    with open(output_path, "r") as f:
        data = json.load(f)
        assert data == sample_geojson_dict

    # Check archive
    archive_path = tmp_path / archive_name if archive else None
    if archive_path is not None:
        assert archive_path.is_dir()
        parquet_path = (archive_path / file_name).with_suffix(".parquet")
        assert parquet_path.exists()
        # Read back and compare
        archived_gdf = gpd.read_parquet(parquet_path)
        assert len(archived_gdf) == 2
        assert archived_gdf.iloc[0]["col1"] == "a"
    else:
        assert not (tmp_path / "archive_folder").exists()
