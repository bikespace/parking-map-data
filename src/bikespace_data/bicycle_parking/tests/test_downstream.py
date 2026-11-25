import geopandas as gpd
import pandas as pd

from bikespace_data.bicycle_parking.downstream import (
    combine_list,
    extract_ref_tags,
    get_member_ref_id,
    rack_ref_columns,
    summarize_boolean,
    summarize_freq,
    group_proximate_rings,
    group_proximate_racks,
)

# see properties.description for test case notes
mock_gdf = gpd.GeoDataFrame.from_features(
    [
        {
            "type": "Feature",
            "properties": {
                "description": "No ref tags",
                "amenity": "bicycle_parking",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-79.4004991, 43.6605147],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "open.toronto.ca ref, value 'no'",
                "amenity": "bicycle_parking",
                "ref:open.toronto.ca": "no",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-79.2650674, 43.7332707],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "open.toronto.ca street furniture ref; multiple values including with and without whitespace",
                "amenity": "bicycle_parking",
                "ref:open.toronto.ca": "yes",
                "ref:open.toronto.ca:street-furniture-bicycle-parking:id": "BP-34427;BP-34426; BP-34423",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-79.4015863, 43.6632417],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "open.toronto.ca street furniture ref; single  value",
                "amenity": "bicycle_parking",
                "ref:open.toronto.ca:street-furniture-bicycle-parking:id": "BP-09460",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-79.3746154, 43.667301],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "open.toronto.ca refs for high cap, racks, and street furniture",
                "amenity": "bicycle_parking",
                "ref:open.toronto.ca:bicycle-parking-high-capacity-outdoor:id": "78",
                "ref:open.toronto.ca:bicycle-parking-racks:objectid": "52",
                "ref:open.toronto.ca:street-furniture-bicycle-parking:id": "BP-24232",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-79.4658072, 43.6544076],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "open.toronto.ca high cap ref",
                "amenity": "bicycle_parking",
                "ref:open.toronto.ca:bicycle-parking-high-capacity-outdoor:id": "43",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-79.4685262, 43.6528776],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "open.toronto.ca bike station ref",
                "amenity": "bicycle_parking",
                "bicycle_parking": "building",
                "ref:open.toronto.ca:bicycle-parking-bike-stations-indoor:id": "2",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-79.2894687, 43.6945942],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "toronto.ca lockers ref",
                "amenity": "bicycle_parking",
                "bicycle_parking": "lockers",
                "ref:toronto.ca:lockers:title": "Bayview Subway Station",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-79.3873901, 43.7670662],
            },
        },
    ],
    crs="EPSG:4326",
)


def test_extract_ref_tags():
    """Extract ref tags from a mock gdf using the 'ref:(open\\.)?toronto\\.ca' pattern (for 'ref:open.toronto.ca' and 'ref:toronto.ca' prefixes) and ensure that all the tags are properly extracted."""

    ref_tags = extract_ref_tags(mock_gdf, r"ref:(open\.)?toronto\.ca")

    assert ref_tags == {
        "ref:open.toronto.ca": ["no", "yes"],
        "ref:open.toronto.ca:street-furniture-bicycle-parking:id": [
            "BP-34427",
            "BP-34426",
            "BP-34423",
            "BP-09460",
            "BP-24232",
        ],
        "ref:open.toronto.ca:bicycle-parking-high-capacity-outdoor:id": ["78", "43"],
        "ref:open.toronto.ca:bicycle-parking-racks:objectid": ["52"],
        "ref:open.toronto.ca:bicycle-parking-bike-stations-indoor:id": ["2"],
        "ref:toronto.ca:lockers:title": ["Bayview Subway Station"],
    }


