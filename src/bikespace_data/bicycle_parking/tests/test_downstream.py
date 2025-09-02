import geopandas as gpd
import pandas as pd

from bikespace_data.bicycle_parking.downstream import (
    combine_list,
    extract_ref_tags,
    summarize_boolean,
    summarize_freq,
)

mock_gdf = gpd.GeoDataFrame.from_features(
    [
        {
            "type": "Feature",
            "properties": {"amenity": "bicycle_parking", "description": "No ref tags"},
            "geometry": {"type": "Point", "coordinates": [-79.4004991, 43.6605147]},
        },
        {
            "type": "Feature",
            "properties": {
                "amenity": "bicycle_parking",
                "description": "open.toronto.ca ref, value 'no'",
                "ref:open.toronto.ca": "no",
            },
            "geometry": {"type": "Point", "coordinates": [-79.2650674, 43.7332707]},
        },
        {
            "type": "Feature",
            "properties": {
                "amenity": "bicycle_parking",
                "description": "open.toronto.ca street furniture ref; multiple values including with and without whitespace",
                "ref:open.toronto.ca": "yes",
                "ref:open.toronto.ca:street-furniture-bicycle-parking:id": "BP-34427;BP-34426; BP-34423",
            },
            "geometry": {"type": "Point", "coordinates": [-79.4015863, 43.6632417]},
        },
        {
            "type": "Feature",
            "properties": {
                "amenity": "bicycle_parking",
                "description": "open.toronto.ca street furniture ref; single  value",
                "ref:open.toronto.ca:street-furniture-bicycle-parking:id": "BP-09460",
            },
            "geometry": {"type": "Point", "coordinates": [-79.3746154, 43.667301]},
        },
        {
            "type": "Feature",
            "properties": {
                "amenity": "bicycle_parking",
                "description": "open.toronto.ca refs for high cap, racks, and street furniture",
                "ref:open.toronto.ca:bicycle-parking-high-capacity-outdoor:id": "78",
                "ref:open.toronto.ca:bicycle-parking-racks:objectid": "52",
                "ref:open.toronto.ca:street-furniture-bicycle-parking:id": "BP-24232",
            },
            "geometry": {"type": "Point", "coordinates": [-79.4658072, 43.6544076]},
        },
        {
            "type": "Feature",
            "properties": {
                "amenity": "bicycle_parking",
                "description": "open.toronto.ca high cap ref",
                "ref:open.toronto.ca:bicycle-parking-high-capacity-outdoor:id": "43",
            },
            "geometry": {"type": "Point", "coordinates": [-79.4685262, 43.6528776]},
        },
        {
            "type": "Feature",
            "properties": {
                "amenity": "bicycle_parking",
                "bicycle_parking": "building",
                "description": "open.toronto.ca bike station ref",
                "ref:open.toronto.ca:bicycle-parking-bike-stations-indoor:id": "2",
            },
            "geometry": {"type": "Point", "coordinates": [-79.2894687, 43.6945942]},
        },
        {
            "type": "Feature",
            "properties": {
                "amenity": "bicycle_parking",
                "bicycle_parking": "lockers",
                "description": "toronto.ca lockers ref",
                "ref:toronto.ca:lockers:title": "Bayview Subway Station",
            },
            "geometry": {"type": "Point", "coordinates": [-79.3873901, 43.7670662]},
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
