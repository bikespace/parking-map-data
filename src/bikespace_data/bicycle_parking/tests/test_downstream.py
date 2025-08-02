import geopandas as gpd

from bikespace_data.bicycle_parking.downstream import extract_ref_tags

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
    """Extract ref tags from a mock gdf using the 'ref:open.toronto.ca' and 'ref:toronto.ca' patterns and ensure that all the tags are properly extracted."""

    open_toronto_ca_tags = extract_ref_tags(mock_gdf, "ref:open.toronto.ca")
    toronto_ca_tags = extract_ref_tags(mock_gdf, "ref:toronto.ca")

    assert open_toronto_ca_tags == {
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
    }
    assert toronto_ca_tags == {
        "ref:toronto.ca:lockers:title": ["Bayview Subway Station"]
    }
