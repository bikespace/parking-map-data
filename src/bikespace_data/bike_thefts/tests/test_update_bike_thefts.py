from unittest.mock import Mock

import pytest
import requests
import pandas as pd
from bikespace_data.bike_thefts import update_bike_thefts as thefts


def feature(identifier):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-79.4, 43.6]},
        "properties": {
            "OBJECTID": identifier,
            "OCC_DATE": 1388552400000,
            "REPORT_DATE": 1388552400000,
            "OCC_YEAR": "2014",
            "PREMISES_TYPE": "Outside",
            "BIKE_TYPE": "MT",
            "BIKE_COLOUR": None,
            "STATUS": "STOLEN",
            "LAT_WGS84": 43.6,
            "LONG_WGS84": -79.4,
        },
    }


def test_pagination_and_normalization(monkeypatch):
    request = Mock(side_effect=[
        {"features": [feature(1)], "properties": {"exceededTransferLimit": True}},
        {"features": [feature(2)]},
    ])
    monkeypatch.setattr(thefts, "request_arcgis_json", request)
    gdf = thefts.fetch_thefts({"maxRecordCount": 2000, "objectIdField": "OBJECTID"})
    assert gdf['_id'].tolist() == [1, 2]
    assert gdf['OCC_DATE'].str[:10].tolist() == ['2014-01-01'] * 2
    assert gdf['OCC_YEAR'].tolist() == ['2014'] * 2
    assert gdf.crs is not None
    assert gdf.crs.to_epsg() == 4326
    assert gdf.geometry.x.iloc[0] == pytest.approx(-79.4)
    assert gdf.geometry.y.iloc[0] == pytest.approx(43.6)
    assert request.call_args_list[0].args[0] == f"{thefts.LAYER_URL}/query"
    assert request.call_args_list[1].args[1]['resultOffset'] == 1


@pytest.mark.parametrize('payload', [
    {"features": []},
    {"features": [], "properties": {"exceededTransferLimit": True}},
])
def test_empty_response_fails(monkeypatch, payload):
    monkeypatch.setattr(thefts, "request_arcgis_json", Mock(return_value=payload))
    with pytest.raises(RuntimeError):
        thefts.fetch_thefts({"maxRecordCount": 2000, "objectIdField": "OBJECTID"})


def test_api_error(monkeypatch):
    response = Mock()
    response.json.return_value = {"error": {"message": "Query failed"}}
    monkeypatch.setattr(thefts.requests, "get", Mock(return_value=response))
    with pytest.raises(RuntimeError, match="Query failed"):
        thefts.request_arcgis_json(f"{thefts.LAYER_URL}/query", {})
    response.raise_for_status.assert_called_once()


def test_http_error(monkeypatch):
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError('503')
    monkeypatch.setattr(thefts.requests, "get", Mock(return_value=response))
    with pytest.raises(requests.HTTPError):
        thefts.request_arcgis_json(f"{thefts.LAYER_URL}/query", {})

# Update mock record to have a recent date so that it is not filtered out by the main function. This ensures that the output schema is preserved and can be tested. 
def test_main_preserves_output_schema(monkeypatch, tmp_path):
    record = feature(1)
    recent = pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=30)
    timestamp_ms = int(recent.timestamp() * 1000)
    record["properties"]["OCC_DATE"] = timestamp_ms
    record["properties"]["REPORT_DATE"] = timestamp_ms

    request = Mock(side_effect=[
        {"maxRecordCount": 2000, "objectIdField": "OBJECTID",
         "editingInfo": {"lastEditDate": 1791468674571}},
        {"features": [record]},
    ])
    
    monkeypatch.setattr(thefts, "request_arcgis_json", request)
    status = Mock()
    status.last_updated.return_value = None
    monkeypatch.setattr(thefts, 'StatusManager', Mock(return_value=status))
    save = Mock()
    monkeypatch.setattr(thefts, 'save_geo_output', save)
    thefts.main(output_dir=tmp_path)
    output = save.call_args_list[1].args[0]
    assert output['id'].tolist() == ['1']
    assert output["date"].tolist() == [recent.strftime("%Y-%m-%d")]
    assert output['bikeType'].tolist() == ['Mountain bike']
    assert output['color'].tolist() == ['Unknown']
    assert output['status'].tolist() == ['stolen']
    status.save.assert_called_once()
