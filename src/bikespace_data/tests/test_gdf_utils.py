from datetime import date, datetime, timezone

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from bikespace_data.utilities.gdf_utils import dt_cols_to_str


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
    )
