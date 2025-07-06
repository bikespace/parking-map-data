# from fiona/model.pyi in https://github.com/Toblerity/Fiona/pull/1259/files as of 2025-06-15

from typing import Literal, NotRequired, Required, TypedDict

GeoJSONPosition = tuple[float, float] | tuple[float, float, float]
GeoJSONLineStringCoordinateArray = list[GeoJSONPosition]  # two or more positions
GeoJSONLinearRing = list[GeoJSONPosition]  # closed with four or more positions
GeoJSONPolygonCoordinateArray = list[GeoJSONLinearRing]


class GeoJSONPoint(TypedDict):
    type: Required[Literal["Point"]]
    coordinates: Required[GeoJSONPosition]


class GeoJSONMultiPoint(TypedDict):
    type: Literal["MultiPoint"]
    coordinates: list[GeoJSONPosition]


class GeoJSONLineString(TypedDict):
    type: Literal["LineString"]
    coordinates: GeoJSONLineStringCoordinateArray


class GeoJSONMultiLineString(TypedDict):
    type: Literal["MultiLineString"]
    coordinates: list[GeoJSONLineStringCoordinateArray]


class GeoJSONPolygon(TypedDict):
    type: Literal["Polygon"]
    coordinates: GeoJSONPolygonCoordinateArray


class GeoJSONMultiPolygon(TypedDict):
    type: Literal["MultiPolygon"]
    coordinates: list[GeoJSONPolygonCoordinateArray]


GeoJSONGeometry = (
    GeoJSONPoint
    | GeoJSONMultiPoint
    | GeoJSONLineString
    | GeoJSONMultiLineString
    | GeoJSONPolygon
    | GeoJSONMultiPolygon
)


class GeoJSONFeature(TypedDict):
    type: Literal["Feature"]
    geometry: GeoJSONGeometry | None
    properties: dict | None
    id: NotRequired[str | float]


class GeoJSONFeatureCollection(TypedDict):
    type: Literal["FeatureCollection"]
    features: list[GeoJSONFeature]