def test_summarize_freq():
    df = pd.DataFrame(
        {
            "mixed_col": [1, 2, 2, "three", "three", "three", pd.NA, pd.NA],
            "same_col_int": [1, 1, 1, 1, 1, 1, 1, 1],
            "same_col_char": ["a", "a", "a", "a", "a", "a", "a", "a"],
            "same_col_str": ["abc", "abc", "abc", "abc", "abc", "abc", "abc", "abc"],
            "all_na_col": [pd.NA, pd.NA, pd.NA, pd.NA, pd.NA, pd.NA, pd.NA, pd.NA],
            "same_na_first": [pd.NA, "a", "a", "a", "a", "a", "a", pd.NA],
            "mix_na_none": [pd.NA, None, pd.NA, None, pd.NA, None, pd.NA, None],
            "blank_strings": [1, "two", "two", "", "", "", pd.NA, pd.NA],
        }
    )
    assert (
        summarize_freq(df["mixed_col"]) == "three (n=3), 2 (n=2), <NA> (n=2), 1 (n=1)"
    )
    assert summarize_freq(df["same_col_int"]) == 1
    assert summarize_freq(df["same_col_char"]) == "a"
    assert summarize_freq(df["same_col_str"]) == "abc"
    assert summarize_freq(df["all_na_col"]) is pd.NA
    assert summarize_freq(df["same_na_first"]) == "a (n=6), <NA> (n=2)"
    assert summarize_freq(df["mix_na_none"]) is pd.NA
    assert summarize_freq(df["blank_strings"]) == "<NA> (n=5), two (n=2), 1 (n=1)"


def test_summarize_boolean():
    df = pd.DataFrame(
        {
            "all_yes": ["yes", "yes", "yes"],  # 'yes'
            "all_yes_na": [pd.NA, "yes", "yes"],  # 'probably yes'
            "all_no": ["no", "no", "no"],  # 'no'
            "all_no_na": [pd.NA, "no", "no"],  # 'probably no'
            "some_yes_some_no": [pd.NA, "yes", "no"],  # 'maybe'
            "other_values": [pd.NA, "yes", "blue"],
        }
    )

    assert summarize_boolean(df["all_yes"]) == "yes"
    assert summarize_boolean(df["all_yes_na"]) == "probably yes"
    assert summarize_boolean(df["all_yes_na"], fill_value="yes") == "yes"
    assert summarize_boolean(df["all_yes_na"], fill_value="no") == "maybe"
    assert summarize_boolean(df["all_no"]) == "no"
    assert summarize_boolean(df["all_no_na"]) == "probably no"
    assert summarize_boolean(df["some_yes_some_no"]) == "maybe"
    assert summarize_boolean(df["other_values"]) == "<NA> (n=1), yes (n=1), blue (n=1)"


def test_get_member_ref_id():
    """Should return the first non-null ref id column in priority order, or fall back to a
    rounded-coordinate key (matching the frontend's parkingFeatureKey() priority) when none
    of the row's source datasets provide one."""
    has_ref_id = gpd.GeoDataFrame.from_features(
        [
            {
                "type": "Feature",
                "properties": {
                    "ref:open.toronto.ca:bicycle-parking-high-capacity-outdoor:id": "78",
                    "ref:open.toronto.ca:bicycle-parking-racks:objectid": "52",
                },
                "geometry": {"type": "Point", "coordinates": [-79.4658072, 43.6544076]},
            }
        ],
        crs="EPSG:4326",
    ).iloc[0]
    # no street-furniture id present, so the next column in priority order (high-capacity) wins
    assert get_member_ref_id(has_ref_id, rack_ref_columns) == "78"

    no_ref_id = gpd.GeoDataFrame.from_features(
        [
            {
                "type": "Feature",
                "properties": {"description": "no ref ids"},
                "geometry": {"type": "Point", "coordinates": [-79.4, 43.66]},
            }
        ],
        crs="EPSG:4326",
    ).iloc[0]
    assert get_member_ref_id(no_ref_id, rack_ref_columns) == "-79.4,43.66"


def test_combine_list():
    df = pd.DataFrame(
        {
            "all_str": ["id1", "id2", "id3"],
            "all_int": [1, 2, 3],
            "mixed": ["id1", 2, "id3"],
            "has_na": [pd.NA, "id1", "id2"],
            "has_na_none": [None, "id1", "id2"],
            "has_na_blank": ["", "id1", "id2"],
            "all_na": [pd.NA, pd.NA, pd.NA],
        }
    )

    assert combine_list(df["all_str"]) == "id1;id2;id3"
    assert combine_list(df["all_int"]) == "1;2;3"
    assert combine_list(df["mixed"]) == "id1;2;id3"
    assert combine_list(df["has_na"]) == "id1;id2"
    assert combine_list(df["has_na_none"]) == "id1;id2"
    assert combine_list(df["has_na_blank"]) == "id1;id2"
    assert combine_list(df["all_na"]) is pd.NA


