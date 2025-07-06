from conversions import (
    _bicycle_parking_high_capacity_outdoor,
    _bicycle_parking_racks,
    _bicycle_parking_bike_stations_indoor,
    _street_furniture_bicycle_parking,
    _osm_bicycle_parking_city_of_toronto,
    _toronto_lockers,
)
from enum import Enum, auto


class _MapType(Enum):
    FILTER = auto()
    TRANSFORM = auto()


def _get_map(_MapType, dataset_name):
    if dataset_name == "bicycle-parking-high-capacity-outdoor":
        return _bicycle_parking_high_capacity_outdoor
    elif dataset_name == "bicycle-parking-racks":
        return _bicycle_parking_racks
    elif dataset_name == "bicycle-parking-bike-stations-indoor":
        return _bicycle_parking_bike_stations_indoor
    elif dataset_name == "street-furniture-bicycle-parking":
        return _street_furniture_bicycle_parking
    elif dataset_name == "osm_bicycle_parking_city_of_toronto":
        return _osm_bicycle_parking_city_of_toronto
    elif dataset_name == "toronto_lockers":
        return _toronto_lockers


def get_filter(dataset_name):
    """Returns filter function.

    Parameters
    ----------
    dataset_name: str
    """
    return _get_map(_MapType.FILTER, dataset_name).filter_properties


def get_transform(dataset_name):
    """Returns transform function.

    Parameters
    ----------
    dataset_name: str
    """
    return _get_map(_MapType.TRANSFORM, dataset_name).transform_properties