# see properties.description for test case notes
mock_clusterable_rings = gpd.GeoDataFrame.from_features(
    [
        {
            "type": "Feature",
            "properties": {
                "description": "should join a cluster of three; null should be replaced with pd.NA",
                "meta_source_dataset": "street-furniture-bicycle-parking",
                "amenity": "bicycle_parking",
                "capacity": "null",
                "dbscan_cluster": "yes",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [100, 100],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "should join a cluster of three",
                "meta_source_dataset": "street-furniture-bicycle-parking",
                "amenity": "bicycle_parking",
                "dbscan_cluster": "yes",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [100, 103],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "should join a cluster of three",
                "meta_source_dataset": "street-furniture-bicycle-parking",
                "amenity": "bicycle_parking",
                "dbscan_cluster": "yes",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [100, 106],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "should remain unclustered",
                "meta_source_dataset": "street-furniture-bicycle-parking",
                "amenity": "bicycle_parking",
                "dbscan_cluster": "no",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [200, 200],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "should remain unclustered",
                "meta_source_dataset": "street-furniture-bicycle-parking",
                "amenity": "bicycle_parking",
                "dbscan_cluster": "no",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [300, 300],
            },
        },
    ],
    crs="EPSG:32617",  # UTM 17 N
)

mock_not_clusterable_rings = mock_clusterable_rings[
    mock_clusterable_rings["dbscan_cluster"] == "no"
]

mock_empty_rings_table = mock_clusterable_rings[
    mock_clusterable_rings["amenity"] == "give_me_an_empty_table"
]


def test_group_proximate_rings():
    """Check that the test_group_proximate_rings function works as expected under different input conditions:

    - dataset with a mix of clusterable points, including points within 5m of each other, and points that are not within 5m of each other (should not cluster)
    - dataset with only points that are not within 5m of each other (should not cluster, no dbscan matches)
    - empty dataset with no points (should return empty table)
    """
    expected_cluster, member_cluster_ids = group_proximate_rings(mock_clusterable_rings)
    # one cluster of three, two unclustered. Quantity should be a string and there should not be "null" string values in output (should be pd.NA)
    assert len(expected_cluster) == 3
    assert "3" in expected_cluster["quantity"].unique()
    assert "null" not in expected_cluster["capacity"].dropna().unique()
    assert expected_cluster["capacity"].hasnans

    # the row for the 3-member cluster should carry a meta_cluster_id; the two singleton
    # "clusters" (dbscan min_samples=1 gives every row a label) should not
    clustered_row = expected_cluster[expected_cluster["quantity"] == "3"]
    assert clustered_row["meta_cluster_id"].notna().all()
    singleton_rows = expected_cluster[expected_cluster["quantity"] != "3"]
    assert singleton_rows["meta_cluster_id"].isna().all()

    # the member lookup should only contain entries for the actual (3-member) cluster, all
    # sharing the same id as the dissolved row, keyed by each member's own coordinate-based id
    # (none of these mock rows have a ref:open.toronto.ca:... id, so they fall back to that)
    assert len(member_cluster_ids) == 3
    assert len(set(member_cluster_ids.values())) == 1
    assert clustered_row["meta_cluster_id"].iloc[0] in member_cluster_ids.values()

    expected_nocluster, nocluster_member_ids = group_proximate_rings(
        mock_not_clusterable_rings
    )
    # two unclustered
    assert len(expected_nocluster) == 2
    assert expected_nocluster["meta_cluster_id"].isna().all()
    assert nocluster_member_ids == {}

    expected_empty, empty_member_ids = group_proximate_rings(mock_empty_rings_table)
    # empty table in, empty table out
    assert len(expected_empty) == 0
    assert empty_member_ids == {}


# see properties.description for test case notes
mock_clusterable_city_racks = gpd.GeoDataFrame.from_features(
    [
        {
            "type": "Feature",
            "properties": {
                "description": "high-capacity dataset, should join a cluster of three",
                "meta_source_dataset": "bicycle-parking-high-capacity-outdoor",
                "amenity": "bicycle_parking",
                "dbscan_cluster": "yes",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [100, 100],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "racks dataset, should join a cluster of three",
                "meta_source_dataset": "bicycle-parking-racks",
                "amenity": "bicycle_parking",
                "dbscan_cluster": "yes",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [100, 120],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "street-furniture dataset, should join a cluster of three",
                "meta_source_dataset": "street-furniture-bicycle-parking",
                "amenity": "bicycle_parking",
                "dbscan_cluster": "yes",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [100, 140],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "street-furniture dataset, within 30m of another, but from the same dataset, so should not cluster",
                "meta_source_dataset": "street-furniture-bicycle-parking",
                "amenity": "bicycle_parking",
                "dbscan_cluster": "yes",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [200, 200],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "street-furniture dataset, within 30m of another, but from the same dataset, so should not cluster",
                "meta_source_dataset": "street-furniture-bicycle-parking",
                "amenity": "bicycle_parking",
                "dbscan_cluster": "yes",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [200, 220],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "street-furniture dataset, not within 30m of another, should not cluster",
                "meta_source_dataset": "street-furniture-bicycle-parking",
                "amenity": "bicycle_parking",
                "dbscan_cluster": "no",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [300, 300],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "description": "racks dataset, not within 30m of another, should not cluster",
                "meta_source_dataset": "bicycle-parking-racks",
                "amenity": "bicycle_parking",
                "dbscan_cluster": "no",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [400, 400],
            },
        },
    ],
    crs="EPSG:32617",  # UTM 17 N
)

mock_not_clusterable_city_racks = mock_clusterable_city_racks[
    mock_clusterable_city_racks["dbscan_cluster"] == "no"
]

mock_empty_racks_table = mock_clusterable_city_racks[
    mock_clusterable_city_racks["amenity"] == "give_me_an_empty_table"
]


def test_group_proximate_racks():
    """Check that the test_group_proximate_racks function works as expected under different input conditions:

    - dataset with a mix of clusterable points, points within 30m but from the same dataset (should not cluster), and points that are not within 30m of each other (should not cluster)
    - dataset with only points that are not within 30m of each other (should not cluster, no dbscan matches)
    - empty dataset with no points (should return empty table)
    """
    expected_cluster, member_cluster_ids = group_proximate_racks(
        mock_clusterable_city_racks
    )
    # one cluster of three, two within 30m but from same dataset, two not within 30m
    assert len(expected_cluster) == 5

    # the dissolved 3-source cluster row should carry a meta_cluster_id; the 4 rows that
    # reverted to singles (same-dataset-only pair + the two isolated points) should not
    clustered_rows = expected_cluster[expected_cluster["meta_cluster_id"].notna()]
    assert len(clustered_rows) == 1
    singleton_rows = expected_cluster[expected_cluster["meta_cluster_id"].isna()]
    assert len(singleton_rows) == 4

    # member lookup has one entry per member of the actual 3-source cluster, all sharing the
    # dissolved row's id (keyed by coordinate-based fallback id, since these mocks have no
    # ref:open.toronto.ca:... id)
    assert len(member_cluster_ids) == 3
    assert set(member_cluster_ids.values()) == set(clustered_rows["meta_cluster_id"])

    expected_nocluster, nocluster_member_ids = group_proximate_racks(
        mock_not_clusterable_city_racks
    )
    # two not within 30m
    assert len(expected_nocluster) == 2
    assert expected_nocluster["meta_cluster_id"].isna().all()
    assert nocluster_member_ids == {}

    expected_empty, empty_member_ids = group_proximate_racks(mock_empty_racks_table)
    # empty table in, empty table out
    assert len(expected_empty) == 0
    assert empty_member_ids == {}
